# Product

<!-- impeccable:product-schema 1 -->

## Platform

web

## Users

One operator: the builder, a solo real estate wholesaler working South Florida. He uses Hestia on a Mac at a desk and on his phone, about equally. His job is to find discounted auction and tax-deed properties early, judge them fast, and assign the good ones to cash buyers.

## Product Purpose

Hestia turns public auction lists into a short list worth acting on. It pulls upcoming sales, checks each parcel against public records, scores it from 1 to 10, and tracks the few deals he pursues from first look to closing. Success: reviewing a new week of deals takes 5 to 10 minutes, and more time goes to the best ones.

## Positioning

Wholesaler CRMs start from leads someone already found. Auction desks stop at a bid sheet. Hestia starts from the county's own sale calendar and does the first pass of due diligence automatically, citing which public source said what. A factor only gets full points when two sources agree.

## Operating Context

- Counties: Broward, Miami-Dade, and Lee from the RealAuction calendars. Collier tax deeds are in person and not collected.
- Weekly loop: collect upcoming sales, score them, skim the best, then check title and condition by hand for the few worth pursuing.
- Sale days come in batches of 20 to 40 properties. Untouched deals drop off after their sale day.
- Runs on his Umbrel home server at `umbrel.local:18080`, on the home network only. The same machine runs a Bitcoin node and a mining pool, which must not be disturbed.

## Capabilities and Constraints

- Collect upcoming tax deed and foreclosure sales. Price is the opening bid, or the final judgment for foreclosures.
- Score from 1 to 10 on five factors: resale value, comparables, legal, occupancy, and other liens. Legal and liens are not checked yet, so 6 is the current ceiling.
- Statuses: New, Watching, Under Contract, Assigned, Closed, Dead. Deals can also be added by hand, with filters and an estimated value he types himself.
- The tax roll value is shown beside a deal, never as its estimated value.
- Keep it light: Python standard library, one SQLite file, and no external font or script hosts. The container is capped at a quarter CPU and 128 MB.
- No login. Anyone on the home network can edit.
- Not built yet: estimated repairs, red-flag notes, a Pursue / Pass / Watch decision, and the private buyer list.

## Evidence on Hand

Real public auction data: about 98 upcoming properties with case numbers, parcels, prices, tax roll values, and scores. No property photos come from these sources. No buyers, closed deals, or results exist yet, so none can be shown.

## Product Principles

1. Personal first: built for one operator's workflow, not imaginary users.
2. Speed over perfection: fast triage beats a complete report.
3. Data quality matters most: say what a source did not check instead of guessing.
4. Minimal viable everything: add only what removes real friction.
5. Stay legal and clean: public records only, with a clear trail of where each fact came from.
