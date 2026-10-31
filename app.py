"""Local deal list. Run: python3 app.py"""

import html
import json
import os
import threading
from contextlib import closing
from datetime import date, datetime, timedelta
from zoneinfo import ZoneInfo
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from pathlib import Path
from urllib.parse import parse_qs, quote, urlparse

import deals
import diligence
import sources

DB_PATH = Path(os.environ.get("HESTIA_DB", Path(__file__).resolve().parent / "data" / "hestia.db"))
HOST = os.environ.get("HOST", "127.0.0.1")
PORT = int(os.environ.get("PORT", "8080"))
MAX_BODY = 100_000


def safe_href(url):
    url = (url or "").strip()
    if url.startswith("https://") or url.startswith("http://"):
        return url
    return ""


def safe_next(value):
    value = (value or "").strip()
    if not value.startswith("/") or value.startswith("//") or "\\" in value or any(c in value for c in "\r\n"):
        return "/"
    return value


def money(number):
    if number is None:
        return "—"
    whole = abs(number - round(number)) < 0.001
    body = f"{abs(number):,.0f}" if whole else f"{abs(number):,.2f}"
    return f"-${body}" if number < 0 else f"${body}"


def format_updated(iso):
    try:
        when = datetime.fromisoformat(iso).astimezone()
    except ValueError:
        return ""
    return when.strftime("%b %-d")


def _one(form, key):
    values = form.get(key) or [""]
    return values[0]


def _filters(params):
    raw = {
        "status": _one(params, "status").strip(),
        "location": _one(params, "location").strip(),
        "source": _one(params, "source").strip(),
        "min_price": _one(params, "min_price").strip(),
        "max_price": _one(params, "max_price").strip(),
    }
    parsed = {"min_price": None, "max_price": None}
    error = ""
    try:
        if raw["min_price"]:
            parsed["min_price"] = deals.parse_money(raw["min_price"])
        if raw["max_price"]:
            parsed["max_price"] = deals.parse_money(raw["max_price"])
    except ValueError as exc:
        error = str(exc)
    return raw, parsed, error


def _query(raw):
    parts = []
    for key in ("status", "location", "source", "min_price", "max_price"):
        if raw.get(key):
            parts.append(f"{key}={quote(raw[key])}")
    return ("?" + "&".join(parts)) if parts else ""


def _option(value, current, label=None):
    selected = " selected" if value == current else ""
    return f'<option value="{html.escape(value)}"{selected}>{html.escape(label or value)}</option>'


def _status_select(name, current):
    options = "".join(_option(status, current) for status in deals.STATUSES)
    return f'<select name="{name}" aria-label="Status">{options}</select>'


_UPPER = {"N", "S", "E", "W", "NE", "NW", "SE", "SW", "FL", "US"}
STATIC = {
    "desk.css": "text/css; charset=utf-8",
    "desk.js": "text/javascript; charset=utf-8",
    "fonts/eb-garamond.woff2": "font/woff2",
    "hestia.apk": "application/vnd.android.package-archive",
    "hestia-native.apk": "application/vnd.android.package-archive",
    "app-version.json": "application/json",
}
STATIC_DIR = Path(__file__).resolve().parent / "static"


def app_version():
    try:
        return int(json.loads((STATIC_DIR / "app-version.json").read_text())["version_code"])
    except (OSError, ValueError, KeyError):
        return 0

HELP = {
    "sale": ("Sale day", "The day the county runs the online auction. Deals you never touched are removed the next time you collect after their sale day passes."),
    "bid": ("Opening bid", "On a tax deed, the county's starting price: the unpaid taxes, interest, and fees. Bidding opens here and often finishes much higher."),
    "judgment": ("Final judgment", "Foreclosures publish no opening bid. This is what the court awarded the lender. The lender can bid up to it without new cash, so expect to pay more than this to win."),
    "bid_column": ("Bid", "The opening bid on tax deeds. On foreclosures it is the final judgment, marked “judgment” under the amount."),
    "roll": ("Tax roll value", "The just value the property appraiser puts on the tax roll, from the Florida state roll and the county appraiser. It is an assessment for taxes, not an appraisal, and often runs below market price."),
    "ratio": ("Roll ÷ bid", "Tax roll value divided by the bid. 2× means the roll says the property is worth twice the starting price. The winning bid is usually higher, so the real gap is smaller."),
    "parcel": ("Parcel", "The county's ID for the land. Search it on the property appraiser and tax collector sites to see the owner, taxes owed, and past sales."),
    "case": ("Case", "The auction's case number. For a foreclosure, look it up on the county clerk's docket to see who sued, the judgment, and anything filed since."),
    "your_value": ("Your value", "Your own estimate of what the property would sell for. Hestia never fills this in for you."),
    "spread": ("Spread", "Your value minus the bid. It is the room you have for repairs, closing costs, your fee, and the buyer's profit."),
    "score": ("Score", "1 to 10, from seven checks worth up to 2 points each. Only checks that a source answered count. The color says how far to trust it: blue excellent, green good, yellow fair, red risky, gray not enough data."),
    "band": ("Score color", "Gray until the value is confirmed by two independent sources and at least four checks answered. Red when any check raises a hard warning, such as an HOA foreclosure, an open code lien, or a bid above the value. Blue needs 8 or more and your own lien search in the Title checked step."),
    "resale": ("Resale value", "The tax roll value, backed up by a real sale since 2023 within 25% of it, or by three or more nearby sales near it. The state roll copies the county roll, so the two rolls count as one source. 2 points when the confirmed value is at least twice the bid."),
    "comps": ("Comparables", "Qualified sales of $10,000 or more near the property in the last two years. 2 points when at least three of them have a median of 1.5 times the bid or more, close to the tax roll value. 1 point with fewer sales, or when nearby assessments with the same use match the roll."),
    "title": ("Title", "Whether the sale clears the mortgage. Tax deeds and circuit-court foreclosures by the lender usually do, so they start at 1. A county-court foreclosure is usually an HOA, and the mortgage survives: that is a red warning. Your own docket check in Title checked makes it 2."),
    "code": ("Code and building", "Open code cases, unpaid code liens, and unsafe-structure cases from the county. Miami-Dade has three sources and Lee has one. Broward has no public source yet, so it stays unchecked there."),
    "flood": ("Flood", "FEMA's flood map at the property. 2 points for minimal hazard, 1 for the 0.2% zone, 0 where flood insurance is required. Coastal V zones are a red warning."),
    "occupancy": ("Occupancy", "Whether someone likely lives there. A homestead exemption, or the owner's mail going to the property, means someone probably does. 1 point for no homestead on the roll, 2 when the owner's mail also goes elsewhere. It is a signal, not a drive-by."),
    "liens": ("Other liens", "ATTOM reports the open loan and whether the tax is delinquent. That is the Loan and Tax lines, and it is what the score uses. The Also line is a second report and does not change the color. Delinquent taxes on a foreclosure, or a second loan on a foreclosure, turn the deal red. A tax deed is expected to be delinquent, and it clears private loans, so those do not. Judgments and association liens still need your clerk search."),
    "status": ("Step", "Where a deal sits in your process: Found, Researched, Title checked, Bid set, Won, Buyer assigned, Closed. Passed is a deal you dropped."),
    "steps": ("The process", "Every deal moves through seven steps. Hestia does Found and Researched for you. Title checked is your docket and lien search. Bid set is your ceiling. Won, Buyer assigned, and Closed track the deal to the end."),
    "location": ("Location", "City or zip code. Part of a word is enough: “Lauder” matches Lauderhill and Fort Lauderdale."),
    "source": ("Source", "Where the deal came from, such as “Broward tax deed” or “Lee foreclosure”. Part of a word is enough: “Lee” matches both Lee lists."),
    "bid_range": ("Bid range", "Only show deals whose bid falls in this range. Leave a box empty for no limit."),
    "price": ("Asking price", "What you would pay: the seller's asking price, or the bid you plan to make."),
}
FACTOR_HELP = {
    "Resale value": "resale",
    "Comparables": "comps",
    "Title": "title",
    "Code and building": "code",
    "Flood": "flood",
    "Occupancy": "occupancy",
    "Other liens": "liens",
}
PIPELINE = deals.STEPS[2:]
STEP_GUIDE = {
    "Found": "Fresh from the auction list. Score it to read the tax rolls, code cases, flood map, and nearby sales.",
    "Researched": "The public records are read. Now check what Hestia can't: the court docket, recorded liens, and taxes owed.",
    "Title checked": "Set the most you will pay. Leave room for repairs, closing costs, your fee, and the buyer's profit.",
    "Bid set": "Open the auction and enter your ceiling. The county then bids for you, $100 at a time, and stops at that number. Your deposit has to clear before the sale.",
    "Won": "Find a cash buyer and sign the assignment.",
    "Buyer assigned": "Close with the buyer and the title company.",
    "Closed": "Done. The deal is closed.",
    "Passed": "You passed on this deal. Reopen it to pick it back up.",
}
REGIONS = ("Palm Beach", "Broward", "Miami-Dade", "Monroe", "Lee")
CHECK_LINKS = {
    "Palm Beach": (
        ("Court docket", "https://appsgp.mypalmbeachclerk.com/eCaseView/"),
        ("Recorded liens", "https://erec.mypalmbeachclerk.com/"),
        ("Taxes owed", "https://pbctax.publicaccessnow.com/"),
    ),
    "Monroe": (
        ("Court docket", "https://www.monroe-clerk.com/court-records/"),
        ("Recorded liens", "https://www.monroe-clerk.com/"),
        ("Taxes owed", "https://monroe.county-taxes.com/public"),
    ),
    "Miami-Dade": (
        ("Court docket", "https://www2.miamidadeclerk.gov/ocs/"),
        ("Recorded liens", "https://onlineservices.miamidadeclerk.gov/officialrecords/"),
        ("Taxes owed", "https://miamidade.county-taxes.com/public"),
    ),
    "Broward": (
        ("Court docket", "https://www.browardclerk.org/Web2/CaseSearchECA"),
        ("Recorded liens", "https://officialrecords.broward.org/AcclaimWeb"),
        ("Taxes owed", "https://broward.county-taxes.com/public"),
    ),
    "Lee": (
        ("Court docket", "https://matrix.leeclerk.org/"),
        ("Recorded liens", "https://or.leeclerk.org/"),
        ("Taxes owed", "https://lee.county-taxes.com/public"),
    ),
}


