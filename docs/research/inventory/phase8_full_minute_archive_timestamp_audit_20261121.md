# Phase 8 — Binance minute archive timestamp-grid audit

Audit date: 2026-11-21. Scope was timestamp columns and file coverage only;
no signal features, outcomes, or strategy scores were read or computed. The
NAS source was opened read-only at
`/Volumes/home/mac/CODE/trading_data/external/crypto/binance`.

## Inventory and clean cohort

| Dataset | Symbol directories | Files in 26-month window |
|---|---:|---:|
| Spot 1m OHLCV | 33 | 858 present / 4 missing |
| USD-M perpetual 1m OHLCV | 35 | 910 |
| USD-M mark-price 1m | 35 | 910 |
| USD-M funding | 35 | 906 present / 4 missing |

Thirty-two symbols have all four monthly dataset files from 2024-09 through
2026-10 (832 symbol-months per dataset; 3,328 files total). This is file
presence, not proof every file has complete observations. For the price-series
minute-grid comparison, the 32-symbol cohort from 2024-10 through 2026-10
contains 25 months with complete, aligned spot and perpetual contract opens.
The shared mark-price gap on 2026-06-29 must be excluded from any three-price
comparison. The 2024-09 partial-listing month is also excluded from the clean
aligned cohort.

## Timestamp checks

The read-only audit loaded timestamp fields, normalized spot `open_time` from
microseconds to milliseconds where applicable, and checked strict 60-second
increments, expected calendar grids, and exact per-symbol/per-month
spot/perpetual/mark timestamp-array equality. Totals read were 37,392,060 spot
rows, 39,848,385 perpetual rows, 39,798,112 mark-price rows, and 91,685
funding rows. Across the full symbol union, 90 symbol-month price-array
comparisons failed; this includes symbols without a matching spot archive and
known partial/incomplete months. The complete-file intersection has 32 symbols
across all 26 requested months (832 symbol-months); file presence is not
completeness proof.

| Dataset | Files failing the checked grid | Finding |
|---|---:|---|
| Spot 1m OHLCV | 2 | POLUSDT 2024-09 is partial (25,320 rows, starts 2024-09-13 10:00 UTC); TONUSDT 2026-06 has 41,940 rows. Four TON spot files are missing in 2026-07..10. |
| USD-M perpetual 1m OHLCV | 1 | POLUSDT 2024-09 is partial (25,185 rows, starts 2024-09-13 12:15 UTC). |
| USD-M mark-price 1m | 36 | Thirty-five symbol-month files have a shared 1,440-minute gap on 2026-06-29; POLUSDT 2024-09 is also partial (25,312 rows). |
| USD-M funding | 3 | Three 2026-06 timestamp steps are 8 hours while both adjacent `funding_interval_hours` labels say 4: ENAUSDT, POLUSDT, TIAUSDT. Four TON funding files are missing in 2026-07..10. |

Within the 32-symbol complete-file intersection, spot and perpetual timestamp
arrays match in every month from 2024-10 through 2026-10 (25 months). Mark data
differs in 2026-06 for all 32 symbols because of the missing day. Funding also
has the three interval-label inconsistencies above. `calc_time` semantics
remain unverified: even a valid timestamp step does not establish the first
time a rate was knowable or chargeable.

## Allowed conclusion and remaining limits

- The 32-symbol 2024-10..2026-10 cohort can support price-only development on
  complete spot/perpetual minute grids, subject to separate OHLC/content,
  source-hash, and point-in-time-universe validation.
- Any mark-price comparison must exclude 2026-06-29 for all 32 symbols or use
  an independently validated replacement. Do not interpolate the gap.
- This is an exposed historical archive; it is not untouched OOS or forward
  evidence. It does not establish bid/ask, fills, slippage, liquidation paths,
  funding publication timing, survivorship safety, or data licensing.
- This audit did not inspect candle values beyond timestamp fields and did not
  authorize strategy scoring. Phase 9 remains blocked because there is no
  individually validated Core strategy.

The audit is reproducible with
`/opt/anaconda3/bin/python3 scripts/research/audit_crypto_minute_archive.py --root /Volumes/home/mac/CODE/trading_data/external/crypto/binance --start-month 2024-09 --end-month 2026-10 --output docs/research/inventory/crypto_minute_archive_timestamp_audit_20261121.json`.
It reads timestamp columns, checks calendar grids and declared funding intervals, and emits each file status. The
full run did not compute file hashes (`--sha256` was not passed); no hash
integrity claim is made. Verify source hashes before scoring. The result is
`crypto_minute_archive_timestamp_audit_20261121.json` in this directory.
