# Project Hestia – Product Vision

Named after *Hestia*, the Greek goddess of the hearth and home.

## One-sentence goal

Make the process of finding discounted government/auction properties and flipping them to cash buyers as fast and low-friction as possible — for me.

## Primary User

Me (the builder). This tool exists to serve my own deal flow first.

## Success Metrics (Personal)

•⁠  ⁠I can review new potential deals in under 5–10 minutes
•⁠  ⁠I spend less time hunting for properties and more time on the best ones
•⁠  ⁠Packaging a deal for a buyer takes minutes instead of 30–60+ minutes
•⁠  ⁠I close more (or better) deals because of cleaner process and faster response

## Core Principles

1.⁠ ⁠*Personal first* — Optimize for my workflow, not imaginary users
2.⁠ ⁠*Speed over perfection* — A working tool I actually use beats a polished one I abandon
3.⁠ ⁠*Data quality matters most* — Garbage in = wasted time
4.⁠ ⁠*Minimal viable everything* — Only add features that remove real friction
5.⁠ ⁠*Stay legal and clean* — Clear tracking, good records, proper contracts
6.⁠ ⁠*Lives on my Umbrel* — A separate Docker container on `umbrel.local`, also reachable at `hestia.trading` behind Cloudflare Access. Deal data sits on that disk. The Bitcoin node and the pool are left alone

## Out of Scope (for now)

•⁠  ⁠Public marketplace
•⁠  ⁠Multi-user accounts
•⁠  ⁠Complex AI agents
•⁠  ⁠Automatic bidding or fully autonomous purchasing
•⁠  ⁠Payment processing / escrow handling

The Android app is built. It uses the same API as the web desk. Stack, providers, and the plans that were not bought are in `docs/stack.md`.

## Future Possibility

If the tool becomes highly valuable for me, it can later be cleaned up and offered to a small group of other investors. That is optional and secondary.
