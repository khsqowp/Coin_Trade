# R005 handoff

## Current state

- Added a single proposed macro-to-micro orderbook-replenishment candidate; it is not a performance-tested strategy.
- Existing L2 pilot raw file passed an independent SHA-256/record/JSON/newline check. The capture is two symbols and approximately one hour; no reconnect occurred naturally.
- Follow-on implementation added an offline-only deterministic reducer at `scripts/research/crypto_l2_compact.py` and three focused tests. Full `chart_predictor/tests`: 228 passed, one environment warning. No live feed was started.
- Reducer replayed the immutable 208,224-record pilot twice; both outputs matched SHA-256 `57f8bcf1694167f779f2c007f94e7eee6ecfed7b502a1880b45de52f343c6362`, with two sequence-valid snapshots and zero replay invalidations. It emitted 208,163 rows (104,508,285 bytes) from 230,845,049 source bytes. Strategy metrics remain null.
- Streaming Zstandard 1.5.7 reduced the compact sample to 9,942,735 bytes (9.51% of compact size). A linear 20-symbol/year projection is about 0.871 decimal TB/year. That is an extrapolation from one two-symbol hour, not a measured production rate; the output artifact was temporary and is not committed.
- The reducer is an engineering prototype, not the required feature/path recorder: it stores a compact row per depth update and eligible trade, and its storage projection is still unverified. The R005 data gate remains closed.
- The five R005 documents were committed and pushed in `0f6fa2870b320da5e257cd643424728ff0a205eb`. The implementation and test changes from this follow-on are not yet committed.
- The raw capture hash is in `manifest.json`. The 20-symbol raw-size projection is explicitly labeled as linear extrapolation and is not a measured rate.
- Zstandard 1.5.7 streaming compression reduced this sample to 44,188,758 bytes (19.14% of the original); the estimated 20-symbol year remains about 3.87 decimal TB at that sample ratio. No compressed file was written.

## Next implementation increment

1. Extend the offline reducer into a bounded feature/path ledger that aggregates aggressor quote volume into UTC-aligned, non-overlapping 10-second windows and preserves depth minima/replenishment plus executable quote paths without retaining each raw event. Make the watermark/late-event policy explicit; preserve update IDs, event and receive timestamps, counts, gap/reconnect flags, and rolling hashes.
2. Preserve enough 1-minute bid/ask OHLC and event-order information to resolve target/stop paths conservatively. Save top-five executable depth at candidate entry/exit events for fixed-notional cost estimation; do not claim fills from midprice alone.
3. Run synthetic unit tests for buy/sell aggressor classification, depth consumption/replenishment, two-second timing, missing sequence rejection, gap invalidation, UTC aggregation, no future-data use, and deterministic replay. Replay the existing pilot only to verify parser/feature output, not to estimate signal quality.
4. Measure feature/path storage and deterministic replay on bounded local captures. This prototype's current ~0.871 TB/year 20-symbol extrapolation is only a sample projection and is not accepted as proof of sustained storage capacity. Do not start long-running collection until the aggregate recorder's hard cap, recovery, and capacity tests pass.
5. Freeze remaining calibration/sample-count/cost/access decisions and complete the checklist in `plan.md`; only then register a performance study.

## Separate equity track

KR and US stock/ETF performance sweeps remain blocked by point-in-time universe, inactive/delisted history, corporate actions, data rights, and (for US) a verified licensed dataset. Existing exposed cohorts must not be retuned. The missing user-controlled gate is to confirm an existing qualifying license or authorize the relevant registration/purchase path; no account, contact, purchase, or terms acceptance was performed.
