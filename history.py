"""Past auction results from the public RealAuction pages, and the county summary the Past results page draws.

    python3 history.py pull 2025-10-30 2026-10-30 data/history.jsonl
    python3 history.py summarize data/history.jsonl static/results.json
"""

import html
import json
import re
import statistics
import sys
import time
import urllib.request
from datetime import date, timedelta

import sources

REGIONS = ("Palm Beach", "Broward", "Miami-Dade", "Monroe", "Lee")
# A sale needs a real base price and enough buyers before a median means anything.
MIN_SALES = 10


def _fields(chunk):
    found = {}
    for label, value in re.findall(r"AD_LBL[^>]*>(.*?)</td>\s*<td[^>]*AD_DTA[^>]*>(.*?)</td>", chunk, re.S):
        key = " ".join(re.sub(r"<[^>]+>", " ", label).split()).rstrip(":")
        text = " ".join(re.sub(r"<[^>]+>", " ", value).split())
        if key:
            found[key] = html.unescape(text)
        elif text and "city" not in found:
            found["city"] = text
    return found


def pull_day(site, day):
    """The closed and canceled auctions of one sale day, with how each ended."""
    host = site["host"]
    opener = urllib.request.build_opener(urllib.request.HTTPCookieProcessor())
    sources._get(opener, f"{host}/index.cfm?zaction=AUCTION&Zmethod=PREVIEW&AUCTIONDATE={day:%m/%d/%Y}")
    rows, seen, page = [], set(), 0
    for _ in range(sources.MAX_PAGES):
        url = f"{host}/index.cfm?zaction=AUCTION&Zmethod=UPDATE&FNC=LOAD&AREA=C&PageDir=0&doR=1&tx={int(time.time() * 1000)}&bypassPage={page}"
        _, body = sources._get(opener, url, b"test=1")
        payload = json.loads(body[body.find("{"):])
        chunks = re.split(r'<div id="AITEM_', sources.decode_auction_html(payload.get("retHTML") or ""))[1:]
        items = {chunk.split('"', 1)[0]: _fields(chunk) for chunk in chunks}
        fresh = [aid for aid in items if aid not in seen]
        if not fresh:
            break
        _, update = sources._get(opener, f"{host}/index.cfm?zaction=AUCTION&ZMETHOD=UPDATE&FNC=UPDATE&ref={payload['rlist']}&tx={int(time.time() * 1000)}")
        states = {item["AID"]: item for item in json.loads(update[update.find('{"PC"'):])["ADATA"]["AITEM"]}
        for aid in fresh:
            state = states.get(aid, {})
            rows.append({"county": site["county"], "host": host, "day": f"{day:%m/%d/%Y}", "aid": aid, **items[aid], "status": state.get("A"), "msg": state.get("B"), "sold_to": state.get("ST"), "amount": state.get("D")})
        seen.update(fresh)
        page = 2 if page == 0 else page + 1
        time.sleep(0.4)
    return rows


def pull(start, end, path):
    with open(path, "a") as out:
        for site in sources.SITES:
            day = end
            while day >= start:
                if day.weekday() < 5:
                    try:
                        for row in pull_day(site, day):
                            out.write(json.dumps(row) + "\n")
                        out.flush()
                    except Exception as exc:
                        print(site["host"], day, exc.__class__.__name__, flush=True)
                    time.sleep(0.4)
                day -= timedelta(days=1)


def _money(text):
    found = re.sub(r"[^\d.]", "", text or "")
    return float(found) if found else 0.0


def _kind(row):
    text = (row.get("Auction Type") or "").upper()
    return "Tax deed" if "TAX" in text else "Foreclosure" if "FORECLOS" in text else ""


def _ended(row):
    if row.get("status") != "Auction Sold":
        return "unsold"
    return "outside" if "3rd" in (row.get("sold_to") or "") else "kept"


def summarize(rows):
    """Rows are counted once per auction. A multiple is the price paid over the opening bid or the judgment."""
    unique = {(row["host"], row["aid"]): row for row in rows}.values()
    days = [row["day"] for row in unique]
    ordered = sorted(days, key=lambda text: (text[6:], text[:5]))
    counties = []
    for county in REGIONS:
        kinds = []
        for kind in ("Foreclosure", "Tax deed"):
            members = [row for row in unique if row["county"] == county and _kind(row) == kind]
            if not members:
                continue
            counts = {name: sum(1 for row in members if _ended(row) == name) for name in ("unsold", "kept", "outside")}
            base = "Opening Bid" if kind == "Tax deed" else "Final Judgment Amount"
            multiples = sorted(
                _money(row["amount"]) / _money(row[base])
                for row in members
                if _ended(row) == "outside" and _money(row.get("amount")) and _money(row.get(base))
            )
            entry = {"kind": kind, "total": len(members), **counts, "buyers": len(multiples)}
            if len(multiples) >= MIN_SALES:
                entry["median"] = round(statistics.median(multiples), 2)
            kinds.append(entry)
        if kinds:
            counties.append({"county": county, "kinds": kinds})
    return {"from": ordered[0] if ordered else "", "through": ordered[-1] if ordered else "", "counties": counties}


if __name__ == "__main__":
    if sys.argv[1] == "pull":
        pull(date.fromisoformat(sys.argv[2]), date.fromisoformat(sys.argv[3]), sys.argv[4])
    else:
        with open(sys.argv[2]) as source:
            summary = summarize([json.loads(line) for line in source])
        with open(sys.argv[3], "w") as out:
            json.dump(summary, out, indent=1)
            out.write("\n")
