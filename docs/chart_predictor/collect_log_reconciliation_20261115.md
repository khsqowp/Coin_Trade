# Candle collection log reconciliation — 2026-11-15

Read-only comparison of per-symbol logged inserted-row counts with the current `candles.sqlite` counts.

- `collect.log`: 100 symbol entries, 4,276,818 reported inserts.
- `collect120.log`: 98 successful symbol entries, 12,562,206 reported inserts.
- Exact per-symbol count matches: 97/100.
- Mismatches: BTCUSDT, ETHUSDT, HUSDT. BTC logged 20 in `collect.log`; ETHUSDT and HUSDT have `ConnectionError` in `collect120.log`.

## Interpretation

The counts match exactly for 97 symbols, which is consistent with these two collection runs accounting for most rows in the DB. It does not prove row-key lineage: the collector logs newly inserted counts, prior rows may already have existed, and failed runs can leave earlier committed pages in SQLite. The logs contain no request time bounds, per-page response hashes, or complete resume manifest. Preserve this uncertainty instead of treating the row totals as provenance proof. Exact per-symbol rows, first/last timestamps, deltas, and failures are listed in the JSON report.
