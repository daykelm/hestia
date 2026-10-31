# Features

Prioritized for personal use. Build in this order unless real usage shows a different bottleneck.

## First

These run beside the epics. They cost little, and they decide how far the rest can be trusted.

- [ ] Take one real deal from the sale list to a closing or a recorded loss. No deal has closed yet, so the score has not been tested against a result.
- [ ] Settle which report is right on loans. ATTOM showed no loan where RealEstateAPI showed one on 16 foreclosures, and the score still reads ATTOM alone, so a deal can stay green with a loan behind it. Check about 10 against the county records and the docket, starting with 3530 Mystic Pointe Dr 411, 8201 NW 16 St, 3240 NW 203 Ln, and 3283 NW 99 St. Check what ATTOM's `FirstConcurrent` covers, and if it misses later loans, stop calling a blank "No open loan" and feed the higher loan into the score.
- [ ] Close the home port. Port 18080 has no login, and a POST with no `Origin` header passes the same-origin check, so anything on the home network can read and change deals. Require a token, or bind the port to the tunnel only.
- [ ] Decide what happens when the trials end. ATTOM has no paid plan chosen, and the score loses its loan and tax lines without it. RealEstateAPI has a 14-day trial, and neither its end date nor its balance is recorded here.
- [ ] Add tests for the RealAuction, ATTOM, and RealEstateAPI parsers, using saved responses. A vendor format change should fail a test, not quietly change a score.
- [ ] Replace the cost estimates in `diligence.py` with real quotes for quiet title, stamps, and recording, and have a Florida title attorney check the rules behind best and worst.
- [ ] Find out whether the building still stands. A buyer can pay for a parcel whose building is gone. Try the building and land split on the roll, demolition permits, unsafe-structure cases, and the date of the satellite image. Until then it is a hand check on every deal.
- [ ] Decide whether the WebView shell in `android/` stays now that the Expo app exists.

## Epics

These cut steps out of the current desk. The seven steps stay. What goes is the extra click, the repeated number, and the long factor list.

### Epic: Open on the deals that matter

The desk currently asks for a score click, then shows every researched deal. Scoring already moves a deal from Found to Researched. Sale day, the color, and the roll-to-bid gap are enough to decide what to open.

- [ ] Collect and score in one run, before the sale morning. No "Score this deal" on each row.
- [x] The first screen is the next sale only, grouped by verdict. Can't say and Pass stay one tap away.
- [x] A row is the address, any danger, and the total cost from best to worst.

Done when a sale morning starts on the deals worth opening, with nothing left to score.

### Epic: One card, four lines

Each deal already pulls the auction list, both tax rolls, nearby sales, code cases, flood, and a satellite photo. The plate then repeats that as seven factors. The useful answer is short, and each line names its source.

- Worth: the roll, and whether a real sale since 2023 agrees.
- Room: how many times the roll covers the bid.
- Danger: one line, or "none in the public records." An HOA case, an open code lien, a coastal flood zone, or a bid above the roll.
- Still open: only the checks no source answered. Usually the docket, recorded liens, and taxes past the opening bid.

The factor list stays behind the card. When an ATTOM key is on the Umbrel, the open-loan amount and the delinquent tax replace two of those "still open" lines. RealEstateAPI is a second Also line on that card and does not change the color. The court docket stays a manual check.

Done when a deal can be judged from the card without opening the factor list.

### Epic: Title check only when something is still unknown

Title checked is three county websites and two boxes that only record that they were ticked. A tax deed with no open loan and a delinquent tax that matches the bid does not need the same path as an HOA foreclosure.

- Show the three links only for the lines still open on the card.
- The docket question is one answer: lender, association, or not a lawsuit. A tax-deed application is not a lawsuit.
- Record the answer, not a bare tick. The score uses that answer the way it already uses the two boxes.

Done when a clean tax deed can reach a ceiling without visiting sites that have nothing new to say.

### Epic: Ceiling to the auction, then the buyer

The ceiling is typed in Hestia, typed again on RealAuction, and the buyer is typed from scratch after a win. The county already bids in $100 steps up to the ceiling once a deposit has cleared. Hestia cannot send that bid. It can stop the retyping around it.

- Setting the ceiling copies it. Place this bid opens that property. The deposit still has to clear on the county site before the sale.
- After the sale, one outcome: the price you won at, or lost. No extra step between the ceiling and the result.
- Buyers are saved once, with what they buy and how to reach them. Assigning is a pick and a fee.
- The message to the buyer is the card plus the won price and the fee. Copy it. No separate package to assemble.

Done when a pursued deal goes from ceiling to a buyer message without typing the same number twice, and without writing the summary by hand.

### Epic: Sale-day plan

