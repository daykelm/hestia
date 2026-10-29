import tempfile
import unittest
from datetime import date
from pathlib import Path

import app
import deals
import sources


class DealTests(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.conn = deals.connect(Path(self.tmp.name) / "t.db")

    def tearDown(self):
        self.conn.close()
        self.tmp.cleanup()

    def add(self, **kwargs):
        fields = {
            "address": "1 Oak St",
            "location": "Tampa, FL",
            "price": 40000,
            "estimated_value": 90000,
            "source": "County tax sale",
            "notes": "",
            "link": "",
            "status": "New",
        }
        fields.update(kwargs)
        return deals.add_deal(self.conn, **fields)

    def test_spread_and_sort(self):
        self.assertEqual(deals.spread(40000, 95000), 55000)
        self.assertIsNone(deals.spread(40000, None))
        self.add(address="Small", price=40000, estimated_value=50000)
        self.add(address="Big", price=20000, estimated_value=90000)
        self.add(address="Unknown", price=10000, estimated_value=None)
        rows = deals.list_deals(self.conn)
        self.assertEqual([row["address"] for row in rows], ["Big", "Small", "Unknown"])

    def test_filters(self):
        self.add(address="A", location="Tampa, FL", source="County tax sale", price=50000, status="Watching")
        self.add(address="B", location="Miami, FL", source="Auction", price=200000, status="New")
        self.add(address="C", location="Tampa, FL", source="Auction", price=None, status="New")
        places = deals.list_deals(self.conn, location="tampa")
        self.assertEqual({row["address"] for row in places}, {"A", "C"})
        sources = deals.list_deals(self.conn, source="tax")
        self.assertEqual([row["address"] for row in sources], ["A"])
        priced = deals.list_deals(self.conn, min_price=40000, max_price=80000)
        self.assertEqual([row["address"] for row in priced], ["A"])
        watching = deals.list_deals(self.conn, status="Watching")
        self.assertEqual([row["address"] for row in watching], ["A"])

    def test_rejects_bad_input(self):
        with self.assertRaises(ValueError):
            self.add(address="  ")
        with self.assertRaises(ValueError):
            self.add(status="Maybe")
        with self.assertRaises(ValueError):
            deals.parse_money("-5")
        self.assertEqual(deals.parse_money("$1,200"), 1200)
        self.assertIsNone(deals.parse_money("  "))

    def test_move_status(self):
        deal_id = self.add()
        deals.set_status(self.conn, deal_id, "Under Contract")
        row = deals.list_deals(self.conn)[0]
        self.assertEqual(row["status"], "Under Contract")
        with self.assertRaises(ValueError):
            deals.set_status(self.conn, 999, "Dead")

    def test_page_escapes_and_links(self):
        page = app.render_page(
            [
                {
                    "id": 1,
                    "address": "<script>",
                    "location": "",
                    "price": 10,
                    "estimated_value": 30,
                    "spread": 20,
                    "source": "",
                    "notes": "",
                    "link": "javascript:alert(1)",
                    "status": "New",
                    "updated_at": "2026-10-28T12:00:00+00:00",
                }
            ],
            {},
        )
        self.assertIn("&lt;script&gt;", page)
        self.assertNotIn("javascript:alert", page)
        self.assertEqual(app.safe_href("javascript:alert(1)"), "")
        self.assertEqual(app.safe_href("https://example.com/a"), "https://example.com/a")
        self.assertEqual(app.safe_next("https://evil.test"), "/")
        self.assertEqual(app.safe_next("/?status=New"), "/?status=New")

    def test_south_florida_listing_merges_on_parcel(self):
        calendar = """
        <div dayid='11/23/2026'>Tax Deed<br><span class="CALSCH">41</span> TD</div>
        <div dayid='10/01/2026'>Tax Deed<br>TD</div>
        """
        sales, _ = sources.parse_calendar(calendar, today=date(2026, 10, 29))
        self.assertEqual([sale["date"] for sale in sales], ["11/23/2026"])
        _, next_link = sources.parse_calendar(
            '<a href="calendar&selCalDate=%7Bts%20%272026%2D11%2D01%27%7D" aria-label="Next Month November">',
            today=date(2026, 10, 29),
        )
        self.assertIn("selCalDate", next_link)
        decoded = sources.decode_auction_html(
            '<div id="AITEM_9" @A@E_ITEM">'
            '@H@CAD_LBL">Property Address:@F @CAD_DTA">4017 N CYPRESS DRIVE@G'
            '@H@CAD_LBL">@F @CAD_DTA">POMPANO BEACH, FL- 33069@G'
            '@H@CAD_LBL">Opening Bid:@F @CAD_DTA">$30,102.66@G'
            '@H@CAD_LBL">Parcel ID:@F @CAD_DTA">494205-AH-0170@G'
            '@H@CAD_LBL">Case #:@F @CAD_DTA">53779@G'
        )
        fragment = decoded
        listing = sources.parse_listings(fragment, county="Broward", kind="Tax deed", sale_date="11/23/2026", page_url="https://example.test/sale")[0]
        self.assertEqual(listing["price"], 30102.66)
        self.assertEqual(listing["location"], "POMPANO BEACH, FL- 33069")
        self.assertEqual(deals.upsert_listing(self.conn, listing), "added")
        deals.set_status(self.conn, deals.list_deals(self.conn)[0]["id"], "Watching")
        listing["price"] = 100
        self.assertEqual(deals.upsert_listing(self.conn, listing), "updated")
        row = deals.list_deals(self.conn)[0]
        self.assertEqual(row["price"], 100)
        self.assertEqual(row["status"], "Watching")
        self.assertEqual(row["metadata"]["parcel"], "494205-AH-0170")
        self.assertEqual(len(deals.list_deals(self.conn)), 1)
        kept = app.render_page(
            [
                {
                    "id": 2,
                    "address": "A",
                    "location": "Tampa",
                    "price": 1,
                    "estimated_value": 2,
                    "spread": 1,
                    "source": "",
                    "notes": "",
                    "link": "",
                    "status": "New",
                    "updated_at": "2026-10-28T12:00:00+00:00",
                }
            ],
            {"status": "", "location": "Tampa", "source": "", "min_price": "", "max_price": ""},
        )
        self.assertIn('name="next" value="/?location=Tampa"', kept)


if __name__ == "__main__":
    unittest.main()
