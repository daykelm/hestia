"""Pull the next public auction lists for South Florida. Images stay as links."""

import json
import re
import time
import urllib.request
from datetime import date, datetime, timedelta
from html import unescape

# Broward and Lee split tax deeds and foreclosures. Miami-Dade publishes both on one calendar.
# Collier tax deeds are in-person and are not on this auction system.
_BID_HOST = {
    ("Broward", "tax deed"): "https://broward.realtaxdeed.com",
    ("Broward", "foreclosure"): "https://broward.realforeclose.com",
    ("Miami-Dade", "tax deed"): "https://www.miamidade.realforeclose.com",
    ("Miami-Dade", "foreclosure"): "https://www.miamidade.realforeclose.com",
    ("Lee", "tax deed"): "https://lee.realtaxdeed.com",
    ("Lee", "foreclosure"): "https://lee.realforeclose.com",
    ("Palm Beach", "tax deed"): "https://palmbeach.realtaxdeed.com",
    ("Palm Beach", "foreclosure"): "https://palmbeach.realforeclose.com",
    ("Monroe", "tax deed"): "https://monroe.realtaxdeed.com",
}


def bid_url(meta):
    """The property page where a registered bidder enters a maximum. The county then bids up to it."""
    aid = re.sub(r"\D", "", str((meta or {}).get("auction_id") or ""))
    host = _BID_HOST.get(((meta or {}).get("county"), ((meta or {}).get("kind") or "").lower()))
    if not aid or not host:
        return ""
    return f"{host}/index.cfm?zaction=auction&zmethod=details&AID={aid}"


SITES = (
    {"county": "Palm Beach", "host": "https://palmbeach.realtaxdeed.com"},
    {"county": "Palm Beach", "host": "https://palmbeach.realforeclose.com"},
    {"county": "Broward", "host": "https://broward.realtaxdeed.com"},
    {"county": "Broward", "host": "https://broward.realforeclose.com"},
    {"county": "Miami-Dade", "host": "https://www.miamidade.realforeclose.com"},
    {"county": "Monroe", "host": "https://monroe.realtaxdeed.com"},
    {"county": "Lee", "host": "https://lee.realtaxdeed.com"},
    {"county": "Lee", "host": "https://lee.realforeclose.com"},
)

UA = "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/128.0.0.0 Safari/537.36"
# shortcut: twelve pages per sale day, raise the cap if a single county sale no longer fits
MAX_PAGES = 12
# Sales past this are often canceled or reset before their day, and each one costs a loan report to score.
HORIZON_DAYS = 45

_REPLACEMENTS = (
    ("@A", '<div class="'),
    ("@B", "</div>"),
    ("@C", 'class="'),
    ("@D", "<div>"),
    ("@E", "AUCTION"),
    ("@F", "</td><td"),
    ("@G", "</td></tr>"),
    ("@H", "<tr><td "),
    ("@I", "table"),
    ("@J", 'p_back="NextCheck='),
    ("@K", 'style="display:none"'),
    ("@L", "/index.cfm?zaction=auction&zmethod=details&AID="),
)


def decode_auction_html(raw):
    for old, new in _REPLACEMENTS:
        raw = raw.replace(old, new)
    return raw


def parse_calendar(html, today=None):
    today = today or date.today()
    sales = []
    for match in re.finditer(r"dayid='(\d{1,2}/\d{1,2}/\d{4})'([\s\S]{0,400}?)</div>", html):
        when = datetime.strptime(match.group(1), "%m/%d/%Y").date()
        if when < today:
            continue
        block = match.group(2)
        kind = "Tax deed" if "Tax Deed" in block else "Foreclosure" if "Foreclosure" in block else ""
        if not kind:
            continue
        sales.append({"date": match.group(1), "kind": kind, "when": when})
    next_link = ""
    found = re.search(r'href="([^"]*selCalDate=[^"]+)"[^>]*aria-label="Next Month', html)
    if found:
        next_link = unescape(found.group(1))
    return sorted(sales, key=lambda item: item["when"]), next_link


