import tempfile
import unittest
from datetime import date
from pathlib import Path

import app
import deals
import diligence
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
        self.assertEqual(row["status"], "Won")
        with self.assertRaises(ValueError):
            deals.set_status(self.conn, 999, "Dead")

    def test_steps_move_one_at_a_time_and_collect_what_they_need(self):
        deal_id = self.add(status="Found")
        with self.assertRaises(ValueError):
            deals.advance(self.conn, deal_id, "Researched", {})
        deals.save_diligence(self.conn, deal_id, {"score": 6, "factors": []}, 100000)
        self.assertEqual(deals.list_deals(self.conn)[0]["status"], "Researched")
        with self.assertRaises(ValueError):
            deals.advance(self.conn, deal_id, "Bid set", {"max_bid": 5})
        with self.assertRaises(ValueError):
            deals.advance(self.conn, deal_id, "Title checked", {"title": True, "liens": False})
        deals.advance(self.conn, deal_id, "Title checked", {"title": True, "liens": True})
        deals.advance(self.conn, deal_id, "Bid set", {"max_bid": 50000})
        deals.advance(self.conn, deal_id, "Won", {"won_price": 48000})
        self.assertNotIn("Passed", deals.allowed_moves("Won", True))
        deals.advance(self.conn, deal_id, "Buyer assigned", {"buyer": "Ana", "fee": 9000})
        deals.advance(self.conn, deal_id, "Closed", {})
        row = deals.list_deals(self.conn)[0]
        self.assertEqual(row["status"], "Closed")
        self.assertEqual((row["metadata"]["max_bid"], row["metadata"]["buyer"], row["metadata"]["fee"]), (50000, "Ana", 9000))
        self.assertEqual(deals.allowed_moves("Passed", True), ["Researched"])

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
        for key in app.HELP:
            self.assertIn(f'id="help-{key}"', page)
        self.assertIn('popovertarget="help-roll"', page)
        self.assertIn(f'data-app-version="{app.app_version()}"', page)
        self.assertIn('id="app-update" hidden', page)
        self.assertIn('class="process"', page)
        self.assertIn("Step 1 of 7", page)
        today = date.today().strftime("%m/%d/%Y")
        grouped = app.render_page(
            [
                {
                    "id": 7,
                    "address": "12 Oak",
                    "location": "Miami, FL",
                    "price": 20000,
                    "estimated_value": None,
                    "spread": None,
                    "source": "",
                    "notes": "",
                    "link": "",
                    "status": "Researched",
                    "metadata": {"sale_date": today, "roll_value": 200000, "diligence": {"score": 7, "band": "good", "point": [-80.2, 25.8]}},
                }
            ],
            {},
        )
        self.assertIn("Today", grouped)
        self.assertIn('class="thumb"', grouped)
        self.assertIn("Worth", grouped)
        self.assertIn("Zillow", grouped)
        self.assertIn("google.com/maps/search", grouped)
        self.assertIn(">Look up<", grouped)
        self.assertIn("World_Imagery", grouped)
        self.assertEqual(
            sources.bid_url({"county": "Miami-Dade", "kind": "Tax deed", "auction_id": "1519824"}),
            "https://www.miamidade.realforeclose.com/index.cfm?zaction=auction&zmethod=details&AID=1519824",
        )
        self.assertEqual(sources.bid_url({"county": "Lee", "kind": "Foreclosure", "auction_id": "abc"}), "")
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
        self.assertEqual(row["status"], "Researched")
        self.assertEqual(row["metadata"]["parcel"], "494205-AH-0170")
        self.assertEqual(len(deals.list_deals(self.conn)), 1)

    def test_foreclosure_price_roll_value_and_past_sales(self):
        fragment = (
            '<div id="AITEM_7" class="AUCTION_ITEM"><table>'
            '<tr><td class="AD_LBL">Final Judgment Amount:</td><td class="AD_DTA">$182,410.55</td></tr>'
            '<tr><td class="AD_LBL">Plaintiff Max Bid:</td><td class="AD_DTA">Hidden</td></tr>'
            '<tr><td class="AD_LBL">Property Address:</td><td class="AD_DTA">1 MAIN ST</td></tr>'
            '<tr><td class="AD_LBL">Parcel ID:</td><td class="AD_DTA">11-22</td></tr>'
            "</table></div>"
        )
        listing = sources.parse_listings(fragment, county="Lee", kind="Foreclosure", sale_date="10/29/2026", page_url="https://example.test")[0]
        self.assertEqual(listing["price"], 182410.55)
        self.assertEqual(listing["metadata"]["price_basis"], "final judgment")
        deals.upsert_listing(self.conn, listing)
        deal_id = deals.list_deals(self.conn)[0]["id"]
        deals.save_diligence(self.conn, deal_id, {"score": 4, "factors": []}, 300000)
        row = deals.list_deals(self.conn)[0]
        self.assertIsNone(row["estimated_value"])
        self.assertEqual(row["metadata"]["roll_value"], 300000)
        listing["price"] = 150000
        deals.upsert_listing(self.conn, listing)
        self.assertNotIn("diligence", deals.list_deals(self.conn)[0]["metadata"])
        self.assertEqual(deals.drop_past_sales(self.conn, date(2026, 10, 29)), 0)
        self.assertEqual(deals.drop_past_sales(self.conn, date(2026, 10, 30)), 1)
        self.assertEqual(deals.list_deals(self.conn), [])

    def test_score_uses_two_rolls_and_leaves_liens_open(self):
        record = diligence.parse_broward_record(
            "<tr><td>2026</td><td>$21,460</td><td>$193,180</td><td>$214,640</td><td>$141,580</td></tr>"
            "<tr><td>Homestead</td><td>0</td></tr>"
            "<tr><td>4/29/2010</td><td>WD-Q</td><td>$69,000</td></tr>"
            "Adj. Bldg. S.F. 1500 Units/Beds/Baths 1/3/2 Eff./Act. Year Built: 1977/1976"
        )
        self.assertEqual(record["just"], 214640)
        self.assertEqual(record["house"], "3 bed · 2 bath · 1,500 sq ft · built 1976")
        report = diligence.parse_attom({"property": [{"assessment": {
            "delinquentyear": 2023,
            "tax": {"taxAmt": 4200, "taxYear": 2024},
            "mortgage": {
                "FirstConcurrent": {"amount": 180000, "LenderFirstName": "WELLS FARGO", "date": "2019-06-01"},
                "SecondConcurrent": {"amount": 25000},
            },
        }}]})
        self.assertEqual(report["loan"], "WELLS FARGO · $180,000 · 2019, plus $25,000")
        self.assertEqual(report["tax"], "Delinquent since 2023, bill $4,200")
        self.assertEqual(diligence.parse_attom({}), {})
        same = diligence.parse_reapi(
            {"data": {"propertyInfo": {"address": {"label": "12 SW 3 Ave, Miami, FL 33101"}}, "freeClear": True, "taxInfo": {"taxAmount": "1200", "year": 2024}, "lotInfo": {"apn": "01-02"}}},
            "12 SW 3 AVE",
            "01-02",
        )
        self.assertEqual(same["match"], "parcel")
        self.assertEqual(same["loan"], "No open loan on the report")
        self.assertIn("Tax bill $1,200 for 2024", diligence.reapi_sentence(same, "12 SW 3 AVE", report["loan"], report["tax"]))
        unit = diligence.parse_reapi(
            {"data": {"propertyInfo": {"address": {"label": "12 SW 3 Ave Apt 4"}}, "currentMortgages": [{"lenderName": "BANK", "amount": 50000, "documentDate": "2018-01-02"}], "taxLien": True, "taxInfo": {"taxAmount": "800"}}},
            "12 SW 3 AVE",
        )
        self.assertEqual(unit["match"], "unit")
        self.assertTrue(diligence.reapi_sentence(unit, "12 SW 3 AVE").startswith("Not this door"))
        self.assertIn("Disagrees", diligence.reapi_sentence(same, "12 SW 3 AVE", "No open loan on the report", "Delinquent since 2023"))
        self.assertFalse(record["homestead"])
        comps = diligence.parse_broward_comps(
            "5/15/2026 04 WD 120890819 Q $203,000 6/26/2026 04 QCD 120993106 T $100 "
            "1/2/2025 04 WD 1 Q $185,000 3/3/2025 04 WD 1 Q $175,000"
        )
        self.assertEqual([item["price"] for item in comps], [203000, 185000, 175000])
        facts = {
            "price": 20000,
            "address": "12 SW 3 AVE",
            "kind": "Tax deed",
            "case": "53988",
            "values": [
                {"source": "Florida DOR roll", "kind": "just", "amount": 200000},
                {"source": "Broward appraiser", "kind": "just", "amount": 200000},
            ],
            "homestead": [
                {"source": "Florida DOR roll", "yes": False},
                {"source": "Broward appraiser", "yes": False},
            ],
            "comps": comps,
            "flood": {"zone": "X", "subtype": "AREA OF MINIMAL FLOOD HAZARD", "special": False},
            "addresses": {"the state roll": "12 SW 3RD AVE"},
            "point": (-80.1434567891, 26.1212345678),
        }
        result = diligence.score_facts(facts, today=date(2026, 10, 29))["diligence"]
        self.assertEqual(result["point"], [-80.143457, 26.121235])
        self.assertIn("bbox=-80.144", diligence.aerial_url(result["point"]))
        self.assertEqual(diligence.apply_review(result, {"title": True})["point"], result["point"])
        points = {item["name"]: (item["points"], item["checked"]) for item in result["factors"]}
        self.assertEqual(points["Resale value"], (2, True))
        self.assertEqual(points["Title"], (1, True))
        self.assertEqual(points["Code and building"], (0, False))
        self.assertEqual(points["Other liens"], (0, False))
        self.assertEqual(points["Occupancy"], (1, True))
        self.assertEqual(result["band"], "good")
        reported = diligence.score_facts({**facts, "loan": report["loan"], "tax": report["tax"]}, today=date(2026, 10, 29))["diligence"]
        self.assertEqual(reported["cause"], "Taxes")
        self.assertEqual(reported["band"], "good")
        self.assertFalse(any("Delinquent taxes" in flag for flag in reported["flags"]))
        owed = diligence.score_facts(
            {**facts, "kind": "Foreclosure", "case": "2015-023088-CA-01", "loan": report["loan"], "tax": report["tax"]},
            today=date(2026, 10, 29),
        )["diligence"]
        self.assertEqual(owed["cause"], "Taxes and mortgage")
        self.assertEqual(owed["band"], "risky")
        self.assertIn("Delinquent taxes sit on top of the mortgage foreclosure.", owed["flags"])
        both = diligence.score_facts(
            {**facts, "kind": "Foreclosure", "case": "COCE-26-008349", "loan": "No open loan on the report", "tax": report["tax"]},
            today=date(2026, 10, 29),
        )["diligence"]
        self.assertEqual(both["cause"], "Taxes and HOA lien")
        self.assertIn("HOA lien and delinquent taxes", both["flags"][0])
        reviewed = diligence.apply_review(result, {"title": True, "liens": True}, today=date(2026, 10, 29))
        self.assertGreaterEqual(reviewed["score"], 8)
        self.assertEqual(reviewed["band"], "excellent")

        # Two copies of one roll are not two sources: without a sale or nearby sales the color stays gray.
        alone = diligence.score_facts({**facts, "comps": []}, today=date(2026, 10, 29))["diligence"]
        self.assertEqual(alone["band"], "thin")
        conflict = diligence.score_facts(
            {**facts, "values": [{"source": "A", "kind": "just", "amount": 100000}, {"source": "B", "kind": "just", "amount": 200000}]},
            today=date(2026, 10, 29),
        )["diligence"]
        self.assertEqual(conflict["band"], "thin")

        hoa = diligence.score_facts({**facts, "kind": "Foreclosure", "case": "COCE-26-008349"}, today=date(2026, 10, 29))["diligence"]
        self.assertEqual(hoa["band"], "risky")
        self.assertTrue(any("HOA" in flag for flag in hoa["flags"]))
        self.assertEqual(diligence.court_of("2015-023088-CA-01"), "circuit")
        self.assertEqual(diligence.court_of("19-CC-001234"), "county")
        self.assertEqual(diligence.court_of("CACE-26-000648"), "circuit")

        wrong = diligence.score_facts({**facts, "addresses": {"the state roll": "14 SW 3RD AVE"}}, today=date(2026, 10, 29))["diligence"]
        self.assertEqual(wrong["band"], "thin")
        self.assertIn("house number", wrong["reason"])

        lien = diligence.score_facts(
            {**facts, "code": {"sources": ["Miami-Dade code liens"], "liens": ["code lien for junk (1)"], "unsafe": [], "open": []}},
            today=date(2026, 10, 29),
        )["diligence"]
        self.assertEqual(lien["band"], "risky")
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
