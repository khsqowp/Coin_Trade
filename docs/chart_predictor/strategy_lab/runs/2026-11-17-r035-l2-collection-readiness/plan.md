# R035 — 20-symbol public L2 collection readiness

## Question

Can the local collector sustain synchronized public USD-M depth-diff and aggregate-trade capture for a 20-contract cohort, with bounded runtime/storage and auditable integrity, before any prospective L2 strategy test is designed?

## Fixed scope

- Public Binance endpoints only; no credentials, account calls, order placement, signal generation, or live/manual-trading recommendations.
- Cohort: BTC, ETH, BNB, SOL, XRP, ADA, DOGE, TRX, AVAX, LINK, BCH, LTC, DOT, UNI, NEAR, ATOM, ETC, FIL, APT, ARB — each quoted in USDT.
- Verify current contract metadata, public depth@500ms and aggTrade WebSocket connectivity, and REST depth snapshot availability.
- Capture a 120-second feasibility sample; hard runtime 180 seconds, startup timeout 30 seconds, output ceiling 256 MiB.
- Local ignored raw capture only. No large raw market data committed.
- This is a collector/data-quality pilot, not strategy training, backtest, OOS, or evidence of predictive edge.

## Verification gates

1. All 20 are active USDT perpetual contracts at preflight time.
2. Both combined public WebSocket streams open and all REST snapshots return valid update IDs.
3. Capture completes within limits; every symbol's local book validity coverage is at least 99%.
4. Segment SHA-256 and record count verify against the manifest; no unexpected reconnects or missing trade-ID jumps are reported.
5. Report reconnect recovery as untested unless an injected or natural reconnect actually occurs.

## Candidate research gate

The prospective L2 hypothesis is not yet registered. Before collecting any data that could be called OOS, write a separate immutable protocol specifying observable book state, depletion/refill event, direction, entry timing, stop/invalidation, target, bar/clock deadline, symbol/event deduplication, execution costs, baselines, and the sealed forward interval. Do not use this feasibility sample as OOS. The user-approved pass rule remains target-first precision ≥80% on ≥200 non-overlapping OOS events; deadline-close direction accuracy is separate.