def help_button(key):
    title = HELP[key][0]
    return (
        f'<button type="button" class="help" popovertarget="help-{key}" aria-label="What is {html.escape(title, quote=True)}?">'
        '<svg aria-hidden="true"><use href="#i-help"></use></svg></button>'
    )


def _help_popovers():
    return "".join(
        f'<div popover id="help-{key}" class="help-pop" role="dialog" aria-labelledby="help-{key}-t">'
        f'<h3 id="help-{key}-t">{html.escape(title)}</h3><p>{html.escape(text)}</p>'
        f'<button type="button" popovertarget="help-{key}" popovertargetaction="hide">Got it</button></div>'
        for key, (title, text) in HELP.items()
    )


def display_name(text):
    words = []
    for word in (text or "").split():
        bare = word.strip(",#")
        words.append(word if bare.upper() in _UPPER or any(c.isdigit() for c in bare) else word.capitalize())
    return " ".join(words)


def display_place(location):
    city, _, rest = (location or "").partition(",")
    zip_code = rest.replace("FL-", "").replace("FL", "").strip()
    return " ".join(part for part in (display_name(city.strip()), zip_code) if part)


def _meta(deal):
    return deal.get("metadata") or {}


def _score(deal):
    return int((_meta(deal).get("diligence") or {}).get("score") or 0)


def _band(deal):
    """Scores from the first version of the rules had no color. They show gray until rescored."""
    row = _meta(deal).get("diligence") or {}
    if not row.get("score"):
        return ""
    return row.get("band") or "thin"


BAND_LABEL = diligence.BANDS


def _mag(score, band=""):
    size = 3 + score * 1.6 if score else 4
    kind = f" band-{band}" if score and band else " empty"
    return f'<span class="mag{kind}" style="--d:{size:.1f}px" aria-hidden="true"></span>'


def _stepper(status):
    at = deals.STEPS.index(status) if status in deals.STEPS else -1
    items = []
    for n, step in enumerate(deals.STEPS):
        state = "done" if n < at else "now" if n == at else ""
        current = ' aria-current="step"' if n == at else ""
        items.append(f'<li class="{state}"{current} title="{html.escape(step, quote=True)}"><span class="dot" aria-hidden="true"></span><span class="label">{html.escape(step)}</span></li>')
    return f'<ol class="stepper" aria-label="Steps">{"".join(items)}</ol>'


