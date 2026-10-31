"""Score one property from public records. A factor only counts once a source answered it, and a color needs two sources to agree on value."""

import json
import math
import os
import re
import time
import urllib.error
import urllib.parse
import urllib.request
from datetime import date

import sources

# Taxes owed, clerk dockets, and recorded liens sit behind captchas, so Title and Other liens need your own check before a deal can turn blue.
VERSION = 3
FDOR = "https://services9.arcgis.com/Gh9awoU677aKree0/arcgis/rest/services/Florida_Statewide_Cadastral/FeatureServer/0/query"
MIAMI = "https://services.arcgis.com/8Pc9XBTAsYuxx9Ny/arcgis/rest/services/PaParcelView_gdb/FeatureServer/0/query"
MIAMI_SERVICES = "https://services.arcgis.com/8Pc9XBTAsYuxx9Ny/arcgis/rest/services"
LEE = "https://gismapserver.leegov.com/gisserver910/rest/services/DataExplorer/Parcels/MapServer/0/query"
LEE_NUISANCE = "https://services2.arcgis.com/LvWGAAhHwbCJ2GMP/arcgis/rest/services/NuisanceAccumulationViolations/FeatureServer/0/query"
FEMA = "https://hazards.fema.gov/arcgis/rest/services/public/NFHL/MapServer/28/query"
CENSUS = "https://geocoding.geo.census.gov/geocoder/locations/onelineaddress"
FIPS = {"Palm Beach": "12099", "Broward": "12011", "Miami-Dade": "12086", "Monroe": "12087", "Lee": "12071"}
_UNIT = re.compile(r"(?:#|\b(?:APT|UNIT|STE|SUITE)\b)\s*[A-Z0-9-]+", re.I)

RECENT_SALE_YEAR = 2023
# Planning estimates. Replace them with real quotes from a title company or a closed deal.
COST_STAMP_RATE = 0.007
COST_RECORDING = 500
COST_QUIET_TITLE = (2500, 5000)
COST_VALUE_SHARE = 0.7
LOAN_GAP = 1.1
# What outside buyers paid against the tax roll, 10/30/2025 to 10/30/2026: sales, the median share, and the part who paid at or under each share.
# County rows need 100 sales. The rest use the pooled row. history.py pulls the sales, and this table was built from them and the state roll.
MARKET_STEPS = (0.4, 0.5, 0.6, 0.7, 0.8, 0.9, 1.0)
MARKET = {
    ("Broward", "foreclosure"): (356, 0.58, (0.32, 0.42, 0.53, 0.65, 0.8, 0.92, 0.98)),
    ("Lee", "foreclosure"): (175, 0.69, (0.14, 0.19, 0.3, 0.54, 0.79, 0.91, 0.97)),
    ("Miami-Dade", "foreclosure"): (251, 0.88, (0.14, 0.17, 0.21, 0.26, 0.39, 0.55, 0.79)),
    ("Palm Beach", "foreclosure"): (210, 0.7, (0.3, 0.35, 0.4, 0.5, 0.64, 0.79, 0.9)),
    ("Lee", "tax deed"): (101, 0.75, (0.13, 0.22, 0.32, 0.42, 0.6, 0.79, 0.9)),
    ("", "foreclosure"): (992, 0.7, (0.24, 0.3, 0.38, 0.5, 0.66, 0.8, 0.91)),
    ("", "tax deed"): (140, 0.74, (0.15, 0.24, 0.34, 0.44, 0.63, 0.81, 0.91)),
}
LAND_HEAVY = 0.9
BANDS = {
    "excellent": "Excellent",
    "good": "Good",
    "fair": "Fair",
    "risky": "Risky",
    "thin": "Not enough data",
}
_DIRECTIONS = {"N", "S", "E", "W", "NE", "NW", "SE", "SW"}


def compact_parcel(raw):
    return re.sub(r"[^A-Z0-9]", "", (raw or "").upper())


def _money(raw):
    try:
        return float(str(raw).replace("$", "").replace(",", ""))
    except (TypeError, ValueError):
        return None


def _text(html):
    text = re.sub(r"<[^>]+>", " ", html)
    text = text.replace("&nbsp;", " ")
    return re.sub(r"\s+", " ", text)


def _count(value):
    number = float(value)
    return str(int(number)) if number == int(number) else f"{number:g}"


def format_house(*, beds=None, baths=None, sqft=None, year=None, pool=False, garage=False):
    """One line from the property appraiser. No listing site has this for an auction house."""
    bits = []
    if beds:
        bits.append(f"{_count(beds)} bed")
    if baths:
        bits.append(f"{_count(baths)} bath")
    if sqft:
        bits.append(f"{int(float(sqft)):,} sq ft")
    if year:
        bits.append(f"built {int(year)}")
    line = " · ".join(bits)
    extras = [name for name, yes in (("pool", pool), ("garage", garage)) if yes]
    if extras:
        line = f"{line}, {', '.join(extras)}" if line else ", ".join(extras)
    return line


def parse_broward_record(html):
    text = _text(html)
    found = re.search(r"2026\s+\$([\d,]+)\s+\$([\d,]+)\s+\$([\d,]+)\s+\$([\d,]+)", text)
    just = _money(found.group(3)) if found else None
    homestead = re.findall(r"Homestead\s+(\d+)", text)
    sales = []
    for month, day, year, kind, price in re.findall(
        r"(\d{1,2})/(\d{1,2})/(\d{4})\s+([A-Z-]+)\s+\$([\d,]+)", text
    ):
        amount = _money(price)
        if amount and "WD" in kind:
            sales.append({"year": int(year), "price": amount})
    rooms = re.search(r"Units/Beds/Baths\s+\d+/(\d+)/(\d+)", text)
    area = re.search(r"Bldg\. S\.F\.\s+([\d,]+)", text)
    built = re.search(r"Year Built:\s+\d{4}/(\d{4})", text)
    house = format_house(
        beds=int(rooms.group(1)) if rooms else None,
        baths=int(rooms.group(2)) if rooms else None,
        sqft=_money(area.group(1)) if area else None,
        year=int(built.group(1)) if built else None,
    )
    return {"just": just, "homestead": bool(homestead and int(homestead[-1]) > 0), "sales": sales, "house": house}


def parse_broward_comps(html):
    text = _text(html)
    comps = []
    for month, day, year, flag, price in re.findall(
        r"(\d{1,2})/(\d{1,2})/(\d{4})\s+\d{2}\s+[A-Z]+\s+\d+\s+([QT])\s+\$([\d,]+)", text
    ):
        amount = _money(price)
        if flag == "Q" and amount and amount >= 10000:
            comps.append({"year": int(year), "price": amount, "source": "Broward subdivision sales"})
    return comps


