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

The timestamp audit is reproducible with:

```bash
/opt/anaconda3/bin/python3 scripts/research/audit_crypto_minute_archive.py --root /Volumes/home/mac/CODE/trading_data/external/crypto/binance --start-month 2024-09 --end-month 2026-10 --output docs/research/inventory/crypto_minute_archive_timestamp_audit_20261121.json
```

The separate full-window SHA-256 run was:

```bash
/opt/anaconda3/bin/python3 scripts/research/audit_crypto_minute_archive.py --root /Volumes/home/mac/CODE/trading_data/external/crypto/binance --start-month 2024-09 --end-month 2026-10 --output docs/research/inventory/crypto_minute_archive_sha256_audit_20261121.json --sha256
```

It hashed all 3,580 present monthly files (4,631,097,912 bytes); 3,328 files
(4,305,562,265 bytes) belong to the 32-symbol complete-file intersection.
All 3,580 files had unchanged size, mtime, and inode during their individual
hash read. Eight expected files are missing. This is a FAIL data-quality
snapshot, not a clean-data approval. Local SHA-256 values create reproducible
fingerprints but are not Binance-published checksums or proof of source
authenticity. The output is `crypto_minute_archive_sha256_audit_20261121.json`.

## Candle-value invariant audit

The full-window value pass read all present OHLC price rows: 37,392,060 spot,
39,848,385 USD-M perpetual, and 39,798,112 mark-price rows. It checked finite
positive OHLC, the high/low envelope around open and close, nonnegative finite
base and quote volume, nonnegative integer trade count, and close time exactly
59,999 milliseconds after normalized open time. The close-time comparison
uses integer unit conversion so microsecond spot timestamps are not rounded
through floating point. **No checked price row violated these value rules.**

The overall value-audit status remains FAIL because it also carries the
archive's timestamp/calendar/funding failures: 90 full-union price timestamp
array mismatches, partial spot/perpetual months, the 35 shared mark-price
missing-day gaps, three funding interval-step anomalies, and eight expected
missing files. The OHLC result is structural consistency only; it does not
verify market-price truth against Binance, upstream checksums, licensing,
point-in-time universe membership, execution costs, or funding availability.
Full per-file output: `crypto_minute_archive_ohlc_audit_20261121.json`.

Reproduce the value pass with:

```bash
/opt/anaconda3/bin/python3 scripts/research/audit_crypto_minute_archive.py --root /Volumes/home/mac/CODE/trading_data/external/crypto/binance --start-month 2024-09 --end-month 2026-10 --output docs/research/inventory/crypto_minute_archive_ohlc_audit_20261121.json --ohlc-values
```