def _step_panel(deal, next_query):
    """What this step means and the one action that moves it on."""
    meta = _meta(deal)
    status = deals.LEGACY.get(deal["status"], deal["status"])
    status = status if status in deals.STATUSES else "Found"
    did = int(deal["id"])
    hidden = (
        f'<input type="hidden" name="id" value="{did}">'
        f'<input type="hidden" name="next" value="{html.escape(next_query or "/", quote=True)}">'
    )

    def move(to, label, primary=False, body=""):
        cls = ' class="primary"' if primary else ""
        return (
            f'<form method="post" action="/deals/step" class="step-form">{hidden}'
            f'<input type="hidden" name="to" value="{html.escape(to, quote=True)}">{body}'
            f'<button type="submit"{cls}>{html.escape(label)}</button></form>'
        )

    def money_input(name, label, value=None):
        shown = "" if value is None else f"{value:.0f}"
        return (
            f'<label>{html.escape(label)}<input name="{name}" inputmode="decimal" value="{shown}" required></label>'
        )

    researched = "diligence" in meta
    main = ""
    if status == "Found":
        main = (
            f'<form method="post" action="/deals/research" class="step-form">{hidden}'
            '<button type="submit" class="primary">Score this deal</button></form>'
        )
    elif status == "Researched":
        links = "".join(
            f'<li><a href="{url}" rel="noreferrer" target="_blank">{html.escape(name)}</a></li>'
            for name, url in CHECK_LINKS.get(meta.get("county") or "", ())
        )
        refs = " · ".join(f"{k} {html.escape(str(v))}" for k, v in (("Case", meta.get("case")), ("Parcel", meta.get("parcel"))) if v)
        body = (
            (f'<ul class="check-links">{links}</ul>' if links else "")
            + (f'<p class="quiet refs">{refs}</p>' if refs else "")
            + '<label class="tick"><input type="checkbox" name="title" value="1" required>'
            "I read the docket. The sale clears the mortgage.</label>"
            '<label class="tick"><input type="checkbox" name="liens" value="1" required>'
            "I searched liens and taxes owed. Nothing survives the sale.</label>"
        )
        main = move("Title checked", "Mark title checked", True, body)
    elif status == "Title checked":
        main = move("Bid set", "Set my ceiling", True, money_input("max_bid", "Most I will bid", meta.get("max_bid")))
    elif status == "Bid set":
        ceiling = f" Your ceiling is {money(meta.get('max_bid'))}." if meta.get("max_bid") else ""
        place = sources.bid_url(meta)
        place_html = (
            f'<a class="bid" href="{html.escape(place, quote=True)}" rel="noreferrer" target="_blank">Place this bid</a>'
            if place
            else ""
        )
        main = (
            f'<p class="quiet">Sale day {html.escape(meta.get("sale_date") or "not set")}.{ceiling} '
            "The county bids $100 at a time and stops at your ceiling. Your deposit has to clear before the sale.</p>"
            + place_html
            + move("Won", "We won it", True, money_input("won_price", "Winning price"))
        )
    elif status == "Won":
        body = (
            '<label>Buyer<input name="buyer" required></label>'
            '<label>Assignment fee<input name="fee" inputmode="decimal"></label>'
        )
        main = move("Buyer assigned", "Assign the buyer", True, body)
    elif status == "Buyer assigned":
        main = move("Closed", "Mark closed", True)

    extra = []
    for to in deals.allowed_moves(status, researched):
        if status in deals.STEPS and to in deals.STEPS and deals.STEPS.index(to) > deals.STEPS.index(status):
            continue
        if to == "Found":
            continue
        if to == "Passed":
            extra.append(move("Passed", "Lost or skipped" if status == "Bid set" else "Pass"))
        elif status == "Passed":
            extra.append(move(to, "Reopen", True))
        else:
            extra.append(move(to, f"Back to {to}"))
    facts = []
    for key, label in (("max_bid", "Ceiling"), ("won_price", "Won at"), ("buyer", "Buyer"), ("fee", "Fee")):
        if meta.get(key) not in (None, ""):
            value = money(meta[key]) if key != "buyer" else meta[key]
            facts.append(f"<div><dt>{label}</dt><dd>{html.escape(str(value))}</dd></div>")
    at = f"Step {deals.STEPS.index(status) + 1} of {len(deals.STEPS)}" if status in deals.STEPS else "Passed"
    return (
        '<section class="step-panel" aria-label="Process">'
        f'<h3 class="step-head">{html.escape(at)}: <strong>{html.escape(status)}</strong>{help_button("steps")}</h3>'
        f"{_stepper(status)}"
        f'<p class="guide">{html.escape(STEP_GUIDE.get(status, ""))}</p>'
        f'{f"<dl class=step-facts>{chr(10).join(facts)}</dl>" if facts else ""}'
        f"{main}"
        f'{f"<div class=step-more>{chr(10).join(extra)}</div>" if extra else ""}'
        "</section>"
    )


def _factors_html(deal):
    row = _meta(deal).get("diligence") or {}
    if not row.get("score"):
        return '<p class="quiet">Not scored yet. Scoring reads the tax rolls, code cases, the flood map, and nearby sales.</p>'
    band = _band(deal)
    if row.get("version", 1) < diligence.VERSION:
        reason = "Scored under the old rules. Score unchecked again to recheck it against every source."
    else:
        reason = row.get("reason") or ""
    verdict = (
        f'<p class="verdict band-{band}"><strong>{html.escape(BAND_LABEL.get(band, ""))}</strong>'
        f'{help_button("band")}<span>{html.escape(reason)}</span></p>'
    )
    flags = "".join(f"<li>{html.escape(flag)}</li>" for flag in row.get("flags") or [])
    flag_html = f'<ul class="flags" aria-label="Warnings">{flags}</ul>' if flags else ""
    items = []
    for item in row.get("factors") or []:
        points, of = int(item.get("points") or 0), int(item.get("of") or 2)
        checked = item.get("checked", True)
        pips = "".join(f'<span class="pip{" on" if n < points else ""}"></span>' for n in range(of))
        used = item.get("sources") or []
        source_note = f'<span class="srcs">{html.escape(" + ".join(used))}</span>' if used else ""
        mark = f'<span class="pips" aria-label="{points} of {of}">{pips}</span>' if checked else '<span class="unchecked">Not checked</span>'
        items.append(
            f'<li class="{"" if checked else "off"}">'
            f'<span class="factor">{html.escape(item.get("name") or "")}'
            f'{help_button(FACTOR_HELP[item["name"]]) if item.get("name") in FACTOR_HELP else ""}</span>'
            f"{mark}"
            f'<span class="note">{html.escape(item.get("note") or "")}{source_note}</span>'
            "</li>"
        )
    ident = (row.get("identity") or {}).get("note") or ""
    ident_html = f'<p class="quiet ident">{html.escape(ident)}</p>' if ident else ""
    return f'{verdict}{flag_html}<ol class="factors">{"".join(items)}</ol>{ident_html}'


def card_lines(deal):
    """Only what the cost block does not already say. The seven checks stay behind them."""
    row = _meta(deal).get("diligence") or {}
    factors = {item.get("name"): item for item in row.get("factors") or []}
    flags = row.get("flags") or []
    danger = flags[0] if flags else "None on record"
    # shortcut: no source can tell if the building still stands, so it stays open until a permit or demolition feed exists
    open_names = ["Building still standing"]
    open_names += [
        item["name"]
        for item in row.get("factors") or []
        if item.get("checked") is False and item.get("name") not in ("Title", "Other liens")
    ]
    title = factors.get("Title") or {}
    if title and "Your docket check" not in (title.get("sources") or []):
        open_names.append("Court docket")
    liens = factors.get("Other liens") or {}
    if liens and liens.get("checked") is False:
        open_names.append("Other liens")
    lines = []
    if row.get("cause") and row["cause"] != "Taxes":
        lines.append({"label": "Cause", "text": row["cause"]})
    lines += [
        {"label": "Danger", "text": danger},
        {"label": "Still open", "text": ", ".join(open_names)},
    ]
    also = diligence.reapi_sentence(row.get("reapi"), deal.get("address") or "", row.get("loan") or "", row.get("tax") or "")
    if also and (also.startswith(("Not this door", "Parcel record")) or "Disagrees" in also):
        lines.append({"label": "Also", "text": also})
    return lines


def deal_costs(deal):
    return diligence.costs(deal.get("price"), _meta(deal), deal.get("estimated_value"))


def _costs(deal):
    found = deal_costs(deal)
    if not found:
        return ""
    rows = "".join(
        f'<tr><th scope="row">{html.escape(item["item"])}</th><td>{money(item["best"])}</td><td>{money(item["worst"])}</td></tr>'
        for item in found["rows"]
    )
    ceiling = f'<p class="cost-ceiling">Highest bid that fits: {money(found["ceiling"])}</p>' if found.get("ceiling") else ""
    value = ""
    if found.get("value"):
        help_key = "your_value" if found["value_label"] == "Your value" else "roll"
        value = f'<p class="cost-value">{html.escape(found["value_label"])}{help_button(help_key)} {money(found["value"])}. {html.escape(found["value_note"])}</p>'
    why = f'<p class="cost-why">{html.escape(found["why"])}</p>' if found["why"] else ""
    notes = "".join(f"<li>{html.escape(note)}</li>" for note in found["notes"])
    return (
        '<section class="costs" aria-label="Total cost">'
        f'<p class="cost-verdict tone-{found["tone"]}">{html.escape(found["verdict"])}</p>{why}{ceiling}'
        '<table><thead><tr><th scope="col">All in</th><th scope="col">Best</th><th scope="col">Worst</th></tr></thead>'
        f'<tbody>{rows}</tbody><tfoot><tr><th scope="row">Total</th><td>{money(found["best"])}</td><td>{money(found["worst"])}</td></tr></tfoot></table>'
        f'{value}<ul class="cost-notes">{notes}</ul></section>'
    )