def court_of(case):
    """County court cases on a foreclosure list are usually an HOA or condo association collecting dues."""
    text = (case or "").upper()
    if re.search(r"\bCO(CE|NO|SO|WE)\b|-CC-|\bCC\b", text):
        return "county"
    if re.search(r"\bCA(CE|NO|SO|WE)?\b|-CA-|\bCA\b", text):
        return "circuit"
    return ""


def house_number(address):
    tokens = re.findall(r"[A-Z0-9]+", (address or "").upper())
    number = next((token for token in tokens if token.isdigit()), "")
    return "" if number.strip("0") == "" else number.lstrip("0")


def _factor(name, points, note, *, checked=True, sources_used=(), flag=""):
    return {
        "name": name,
        "points": points if checked else 0,
        "of": 2,
        "checked": checked,
        "sources": list(sources_used),
        "note": note,
        "flag": flag,
    }


def _recent_comps(facts, today):
    return [item for item in facts.get("comps") or [] if item.get("price", 0) >= 10000 and item.get("year", 0) >= today.year - 2]


def _resale(facts, today):
    """The state roll copies the county roll, so both count as one assessment. A sale or nearby sales must back it up."""
    price = facts.get("price")
    justs = [item for item in facts.get("values") or [] if item.get("kind") == "just" and item.get("amount")]
    recent_sales = [
        item
        for item in facts.get("values") or []
        if item.get("kind") == "sale" and item.get("amount", 0) >= 10000 and item.get("year", 0) >= RECENT_SALE_YEAR
    ]
    if not justs:
        return None, _factor("Resale value", 0, "No just value came back from the state roll or the county appraiser.", checked=False)
    amounts = [item["amount"] for item in justs]
    if len(justs) >= 2 and min(amounts) and max(amounts) / min(amounts) > 1.2:
        names = " and ".join(f"{item['source']} ${item['amount']:,.0f}" for item in justs[:2])
        return None, _factor("Resale value", 0, f"The rolls disagree: {names}. Value is not confirmed.")
    agreed = sum(amounts) / len(amounts)
    rolls = " and ".join(dict.fromkeys(item["source"] for item in justs))
    used = ["Tax roll"]
    note = f"{rolls} {'both show' if len(justs) >= 2 else 'shows'} a just value of ${agreed:,.0f}."
    close_sale = next((item for item in recent_sales if abs(item["amount"] - agreed) / agreed <= 0.25), None)
    comps = _recent_comps(facts, today)
    median = sorted(item["price"] for item in comps)[len(comps) // 2] if len(comps) >= 3 else None
    if close_sale:
        used.append(f"{close_sale['year']} sale")
        note += f" A {close_sale['year']} sale at ${close_sale['amount']:,.0f} ({close_sale['source']}) backs it up."
    elif median and 0.65 * agreed <= median <= 1.45 * agreed:
        used.append("Nearby sales")
        note += f" {len(comps)} nearby sales with a median of ${median:,.0f} back it up."
    else:
        note += " No sale or nearby sales confirmed it, so the value is one source."
    points = 0
    flag = ""
    if price:
        ratio = agreed / price
        note += f" That is {ratio:.1f} times the bid."
        if len(used) >= 2 and ratio >= 2:
            points = 2
        elif len(used) >= 2 and ratio >= 1.4:
            points = 1
        elif len(used) == 1 and ratio >= 2:
            points = 1
        if len(used) >= 2 and ratio < 1:
            flag = "The bid is already above the confirmed tax roll value."
    else:
        note += " The auction list has no bid to compare."
    return agreed, _factor("Resale value", points, note, sources_used=used, flag=flag)


def _comparables(facts, agreed, today):
    price = facts.get("price")
    comps = _recent_comps(facts, today)
    if comps and price:
        median = sorted(item["price"] for item in comps)[len(comps) // 2]
        source = comps[0]["source"]
        near_value = not agreed or 0.65 * agreed <= median <= 1.45 * agreed
        note = f"{len(comps)} qualified sales from {source}, median ${median:,.0f}."
        if len(comps) >= 3 and median >= 1.5 * price and near_value:
            points = 2
        elif median >= 1.5 * price and near_value:
            points = 1
        else:
            points = 0
            note += " They do not support the gap over the bid."
        return _factor("Comparables", points, note, sources_used=[source])
    neighbors = facts.get("neighbor_values") or []
    if neighbors and agreed:
        median = sorted(neighbors)[len(neighbors) // 2]
        note = f"{len(neighbors)} other parcels in the zip share this use code. Their median just value is ${median:,.0f}. Those are assessments, not sale prices."
        points = 1 if len(neighbors) >= 5 and 0.75 * agreed <= median <= 1.25 * agreed else 0
        return _factor("Comparables", points, note, sources_used=["Neighbor assessments"])
    return _factor("Comparables", 0, "No recent qualified sales came back for this area.", checked=False)


def sale_cause(kind, case, tax=""):
    """Why this sale exists: taxes, an association lien, a mortgage, or more than one."""
    kind = (kind or "").lower()
    delinquent = (tax or "").startswith("Delinquent")
    if kind == "tax deed":
        return "Taxes"
    court = court_of(case)
    hoa = court == "county"
    mortgage = court == "circuit"
    if hoa and delinquent:
        return "Taxes and HOA lien"
    if mortgage and delinquent:
        return "Taxes and mortgage"
    if hoa:
        return "HOA lien"
    if mortgage:
        return "Mortgage"
    if delinquent:
        return "Taxes"
    return ""


def _amounts(text):
    return [float(item.replace(",", "")) for item in re.findall(r"\$([\d,]+)", text or "")]


def _money_text(number):
    return f"${number:,.0f}"


def market_row(county, kind):
    kind = (kind or "").lower()
    return MARKET.get((county, kind)) or MARKET.get(("", kind))


def _share_at_or_under(row, share):
    """Read the table at one share of the roll, in a straight line between its steps."""
    steps = list(zip(MARKET_STEPS, row[2]))
    if share <= steps[0][0]:
        return steps[0][1] * max(share, 0) / steps[0][0]
    for (low, low_part), (high, high_part) in zip(steps, steps[1:]):
        if share <= high:
            return low_part + (high_part - low_part) * (share - low) / (high - low)
    return steps[-1][1]


def _confirmed(row):
    resale = next((item for item in row.get("factors") or [] if item.get("name") == "Resale value"), {})
    return (resale.get("points") or 0) >= 2


def _recent_sale(row):
    """The sale that confirmed the roll. Older scores keep it only in the factor's note."""
    resale = next((item for item in row.get("factors") or [] if item.get("name") == "Resale value"), {})
    found = re.search(r"A \d{4} sale at \$([\d,]+)", resale.get("note") or "")
    return float(found.group(1).replace(",", "")) if found and (resale.get("points") or 0) >= 2 else 0


def _same_door(report):
    return report if (report or {}).get("match") in ("parcel", "address") else {}


def _row(item, best, worst):
    return {"item": item, "best": round(best), "worst": round(worst)}


def costs(price, meta, estimated_value=None, today=None):
    """What a deal could cost in total, and whether that fits its value. Dollar estimates are the COST_ constants, not quotes."""
    row = (meta or {}).get("diligence") or {}
    kind = ((meta or {}).get("kind") or "").lower()
    tax_deed = kind == "tax deed"
    court = court_of((meta or {}).get("case"))
    paid = meta.get("won_price") or meta.get("max_bid") or price
    if meta.get("won_price"):
        label = "Won at"
    elif meta.get("max_bid"):
        label = "Your ceiling"
    else:
        label = "Final judgment" if meta.get("price_basis") == "final judgment" else "Opening bid"
    if not paid:
        return {}

    loan_text = row.get("loan") or ""
    tax_text = row.get("tax") or ""
    report = _same_door(row.get("reapi"))
    # A blank from one report does not prove there is no loan, so the larger of the two sets the worst case.
    answers = [sum(_amounts(text)) for text in (loan_text, report.get("loan")) if text] or [0]
    low = min(answers)
    loans = [max(answers)] if max(answers) else []
    bills = _amounts(tax_text) + _amounts(report.get("tax"))
    bill = max(bills) if bills else 0
    closing = paid * COST_STAMP_RATE + COST_RECORDING
    rows = [_row(label, paid, paid), _row("Deed stamps and recording", closing, closing)]
    notes = []

    if tax_deed:
        rows.append(_row("Quiet title", *COST_QUIET_TITLE))
        if loans:
            notes.append(f"The {_money_text(sum(loans))} loan is not added. A Florida tax deed clears private mortgages (F.S. 197.552), if the lender got proper notice. Confirm that in the tax deed file.")
        if bill:
            notes.append("The opening bid already includes the back taxes. Only the next year's bill is added.")
    elif loans:
        total = sum(loans)
        if court == "county":
            rows.append(_row("Loan that stays on the property", low, total))
            notes.append("An association foreclosure leaves the mortgage in place. This is the amount on the report, not the payoff.")
        else:
            rows.append(_row("Loan, if the sale does not clear it", 0, total))
            notes.append("A sale on the first mortgage clears the loan. A sale on a junior lien does not. The docket says which. This is the amount on the report, not the payoff.")
    if loans and low != loans[0]:
        notes.append(f"The two loan reports differ: {_money_text(low)} and {_money_text(loans[0])}. The higher one sets the worst case. The county records decide which is right.")
    late = re.match(r"Delinquent since (\d{4})", tax_text)
    if late and bill and not tax_deed:
        years = max(1, (today or date.today()).year - int(late.group(1)))
        owed = bill * years
        rows.append(_row("Back taxes, which a foreclosure does not clear", owed, owed))
    if bill and not late or (bill and tax_deed):
        rows.append(_row("Next year's tax bill", 0, bill))

    best = sum(item["best"] for item in rows)
    worst = sum(item["worst"] for item in rows)
    notes.append("Not counted: repairs, government liens that survive the sale, and any bidding past this price.")
    found = {"rows": rows, "best": best, "worst": worst, "notes": notes, "verdict": "", "tone": "unknown", "why": ""}

    roll = meta.get("roll_value")
    sale = _recent_sale(row)
    value = estimated_value or (min(roll, sale) if roll and sale else roll)
    limit = value * COST_VALUE_SHARE if value else 0
    # Stamps grow with the bid, so the ceiling is solved with them in it.
    fixed = worst - paid - paid * COST_STAMP_RATE
    ceiling = round((limit - fixed) / (1 + COST_STAMP_RATE))
    if value:
        found["value"] = value
        found["value_label"] = "Your value" if estimated_value else "Recent sale" if sale and sale < roll else "Tax roll value"
        resale = next((item for item in row.get("factors") or [] if item.get("name") == "Resale value"), {})
        confirmed = (resale.get("points") or 0) >= 2
        found["value_note"] = "" if estimated_value else "Lower than the tax roll." if found["value_label"] == "Recent sale" else "A recent sale agrees." if confirmed else "No recent sale confirms it."
    flags = row.get("flags") or []
    if not row.get("score"):
        found["verdict"] = "Not scored yet"
    elif not value:
        found.update(verdict="Can't say yet", why="No value to compare against.")
    elif row.get("band") == "thin":
        found.update(verdict="Can't say yet", why="The records do not agree enough on this property.")
    elif not tax_deed and not loan_text and not report.get("loan"):
        found.update(verdict="Can't say yet", why="No loan report, so the worst case is unknown.")
    elif best > limit:
        found.update(verdict="Pass at this price", tone="stop", why=f"Even the best case is over {COST_VALUE_SHARE:.0%} of the value.")
    elif worst > limit:
        found.update(verdict="Only if the title clears", tone="warn", why=f"The best case fits. The worst case is over {COST_VALUE_SHARE:.0%} of the value.")
    elif flags:
        found.update(verdict="Numbers fit, danger open", tone="warn", why=flags[0])
    else:
        found.update(verdict="Worth a title check", tone="good", why=f"At this price, the worst case is under {COST_VALUE_SHARE:.0%} of the value.")
    # A ceiling needs a value someone can stand behind. Past buyers show how often it would have won.
    land_heavy = (row.get("land_share") or 0) >= LAND_HEAVY
    if land_heavy:
        notes.insert(0, "Almost all of the tax roll value is land. Check what stands there before trusting the value.")
    if found["tone"] in ("good", "warn") and found["verdict"] != "Only if the title clears" and not land_heavy and (estimated_value or _confirmed(row)) and ceiling > 0:
        found["ceiling"] = ceiling
    market = market_row(meta.get("county"), kind)
    if market and roll:
        note = f"Outside buyers typically paid {market[1]:.0%} of the tax roll in sales like this, about {_money_text(round(roll * market[1], -3))} here ({market[0]} sales)."
        if found.get("ceiling"):
            note += f" About {_share_at_or_under(market, found['ceiling'] / roll):.0%} paid at or under this ceiling."
        found["market_note"] = note
    return found


def title_flag(kind, case, tax=""):
    cause = sale_cause(kind, case, tax)
    if cause == "Taxes and HOA lien":
        return "HOA lien and delinquent taxes. The mortgage stays on the property."
    if cause == "HOA lien":
        return "Likely an HOA foreclosure: the mortgage stays on the property."
    return ""


def _title(facts):
    kind = (facts.get("kind") or "").lower()
    case = facts.get("case") or "unknown case"
    tax = facts.get("tax") or ""
    if kind == "tax deed":
        return _factor(
            "Title",
            1,
            f"Tax deed, case {case}. The cause is unpaid taxes. A tax deed clears mortgages and most private liens, but government liens can survive. The docket was not read.",
            sources_used=["Auction list"],
        )
    court = court_of(facts.get("case"))
    if court == "county":
        return _factor(
            "Title",
            0,
            f"Foreclosure in county court, case {case}. The cause is an HOA or condo lien, and the first mortgage survives the sale.",
            sources_used=["Auction list"],
            flag=title_flag(kind, case, tax),
        )
    if court == "circuit":
        return _factor(
            "Title",
            1,
            f"Foreclosure in circuit court, case {case}. The cause is the mortgage. Read the docket to confirm who sued.",
            sources_used=["Auction list"],
        )
    return _factor("Title", 0, f"The list shows case {case}, and the court could not be read from it.", checked=False)


def _code(facts):
    code = facts.get("code")
    if not code or not code.get("sources"):
        return _factor("Code and building", 0, "No code enforcement source covers this county yet.", checked=False)
    used = code["sources"]
    if code.get("liens") or code.get("unsafe"):
        found = "; ".join((code.get("liens") or []) + (code.get("unsafe") or []))
        return _factor(
            "Code and building",
            0,
            f"Open record found: {found}.",
            sources_used=used,
            flag="Open code lien or unsafe structure on file.",
        )
    if code.get("open"):
        return _factor("Code and building", 0, f"Open case: {'; '.join(code['open'])}.", sources_used=used)
    points = 2 if len(used) >= 2 else 1
    return _factor("Code and building", points, f"No open cases or unpaid liens in {', '.join(used)}.", sources_used=used)


def _flood(facts):
    flood = facts.get("flood")
    if not flood:
        return _factor("Flood", 0, "FEMA's flood map did not answer for this point.", checked=False)
    zone = flood.get("zone") or ""
    detail = flood.get("subtype") or ""
    label = f"FEMA zone {zone}{f' ({detail.lower()})' if detail else ''}."
    if zone.startswith("V"):
        return _factor("Flood", 0, label + " Coastal high-hazard area.", sources_used=["FEMA"], flag="Coastal flood zone: insurance and rebuild rules are strict.")
    if flood.get("special"):
        return _factor("Flood", 0, label + " Flood insurance is required with a mortgage.", sources_used=["FEMA"])
    if "0.2" in detail:
        return _factor("Flood", 1, label, sources_used=["FEMA"])
    return _factor("Flood", 2, label, sources_used=["FEMA"])


def _occupancy(facts):
    homestead = facts.get("homestead") or []
    claimed = [item for item in homestead if item.get("yes")]
    clear = [item for item in homestead if item.get("yes") is False]
    if claimed or facts.get("mail_at_site") is True:
        who = claimed[0]["source"] if claimed else "The county roll"
        return _factor(
            "Occupancy",
            0,
            f"{who} shows a homestead claim or owner mail at the property. That is a residence signal, not a vacancy check.",
            sources_used=[who],
        )
    if clear and facts.get("mail_at_site") is False:
        return _factor(
            "Occupancy",
            2,
            "No homestead on the roll, and the owner's mail goes to another address. Likely not owner-occupied, though a tenant may live there.",
            sources_used=["Tax roll", "Owner mailing address"],
        )
    if clear:
        return _factor(
            "Occupancy",
            1,
            "No homestead on the roll. The state roll copies the county, so that is one signal, and nothing else confirmed it.",
            sources_used=["Tax roll"],
        )
    return _factor("Occupancy", 0, "Neither roll said whether a homestead exemption is on this parcel.", checked=False)


def _liens(facts=None):
    """ATTOM answers the open loan and the tax bill. It does not read judgments or the court docket."""
    facts = facts or {}
    loan = (facts.get("loan") or "").strip()
    tax = (facts.get("tax") or "").strip()
    if not loan and not tax:
        return _factor(
            "Other liens",
            0,
            "No loan or tax report yet. Check the clerk and the tax collector in the Title checked step.",
            checked=False,
        )
    kind = (facts.get("kind") or "").lower()
    note = ". ".join(part for part in (loan, tax) if part) + ". Judgments and association liens are still unread."
    flag = ""
    points = 1
    if kind != "tax deed" and tax.startswith("Delinquent") and court_of(facts.get("case")) != "county":
        points = 0
        flag = "Delinquent taxes sit on top of the mortgage foreclosure."
    elif kind != "tax deed" and "plus $" in loan:
        points = 0
        flag = "A second loan is on the report."
    return _factor("Other liens", points, note, checked=True, sources_used=["ATTOM"], flag=flag)


def identity(facts):
    """The listing, the state roll, and the Census geocoder should all put the same house number on this parcel."""
    listing = house_number(facts.get("address"))
    others = [(name, house_number(value)) for name, value in (facts.get("addresses") or {}).items() if house_number(value)]
    if not listing or not others:
        return {"ok": True, "note": ""}
    wrong = [name for name, number in others if number != listing]
    if wrong:
        return {"ok": False, "note": f"The listing says {listing}, but {' and '.join(wrong)} show a different house number. Check the parcel."}
    return {"ok": True, "note": f"Address confirmed by {' and '.join(name for name, _ in others)}."}


def grade(factors, ident=None):
    """Score counts only checked factors. The color also needs enough of them checked to be trusted."""
    ident = ident or {"ok": True, "note": ""}
    checked = [item for item in factors if item.get("checked")]
    earned = sum(item["points"] for item in checked)
    possible = 2 * len(checked)
    score = round(1 + 9 * earned / possible) if possible else 0
    flags = [item["flag"] for item in factors if item.get("flag")]
    resale = next((item for item in factors if item["name"] == "Resale value"), {})
    liens = next((item for item in factors if item["name"] == "Other liens"), {})
    if not ident["ok"]:
        band, reason = "thin", ident["note"]
    elif len(resale.get("sources") or []) < 2:
        band, reason = "thin", "Value is not confirmed by two sources yet."
    elif len(checked) < 4:
        band, reason = "thin", f"Only {len(checked)} of {len(factors)} checks answered."
    elif flags:
        band, reason = "risky", flags[0]
    elif score <= 3:
        band, reason = "risky", "Most checks came back weak."
    elif score <= 5:
        band, reason = "fair", "Some checks are weak."
    elif score >= 8 and "Your lien search" in (liens.get("sources") or []):
        band, reason = "excellent", "Value confirmed, checks strong, liens cleared by you."
    elif score >= 8:
        band, reason = "good", "Strong on paper. Clear the liens in Title checked to reach Excellent."
    else:
        band, reason = "good", "Most checks are strong."
    return {
        "version": VERSION,
        "score": max(score, 1) if possible else 0,
        "band": band,
        "band_label": BANDS[band],
        "reason": reason,
        "checked": len(checked),
        "flags": flags,
        "identity": ident,
        "factors": factors,
    }


def fold_attom(row, kind, case=""):
    """Name the cause, and count the stored ATTOM lines. Does not call ATTOM again."""
    tax = row.get("tax") or ""
    cause = sale_cause(kind, case, tax)
    if not row.get("factors"):
        out = dict(row)
        if cause:
            out["cause"] = cause
        return out
    factors = []
    for item in row.get("factors") or []:
        item = dict(item)
        if item.get("name") == "Title" and "Your docket check" not in (item.get("sources") or []):
            item["flag"] = title_flag(kind, case, tax)
        if item.get("name") == "Other liens":
            if "Your lien search" in (item.get("sources") or []):
                factors.append(item)
            continue
        factors.append(item)
    if not any(item.get("name") == "Other liens" for item in factors):
        factors.append(_liens({"kind": kind, "case": case, "loan": row.get("loan"), "tax": tax}))
    graded = grade(factors, row.get("identity"))
    for key in ("point", "house", "loan", "tax"):
        if row.get(key):
            graded[key] = row[key]
    if cause:
        graded["cause"] = cause
    if row.get("reapi"):
        graded["reapi"] = row["reapi"]
    return graded


def apply_review(row, review, today=None):
    """Your own docket and lien check counts as a source the robots can't reach."""
    when = (today or date.today()).isoformat()
    factors = []
    for item in row.get("factors") or []:
        item = dict(item)
        if item["name"] == "Title" and review.get("title"):
            item.update(points=2, checked=True, flag="", note=f"You read the docket on {when}: the sale clears the mortgage.")
            item["sources"] = list(dict.fromkeys((item.get("sources") or []) + ["Your docket check"]))
        if item["name"] == "Other liens" and review.get("liens"):
            item.update(points=2, checked=True, flag="", note=f"You searched liens and taxes owed on {when}: nothing survives the sale.")
            item["sources"] = ["Your lien search"]
        factors.append(item)
    graded = grade(factors, row.get("identity"))
    if row.get("point"):
        graded["point"] = row["point"]
    if row.get("house"):
        graded["house"] = row["house"]
    if row.get("loan"):
        graded["loan"] = row["loan"]
    if row.get("tax"):
        graded["tax"] = row["tax"]
    if row.get("cause"):
        graded["cause"] = row["cause"]
    if row.get("reapi"):
        graded["reapi"] = row["reapi"]
    return graded


def score_facts(facts, today=None):
    today = today or date.today()
    agreed, resale = _resale(facts, today)
    factors = [
        resale,
        _comparables(facts, agreed, today),
        _title(facts),
        _code(facts),
        _flood(facts),
        _occupancy(facts),
        _liens(facts),
    ]
    diligence = grade(factors, identity(facts))
    if facts.get("point"):
        diligence["point"] = [round(facts["point"][0], 6), round(facts["point"][1], 6)]
    if facts.get("house"):
        diligence["house"] = facts["house"]
    if facts.get("land_share") is not None:
        diligence["land_share"] = round(facts["land_share"], 3)
    if facts.get("loan"):
        diligence["loan"] = facts["loan"]
    if facts.get("tax"):
        diligence["tax"] = facts["tax"]
    cause = sale_cause(facts.get("kind"), facts.get("case"), facts.get("tax") or "")
    if cause:
        diligence["cause"] = cause
    return {"just_value": round(agreed) if agreed else None, "diligence": diligence}


def street_view_link(point):
    """Google's own Street View page for a (lon, lat) point. It needs no key."""
    lon, lat = point
    return f"https://www.google.com/maps/@?api=1&map_action=pano&viewpoint={lat:.6f},{lon:.6f}"


def street_photo_url(point, width=640, height=400):
    """A Street View photo, loaded by the viewer's browser and never stored. Empty without GOOGLE_MAPS_KEY."""
    key = os.environ.get("GOOGLE_MAPS_KEY", "").strip()
    if not key:
        return ""
    lon, lat = point
    # shortcut: the key sits in the image URL, so restrict it to this one API, cap its quota, and proxy it before a second user arrives
    query = urllib.parse.urlencode({"size": f"{width}x{height}", "location": f"{lat:.6f},{lon:.6f}", "fov": 80, "return_error_code": "true", "key": key})
    return f"https://maps.googleapis.com/maps/api/streetview?{query}"


def aerial_url(point, width=640, height=400):
    """Esri World Imagery around a (lon, lat) point, about 110 m across."""
    lon, lat = point
    half_lat = 0.0005
    half_lon = half_lat * width / height / math.cos(math.radians(lat))
    box = f"{lon - half_lon:.6f},{lat - half_lat:.6f},{lon + half_lon:.6f},{lat + half_lat:.6f}"
    return (
        "https://services.arcgisonline.com/arcgis/rest/services/World_Imagery/MapServer/export"
        f"?bbox={box}&bboxSR=4326&imageSR=3857&size={width},{height}&format=jpg&f=image"
    )


def _get(url, tries=1):
    request = urllib.request.Request(url, headers={"User-Agent": sources.UA, "Accept": "application/json,text/html"})
    for attempt in range(tries):
        try:
            with urllib.request.urlopen(request, timeout=18) as response:
                return response.read().decode("utf-8", "replace")
        except Exception:
            if attempt == tries - 1:
                raise


def _json(raw):
    start = raw.find("{")
    return json.loads(raw[start:])


def _query(base, where, fields, **extra):
    params = {"where": where, "outFields": fields, "returnGeometry": "false", "f": "json", **extra}
    payload = _json(_get(f"{base}?{urllib.parse.urlencode(params)}"))
    if "error" in payload:
        raise ValueError(payload["error"].get("message") or "query failed")
    return [item.get("attributes") or {} for item in payload.get("features") or []], payload


def _fdor(parcel):
    rows, payload = _query(
        FDOR,
        f"PARCEL_ID='{parcel}'",
        "JV,JV_HMSTD,SALE_PRC1,SALE_YR1,PHY_ADDR1,LND_VAL",
        returnGeometry="true",
        returnCentroid="true",
        outSR="4326",
    )
    if not rows:
        return None
    row = dict(rows[0])
    centroid = (payload["features"][0].get("centroid") or {})
    if centroid.get("x") and centroid.get("y"):
        row["point"] = (centroid["x"], centroid["y"])
    return row


def _census(address, location):
    place = re.sub(r"\bFL-?\s*", "FL ", location or "").strip()
    query = urllib.parse.urlencode({"address": f"{address}, {place}", "benchmark": "Public_AR_Current", "format": "json"})
    matches = (_json(_get(f"{CENSUS}?{query}")).get("result") or {}).get("addressMatches") or []
    if not matches:
        return None
    best = matches[0]
    return {"address": best.get("matchedAddress") or "", "point": (best["coordinates"]["x"], best["coordinates"]["y"])}


def _fema(point):
    params = {
        "geometry": f"{point[0]},{point[1]}",
        "geometryType": "esriGeometryPoint",
        "inSR": "4326",
        "spatialRel": "esriSpatialRelIntersects",
        "outFields": "FLD_ZONE,ZONE_SUBTY,SFHA_TF",
        "returnGeometry": "false",
        "f": "json",
    }
    features = _json(_get(f"{FEMA}?{urllib.parse.urlencode(params)}", tries=2)).get("features") or []
    if not features:
        return None
    row = features[0]["attributes"]
    return {"zone": (row.get("FLD_ZONE") or "").strip(), "subtype": (row.get("ZONE_SUBTY") or "").strip(), "special": row.get("SFHA_TF") == "T"}


def _miami_code(folio):
    code = {"sources": [], "liens": [], "unsafe": [], "open": []}
    where = f"FOLIO='{folio}'"
    try:
        rows, _ = _query(f"{MIAMI_SERVICES}/CodeComplianceViolation_Open_View/FeatureServer/0/query", where, "CASE_NUM,PROBLEM_DESC")
        code["sources"].append("Miami-Dade open code cases")
        code["open"] += [f"{(row.get('PROBLEM_DESC') or 'code case').strip()} ({(row.get('CASE_NUM') or '').strip()})" for row in rows]
    except Exception:
        pass
    try:
        rows, _ = _query(f"{MIAMI_SERVICES}/CodeComplianceViolation_Lien_View/FeatureServer/0/query", where, "CASE_NUM,PROBLEM_DESC,LAST_ACTV")
        code["sources"].append("Miami-Dade code liens")
        code["liens"] += [
            f"code lien for {(row.get('PROBLEM_DESC') or '').strip().lower()} ({(row.get('CASE_NUM') or '').strip()})"
            for row in rows
            if "SATISF" not in (row.get("LAST_ACTV") or "").upper()
        ]
    except Exception:
        pass
    try:
        rows, _ = _query(f"{MIAMI_SERVICES}/Open_Building_Violations/FeatureServer/0/query", where, "CASE_NUM,CASE_TYPE,CLOSED_DATE")
        code["sources"].append("Miami-Dade building violations")
        for row in rows:
            if row.get("CLOSED_DATE"):
                continue
            label = f"{(row.get('CASE_TYPE') or 'building case').strip()} ({(row.get('CASE_NUM') or '').strip()})"
            (code["unsafe"] if "UNSAFE" in label.upper() else code["open"]).append(label)
    except Exception:
        pass
    return code


def _lee_code(strap):
    rows, _ = _query(LEE_NUISANCE, f"parcel_number='{strap}'", "record_status,balance_due")
    code = {"sources": ["Lee nuisance cases"], "liens": [], "unsafe": [], "open": []}
    for row in rows:
        status = (row.get("record_status") or "").strip()
        if status.startswith("Closed"):
            continue
        if "Lien" in status or (row.get("balance_due") or 0) > 0:
            code["liens"].append(f"Lee nuisance case, {status.lower()}, ${row.get('balance_due') or 0:,.0f} due")
        else:
            code["open"].append(f"Lee nuisance case, {status.lower()}")
    return code


def lookup_house(county, parcel):
    """The appraiser's description of the house, without rescoring the deal."""
    parcel = compact_parcel(parcel)
    if not parcel or parcel == "PROPERTYAPPRAISER":
        return ""
    facts = {"values": [], "homestead": [], "comps": []}
    try:
        _county(county, parcel, facts)
    except Exception:
        pass
    return facts.get("house") or ""


def research(deal):
    """Every source is tried on its own. One failing leaves the rest."""
    meta = deal.get("metadata") or {}
    if isinstance(meta, str):
        try:
            meta = json.loads(meta or "{}")
        except json.JSONDecodeError:
            meta = {}
    parcel = compact_parcel(meta.get("parcel"))
    county = meta.get("county") or ""
    facts = {
        "price": deal.get("price"),
        "address": deal.get("address") or "",
        "kind": meta.get("kind") or "",
        "case": meta.get("case") or "",
        "values": [],
        "homestead": [],
        "comps": [],
        "neighbor_values": [],
        "mail_at_site": None,
        "addresses": {},
        "code": None,
        "flood": None,
    }
    point = None
    if parcel:
        try:
            row = _fdor(parcel)
        except Exception:
            row = None
        if row:
            if row.get("JV"):
                facts["values"].append({"source": "Florida DOR roll", "kind": "just", "amount": row["JV"]})
            if row.get("JV_HMSTD") is not None:
                facts["homestead"].append({"source": "Florida DOR roll", "yes": row["JV_HMSTD"] > 0})
            if row.get("SALE_PRC1") and row.get("SALE_YR1"):
                facts["values"].append(
                    {"source": "Florida DOR roll", "kind": "sale", "amount": row["SALE_PRC1"], "year": int(row["SALE_YR1"])}
                )
            if row.get("JV") and row.get("LND_VAL") is not None:
                facts["land_share"] = row["LND_VAL"] / row["JV"]
            if row.get("PHY_ADDR1"):
                facts["addresses"]["the state roll"] = row["PHY_ADDR1"]
            point = row.get("point")
        try:
            _county(county, parcel, facts)
        except Exception:
            pass
        try:
            if county == "Miami-Dade":
                facts["code"] = _miami_code(parcel)
            elif county == "Lee":
                facts["code"] = _lee_code(parcel)
        except Exception:
            pass
    try:
        found = _census(deal.get("address") or "", deal.get("location") or "")
    except Exception:
        found = None
    if found:
        facts["addresses"]["the Census geocoder"] = found["address"]
        point = point or found["point"]
    if point:
        facts["point"] = point
        try:
            facts["flood"] = _fema(point)
        except Exception:
            pass
    facts.update(attom_lines(deal.get("address") or "", deal.get("location") or ""))
    return score_facts(facts)


def _dollars(value):
    try:
        number = float(value)
    except (TypeError, ValueError):
        return ""
    if number <= 0:
        return ""
    return f"${number:,.0f}"


def _year(value):
    digits = re.sub(r"\D", "", str(value or ""))[:4]
    return digits if len(digits) == 4 else ""


def parse_attom(payload):
    """Open loan and delinquent tax from one Expanded Profile. This is not a full lien search."""
    props = (payload or {}).get("property") or []
    if not props:
        return {}
    assessment = props[0].get("assessment") or {}
    mortgage = (assessment.get("mortgage") or {}).get("FirstConcurrent") or {}
    lender = " ".join(part for part in (mortgage.get("LenderFirstName"), mortgage.get("lenderLastName")) if part).strip()
    amount = _dollars(mortgage.get("amount"))
    when = _year(mortgage.get("date"))
    if amount:
        loan = " · ".join(part for part in (lender, amount, when) if part)
        second = _dollars(((assessment.get("mortgage") or {}).get("SecondConcurrent") or {}).get("amount"))
        if second:
            loan += f", plus {second}"
    else:
        loan = "No open loan on the report"
    tax_block = assessment.get("tax") or {}
    bill = _dollars(tax_block.get("taxAmt"))
    overdue = _year(assessment.get("delinquentyear"))
    if overdue:
        tax = f"Delinquent since {overdue}"
        if bill:
            tax += f", bill {bill}"
    elif bill:
        tax_year = _year(tax_block.get("taxYear"))
        tax = f"Tax bill {bill}" + (f" for {tax_year}" if tax_year else "")
    else:
        tax = ""
    found = {"loan": loan}
    if tax:
        found["tax"] = tax
    return found


def attom_lines(address, location):
    key = os.environ.get("ATTOM_API_KEY", "").strip()
    address = (address or "").strip()
    if not key or not address:
        return {}
    place = (location or "FL").replace("FL-", "FL ")
    query = urllib.parse.urlencode({"address1": address, "address2": place})
    request = urllib.request.Request(
        f"https://api.gateway.attomdata.com/propertyapi/v1.0.0/property/expandedprofile?{query}",
        headers={"Accept": "application/json", "apikey": key},
    )
    try:
        with urllib.request.urlopen(request, timeout=20) as response:
            payload = json.loads(response.read().decode())
    except Exception:
        return {}
    return parse_attom(payload)


def _extra_unit(listing, found):
    return bool(_UNIT.search(found or "")) and not _UNIT.search(listing or "")


def _loan_open(text):
    if not (text or "").strip():
        return None
    return not text.startswith("No open loan")


def _tax_late(text):
    if not (text or "").strip():
        return None
    return text.startswith("Delinquent")


def parse_reapi(payload, address, parcel=""):
    """Loan and tax from one Property Detail. A unit the sale list did not name is not this door."""
    data = (payload or {}).get("data") or {}
    if isinstance(data, list):
        data = data[0] if data else {}
    if not data:
        return {"match": "miss"}
    info = data.get("propertyInfo") or {}
    addr = info.get("address") or {}
    label = addr.get("label") if isinstance(addr, dict) else ""
    loans = []
    for item in data.get("currentMortgages") or []:
        if not isinstance(item, dict):
            continue
        amount = _dollars(item.get("amount"))
        lender = (item.get("lenderName") or "").strip()
        when = _year(item.get("documentDate") or item.get("recordingDate"))
        line = " · ".join(part for part in (lender, amount, when) if part)
        if line:
            loans.append((line, amount))
    if loans:
        loan = loans[0][0]
        extra = [amount for _, amount in loans[1:] if amount]
        if extra:
            loan += ", plus " + extra[0]
    elif data.get("freeClear") or data.get("openMortgageBalance") in (0, "0"):
        loan = "No open loan on the report"
    else:
        loan = _dollars(data.get("openMortgageBalance"))
    tax_block = data.get("taxInfo") or {}
    bill = _dollars(tax_block.get("taxAmount"))
    year = _year(tax_block.get("year"))
    if data.get("taxLien"):
        tax = "Delinquent" + (f", bill {bill}" if bill else "")
    elif bill:
        tax = f"Tax bill {bill}" + (f" for {year}" if year else "")
    else:
        tax = ""
    apn = ((data.get("lotInfo") or {}).get("apnUnformatted") or (data.get("lotInfo") or {}).get("apn") or "")
    ours = compact_parcel(parcel)
    if ours and ours != "PROPERTYAPPRAISER" and compact_parcel(apn) == ours:
        match = "parcel"
    else:
        left, right = house_number(address), house_number(label)
        if left and right and left == right:
            match = "unit" if _extra_unit(address, label) else "address"
        elif label:
            match = "other"
        else:
            match = "miss"
    found = {"match": match, "address": label or ""}
    if loan:
        found["loan"] = loan
    if tax:
        found["tax"] = tax
    return found


def reapi_sentence(report, listing="", loan="", tax=""):
    """The card line. The score still uses the ATTOM loan and tax."""
    if not report:
        return ""
    if report.get("match") == "miss":
        return "No record for this address."
    body = ". ".join(part for part in (report.get("loan"), report.get("tax")) if part) or "No loan or tax on this report."
    found = report.get("address") or ""
    if report.get("match") in ("unit", "other"):
        return f"Not this door: {found or 'a different property'}. {body}"
    if _extra_unit(listing, found):
        body = f"Parcel record is {found}. {body}"
    open_loan = _loan_open(loan), _loan_open(report.get("loan") or "")
    amounts = sum(_amounts(loan)), sum(_amounts(report.get("loan")))
    # This report only marks delinquency when it holds a tax lien, so its silence is not a no.
    late = _tax_late(tax) is False and _tax_late(report.get("tax") or "") is True
    if (None not in open_loan and open_loan[0] != open_loan[1]) or late or (all(amounts) and max(amounts) > min(amounts) * LOAN_GAP):
        body += " Disagrees with the loan report."
    return body


def _mailing(address, location):
    house, street, city, zip_code = _parts(address, location)
    line = " ".join(part for part in (house, street) if part)
    state_zip = " ".join(part for part in ("FL", zip_code) if part)
    place = ", ".join(part for part in (city, state_zip) if part)
    return f"{line}, {place}" if place else line


def _parts(address, location):
    words = []
    for word in (address or "").split():
        words.append(word.upper() if word.upper() in _DIRECTIONS else (word.title() if word.isupper() else word))
    house = words[0] if words and words[0][:1].isdigit() else ""
    street = " ".join(words[1:] if house else words)
    zip_code = ""
    found = re.search(r"\b(\d{5})\b", location or "")
    if found:
        zip_code = found.group(1)
    city = re.split(r",|\bFL\b", location or "", maxsplit=1)[0].strip(" -")
    if city.isupper():
        city = city.title()
    return house, street, city, zip_code


def _reapi_post(body):
    key = os.environ.get("REALESTATE_API_KEY", "").strip()
    if not key:
        return None
    request = urllib.request.Request(
        "https://api.realestateapi.com/v2/PropertyDetail",
        data=json.dumps(body).encode(),
        headers={"x-api-key": key, "Content-Type": "application/json", "Accept": "application/json"},
        method="POST",
    )
    for attempt in range(2):
        try:
            with urllib.request.urlopen(request, timeout=25) as response:
                return json.loads(response.read().decode())
        except urllib.error.HTTPError as error:
            if error.code == 404:
                return {"data": {}}
            if error.code == 429 and attempt == 0:
                time.sleep(2)
                continue
            raise
    return {"data": {}}


def reapi_report(address, location, parcel="", county=""):
    """One Property Detail. A second credit is spent only when the street hit a different door and a parcel id exists."""
    # shortcut: comps, skip trace, and involuntary liens are separate prices, leave them off
    house, street, city, zip_code = _parts(address, location)
    if house and street and (city or zip_code):
        body = {"house": house, "street": street, "state": "FL", "exact_match": True}
        if city:
            body["city"] = city
        if zip_code:
            body["zip"] = zip_code
    else:
        body = {"address": _mailing(address, location), "exact_match": True}
    payload = _reapi_post(body)
    if payload is None:
        return {}
    report = parse_reapi(payload, address, parcel)
    fips = FIPS.get(county or "")
    ours = compact_parcel(parcel)
    if report.get("match") not in ("unit", "other", "miss") or not fips or not ours or ours == "PROPERTYAPPRAISER":
        return report
    second = _reapi_post({"apn": ours, "fips": fips, "exact_match": True})
    other = parse_reapi(second, address, parcel)
    if other.get("match") in ("parcel", "address"):
        return other
    if report.get("match") == "miss":
        fuzzy = dict(body)
        fuzzy["exact_match"] = False
        third = parse_reapi(_reapi_post(fuzzy), address, parcel)
        if third.get("match") != "miss":
            return third
    return report if report.get("match") != "miss" else other


def _county(county, parcel, facts):
    if county == "Broward":
        record = parse_broward_record(_get(f"https://bcpa.net/RecInfo.asp?URL_Folio={parcel}"))
        if record["just"]:
            facts["values"].append({"source": "Broward appraiser", "kind": "just", "amount": record["just"]})
        if record.get("house"):
            facts["house"] = record["house"]
        facts["homestead"].append({"source": "Broward appraiser", "yes": record["homestead"]})
        for sale in record["sales"]:
            facts["values"].append({"source": "Broward appraiser", "kind": "sale", "amount": sale["price"], "year": sale["year"]})
        if len(parcel) >= 8:
            facts["comps"] = parse_broward_comps(
                _get(f"https://bcpa.net/RecSubSaleSearch.asp?URL_Sort=Date&URL_SubDiv={parcel[:8]}")
            )
    elif county == "Lee":
        rows, _ = _query(
            LEE,
            f"STRAP='{parcel}'",
            "STRAP,JUST,HSTDAMOUNT,DORCODE,SITEZIP,S_1DATE,S_1AMOUNT,S_1TC,BEDROOMS,BATHROOMS,HEATEDAREA,MINBUILTY,POOL,GARAGE",
            resultRecordCount="1",
        )
        if not rows:
            return
        row = rows[0]
        house = format_house(
            beds=row.get("BEDROOMS"),
            baths=row.get("BATHROOMS"),
            sqft=row.get("HEATEDAREA"),
            year=row.get("MINBUILTY"),
            pool=(row.get("POOL") or "") == "Y",
            garage=(row.get("GARAGE") or "") == "Y",
        )
        if house:
            facts["house"] = house
        if row.get("JUST"):
            facts["values"].append({"source": "Lee appraiser", "kind": "just", "amount": row["JUST"]})
        facts["homestead"].append({"source": "Lee appraiser", "yes": (row.get("HSTDAMOUNT") or 0) > 0})
        if row.get("S_1TC") == "01" and (row.get("S_1AMOUNT") or 0) >= 10000 and row.get("S_1DATE"):
            year = date.fromtimestamp(row["S_1DATE"] / 1000).year
            facts["values"].append({"source": "Lee appraiser", "kind": "sale", "amount": row["S_1AMOUNT"], "year": year})
        zip_code = row.get("SITEZIP") or ""
        dor = row.get("DORCODE") or ""
        # Transaction code 01 is a qualified, arm's-length sale on the Florida roll.
        if zip_code and dor:
            since = f"{date.today().year - 2}-01-01"
            sold, _ = _query(
                LEE,
                f"SITEZIP='{zip_code}' AND DORCODE='{dor}' AND STRAP<>'{parcel}' AND S_1TC='01' AND S_1AMOUNT>10000 AND S_1DATE > DATE '{since}'",
                "S_1DATE,S_1AMOUNT",
                resultRecordCount="8",
            )
            facts["comps"] = [
                {"price": item["S_1AMOUNT"], "year": date.fromtimestamp(item["S_1DATE"] / 1000).year, "source": "Lee qualified sales in the zip"}
                for item in sold
                if item.get("S_1AMOUNT") and item.get("S_1DATE")
            ]
        if zip_code and dor and not facts["comps"]:
            nearby, _ = _query(
                LEE,
                f"SITEZIP='{zip_code}' AND DORCODE='{dor}' AND STRAP<>'{parcel}' AND JUST>0",
                "JUST",
                resultRecordCount="8",
            )
            facts["neighbor_values"] = [item["JUST"] for item in nearby if item.get("JUST")]
    elif county == "Miami-Dade":
        rows, _ = _query(
            MIAMI,
            f"FOLIO='{parcel}'",
            "ASSESSED_VAL_CUR,PRICE_1,DOS_1,DOR_CODE_CUR,TRUE_SITE_ZIP_CODE,TRUE_SITE_ADDR,TRUE_MAILING_ADDR1,BEDROOM_COUNT,BATHROOM_COUNT,HALF_BATHROOM_COUNT,YEAR_BUILT,BUILDING_HEATED_AREA",
            resultRecordCount="1",
        )
        if not rows:
            return
        row = rows[0]
        baths = row.get("BATHROOM_COUNT") or 0
        half = row.get("HALF_BATHROOM_COUNT") or 0
        house = format_house(
            beds=row.get("BEDROOM_COUNT"),
            baths=(baths + 0.5 * half) or None,
            sqft=row.get("BUILDING_HEATED_AREA"),
            year=row.get("YEAR_BUILT"),
        )
        if house:
            facts["house"] = house
        dos = str(row.get("DOS_1") or "")
        price = row.get("PRICE_1") or 0
        if price >= 10000 and len(dos) >= 4:
            facts["values"].append(
                {"source": "Miami-Dade appraiser", "kind": "sale", "amount": price, "year": int(dos[:4])}
            )
        site = row.get("TRUE_SITE_ADDR") or ""
        mail = row.get("TRUE_MAILING_ADDR1") or ""
        if site:
            facts["addresses"]["the county appraiser"] = site
        if site and mail:
            facts["mail_at_site"] = compact_parcel(site) in compact_parcel(mail)
        zip_code = (row.get("TRUE_SITE_ZIP_CODE") or "")[:5]
        dor = row.get("DOR_CODE_CUR") or ""
        if zip_code and dor:
            nearby, _ = _query(
                MIAMI,
                f"TRUE_SITE_ZIP_CODE LIKE '{zip_code}%' AND DOR_CODE_CUR='{dor}' AND PRICE_1>10000 AND DOS_1>='20241001' AND FOLIO<>'{parcel}'",
                "PRICE_1,DOS_1",
                resultRecordCount="8",
            )
            for attrs in nearby:
                when = str(attrs.get("DOS_1") or "")
                if attrs.get("PRICE_1") and len(when) >= 4:
                    facts["comps"].append(
                        {"price": attrs["PRICE_1"], "year": int(when[:4]), "source": "Miami-Dade recorded sales in the zip"}
                    )
