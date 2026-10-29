"""Local deal list. Run: python3 app.py"""

import html
import os
from contextlib import closing
from datetime import datetime
from http.server import BaseHTTPRequestHandler, HTTPServer
from pathlib import Path
from urllib.parse import parse_qs, quote, urlparse

import deals

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


def render_page(rows, filters, error="", draft=None):
    draft = draft or {}
    current_query = "/" + _query(filters)
    filter_status = filters.get("status", "")
    status_options = _option("", filter_status, "Any status") + "".join(
        _option(status, filter_status) for status in deals.STATUSES
    )
    add_status = draft.get("status") or "New"

    def field(name, label, value="", kind="text"):
        return (
            f'<label>{html.escape(label)}'
            f'<input name="{name}" value="{html.escape(value)}" inputmode="{"decimal" if kind == "money" else "text"}">'
            f"</label>"
        )

    body_rows = []
    for deal in rows:
        href = safe_href(deal.get("link"))
        address = html.escape(deal["address"])
        if href:
            address = f'<a href="{html.escape(href, quote=True)}">{address}</a>'
        notes = deal.get("notes") or ""
        notes_html = f'<span class="notes">{html.escape(notes)}</span>' if notes else ""
        spread = deal.get("spread")
        spread_class = "spread"
        if spread is not None and spread < 0:
            spread_class += " loss"
        elif spread is not None and spread > 0:
            spread_class += " gain"
        body_rows.append(
            "<tr>"
            f"<td>{address}{notes_html}</td>"
            f"<td>{html.escape(deal.get('location') or '')}</td>"
            f'<td class="num">{money(deal.get("price"))}</td>'
            f'<td class="num">{money(deal.get("estimated_value"))}</td>'
            f'<td class="num {spread_class}">{money(spread)}</td>'
            "<td><form method=\"post\" action=\"/deals/status\" class=\"status-form\">"
            f'<input type="hidden" name="id" value="{int(deal["id"])}">'
            f'<input type="hidden" name="next" value="{html.escape(current_query or "/", quote=True)}">'
            f'{_status_select("status", deal["status"])}'
            '<button type="submit">Move</button></form></td>'
            f"<td>{html.escape(deal.get('source') or '')}</td>"
            f"<td>{html.escape(format_updated(deal.get('updated_at') or ''))}</td>"
            "</tr>"
        )

    if rows:
        table = (
            '<div class="table-wrap"><table>'
            "<thead><tr>"
            "<th>Address</th><th>Location</th>"
            '<th class="num">Asking price</th><th class="num">Estimated value</th><th class="num">Spread</th>'
            "<th>Status</th><th>Source</th><th>Updated</th>"
            "</tr></thead><tbody>"
            + "".join(body_rows)
            + "</tbody></table></div>"
        )
    elif any(filters.values()):
        table = '<p class="empty">No deals match these filters.</p>'
    else:
        table = '<p class="empty">No deals on the desk. Add an address to start.</p>'

    error_html = f'<p class="error" role="alert">{html.escape(error)}</p>' if error else ""
    count = f"{len(rows)} deal" if len(rows) == 1 else f"{len(rows)} deals"
    show_all = f'<a href="/">Show all</a>' if any(filters.values()) else ""

    return f"""<!DOCTYPE html>
<html lang="en">
<head>
<meta charset="utf-8">
<meta name="viewport" content="width=device-width, initial-scale=1">
<title>Hestia</title>
<style>
  :root {{
    color-scheme: light;
    --paper: #e3ebe4;
    --sheet: #f6faf7;
    --ink: #17211c;
    --quiet: #3d4f45;
    --rule: #c3cfc6;
    --pine: #1e6a43;
    --loss: #8e3a32;
    --serif: "Iowan Old Style", Palatino, "Palatino Linotype", Georgia, serif;
    --sans: "Avenir Next", "Segoe UI", sans-serif;
  }}
  * {{ box-sizing: border-box; }}
  body {{
    margin: 0;
    background: var(--paper);
    color: var(--ink);
    font-family: var(--sans);
    font-size: 1rem;
    line-height: 1.4;
  }}
  main {{ max-width: 1180px; margin: 0 auto; padding: 1.75rem 1.25rem 3rem; }}
  header {{ display: flex; justify-content: space-between; align-items: flex-end; gap: 1rem; }}
  h1 {{
    margin: 0;
    font-family: var(--serif);
    font-size: 2.6rem;
    font-weight: 500;
    letter-spacing: -0.03em;
    line-height: 1;
  }}
  h1::after {{
    content: "";
    display: block;
    width: 3.5rem;
    height: 3px;
    margin-top: 0.55rem;
    background: var(--pine);
  }}
  .count {{ margin: 0 0 0.55rem; color: var(--quiet); }}
  form.add, form.filters {{
    display: grid;
    grid-template-columns: 2fr 1.2fr 0.8fr 0.9fr 1fr 1.4fr;
    gap: 0.7rem 0.75rem;
    align-items: end;
  }}
  form.add {{ margin-top: 1.5rem; }}
  form.filters {{
    margin-top: 1.5rem;
    padding-top: 1.15rem;
    border-top: 1px solid var(--rule);
  }}
  form.add {{ grid-template-columns: 2fr 1.2fr 0.8fr 0.9fr 1fr 1.5fr 0.9fr auto; }}
  form.add label:nth-child(6) {{ grid-column: 1 / 4; }}
  label {{ display: flex; flex-direction: column; gap: 0.25rem; font-size: 0.92rem; color: var(--quiet); }}
  input, select, textarea, button {{ font: inherit; color: var(--ink); }}
  input, select, textarea {{
    width: 100%;
    background: #fff;
    border: 1px solid var(--rule);
    border-radius: 0;
    padding: 0.5rem 0.55rem;
  }}
  button {{
    background: var(--ink);
    color: var(--sheet);
    border: 0;
    border-radius: 0;
    padding: 0.55rem 0.85rem;
    cursor: pointer;
  }}
  button:hover {{ background: var(--pine); }}
  :focus-visible {{ outline: 2px solid var(--pine); outline-offset: 2px; }}
  .error {{ color: var(--loss); margin: 1rem 0 0; }}
  .filters-bar {{ display: flex; justify-content: space-between; align-items: center; margin-top: 0.6rem; }}
  .filters-bar a {{ color: var(--pine); }}
  .table-wrap {{ overflow-x: auto; margin-top: 0.5rem; }}
  table {{ width: 100%; border-collapse: collapse; background: var(--sheet); }}
  th, td {{ padding: 0.75rem 0.6rem; border-bottom: 1px solid var(--rule); vertical-align: top; text-align: left; }}
  th {{ font-weight: 400; color: var(--quiet); font-size: 0.88rem; }}
  td.num, th.num {{ text-align: right; font-variant-numeric: tabular-nums; }}
  .spread {{ font-family: var(--serif); font-size: 1.35rem; font-weight: 600; line-height: 1; }}
  .gain {{ color: var(--pine); }}
  .loss {{ color: var(--loss); }}
  a {{ color: var(--ink); }}
  .notes {{ display: block; max-width: 28rem; margin-top: 0.2rem; color: var(--quiet); white-space: pre-wrap; }}
  .status-form {{ display: flex; gap: 0.35rem; align-items: center; }}
  .status-form select {{ width: auto; }}
  .status-form button {{
    background: transparent;
    color: var(--ink);
    border: 1px solid var(--rule);
    padding: 0.4rem 0.55rem;
  }}
  .status-form button:hover {{ background: var(--paper); color: var(--ink); }}
  .empty {{ margin-top: 1.5rem; }}
  @media (max-width: 900px) {{
    form.add, form.filters {{ grid-template-columns: 1fr 1fr; }}
    form.add label:nth-child(6) {{ grid-column: 1 / -1; }}
  }}
  @media (max-width: 640px) {{
    form.add, form.filters, form.add label:nth-child(6) {{ grid-template-columns: 1fr; }}
    form.add label, form.filters label {{ grid-column: 1 / -1; }}
    h1 {{ font-size: 2.1rem; }}
  }}
</style>
</head>
<body>
<main>
  <header>
    <h1>Hestia</h1>
    <p class="count">{html.escape(count)}</p>
  </header>
  {error_html}
  <form class="add" method="post" action="/deals">
    {field("address", "Address", draft.get("address", ""))}
    {field("location", "Location", draft.get("location", ""))}
    {field("price", "Asking price", draft.get("price", ""), "money")}
    {field("estimated_value", "Estimated value", draft.get("estimated_value", ""), "money")}
    {field("source", "Source", draft.get("source", ""))}
    <label>Notes<textarea name="notes" rows="2">{html.escape(draft.get("notes", ""))}</textarea></label>
    {field("link", "Link", draft.get("link", ""))}
    <label>Status{_status_select("status", add_status)}</label>
    <button type="submit">Add deal</button>
  </form>
  <form class="filters" method="get" action="/">
    <label>Status<select name="status">{status_options}</select></label>
    {field("location", "Location", filters.get("location", ""))}
    {field("source", "Source", filters.get("source", ""))}
    {field("min_price", "Min price", filters.get("min_price", ""), "money")}
    {field("max_price", "Max price", filters.get("max_price", ""), "money")}
    <button type="submit">Filter</button>
  </form>
  <div class="filters-bar">{show_all}</div>
  {table}
</main>
</body>
</html>
"""


class Handler(BaseHTTPRequestHandler):
    def do_GET(self):
        parsed = urlparse(self.path)
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
        self._html(render_page(rows, raw, error=error))

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
        if path == "/deals":
            self._add(form)
        elif path == "/deals/status":
            self._move(form)
        else:
            self.send_error(404)

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
            message = str(exc) if isinstance(exc, ValueError) else "That deal is no longer on the list."
            query = nxt.split("?", 1)[1] if "?" in nxt else ""
            raw, parsed_filters, _ = _filters(parse_qs(query))
            rows = _load(raw, parsed_filters) or []
            self._html(render_page(rows, raw, error=message))
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

    def _redirect(self, location):
        self.send_response(303)
        self.send_header("Location", location)
        self.end_headers()

    def log_message(self, fmt, *args):
        print(f"{self.address_string()} {fmt % args}")


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
    server = HTTPServer((HOST, PORT), Handler)
    print(f"Hestia at http://{HOST}:{PORT}")
    server.serve_forever()


if __name__ == "__main__":
    main()