def appraiser_url(meta):
    """The county page Hestia already reads. Photos there, when they exist, stay on that site."""
    county = meta.get("county") or ""
    parcel = (meta.get("parcel") or "").strip()
    if not parcel or parcel == "Property Appraiser":
        return ""
    if county == "Broward":
        return f"https://bcpa.net/RecInfo.asp?URL_Folio={diligence.compact_parcel(parcel)}"
    if county == "Miami-Dade":
        return f"https://www.miamidade.gov/Apps/PA/propertysearch/#/folio/{diligence.compact_parcel(parcel)}"
    if county == "Palm Beach":
        return "https://pbcpao.gov/"
    if county == "Monroe":
        return "https://www.mcpafl.org/"
    if county == "Lee":
        return f"https://www.leepa.org/Display/DisplayParcel.aspx?Strap={quote(parcel)}"
    return ""


def street_links(deal):
    """References you open. None of these sites will hand the photo to the server."""
    meta = _meta(deal)
    links = []
    appraiser = appraiser_url(meta)
    if appraiser:
        links.append({"name": "Appraiser", "url": appraiser})
    address = (deal.get("address") or "").strip()
    if not address:
        return links
    query = quote(f"{address}, {deal.get('location') or 'FL'}")
    links.append({"name": "Map", "url": f"https://www.google.com/maps/search/?api=1&query={query}"})
    links.append({"name": "Zillow", "url": f"https://www.zillow.com/homes/{query}_rb/"})
    links.append({"name": "Realtor", "url": f"https://www.realtor.com/realestateandhomes-search/{query}"})
    return links


def _brief(deal):
    lines = []
    for line in card_lines(deal):
        marked = (
            (line["label"] == "Danger" and line["text"] != "None on record")
            or (line["label"] == "Cause" and ("HOA" in line["text"] or " and " in line["text"]))
            or line["label"] == "Also"
        )
        hot = " hot" if marked else ""
        lines.append(f'<div><dt>{html.escape(line["label"])}</dt><dd class="{hot.strip()}">{html.escape(line["text"])}</dd></div>')
    return f'<dl class="brief">{"".join(lines)}</dl>'


def _street(deal):
    links = "".join(
        f'<a href="{html.escape(item["url"], quote=True)}" rel="noreferrer" target="_blank">{html.escape(item["name"])}</a>'
        for item in street_links(deal)
    )
    return f'<p class="street"><span>Look up</span>{links}</p>' if links else ""


def _plate(deal, next_query):
    meta = _meta(deal)
    did = int(deal["id"])
    score = _score(deal)
    href = safe_href(deal.get("link"))
    coords = [("Sale day", meta.get("sale_date") or "—", "sale")]
    if meta.get("parcel"):
        coords.append(("Parcel", meta["parcel"], "parcel"))
    if meta.get("case"):
        coords.append(("Case", meta["case"], "case"))
    coord_html = "".join(
        f"<div><dt>{html.escape(k)}{help_button(key)}</dt><dd>{html.escape(str(v))}</dd></div>" for k, v, key in coords
    )
    place = " · ".join(part for part in (display_place(deal.get("location")), deal.get("source") or "") if part)
    notes = deal.get("notes") or ""
    media = "".join(
        f'<img src="{html.escape(m["url"], quote=True)}" alt="" loading="lazy" width="120" height="90">'
        for m in deal.get("media") or []
        if m.get("kind") == "image" and safe_href(m.get("url"))
    )
    link = f'<a class="out" href="{html.escape(href, quote=True)}" rel="noreferrer" target="_blank">Open the auction listing</a>' if href else ""
    band = _band(deal)
    score_text = f"{score} of 10" if score else "Unscored"
    house = (meta.get("diligence") or {}).get("house") or ""
    return (
        f'<article class="plate" id="d{did}" aria-labelledby="d{did}-name"'
        f' data-id="{did}" data-bid="{deal.get("price") or ""}" data-roll="{meta.get("roll_value") or ""}"'
        f' data-score="{score}" data-band="{band}" data-status="{html.escape(deal["status"], quote=True)}"'
        f' data-name="{html.escape(display_name(deal["address"]), quote=True)}">'
        '<header>'
        f'<h2 id="d{did}-name" class="star-name" tabindex="-1">{html.escape(display_name(deal["address"]))}</h2>'
        '<button type="button" class="close" data-close>Close</button>'
        f'<p class="where">{html.escape(place)}</p>'
        "</header>"
        f"{_aerial(deal)}"
        f'{f"<p class=house>{html.escape(house)}</p>" if house else ""}'
        f"{_costs(deal)}"
        f"{_brief(deal)}"
        f"{_step_panel(deal, next_query)}"
        f'<dl class="coords">{coord_html}</dl>'
        f'<h3 class="mag-head">{_mag(score, band)}Score{help_button("score")}<span class="band-{band}">{score_text}</span></h3>'
        f'<details class="checks"><summary>Seven checks</summary>{_factors_html(deal)}</details>'
        f'{f"<p class=notes>{html.escape(notes)}</p>" if notes else ""}'
        f'{f"<div class=media>{media}</div>" if media else ""}'
        f"{link}{_street(deal)}"
        "</article>"
    )


def _aerial(deal):
    point = _point(deal)
    if not point:
        return ""
    name = html.escape(display_name(deal["address"]), quote=True)
    street = html.escape(diligence.street_photo_url(point), quote=True)
    # A missing street photo removes itself, and the satellite stays.
    photo = (
        f'<figure class="aerial"><img src="{street}" alt="Street view of {name}" loading="lazy" width="640" height="400"'
        ' onerror="this.closest(\'figure\').remove()"><figcaption>Street View · Google</figcaption></figure>'
        if street
        else ""
    )
    return (
        photo +
        f'<figure class="aerial"><img src="{html.escape(diligence.aerial_url(point), quote=True)}"'
        f' alt="Satellite view of {name}" loading="lazy" width="640" height="400">'
        '<span class="pin" aria-hidden="true"></span><figcaption>Satellite · Esri World Imagery</figcaption></figure>'
        f'{_street_view(deal, "sv-button")}'
    )


def _today():
    """Sale days are Florida auction days, and the Umbrel clock runs on UTC."""
    return datetime.now(ZoneInfo("America/New_York")).date()


def _sale_day(deal):
    try:
        return datetime.strptime(_meta(deal).get("sale_date") or "", "%m/%d/%Y").date()
    except ValueError:
        return None


def _day_heading(day, today):
    if day == today:
        return f"Today · {day.strftime('%b %-d')}"
    if day == today + timedelta(days=1):
        return f"Tomorrow · {day.strftime('%b %-d')}"
    return day.strftime("%A · %b %-d")


# The order a sale morning reads in. The first three start open, because those are the deals to act on.
VERDICT_GROUPS = (
    ("Worth a title check", True),
    ("Numbers fit, danger open", True),
    ("Only if the title clears", True),
    ("Can't say yet", False),
    ("Not scored yet", False),
    ("Pass at this price", False),
    ("No price on the list", False),
)


def _verdict(deal):
    return deal_costs(deal).get("verdict") or "No price on the list"


def _short(number):
    if number >= 1_000_000:
        return f"${number / 1_000_000:.1f}M"
    return f"${number / 1000:.0f}K" if number >= 1000 else f"${number:.0f}"


def _cost_range(deal):
    found = deal_costs(deal)
    if not found:
        return "—"
    best, worst = _short(found["best"]), _short(found["worst"])
    return best if best == worst else f"{best}–{worst}"


def _point(deal):
    point = (_meta(deal).get("diligence") or {}).get("point")
    return point if point and len(point) == 2 else None


