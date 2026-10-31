# Features

Prioritized for personal use. Build in this order unless real usage shows a different bottleneck.

## Epics

These cut steps out of the current desk. The seven steps stay. What goes is the extra click, the repeated number, and the long factor list.

### Epic: Open on the deals that matter

The desk currently asks for a score click, then shows every researched deal. Scoring already moves a deal from Found to Researched. Sale day, the color, and the roll-to-bid gap are enough to decide what to open.

- Collect and score in one run, before the sale morning. No "Score this deal" on each row.
- The first screen is the next sale only, good and fair first. Risky and not-enough-data stay one tap away.
- A row is the address, the color, the bid, the roll, and how many times the roll covers the bid.

Done when a sale morning starts on the deals worth opening, with nothing left to score.

### Epic: One card, four lines

Each deal already pulls the auction list, both tax rolls, nearby sales, code cases, flood, and a satellite photo. The plate then repeats that as seven factors. The useful answer is short, and each line names its source.

- Worth: the roll, and whether a real sale since 2023 agrees.
- Room: how many times the roll covers the bid.
- Danger: one line, or "none in the public records." An HOA case, an open code lien, a coastal flood zone, or a bid above the roll.
- Still open: only the checks no source answered. Usually the docket, recorded liens, and taxes past the opening bid.

The factor list stays behind the card. When an ATTOM key is on the Umbrel, the open-loan amount and the delinquent tax replace two of those "still open" lines. The court docket stays a manual check.

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

## Original list

The items below are the first backlog. Several are already built under newer names: the steps are Found through Closed, the score has colors, and there is a phone app. The epics above are the current work.

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
•⁠  ⁠Mobile app
•⁠  ⁠Complex CRM

---

*Rule*: Only move to the next phase after the current phase is actually being used on real deals.
