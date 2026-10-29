"""Deal list storage. Spread is estimated value minus asking price."""

import json
import sqlite3
from datetime import datetime, timezone
from pathlib import Path

STATUSES = (
    "New",
    "Watching",
    "Under Contract",
    "Assigned",
    "Closed",
    "Dead",
)

# shortcut: money is a float, switch to integer cents if these numbers are ever summed into a ledger
# shortcut: sort in Python, move into SQL if one list passes a few thousand rows


def connect(path):
    Path(path).parent.mkdir(parents=True, exist_ok=True)
    conn = sqlite3.connect(path)
    conn.row_factory = sqlite3.Row
    conn.execute(
        """
        CREATE TABLE IF NOT EXISTS deals (
            id INTEGER PRIMARY KEY,
            address TEXT NOT NULL,
            location TEXT NOT NULL DEFAULT '',
            price REAL,
            estimated_value REAL,
            source TEXT NOT NULL DEFAULT '',
            notes TEXT NOT NULL DEFAULT '',
            link TEXT NOT NULL DEFAULT '',
            status TEXT NOT NULL DEFAULT 'New',
            created_at TEXT NOT NULL,
            updated_at TEXT NOT NULL
        )
        """
    )
    columns = {row[1] for row in conn.execute("PRAGMA table_info(deals)")}
    if "metadata" not in columns:
        conn.execute("ALTER TABLE deals ADD COLUMN metadata TEXT NOT NULL DEFAULT '{}'")
    if "dedupe_key" not in columns:
        conn.execute("ALTER TABLE deals ADD COLUMN dedupe_key TEXT")
    conn.execute("CREATE UNIQUE INDEX IF NOT EXISTS deals_dedupe ON deals(dedupe_key)")
    conn.execute(
        """
        CREATE TABLE IF NOT EXISTS media (
            id INTEGER PRIMARY KEY,
            deal_id INTEGER NOT NULL,
            kind TEXT NOT NULL,
            url TEXT NOT NULL,
            source TEXT NOT NULL DEFAULT '',
            UNIQUE(deal_id, url)
        )
        """
    )
    return conn


def parse_money(raw):
    if raw is None or str(raw).strip() == "":
        return None
    text = str(raw).strip().replace("$", "").replace(",", "")
    try:
        number = float(text)
    except ValueError:
        raise ValueError("Price and estimated value need to be numbers.") from None
    if number < 0:
        raise ValueError("Price and estimated value can't be negative.")
    return number


def spread(price, estimated_value):
    if price is None or estimated_value is None:
        return None
    return estimated_value - price


def _now():
    return datetime.now(timezone.utc).isoformat()


def _clean_status(status):
    if status not in STATUSES:
        raise ValueError("Pick a status from the list.")
    return status


def add_deal(conn, *, address, location, price, estimated_value, source, notes, link, status):
    address = (address or "").strip()
    if not address:
        raise ValueError("Add an address.")
    status = _clean_status(status or "New")
    now = _now()
    cur = conn.execute(
        """
        INSERT INTO deals (
            address, location, price, estimated_value, source, notes, link, status, created_at, updated_at
        ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
        """,
        (
            address,
            (location or "").strip(),
            price,
            estimated_value,
            (source or "").strip(),
            (notes or "").strip(),
            (link or "").strip(),
            status,
            now,
            now,
        ),
    )
    conn.commit()
    return cur.lastrowid


def upsert_listing(conn, listing):
    """One property row. A later pull from the same parcel updates the auction facts and leaves status alone."""
    key = (listing.get("dedupe_key") or "").strip()
    if not key:
        raise ValueError("A collected property needs a parcel or address.")
    address = (listing.get("address") or "").strip()
    if not address:
        raise ValueError("Add an address.")
    metadata = listing.get("metadata") or {}
    now = _now()
    existing = conn.execute("SELECT id, metadata FROM deals WHERE dedupe_key = ?", (key,)).fetchone()
    if existing:
        merged = {}
        try:
            merged = json.loads(existing["metadata"] or "{}")
        except json.JSONDecodeError:
            merged = {}
        merged.update(metadata)
        conn.execute(
            """
            UPDATE deals
            SET address = ?, location = ?, price = ?, source = ?, link = ?, metadata = ?, updated_at = ?
            WHERE id = ?
            """,
            (
                address,
                (listing.get("location") or "").strip(),
                listing.get("price"),
                (listing.get("source") or "").strip(),
                (listing.get("link") or "").strip(),
                json.dumps(merged, separators=(",", ":")),
                now,
                existing["id"],
            ),
        )
        deal_id = existing["id"]
        state = "updated"
    else:
        cur = conn.execute(
            """
            INSERT INTO deals (
                address, location, price, estimated_value, source, notes, link, status,
                created_at, updated_at, metadata, dedupe_key
            ) VALUES (?, ?, ?, NULL, ?, '', ?, 'New', ?, ?, ?, ?)
            """,
            (
                address,
                (listing.get("location") or "").strip(),
                listing.get("price"),
                (listing.get("source") or "").strip(),
                (listing.get("link") or "").strip(),
                now,
                now,
                json.dumps(metadata, separators=(",", ":")),
                key,
            ),
        )
        deal_id = cur.lastrowid
        state = "added"
    for item in listing.get("media") or []:
        url = (item.get("url") or "").strip()
        kind = item.get("kind") if item.get("kind") in ("image", "video") else ""
        if url and kind:
            conn.execute(
                "INSERT OR IGNORE INTO media (deal_id, kind, url, source) VALUES (?, ?, ?, ?)",
                (deal_id, kind, url, (listing.get("source") or "").strip()),
            )
    conn.commit()
    return state


def set_status(conn, deal_id, status):
    status = _clean_status(status)
    cur = conn.execute(
        "UPDATE deals SET status = ?, updated_at = ? WHERE id = ?",
        (status, _now(), deal_id),
    )
    conn.commit()
    if cur.rowcount == 0:
        raise ValueError("That deal is no longer on the list.")


def _like(text):
    escaped = text.replace("\\", "\\\\").replace("%", "\\%").replace("_", "\\_")
    return f"%{escaped}%"


def list_deals(conn, *, status="", location="", source="", min_price=None, max_price=None):
    query = "SELECT * FROM deals WHERE 1=1"
    args = []
    if status:
        query += " AND status = ?"
        args.append(_clean_status(status))
    if location:
        query += " AND location LIKE ? ESCAPE '\\'"
        args.append(_like(location.strip()))
    if source:
        query += " AND source LIKE ? ESCAPE '\\'"
        args.append(_like(source.strip()))
    if min_price is not None:
        query += " AND price IS NOT NULL AND price >= ?"
        args.append(min_price)
    if max_price is not None:
        query += " AND price IS NOT NULL AND price <= ?"
        args.append(max_price)
    rows = conn.execute(query, args).fetchall()
    media_rows = conn.execute("SELECT deal_id, kind, url FROM media").fetchall()
    media = {}
    for item in media_rows:
        media.setdefault(item["deal_id"], []).append({"kind": item["kind"], "url": item["url"]})
    deals = []
    for row in rows:
        deal = dict(row)
        deal["spread"] = spread(deal["price"], deal["estimated_value"])
        try:
            deal["metadata"] = json.loads(deal.get("metadata") or "{}")
        except json.JSONDecodeError:
            deal["metadata"] = {}
        deal["media"] = media.get(deal["id"], [])
        deals.append(deal)
    deals.sort(key=lambda deal: (deal["spread"] is None, -(deal["spread"] or 0), deal["address"].lower()))
    return deals