def _photo(deal, width, height, alt=""):
    """The street photo when Google has one, or the satellite."""
    point = _point(deal)
    if not point:
        return '<span class="card-photo empty" aria-hidden="true"></span>'
    aerial = html.escape(diligence.aerial_url(point, width, height), quote=True)
    street = html.escape(diligence.street_photo_url(point, width, height), quote=True)
    fallback = f' data-fallback="{aerial}" onerror="this.onerror=null;this.src=this.dataset.fallback"' if street else ""
    return f'<img class="card-photo" src="{street or aerial}"{fallback} alt="{html.escape(alt, quote=True)}" loading="lazy" width="{width}" height="{height}">'


def _street_view(deal, css):
    point = _point(deal)
    if not point:
        return ""
    return f'<a class="{css}" href="{html.escape(diligence.street_view_link(point), quote=True)}" rel="noreferrer" target="_blank">Street View</a>'


def _deal_card(deal, dated):
    did = int(deal["id"])
    name = display_name(deal["address"])
    danger = next(line["text"] for line in card_lines(deal) if line["label"] == "Danger")
    danger_html = "" if danger == "None on record" else f'<span class="danger">{html.escape(danger)}</span>'
    house = (_meta(deal).get("diligence") or {}).get("house") or ""
    house_html = f'<span class="facts">{html.escape(house)}</span>' if house else ""
    return (
        f'<li class="deal-card" data-id="{did}">'
        f'<div class="card-top">{_photo(deal, 480, 300)}{_street_view(deal, "sv")}</div>'
        f'<div class="card-body"><span class="cost">{html.escape(_cost_range(deal))}<small>all in</small></span>{house_html}'
        f'<a class="card-name" href="#d{did}">{html.escape(name)}</a>'
        f'<span class="where">{html.escape(_row_hint(deal, dated))}</span>{danger_html}</div>'
        "</li>"
    )


def _row_hint(deal, dated):
    place = display_place(deal.get("location"))
    day = _meta(deal).get("sale_date") if dated else ""
    return " · ".join(part for part in (place, day) if part)


def _verdict_groups(rows, dated=False):
    """Inside a verdict, the deal with the most room under its value comes first."""

    def room(deal):
        found = deal_costs(deal)
        return found["worst"] / found["value"] if found.get("value") else 99

    parts = []
    for verdict, start_open in VERDICT_GROUPS:
        members = sorted((deal for deal in rows if _verdict(deal) == verdict), key=room)
        if not members:
            continue
        body = "".join(_deal_card(deal, dated) for deal in members)
        parts.append(
            f'<details class="group"{" open" if start_open else ""}>'
            f'<summary>{html.escape(verdict)} <span class="c">{len(members)}</span></summary>'
            f'<ul class="cards">{body}</ul></details>'
        )
    return "".join(parts)


def _desk_list(rows, filtered):
    """The next sale first. A filter already narrowed the list, so it shows everything it matched."""
    today = _today()
    days = [_sale_day(deal) for deal in rows]
    upcoming = [day for day in days if day and day >= today]
    if filtered or not upcoming:
        return "", _verdict_groups(rows, dated=True), len(rows)
    next_day = min(upcoming)
    now = [deal for deal in rows if _sale_day(deal) == next_day]
    rest = [deal for deal in rows if _sale_day(deal) != next_day]
    later = ""
    if rest:
        later = (
            f'<details class="later"><summary>Other sales <span class="c">{len(rest)}</span></summary>'
            f"{_verdict_groups(rest, dated=True)}</details>"
        )
    return f"Next sale · {_day_heading(next_day, today)}", _verdict_groups(now) + later, len(now)


def load_results():
    try:
        return json.loads((STATIC_DIR / "results.json").read_text())
    except (OSError, json.JSONDecodeError):
        return {"counties": []}


def _percent(part, whole):
    return f"{round(100 * part / whole)}%" if whole else "0%"


def _ended_row(county, entry):
    total = entry["total"]
    parts = (("unsold", "did not sell"), ("kept", "went back to the plaintiff or certificate holder"), ("outside", "sold to an outside buyer"))
    segments = "".join(
        f'<span class="seg seg-{key}" style="flex-grow:{entry[key]}" title="{html.escape(county)}: {entry[key]:,} of {total:,} {label} ({_percent(entry[key], total)})"></span>'
        for key, label in parts
        if entry[key]
    )
    return (
        f'<div class="result-row"><h4>{html.escape(county)} <span>{total:,} auctions</span></h4><div class="ended-bar" aria-hidden="true">{segments}</div>'
        f'<p>{_percent(entry["unsold"], total)} did not sell · {_percent(entry["kept"], total)} kept · {_percent(entry["outside"], total)} outside buyer</p></div>'
    )


def _paid_row(county, entry, top):
    if "median" not in entry:
        return f'<div class="result-row"><h4>{html.escape(county)}</h4><p>Too few outside sales to say ({entry["buyers"]}).</p></div>'
    width = 85 * entry["median"] / top
    return (
        f'<div class="result-row"><h4>{html.escape(county)} <span>{entry["buyers"]:,} buyers</span></h4>'
        f'<div class="paid-line"><span class="paid-bar" style="width:{width:.1f}%" title="{html.escape(county)}: median {entry["median"]}×"></span><strong>{entry["median"]}×</strong></div></div>'
    )


def _median_text(entry):
    return f"{entry['median']}×" if "median" in entry else "—"


def render_results(summary):
    sections = []
    for kind, base in (("Foreclosure", "the final judgment"), ("Tax deed", "the opening bid")):
        members = [(c["county"], e) for c in summary.get("counties", []) for e in c["kinds"] if e["kind"] == kind]
        if not members:
            continue
        top = max([e.get("median", 0) for _, e in members] + [1])
        rows = "".join(
            f'<tr><th scope="row">{html.escape(county)}</th><td>{e["total"]:,}</td><td>{e["unsold"]:,}</td><td>{e["kept"]:,}</td><td>{e["outside"]:,}</td><td>{_median_text(e)}</td></tr>'
            for county, e in members
        )
        sections.append(
            f'<section class="result-kind"><h2>{kind}s</h2><div class="result-grid">'
            f'<figure><figcaption>How the auctions ended</figcaption>{"".join(_ended_row(county, e) for county, e in members)}</figure>'
            f'<figure><figcaption>What outside buyers paid, as a multiple of {base}. Typical sale.</figcaption>{"".join(_paid_row(county, e, top) for county, e in members)}</figure>'
            f'</div><details class="result-table"><summary>See the numbers</summary><table><thead><tr><th>County</th><th>Auctions</th><th>Did not sell</th><th>Kept</th><th>Outside buyer</th><th>Median paid</th></tr></thead><tbody>{rows}</tbody></table></details></section>'
        )
    body = "".join(sections) or '<p class="quiet">No past results yet.</p>'
    span = f'{summary["from"]} to {summary["through"]}. ' if summary.get("from") else ""
    return f"""<!DOCTYPE html>
<html lang="en">
<head>
<meta charset="utf-8">
<meta name="viewport" content="width=device-width, initial-scale=1, viewport-fit=cover">
<meta name="theme-color" content="#0a1021">
<title>Past results · Hestia</title>
<link rel="stylesheet" href="/static/desk.css">
</head>
<body class="results">
<p><a href="/">‹ Desk</a></p>
<h1>Past results</h1>
<p class="quiet">{html.escape(span)}From the county auction sites. Kept means it went back to the plaintiff or the certificate holder. Prices are what was bid, not what a resale brought.</p>
<ul class="result-legend" aria-label="Legend"><li><span class="seg-unsold"></span>Did not sell</li><li><span class="seg-kept"></span>Kept</li><li><span class="seg-outside"></span>Outside buyer</li></ul>
{body}
</body>
</html>
"""


