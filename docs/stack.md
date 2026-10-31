# Stack, providers, and plans

Hestia is a one-person desk for Broward, Miami-Dade, and Lee auction sales. This page is the map of what it runs on, what it pays for, and what it refused.

![Where Hestia runs](graphics/architecture.png)

The Android app and the web desk both talk to one Python server. Cloudflare Access sits in front of `hestia.trading`. The tunnel is outbound only, so the home router has no port forward for this app. On the Umbrel, the `hestia` container is capped at a quarter CPU and 128 MB, its root filesystem is read-only, and its only disk is `data/hestia.db`. The Bitcoin node and ckpool are on that machine and are not on this network.

## Tech stack

| Layer | What it is |
| --- | --- |
| Server | Python 3.12, standard library only. `ThreadingHTTPServer` in `app.py`. No web framework. |
| Desk | Static HTML, `static/desk.css`, `static/desk.js`. EB Garamond is a file in the repo, not a font host. |
| Data | One SQLite file, `HESTIA_DB` (`/data/hestia.db` in the container). |
| Host | Docker Compose project `hestia` on the Umbrel. Image `python:3.12-slim`. |
| Edge | `cloudflare/cloudflared`, Compose profile `tunnel`, HTTP/2. Cloudflare Access on the hostname. |
| Phone | Expo SDK 58, React Native 0.88, Expo Router. Package `com.hestia.trading`. |
| Phone updates | EAS Update on the `production` channel. Close the app and open it again to take one. The installed APK is [hestia-native.apk](https://hestia.trading/static/hestia-native.apk), arm64. A new APK is only for a native module change. |
| Tests | `python3 -m unittest test_deals` |
| Ship | `./deploy.sh` tests, syncs the app files, rebuilds the hestia container, and publishes an over-the-air update when `mobile/` changed. |

Sale days are America/New_York. The Umbrel clock is not the sale clock.

```mermaid
flowchart LR
  found[Found] --> researched[Researched]
  researched --> title[Title checked]
  title --> bid[Bid set]
  bid --> won[Won]
  won --> buyer[Buyer assigned]
  buyer --> closed[Closed]
```

Passed sits beside that line. Hestia fills Found and Researched. Title checked is the docket and the lien search. Bid set is the ceiling. The county site still places the bid.

## How a deal gets a card

![How a deal gets a card](graphics/research.png)

The score uses only factors a source actually answered. Each checked factor can earn 0, 1, or 2. The number is `round(1 + 9 × earned / possible)`, and possible is 2 times the number of checked factors. Version 3 of the rules lives in `diligence.py`.

| Band | When |
| --- | --- |
| Excellent | Score at least 8, and the operator recorded a lien search. ATTOM answering the loan line is not that search. |
| Good | Score at least 6, and no flag. A strong paper score stays Good until that lien search. |
| Fair | Score 4 or 5, and no flag. |
| Risky | Any flag, or a score of 3 or less. |
| Not enough data | The house number disagrees across sources, resale has fewer than two sources, or fewer than four factors were checked. |

On the sky map the bands are blue, green, yellow, red, and a hollow dot. Amber on the card marks danger, a tax line that starts with Delinquent, or a cause that is an HOA lien or more than one thing. It also marks an Also line that disagrees with ATTOM, names a unit the sale list did not, or is a different door. A tax deed is not red just because the taxes are delinquent. That is why it is in the sale. An HOA case in county court is red. Delinquent taxes on a foreclosure, or a second loan on a foreclosure, are red.

The cause is read from the auction type, the court in the case number, and the ATTOM tax line.

| What the list shows | Cause |
| --- | --- |
| Tax deed | Taxes |
| County court, taxes delinquent | Taxes and HOA lien |
| Circuit court, taxes delinquent | Taxes and mortgage |
| County court only | HOA lien |
| Circuit court only | Mortgage |
| Delinquent taxes, court not readable | Taxes |

County-court case numbers are the ones Hestia can see as COCE, CONO, COSO, COWE, or a county-court marker. Circuit numbers are CACE or a CA marker. An HOA suit filed in circuit court still reads as Mortgage until the docket is opened.

The card opens on the total cost, then Danger and Still open. Cause shows when it is not plain taxes, and Also shows only when it disagrees or names another door. Parcel and case sit lower, and the seven factors stay behind the card: resale value, comparables, title, code and building, flood, occupancy, and other liens.

## What a deal costs in total

`diligence.costs` adds a best and a worst case, then compares them with 70% of the value. The value is your own, or the tax roll if you have not set one. The roll is a yardstick and lags the market.

| Line | Tax deed | Foreclosure |
| --- | --- | --- |
| Price | Opening bid, your ceiling, or the won price | Final judgment, your ceiling, or the won price |
| Stamps and recording | 0.7% plus $500 | 0.7% plus $500 |
| Quiet title | $2,500 best, $5,000 worst | None |
| Open loan | Not added. F.S. 197.552 clears private mortgages. Municipal, county, special district, and community development district liens survive | County court: added to both. Otherwise worst case only |
| Back taxes | Already in the opening bid | Added to both |
| Next year's tax bill | Worst case only | Worst case only |

The dollar figures and the 70% are planning estimates in the `COST_` constants of `diligence.py`, not quotes. Repairs, surviving government liens, and bidding past the price are not counted. The loan is the amount on the report, not the payoff. Nothing yet tells Hestia that a building still stands, so that stays on Still open for every deal.

| Verdict | When |
| --- | --- |
| Worth a title check | The worst case is at or under 70% of the value, with no flag |
| Numbers fit, danger open | The same, with a flag |
| Only if the title clears | The best case fits and the worst does not |
| Pass at this price | The best case is over 70% |
| Can't say yet | No value, not enough data, or a foreclosure with no loan report |

Also is the second loan-and-tax report. It does not change the band, and it does change the cost. "Disagrees" means one side says a loan is open and the other does not, the loan amounts differ by more than 10%, or RealEstateAPI marks a delinquency ATTOM does not. RealEstateAPI marked no delinquency on any of the 98 sales, including the tax deeds, so its silence is not read as a no. "Parcel record is …" means the county parcel id came back as a unit the auction list did not name. "Not this door" means the report is a different address. "No record for this address" means the lookup missed.

The cost block uses both reports. When they differ on a loan, the higher amount sets the worst case. On a tax deed that changes nothing, because the deed clears private mortgages. A report for another door or unit is not used.

On the 98 sales that were on the desk when this was pulled, the first comparison counted 45 disagreements. 22 of them were only about delinquency, which is the silence above. Of the 23 loan disagreements, ATTOM showed no loan and RealEstateAPI showed one 18 times. 16 of those were foreclosures. A lawsuit to foreclose usually means a loan exists, so ATTOM's "No open loan" should not be read as proof. It is not yet known why it misses them. `parse_attom` reads only `FirstConcurrent`, which may cover only the loan recorded with the last sale. No county record has checked either report yet.

About 160 lookups, about $16 of the $200 credit. The balance left at the vendor was not read back. A rescore keeps the stored report and does not buy it again.

## What past sales showed

`history.py` pulled 10,339 closed or canceled auctions from the public RealAuction pages, 10/30/2025 to 10/30/2026. 3,381 sold, 1,549 of them to outside buyers. 1,132 of those outside sales had a state tax roll value on file, and those built the `MARKET` table in `diligence.py`. 245 auctions ended with the bidder walking away.

| What the test found | What changed |
| --- | --- |
| 139 of 140 tax deeds looked fine at the opening bid, and 98% sold at least 5% over it | A verdict now says it holds at this price. The card adds what buyers typically paid |
| Buyers typically paid 58% to 88% of the roll, by county and sale type | The ceiling line shows how often it would have won |
| A roll can sit above a real sale | The value is the lower of the roll and a confirming recent sale |
| 106 of 140 tax deeds had under 10% of the roll in the building | A land-heavy roll gets a warning and no ceiling, once scored with the new field |

The test measures what it took to win. It does not measure profit, and it has no record of loans or liens at the time of sale. The roll is today's, not the roll on the sale day. The archive holds one Broward tax deed sale and no Monroe foreclosures. Miami-Dade tax deeds and Palm Beach tax deeds use the pooled row. Lee foreclosures often sold under the judgment, so the judgment is a weak guide there.

## Providers in the score

![Providers](graphics/providers.png)

| Provider | Plan | What Hestia takes |
| --- | --- | --- |
| RealAuction | Free public calendars | Broward tax deeds and foreclosures, Miami-Dade (both on one calendar), Lee tax deeds and foreclosures. Opening bid, or the final judgment on a foreclosure. |
| County appraisers | Free | Broward `bcpa.net`, Miami-Dade PaParcelView, Lee parcel GIS. House line, just value, homestead, sales. |
| Florida Department of Revenue | Free cadastral service | Statewide just value, homestead, last sale, and a point. |
| Miami-Dade and Lee code GIS | Free | Open code cases, code liens, building violations, Lee nuisance cases. Broward has no code layer here, so that factor stays unchecked. |
| US Census geocoder | Free | A second address and a point when the roll has none. |
| FEMA flood map | Free | Zone. Coastal V zones raise a flag. |
| Esri World Imagery | Free | The satellite on the card, and the card photo when no street photo exists. |
| Google Street View | The link needs no key. The photo uses Street View Static with `GOOGLE_MAPS_KEY` in `~/hestia/.env`, and no plan is chosen | The photo on the list and the card, loaded by the viewer's device and not stored. The date of the image is not shown, so it does not prove a building still stands. |
| ATTOM Property API | Trial key, no paid plan chosen | Expanded Profile. Open first loan, a second loan amount when present, tax bill, and delinquent year. One call per address. Judgments and the docket are not in this report. |

The ATTOM key is `ATTOM_API_KEY` in `~/hestia/.env` on the Umbrel, passed into the container by Compose. The value is not in git.

Street links on the card open the county appraiser, Google Maps, Zillow, and Realtor.com. Those pages are not fetched. Zillow refused automated requests and Realtor rate-limited them. County photo pages are not scraped.

## Plans that were not bought

The comparison was about a second loan-and-tax source, not a replacement for the county rolls.

| Vendor | Published offer | Decision |
| --- | --- | --- |
| RealEstateAPI pay as you go | $0.10 per property record, no minimum, no autocomplete. A $200 credit is in use. | Pulled for the current sale list. The Also line on the card shows it. The score still uses ATTOM. The cost block uses both. A street match often returned a different unit, so the pull prefers the county parcel id. |
| RealEstateAPI Starter | $599 a month, 30,000 credits. The published price assumes an annual term. | Not bought. |
| RealEstateAPI Growth | $1,200 a month, 150,000 credits | Not bought. |
| RealEstateAPI Pro | $2,500 a month, 400,000 credits | Not bought. |
| RealEstateAPI Enterprise | Contact sales | Not contacted. |
| RealEstateAPI free trial | $200 of credits, 14 days, no card. It does not turn into the $599 plan by itself. | This is the credit in use. |
| ATTOM after the trial | No public self-serve price was chosen | Still on the trial key. |
| RentCast | A small monthly plan, and 50 free calls a month | Not used. It does not return an open loan or a delinquent year, and 50 calls is smaller than one sale list. |
| Estated | Old free-credit offer | Not available to new customers. ATTOM acquired it in 2022. |
| OpenWeb Ninja, RealtyAPI | Listing-scrape plans | Not used. Wrong dataset. |

RealEstateAPI extras that were not turned on, because they cost more: comparable sales, skip trace, and involuntary liens. Property Search count calls also spend a credit on pay as you go, so those were not used either.

`REALESTATE_API_KEY` is in the Umbrel container. A rescore does not call RealEstateAPI again. The Also line is the stored report.

## What is still by hand

Clerk sites sit behind captchas and are not bypassed. The docket, judgments, and association liens outside the case-number guess stay on the Title checked step. Condo units often miss the county house line. A Lee row whose parcel text is the words "Property Appraiser" cannot be looked up. Hestia does not bid, does not email buyers, and does not store a buyer list yet. That work is in [FEATURES.md](../FEATURES.md).
