# Divergence study input-data audit

Audit date: 2026-11-18
Market outcomes/signals inspected: no
Database opened: SQLite read-only (`mode=ro`)
Input: `chart_predictor/data/vision_pit_dev_sample.sqlite`

## Frozen file and candle inventory

- File size: 28 GiB (filesystem listing: 28G).
- SHA-256: `bb64efa272bab6c5bed258ec7284f9212165c8912cfcd824f51863ae5d88fafa`.
- `candles`: 241,389,061 one-minute rows across 86 symbols; timestamp range 2021-01-01 00:00 UTC through 2026-10-31 23:59 UTC.
- `archive_manifest`: 5,522 monthly records; 86 symbols; manifest month range 2021-01 through 2026-10.
- 75 symbols have at least 1,764 calendar days between their first and last row. Of these, 40 have a complete one-minute sequence over that span; 35 have missing minute rows. Across all 86 symbols, 38 have at least one missing minute relative to the first-to-last timestamp span. No off-minute timestamps were found in the per-symbol aggregate.
- The table primary key `(symbol, open_ms)` prevents duplicate symbol-minute rows.

## Consequences for the frozen study

The dataset has enough calendar span and at least 20 structurally continuous symbols to attempt the five fixed walk-forward windows, after 4-hour indicator warm-up. This is a feasibility result only; it does not establish adequate signal counts or successful walk-forward performance. Keep all 86 symbols in the predeclared archive universe where candle history is available; never select symbols using outcomes. Mark every emitted signal whose required execution path intersects a missing minute as unresolved/inconclusive, include it in coverage accounting, and do not call it a resolved win. Report the 40 gap-free long-span symbols as a data-quality stratum, not as an outcome-selected universe.

The archive is not proven to be a complete point-in-time universe of every listed/delisted perpetual contract. The findings support conclusions only for this frozen 86-symbol archive sample. Symbol listing/delisting and contract-incarnation survivorship remain material limitations and must be explicit in every result.

This audit did not inspect OHLC outcomes, build divergence signals, or access any sealed performance labels. No strategy result is available yet.