def _regions(rows, current):
    """Counties north to south, then Lee. A county is a filter on where the sale came from."""
    counts = {}
    for deal in rows:
        county = _meta(deal).get("county") or ""
        if deal["status"] in ("Found", "Researched"):
            counts[county] = counts.get(county, 0) + 1
    links = [f'<a href="/"{" aria-current=page" if not current else ""}>All <span class="c">{sum(counts.values())}</span></a>']
    for county in REGIONS:
        on = " aria-current=page" if current == county else ""
        links.append(f'<a href="/?source={quote(county)}"{on}>{html.escape(county)} <span class="c">{counts.get(county, 0)}</span></a>')
    return f'<nav class="regions" aria-label="County">{"".join(links)}</nav>'


def _pipeline(rows):
    groups = []
    for status in PIPELINE:
        members = [deal for deal in rows if deal["status"] == status]
        items = "".join(
            f'<li><a href="#d{int(d["id"])}" data-id="{int(d["id"])}">{html.escape(display_name(d["address"]))}</a>'
            f'<span class="num">{money(d.get("price"))}</span></li>'
            for d in members
        )
        body = f"<ul>{items}</ul>" if items else ""
        groups.append(f'<section><h3>{status} <span class="num">{len(members)}</span></h3>{body}</section>')
    if not any(deal["status"] in PIPELINE for deal in rows):
        groups.insert(0, '<p class="quiet">Nothing past Researched yet. Mark a deal title checked and it moves here.</p>')
    passed = sum(1 for deal in rows if deal["status"] == "Passed")
    if passed:
        groups.append(f'<p class="quiet"><a href="/?status=Passed">Passed deals ({passed})</a></p>')
    return "".join(groups)


def _process(rows, current):
    """The seven steps across the top, each with its count. A step is a filter."""
    items = []
    for n, step in enumerate(deals.STEPS, 1):
        count = sum(1 for deal in rows if deal["status"] == step)
        on = ' aria-current="page"' if step == current else ""
        items.append(
            f'<li><a href="/?status={quote(step)}"{on}><span class="n">{n}</span>'
            f'<span class="step-name">{html.escape(step)}</span><span class="c">{count}</span></a></li>'
        )
    return f'<nav class="process" aria-label="Process"><ol>{"".join(items)}</ol>{help_button("steps")}</nav>'


def _next_sale(rows):
    days = []
    for deal in rows:
        try:
            days.append(datetime.strptime(_meta(deal).get("sale_date") or "", "%m/%d/%Y").date())
        except ValueError:
            continue
    upcoming = [day for day in days if day >= _today()]
    return min(upcoming).strftime("%b %-d") if upcoming else ""


def render_page(rows, filters, error="", draft=None, everything=None):
    draft = draft or {}
    everything = rows if everything is None else everything
    current_query = "/" + _query(filters)
    filter_status = filters.get("status", "")
    status_options = _option("", filter_status, "Any status") + "".join(
        _option(status, filter_status) for status in deals.STATUSES
    )
    add_status = draft.get("status") or "Found"

    def field(form, name, label, value="", kind="text", help_key=""):
        return (
            f'<div class="field-row"><span class="field-head"><label for="{form}-{name}">{html.escape(label)}</label>'
            f'{help_button(help_key) if help_key else ""}</span>'
            f'<input id="{form}-{name}" name="{name}" value="{html.escape(value)}" inputmode="{"decimal" if kind == "money" else "text"}">'
            "</div>"
        )

    def picker(form, label, control, help_key):
        control = control.replace("<select ", f'<select id="{form}-status" ', 1)
        return (
            f'<div class="field-row"><span class="field-head"><label for="{form}-status">{label}</label>{help_button(help_key)}</span>'
            f"{control}</div>"
        )

    lane = (filter_status,) if filter_status else ("Found", "Researched")
    index_rows = [deal for deal in rows if deal["status"] in lane]
    index_title = filter_status or "From the auctions"
    region = filters.get("source", "") if filters.get("source", "") in REGIONS else ""
    index_count = len(index_rows)
    if index_rows:
        narrowed = any(value for key, value in filters.items() if not (key == "source" and value in REGIONS))
        next_title, index, index_count = _desk_list(index_rows, narrowed)
        index_title = next_title or index_title
    elif any(filters.values()):
        index = '<p class="empty">No deals match these filters. <a href="/">Show all</a></p>'
    else:
        index = '<p class="empty">No deals on the desk. Collect South Florida sales to pull the next auctions.</p>'

    plates = "".join(_plate(deal, current_query) for deal in rows)
    error_html = f'<p class="error" role="alert">{html.escape(error)}</p>' if error else ""
    unscored = sum(1 for deal in everything if (_meta(deal).get("diligence") or {}).get("version", 0) < diligence.VERSION)
    next_sale = _next_sale(everything)
    counts = [f"{len(everything)} deals"]
    if unscored:
        counts.append(f"{unscored} to score")
    if next_sale:
        counts.append(f"next sale {next_sale}")
    in_pipeline = sum(1 for deal in everything if deal["status"] in PIPELINE)
    show_all = '<a href="/">Show all</a>' if any(filters.values()) else ""
    filters_open = " open" if any(filters.get(key) for key in ("location", "source", "min_price", "max_price")) else ""
    add_open = " open" if draft else ""

    return f"""<!DOCTYPE html>
<html lang="en" data-app-version="{app_version()}">
<head>
<meta charset="utf-8">
<meta name="viewport" content="width=device-width, initial-scale=1, viewport-fit=cover">
<meta name="theme-color" content="#0a1021">
<title>Hestia</title>
<link rel="preload" href="/static/fonts/eb-garamond.woff2" as="font" type="font/woff2" crossorigin>
<link rel="stylesheet" href="/static/desk.css">
<script>document.documentElement.classList.add("js"); if (/; wv[)]/.test(navigator.userAgent)) document.documentElement.classList.add("in-app")</script>
</head>
<body>
<header class="bar">
  <h1 class="mark"><svg viewBox="0 0 24 24" aria-hidden="true"><path d="M12 1.5 13.6 10.4 22.5 12 13.6 13.6 12 22.5 10.4 13.6 1.5 12 10.4 10.4Z"/></svg>Hestia</h1>
  <p class="counts" id="count">{html.escape(" · ".join(counts))} · <a href="#pipe-title">{in_pipeline} in pipeline</a></p>
  <p class="note" id="collect-note" role="status"></p>
</header>
<p class="app-update" id="app-update" hidden>This is the old Hestia app. <a href="/static/hestia-native.apk">Install the current one</a>, then uninstall this copy.</p>
{error_html}
<div class="tools">
  <details{filters_open}>
    <summary>Filter</summary>
    <form class="filters" method="get" action="/">
      {picker("filter", "Status", f'<select name="status">{status_options}</select>', "status")}
      {field("filter", "location", "Location", filters.get("location", ""), help_key="location")}
      {field("filter", "source", "Source", filters.get("source", ""), help_key="source")}
      {field("filter", "min_price", "Min bid", filters.get("min_price", ""), "money", "bid_range")}
      {field("filter", "max_price", "Max bid", filters.get("max_price", ""), "money", "bid_range")}
      <button type="submit">Filter</button>
    </form>
  </details>
  <details>
    <summary>Chart</summary>
    <section class="chart" aria-labelledby="chart-title">
      <h2 id="chart-title" class="sr">Bid against tax roll value</h2>
      <div class="sky-box"><svg id="sky" role="img" aria-label="Each deal is a dot. Further right costs more, higher has a larger tax roll value, bigger scored higher, and the color is the score color."></svg></div>
      <p class="off-chart quiet" id="off-chart"></p>
    </section>
  </details>
  <details>
    <summary>Steps</summary>
    {_process(everything, filter_status)}
  </details>
  <details>
    <summary>Collect</summary>
    <div class="actions">
      <button type="button" id="score">Score unchecked</button>
      <button type="button" id="collect" class="primary">Collect<span class="long"> South Florida</span> sales</button>
    </div>
  </details>
  <details{add_open}>
    <summary>Add a deal</summary>
    <form class="add" method="post" action="/deals">
      {field("add", "address", "Address", draft.get("address", ""))}
      {field("add", "location", "Location", draft.get("location", ""))}
      {field("add", "price", "Asking price", draft.get("price", ""), "money", "price")}
      {field("add", "estimated_value", "Your value estimate", draft.get("estimated_value", ""), "money", "your_value")}
      {field("add", "source", "Source", draft.get("source", ""))}
      {field("add", "link", "Link", draft.get("link", ""))}
      <label class="wide">Notes<textarea name="notes" rows="2">{html.escape(draft.get("notes", ""))}</textarea></label>
      {picker("add", "Status", _status_select("status", add_status), "status")}
      <button type="submit">Add deal</button>
    </form>
  </details>
  <a href="/results">Past results</a>
  {show_all}
  <a class="get-app" href="/static/hestia-native.apk" download>Get the Android app</a>
</div>
{_regions(everything, region)}
<main class="desk">
  <div class="field">
    <section class="lane" aria-labelledby="index-title">
      <h2 id="index-title">{html.escape(index_title)} <span>{index_count}</span></h2>
      {index}
    </section>
  </div>
  <aside class="side">
    <div class="plates" id="plates">{plates}</div>
    <div class="scrim" data-close hidden></div>
    <section class="lane pipeline" aria-labelledby="pipe-title">
      <h2 id="pipe-title">My pipeline</h2>
      {_pipeline(everything)}
    </section>
  </aside>
</main>
<svg width="0" height="0" class="sr" aria-hidden="true"><symbol id="i-help" viewBox="0 0 16 16"><circle cx="8" cy="8" r="6.75" fill="none" stroke="currentColor" stroke-width="1.25"/><path d="M8 4.4v4.6" stroke="currentColor" stroke-width="1.5" stroke-linecap="round"/><circle cx="8" cy="11.5" r="0.95" fill="currentColor"/></symbol></svg>
{_help_popovers()}
<script src="/static/desk.js" defer></script>
</body>
</html>
"""


