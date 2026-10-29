# Project Hestia

A private tool built for *personal use* to make finding discounted / government / auction properties and quickly flipping them to cash buyers as smooth as possible.

Named after *Hestia*, the Greek goddess of the hearth and home.

## Goal

Find good deals → Secure them (under contract or buy) → Package and assign/sell to a cash buyer or wholesaler with minimal friction.

This is *not* a public marketplace. It is a personal operating system for one investor (you).

## Core Workflow

1.⁠ ⁠Ingest deals from government auctions, tax sales, seized properties, and other discounted sources
2.⁠ ⁠Quickly qualify deals (price, estimated value, red flags, potential spread)
3.⁠ ⁠Track deals through stages (Watching → Under Contract → Assigned → Closed)
4.⁠ ⁠Package deals cleanly and send to your buyer list
5.⁠ ⁠Generate basic contracts / assignment paperwork

## Tech Stack (Initial Recommendation)

•⁠  ⁠*Backend / Scripts*: Python
•⁠  ⁠*Frontend* (optional later): Next.js or simple Streamlit / FastAPI + HTMX
•⁠  ⁠*Database*: SQLite (start simple) → PostgreSQL later if needed
•⁠  ⁠*Hosting*: My Umbrel server at `umbrel.local` (local first). Cloud (Railway / Vercel / VPS) only if this outgrows the home server.

## Project Structure


project-hestia/
├── README.md
├── PRODUCT.md
├── FEATURES.md
├── ARCHITECTURE.md
├── ROADMAP.md
├── DATA_SOURCES.md
├── src/
│   ├── data/
│   ├── analysis/
│   ├── tracking/
│   └── buyers/
├── data/                  # local deal storage
└── templates/             # contract & deal package templates


## Local Server

Hestia runs as its own Docker container on the Umbrel at `umbrel.local`. The deal database is the `data/` folder next to this repo, on that server's disk. The container does not join the Bitcoin node or the pool, does not mount their data, and does not get the Docker socket. It is capped at a quarter CPU and 128 MB so it cannot crowd them out. Nothing here is meant for a public host.

## Getting Started

This is the Phase 1 deal list from `FEATURES.md`: add a deal, scan the spread, filter the list, and move the status.

```bash
python3 app.py
```

Open http://127.0.0.1:8080. Deals are stored in `data/hestia.db`.

On the Umbrel, clone this repo into its own folder, such as `~/hestia`, not into the node or pool directories. From that folder:

```bash
docker compose up -d --build
```

Open http://umbrel.local:18080. The database file is `data/hestia.db` in that folder. `docker compose down` stops only this container.

Spread is estimated value minus asking price. Repairs, red flags, and the buyer list come after this list is in real use.

---

Built for personal use first. Expand later only if it proves valuable.