Ideas taken from [LoomBids](https://loombids.com/en/), a bidding tool for car auctions such as Copart, seen from its public page only. Hestia takes the plan around the bid, and a person still places every bid.

- [ ] Watchlist for each sale: the address, the verdict, the ceiling, whether the deposit cleared, and whether title is checked.
- [ ] Stages for each deal on the list: To configure, Upcoming, Live, Closed. They sit on top of the seven steps and do not replace them.
- [ ] A budget and a target for each sale day, such as $150,000 across 2 properties. Warn when the ceilings add up to more than the budget.
- [ ] Stop at the target. After enough wins, tell the user to cancel the remaining maximums on the county site. Hestia cannot cancel them itself.
- [ ] "What it typically sells for" on each card, from the past results of similar sales in that county.
- [ ] Once there is a team, tie each ceiling and result to the person who set it, with a limit per person. This waits for accounts under [Toward many users](#toward-many-users).

Done when a sale morning shows every ceiling against one budget, and a win makes clear which maximums to cancel.

Automatic bidding stays out of scope. Revisit it only after real closed deals, verdicts that held up against results, and written permission or an official route from RealAuction. The county site already bids up to a maximum, so the problem left is setting the right number.

## Toward many users

The builder is the first user of many, and so far the only one. Every feature still has to work for that one user first. Nothing here starts before the first real deal, and accounts are not built before a second user is close.

One rule applies now: new work should not make these items harder. The sale, the parcel, and the score belong to everyone. The ceiling, the review, and the buyer belong to one user. Keep them apart in new code, starting with the buyer list.

1. **Accounts and separate data.** There is no app login, only Cloudflare Access. `deals` holds one row per property, and its `metadata` keeps public research beside the ceiling, the won price, and the buyer. Two users cannot follow the same sale. Split it into a shared property and one private deal per user, so research is paid for once. Decide then whether a user's own lien search stays out of the shared score.
2. **Hosting.** A home Umbrel beside a Bitcoin node, capped at 128 MB, cannot hold customer data. Move to a cloud host with backups. The standard-library server can carry a small group and needs another look past that.
3. **Data cost and licenses.** The current pull cost about $16 for 98 sales at RealEstateAPI, about 160 lookups. ATTOM has no price yet. These costs set the price of the product. Ask both vendors whether their terms allow use for other people, and check the terms of the county and RealAuction data. Collecting for yourself is not the same as reselling.
4. **Legal exposure.** Excellent on a property with a missed lien can cost someone real money. Have a lawyer review the wording, the disclaimers, and the terms before charging. Wholesaling rules also differ by state.
5. **Coverage.** Three Florida counties work today, and much of the parsing is specific to each. Every new county is new work. South Florida is the first market.

The first item in [First](#first) is also the evidence for any of this. A closed deal is what can be shown to another investor.

## Original list

The items below are the first backlog. Several are already built under newer names: the steps are Found through Closed, the score has colors, and there is a phone app. The sections above are the current work.

## Phase 1 – Minimum Useful Version (Start Here)

### 1. Deal Intake & List
•⁠  ⁠[x] Ability to add deals manually (address, price, source, notes, link)
•⁠  ⁠[x] Simple clean table/list view of all deals
•⁠  ⁠[x] Basic filters (status, location, price range, source)
•⁠  ⁠[x] Key fields visible at a glance: Address, Asking/Auction Price, Estimated Value, Potential Spread, Status, Source

### 2. Deal Qualification (Fast)
•⁠  ⁠[x] Fields for Estimated ARV / Value
•⁠  ⁠[ ] Estimated repairs (simple number or notes)
•⁠  ⁠[x] Calculated potential spread / assignment fee target
•⁠  ⁠[ ] Red flag notes
•⁠  ⁠[ ] Quick “Pursue / Pass / Watch” decision

### 3. Deal Tracking
•⁠  ⁠[x] Statuses: New → Watching → Under Contract → Assigned → Closed → Dead
•⁠  ⁠[x] Ability to move deals between statuses easily
•⁠  ⁠[x] Basic timeline / last updated

### 4. Buyer List (Private)
•⁠  ⁠[ ] Simple list of cash buyers / wholesalers
•⁠  ⁠[ ] Notes: what they buy, preferred locations, contact method, past deals
•⁠  ⁠[ ] Ability to mark which buyers a specific deal was sent to

## Phase 2 – Reduce Friction

•⁠  ⁠[ ] Deal package generator (clean summary + key numbers + photos/links ready to send)
•⁠  ⁠[ ] Basic contract / assignment agreement templates
•⁠  ⁠[ ] Email or message draft generation for buyers
•⁠  ⁠[ ] Simple alerts (new deals matching criteria)
•⁠  ⁠[ ] Better data import (CSV, basic scraping helpers, or manual bulk add)

## Phase 3 – Only If Needed

•⁠  ⁠[ ] Light AI assistance (summarize property, suggest offer range, draft outreach)
•⁠  ⁠[ ] Multi-county or multi-state support
•⁠  ⁠[ ] Automated data pulls from preferred sources
•⁠  ⁠[ ] Dashboard with simple stats (deals worked, assignment fees, conversion)
•⁠  ⁠[ ] Document storage per deal

## Explicitly Not Building (Yet)

•⁠  ⁠Public-facing website
•⁠  ⁠User accounts / login system
•⁠  ⁠Payment or escrow features
•⁠  ⁠Fully autonomous agents
•⁠  ⁠Complex CRM

The Android app is built. It is not a second product. It reads the same desk.

---

*Rule*: Only move to the next phase after the current phase is actually being used on real deals.