class Handler(BaseHTTPRequestHandler):
    def do_GET(self):
        parsed = urlparse(self.path)
        if parsed.path == "/api/deals":
            raw, parsed_filters, error = _filters(parse_qs(parsed.query, keep_blank_values=True))
            if error:
                self._json({"error": error}, 400)
                return
            rows = _load(raw, parsed_filters) or []
            self._json([_prepare(row) for row in rows])
            return
        if parsed.path == "/api/results":
            self._json(load_results())
            return
        if parsed.path == "/results":
            self._html(render_results(load_results()))
            return
        if parsed.path == "/api/guide":
            self._json(guide())
            return
        if parsed.path.startswith("/static/") and parsed.path[8:] in STATIC:
            self._static(parsed.path[8:])
            return
        if parsed.path != "/":
            self.send_error(404)
            return
        params = parse_qs(parsed.query, keep_blank_values=True)
        raw, parsed_filters, error = _filters(params)
        if not error and any(key in params and not raw[key] for key in raw):
            self._redirect(_query(raw) or "/")
            return
        if error:
            parsed_filters = {"min_price": None, "max_price": None}
        rows = _load(raw, parsed_filters)
        if rows is None:
            error = error or "Pick a status from the list."
            raw = {**raw, "status": ""}
            rows = _load(raw, parsed_filters) or []
        self._html(render_page(rows, raw, error=error, everything=_everything()))

    def do_POST(self):
        if not _same_origin(self):
            self.send_error(403)
            return
        if self.headers.get("Content-Type", "").split(";")[0].strip() != "application/x-www-form-urlencoded":
            self.send_error(415)
            return
        length = int(self.headers.get("Content-Length", "0") or "0")
        if length > MAX_BODY:
            self.send_error(413)
            return
        form = parse_qs(self.rfile.read(length).decode("utf-8", "replace"))
        path = urlparse(self.path).path
        if path == "/api/collect":
            self._collect()
        elif path == "/api/score":
            self._score()
        elif path == "/deals":
            self._add(form)
        elif path == "/deals/status":
            self._move(form)
        elif path == "/deals/step":
            self._step(form)
        elif path == "/deals/research":
            self._research(form)
        elif path in ("/api/step", "/api/research"):
            self._api(path, form)
        else:
            self.send_error(404)

    def _score(self):
        # Two deals per call keeps each request well under Cloudflare's 100-second limit.
        with closing(deals.connect(DB_PATH)) as conn:
            pending, left = deals.pending_scores(conn, 2, diligence.VERSION)
        if not pending:
            self._json({"scored": 0, "left": 0, "note": "Every deal is scored under the current rules."})
            return
        for deal in pending:
            _rescore(deal)
        with closing(deals.connect(DB_PATH)) as conn:
            _, left = deals.pending_scores(conn, 1, diligence.VERSION)
        self._json({"scored": len(pending), "left": left, "note": f"Scored {len(pending)}. {left} still to check."})

    def _research(self, form):
        nxt = safe_next(_one(form, "next"))
        try:
            deal_id = int(_one(form, "id"))
            with closing(deals.connect(DB_PATH)) as conn:
                found, _ = deals.pending_scores(conn, 1, only=deal_id)
            if not found:
                raise ValueError("That deal is no longer on the list.")
            _rescore(found[0])
        except (ValueError, TypeError) as exc:
            self._error_page(nxt, str(exc) if isinstance(exc, ValueError) else "That deal is no longer on the list.")
            return
        self._redirect(_with_hash(nxt, deal_id))

    def _step(self, form):
        nxt = safe_next(_one(form, "next"))
        try:
            deal_id = _do_step(form)
        except (ValueError, TypeError) as exc:
            self._error_page(nxt, str(exc) if isinstance(exc, ValueError) else "That deal is no longer on the list.")
            return
        self._redirect(_with_hash(nxt, deal_id))

    def _api(self, path, form):
        """The native app's calls. Same rules as the desk, answered in JSON."""
        try:
            deal_id = int(_one(form, "id"))
            if path == "/api/step":
                _do_step(form)
            else:
                with closing(deals.connect(DB_PATH)) as conn:
                    found, _ = deals.pending_scores(conn, 1, only=deal_id)
                if not found:
                    raise ValueError("That deal is no longer on the list.")
                _rescore(found[0])
        except (ValueError, TypeError) as exc:
            self._json({"error": str(exc) if isinstance(exc, ValueError) else "That deal is no longer on the list."}, 400)
            return
        deal = next((row for row in _everything() if row["id"] == deal_id), None)
        self._json({"deal": _prepare(deal) if deal else None})

    def _error_page(self, nxt, message):
        query = nxt.split("?", 1)[1].split("#", 1)[0] if "?" in nxt else ""
        raw, parsed_filters, _ = _filters(parse_qs(query))
        rows = _load(raw, parsed_filters) or []
        self._html(render_page(rows, raw, error=message, everything=_everything()))

    def _collect(self):
        self._json(collect_step())

    def _json(self, payload, status=200):
        data = json.dumps(payload).encode()
        self.send_response(status)
        self.send_header("Content-Type", "application/json; charset=utf-8")
        self.send_header("Content-Length", str(len(data)))
        self.end_headers()
        self.wfile.write(data)

    def _add(self, form):
        draft = {key: _one(form, key) for key in ("address", "location", "price", "estimated_value", "source", "notes", "link", "status")}
        try:
            price = deals.parse_money(draft["price"])
            estimated = deals.parse_money(draft["estimated_value"])
            with closing(deals.connect(DB_PATH)) as conn:
                deals.add_deal(
                    conn,
                    address=draft["address"],
                    location=draft["location"],
                    price=price,
                    estimated_value=estimated,
                    source=draft["source"],
                    notes=draft["notes"],
                    link=draft["link"],
                    status=draft["status"] or "New",
                )
        except ValueError as exc:
            with closing(deals.connect(DB_PATH)) as conn:
                rows = deals.list_deals(conn)
            self._html(render_page(rows, {}, error=str(exc), draft=draft))
            return
        self._redirect("/")

    def _move(self, form):
        nxt = safe_next(_one(form, "next"))
        try:
            deal_id = int(_one(form, "id"))
            with closing(deals.connect(DB_PATH)) as conn:
                deals.set_status(conn, deal_id, _one(form, "status"))
        except (ValueError, TypeError) as exc:
            self._error_page(nxt, str(exc) if isinstance(exc, ValueError) else "That deal is no longer on the list.")
            return
        self._redirect(nxt)

    def _html(self, body, status=200):
        data = body.encode()
        self.send_response(status)
        self.send_header("Content-Type", "text/html; charset=utf-8")
        self.send_header("Content-Length", str(len(data)))
        self.send_header("X-Content-Type-Options", "nosniff")
        self.end_headers()
        self.wfile.write(data)

    def _static(self, name):
        path = STATIC_DIR / name
        if not path.is_file():
            self.send_error(404)
            return
        data = path.read_bytes()
        self.send_response(200)
        self.send_header("Content-Type", STATIC[name])
        if name.endswith(".apk"):
            self.send_header("Content-Disposition", f'attachment; filename="{Path(name).name}"')
        self.send_header("Content-Length", str(len(data)))
        self.send_header("Cache-Control", "max-age=31536000" if name.startswith("fonts/") else "no-cache")
        self.send_header("X-Content-Type-Options", "nosniff")
        self.end_headers()
        self.wfile.write(data)

    def _redirect(self, location):
        self.send_response(303)
        self.send_header("Location", location)
        self.end_headers()

    def log_message(self, fmt, *args):
        print(f"{self.address_string()} {fmt % args}")


