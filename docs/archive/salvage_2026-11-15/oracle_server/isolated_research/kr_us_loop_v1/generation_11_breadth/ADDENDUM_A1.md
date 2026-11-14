# Addendum A1 — auditability and metric implementation details

Date: 2026-11-06 (Asia/Seoul)

This addendum makes no change to the frozen signal, sector universe, threshold, execution timing, prices, costs, benchmark, or observation windows. Following independent review before any market-price read, it clarifies three implementation details and strengthens failure evidence:

1. **Sample Sharpe:** daily return volatility uses sample standard deviation (`ddof=1`) to match the existing candidate metric convention. A single observation yields Sharpe 0 and is not interpreted.
2. **Activity reporting:** number of evaluated breadth closes, risk-on closes, entries, signal-driven exits, and final terminal liquidation are reported separately. Turnover units are the sum of absolute exposure changes including initial entry and terminal liquidation; these counts are not mislabeled as signal count.
3. **Durable attempt lifecycle:** validate a unique run ID and create an append-only JSONL `STARTED` record followed by `flush`+`fsync` before data hashing/loading. Keep a `STARTED` manifest immediately. On any exception, append+fsync `FAILED` and preserve/update the manifest with the failure. On success, preserve the same manifest path with completed results, then append+fsync `FINISHED`. A run ID whose artifacts already exist is rejected; no prior attempt is overwritten.
4. **Date-index gate:** every input must use a pandas `DatetimeIndex`, not merely an ordered/unique index, before any signals or performance calculations. This makes the preregistered date partition/serialization requirements a fail-closed data gate.
5. **Pandas compatibility:** finite/positive matrix checks use `DataFrame.to_numpy(dtype=float)` plus Python scalar checks, not `DataFrame.applymap`, which is not available in all supported pandas releases. No data values or strategy decisions change.

The code/tests and this addendum are re-frozen in `FREEZE.json` under candidate revision `GEN11-US-SECTOR-BREADTH-200SMA-5OF9-SPY-CASH-A1`. All results remain exploratory. This addendum is required to be reviewed before any performance-data access.