def parse_listings(html, *, county, kind, sale_date, page_url):
    listings = []
    for chunk in re.split(r'<div id="AITEM_', html)[1:]:
        fields = {}
        for label, value in re.findall(r"AD_LBL[^>]*>(.*?)</td>\s*<td[^>]*AD_DTA[^>]*>(.*?)</td>", chunk, re.S):
            key = " ".join(re.sub(r"<[^>]+>", " ", label).split()).rstrip(":")
            text = " ".join(re.sub(r"<[^>]+>", " ", value).split())
            if key:
                fields[key] = text
            elif text and "city" not in fields:
                fields["city"] = text
        address = fields.get("Property Address", "")
        if not address:
            continue
        parcel = fields.get("Parcel ID", "")
        parcel_key = re.sub(r"[^A-Z0-9]", "", parcel.upper())
        aid = chunk.split('"', 1)[0]
        media = []
        for src in re.findall(r'<img[^>]+src="(https?://[^"]+)"', chunk, re.I):
            media.append({"kind": "image", "url": src})
        for src in re.findall(r'<video[^>]+src="(https?://[^"]+)"', chunk, re.I):
            media.append({"kind": "video", "url": src})
        opening = _money(fields.get("Opening Bid"))
        judgment = _money(fields.get("Final Judgment Amount"))
        # Foreclosures publish no opening bid. The judgment is what the lender can bid up to.
        price = opening if opening is not None else judgment
        basis = "opening bid" if opening is not None else "final judgment" if judgment is not None else ""
        # A calendar day can mix both kinds, so the row's own type decides.
        auction_type = fields.get("Auction Type", "").upper()
        kind = "Tax deed" if "TAX" in auction_type else "Foreclosure" if "FORECLOS" in auction_type else kind
        listings.append(
            {
                "dedupe_key": f"{county.lower()}|{parcel_key or address.lower()}",
                "address": address,
                "location": fields.get("city", ""),
                "price": price,
                "source": f"{county} {kind.lower()}",
                "link": page_url,
                "media": media,
                "metadata": {
                    "county": county,
                    "kind": kind,
                    "sale_date": sale_date,
                    "case": fields.get("Case #", ""),
                    "certificate": fields.get("Certificate #", ""),
                    "parcel": parcel,
                    "auction_id": aid,
                    "auction_type": fields.get("Auction Type", ""),
                    "price_basis": basis,
                    "final_judgment": judgment,
                    "plaintiff_max_bid": fields.get("Plaintiff Max Bid", ""),
                },
            }
        )
    return listings


def _money(raw):
    if not raw:
        return None
    text = raw.replace("$", "").replace(",", "").strip()
    try:
        return float(text)
    except ValueError:
        return None


def _get(opener, url, data=None):
    headers = {"User-Agent": UA, "Accept": "text/html"}
    if data is not None:
        headers["Content-Type"] = "application/x-www-form-urlencoded"
    request = urllib.request.Request(url, data=data, headers=headers)
    with opener.open(request, timeout=20) as response:
        final = response.geturl()
        body = response.read().decode("utf-8", "replace")
    return final, body


def _sale_days(opener, host):
    final, html = _get(opener, host + "/index.cfm?zaction=USER&zmethod=CALENDAR")
    if "Auction Calendar" not in html:
        return []
    sales, next_link = parse_calendar(html)
    if next_link:
        if next_link.startswith("/"):
            next_link = host + next_link
        _, nxt = _get(opener, next_link)
        more, _ = parse_calendar(nxt)
        sales.extend(more)
    # A day can appear once per kind, and its page lists both, so each day is read once.
    days = {}
    last = date.today() + timedelta(days=HORIZON_DAYS)
    for sale in sales:
        if sale["when"] <= last:
            days.setdefault(sale["date"], sale)
    return list(days.values())


def _load_page(opener, host, page):
    tx = str(int(time.time() * 1000))
    url = (
        f"{host}/index.cfm?zaction=AUCTION&Zmethod=UPDATE&FNC=LOAD"
        f"&AREA=W&PageDir=0&doR=1&tx={tx}&bypassPage={page}"
    )
    _, body = _get(opener, url, b"test=1")
    start = body.find("{")
    payload = json.loads(body[start:])
    return decode_auction_html(payload.get("retHTML") or "")


def collect_site(site, opener=None):
    opener = opener or urllib.request.build_opener(urllib.request.HTTPCookieProcessor())
    host = site["host"]
    county = site["county"]
    days = _sale_days(opener, host)
    listings = []
    for sale in days:
        page_url = f"{host}/index.cfm?zaction=AUCTION&Zmethod=PREVIEW&AUCTIONDATE={sale['date']}"
        _get(opener, page_url)
        seen = set()
        pages = 0
        page = 0
        while pages < MAX_PAGES:
            html = _load_page(opener, host, page)
            found = parse_listings(html, county=county, kind=sale["kind"], sale_date=sale["date"], page_url=page_url)
            fresh = [item for item in found if item["metadata"]["auction_id"] not in seen]
            if not fresh:
                break
            seen.update(item["metadata"]["auction_id"] for item in fresh)
            listings.extend(fresh)
            pages += 1
            # Page 0 and page 1 are the same first page. Page 2 is the next one.
            page = 2 if page == 0 else page + 1
    return listings


def collect(sites=SITES, progress=None):
    """Returns listings and a short note per site. One site failing leaves the others."""
    listings = []
    notes = []
    for site in sites:
        if progress:
            progress(f"Collecting {site['county']}…")
        try:
            found = collect_site(site)
            listings.extend(found)
            notes.append(f"{site['county']}: {len(found)} from {site['host'].split('//')[1]}")
        except Exception as exc:
            notes.append(f"{site['county']}: {exc.__class__.__name__}")
    notes.append("Collier is not on these auction calendars. Monroe foreclosures are not either.")
    return listings, notes