def _do_step(form):
    deal_id = int(_one(form, "id"))
    to = _one(form, "to")
    data = {
        "title": _one(form, "title") == "1",
        "liens": _one(form, "liens") == "1",
        "max_bid": deals.parse_money(_one(form, "max_bid")),
        "won_price": deals.parse_money(_one(form, "won_price")),
        "buyer": _one(form, "buyer").strip(),
        "fee": deals.parse_money(_one(form, "fee")),
    }
    with closing(deals.connect(DB_PATH)) as conn:
        meta = deals.advance(conn, deal_id, to, data)
        if to == "Title checked" and meta.get("diligence"):
            graded = diligence.apply_review(meta["diligence"], {"title": True, "liens": True})
            deals.save_diligence(conn, deal_id, graded, keep_roll=True)
    return deal_id


def guide():
    """Everything the native app shows as text, so a server deploy updates its wording too."""
    return {
        "steps": list(deals.STEPS),
        "step_guide": STEP_GUIDE,
        "step_fields": {step: list(fields) for step, fields in deals.STEP_FIELDS.items()},
        "bands": diligence.BANDS,
        "help": {key: {"title": title, "text": text} for key, (title, text) in HELP.items()},
        "factor_help": FACTOR_HELP,
        "check_links": {county: [{"name": n, "url": u} for n, u in links] for county, links in CHECK_LINKS.items()},
        "rules_version": diligence.VERSION,
    }


COLLECTING = {"running": False, "note": "", "result": None}
COLLECT_LOCK = threading.Lock()


def _collect_all():
    def progress(note):
        COLLECTING["note"] = note

    try:
        listings, notes = sources.collect(progress=progress)
        added = updated = 0
        with closing(deals.connect(DB_PATH)) as conn:
            for listing in listings:
                state = deals.upsert_listing(conn, listing)
                if state == "added":
                    added += 1
                else:
                    updated += 1
            dropped = deals.drop_past_sales(conn, _today())
        if dropped:
            notes.append(f"Removed {dropped} untouched deals whose sale day has passed.")
        result = {"added": added, "updated": updated, "dropped": dropped, "notes": notes}
    except Exception as exc:
        result = {"added": 0, "updated": 0, "dropped": 0, "notes": [f"Collecting stopped: {exc.__class__.__name__}."]}
    COLLECTING.update(running=False, result=result)


def collect_step(start=None):
    """A full collect outlasts Cloudflare's 100-second limit, so it runs behind the request and the page asks again."""
    with COLLECT_LOCK:
        if COLLECTING["running"]:
            return {"running": True, "note": COLLECTING["note"]}
        if COLLECTING["result"]:
            result, COLLECTING["result"] = COLLECTING["result"], None
            return {"running": False, **result}
        COLLECTING.update(running=True, note="Collecting…")
        threading.Thread(target=start or _collect_all, daemon=True).start()
    return {"running": True, "note": COLLECTING["note"]}


def _rescore(deal):
    """Fresh public records, then your own docket and lien check laid back on top if you already did it."""
    result = diligence.research(deal)
    graded = result["diligence"]
    meta = deal.get("metadata") or {}
    kept = (meta.get("diligence") or {}).get("reapi")
    if kept:
        graded["reapi"] = kept
    if meta.get("title") and meta.get("liens"):
        graded = diligence.apply_review(graded, {"title": True, "liens": True})
    with closing(deals.connect(DB_PATH)) as conn:
        deals.save_diligence(conn, deal["id"], graded, result.get("just_value"))


def _images(deal):
    point = _point(deal)
    if not point:
        return {}
    return {"street_view": diligence.street_view_link(point), "photo": diligence.street_photo_url(point)}


def _prepare(deal):
    """Add the auction bid link for the app. It is derived, so it is not stored."""
    meta = dict(deal.get("metadata") or {})
    url = sources.bid_url(meta)
    if url:
        meta["bid_url"] = url
    return {**deal, "metadata": meta, "card": card_lines(deal), "costs": deal_costs(deal), **_images(deal), "street": street_links(deal)}


def _with_hash(nxt, deal_id):
    return f"{nxt.split('#', 1)[0]}#deal-{deal_id}"


def _everything():
    with closing(deals.connect(DB_PATH)) as conn:
        return deals.list_deals(conn)


def _load(raw, parsed_filters):
    try:
        with closing(deals.connect(DB_PATH)) as conn:
            return deals.list_deals(
                conn,
                status=raw["status"],
                location=raw["location"],
                source=raw["source"],
                min_price=parsed_filters["min_price"],
                max_price=parsed_filters["max_price"],
            )
    except ValueError:
        return None


def _same_origin(handler):
    origin = handler.headers.get("Origin")
    if not origin:
        return True
    host = handler.headers.get("Host", "")
    return origin == f"http://{host}" or origin == f"https://{host}"


def main():
    server = ThreadingHTTPServer((HOST, PORT), Handler)
    print(f"Hestia at http://{HOST}:{PORT}")
    server.serve_forever()


if __name__ == "__main__":
    main()
