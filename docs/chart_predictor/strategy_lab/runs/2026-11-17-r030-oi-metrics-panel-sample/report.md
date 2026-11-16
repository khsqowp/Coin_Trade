# R030 — fixed broad-panel OI metrics archive quality sample

**Decision: OI is worth continuing as a research input, but this remains a NO-GO for strategy scoring.** Across a fixed 740 symbol-day sample, all 720 available ZIP/checksum pairs passed publisher SHA-256 verification, but five archives were structurally incomplete and 20 requested symbol-days had no archive. The OI field itself was nonblank and finite on every row present. This is source-quality evidence, not evidence that OI predicts direction or that the user's 80% target-first gate is achievable.

## Frozen scope and execution

- The plan fixed 37 OHLCV seed symbols and 20 quarterly-spaced dates from 2021-12-01 through 2026-09-01 before downloads: **740 symbol-days**. This is an availability-selected cohort, not a point-in-time futures universe.
- For all 740 requested days, the public archive ZIP and `.CHECKSUM` were checked. Missing archives were retained as missing; no substitute dates, symbols, or REST values were used.
- Of 740 requests, **720 ZIPs and 720 checksums were HTTP 200**, **20 pairs were both HTTP 404**, and there were no mismatched-presence or transport-error cases. All 720 available ZIPs matched the publisher SHA-256.
- The available files contained **205,928 rows** against **207,360 expected slots**. **715 archives** had all 288 expected 5-minute timestamps. Five checksummed archives had only one or two rows, yielding **1,432 missing grid slots** in total:

| Symbol | UTC date | Rows | Missing 5m slots |
|---|---:|---:|---:|
| ALPHAUSDT | 2025-12-01 | 1 | 287 |
| BALUSDT | 2025-06-01 | 1 | 287 |
| BLZUSDT | 2025-03-01 | 2 | 286 |
| ICXUSDT | 2026-09-01 | 2 | 286 |
| RENUSDT | 2025-03-01 | 2 | 286 |

- The 20 absent requests were ALPHAUSDT on 2026-03-01, 2026-06-01, and 2026-09-01; BALUSDT on 2025-09-01, 2025-12-01, and 2026-03-01, 2026-06-01, and 2026-09-01; BLZUSDT on 2025-06-01, 2025-09-01, 2025-12-01, and 2026-03-01, 2026-06-01, and 2026-09-01; and RENUSDT on 2025-06-01, 2025-09-01, 2025-12-01, and 2026-03-01, 2026-06-01, and 2026-09-01. A 404 does not alone establish a contract's delisting date.
- Across all rows in available archives, `sum_open_interest` and `sum_open_interest_value` had **zero blank and zero nonfinite/nonnumeric cells**. No duplicate timestamps or off-grid timestamps were found. Other fields were much less complete: 31,991 blank `count_toptrader_long_short_ratio`, 31,980 blank `sum_toptrader_long_short_ratio`, 10,690 blank `sum_taker_long_short_vol_ratio`, and 8 blank `count_long_short_ratio` cells. These fields cannot be silently substituted for OI.

## Interpretation and next gate

- Checksums establish byte integrity against the publisher file, not completeness; the five tiny but checksummed archives demonstrate that distinction directly.
- The 20 absent files and ten symbols with object-index gaps/early stops in R029 require contract-announcement and first/last-trade cross-checks. The current `exchangeInfo` endpoint describes current state, not a complete point-in-time contract catalog. Official listing/termination announcements plus historical trades or candles are a stronger reconstruction path, but still do not prove every historical trading-rule change.
- OI's displayed `create_time` must not be treated as contemporaneously observable without a validated availability lag. Existing `create_time + 5m` alignment remains limited to the BTC/ETH samples in R026; R030 does not broaden it.
- Keep the 5 defective files quarantined and expose per-symbol/date availability masks. No imputation or backfilling is allowed. Before any candidate is preregistered, establish contract epochs and availability timestamps, then freeze rule, baseline, fees/slippage, stops/targets/deadlines, and untouched OOS boundary.
- The user's crypto pass criterion remains OOS target-first rate ≥80% over at least 200 non-overlapping events. Deadline-close direction accuracy is a separate report. **No signal/outcome was generated; qualified OOS events remain 0.**

The complete 740-entry outcome/hash manifest is `archive_manifest.json`. Raw ZIPs and the detailed temporary parser output remain outside Git at `/private/tmp/r030-oi-metrics-panel-sample/`.
