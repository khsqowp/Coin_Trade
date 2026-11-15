# R005 handoff

## Current state

- Added a single proposed macro-to-micro orderbook-replenishment candidate; it is not a performance-tested strategy.
- Existing L2 pilot raw file passed an independent SHA-256/record/JSON/newline check. The capture is two symbols and approximately one hour; no reconnect occurred naturally.
- `chart_predictor/tests`: 225 passed, one environment warning. No live feed was started in this turn.
- No code or source data file was changed. The worktree was clean before these five R005 documents were added.
- The raw capture hash is in `manifest.json`. The 20-symbol raw-size projection is explicitly labeled as linear extrapolation and is not a measured rate.
- Zstandard 1.5.7 streaming compression reduced this sample to 44,188,758 bytes (19.14% of the original); the estimated 20-symbol year remains about 3.87 decimal TB at that sample ratio. No compressed file was written.

## Next implementation increment

1. Build an event-to-feature pipeline that consumes synchronized depth and aggTrade events and emits compact 1-minute rows with the causal orderbook-replenishment features needed for the frozen T grid. Preserve exact first/last update IDs, event and receive timestamps, event counts, gap/reconnect flags, and rolling hashes per symbol/window.
2. Preserve enough 1-minute bid/ask OHLC and event-order information to resolve target/stop paths conservatively. Save top-five executable depth at candidate entry/exit events for fixed-notional cost estimation; do not claim fills from midprice alone.
3. Run synthetic unit tests for buy/sell aggressor classification, depth consumption/replenishment, two-second timing, missing sequence rejection, gap invalidation, UTC aggregation, no future-data use, and deterministic replay. Replay the existing pilot only to verify parser/feature output, not to estimate signal quality.
4. Measure feature/path storage and deterministic replay on a bounded local capture before extending the symbol cohort or starting a long-running process. Do not use raw JSONL, even Zstandard-compressed, for 20 symbols over weeks/months without a separately approved capacity plan.
5. Freeze remaining calibration/sample-count/cost/access decisions and complete the checklist in `plan.md`; only then register a performance study.

## Separate equity track

KR and US stock/ETF performance sweeps remain blocked by point-in-time universe, inactive/delisted history, corporate actions, data rights, and (for US) a verified licensed dataset. Existing exposed cohorts must not be retuned. The missing user-controlled gate is to confirm an existing qualifying license or authorize the relevant registration/purchase path; no account, contact, purchase, or terms acceptance was performed.
