# Hestia

A private desk for one person working South Florida auction and tax-deed sales. It collects the next sale lists, checks each parcel against public records, and puts a short card on the ones worth opening.

The name is Hestia, the Greek goddess of the hearth and home. This is not a marketplace and not a product for other investors.

The desk runs on a home Umbrel, at `umbrel.local:18080` and at [hestia.trading](https://hestia.trading) behind Cloudflare Access. The same machine runs a Bitcoin node and ckpool. Hestia does not join them.

How the pieces fit, which providers are in the score, and which plans were not bought: [docs/stack.md](docs/stack.md).

![Where Hestia runs](docs/graphics/architecture.png)

## What it does

1. Pull upcoming tax-deed and foreclosure lists for Broward, Miami-Dade, and Lee.
2. Score each parcel from the county roll, nearby sales, code cases, flood, and an ATTOM loan and tax report.
3. Show a card: cause, worth, room, danger, what is still open, the loan, and the tax bill.
4. Track the few deals that are pursued, from title check through a buyer.

Collier tax deeds are in person and are not collected. The court docket is still a manual check. Listing sites are links, not data feeds.

## Run it

On this machine:

```bash
python3 app.py
```

Open http://127.0.0.1:8080. Deals are stored in `data/hestia.db`.

On the Umbrel, from `~/hestia`:

```bash
docker compose up -d --build
```

`./deploy.sh` runs the tests, syncs this app, rebuilds only the hestia container, and publishes an Android update when the phone app changed. API keys stay in `~/hestia/.env` on that machine. They are not in this repo.

## Layout

```
app.py            the desk and the JSON API
deals.py          SQLite
sources.py        RealAuction calendars
diligence.py      research and the score
static/           the web desk
mobile/           the Android app (Expo)
docs/stack.md     stack, providers, and plans
PRODUCT.md        who it is for
FEATURES.md       what to build next
DESIGN.md         the visual system
```
