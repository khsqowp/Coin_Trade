# Binance USD-M metrics archive sample audit — 2026-11-20

## Decision

**Structural sample: PASS for the fixed sample. OI feature timing/provenance: UNRESOLVED. No strategy scoring authorized.** The preregistered one-day OI archive/REST comparison matched at the same timestamp, but the follow-up in [`usdm_oi_timestamp_followup_20261120.md`](usdm_oi_timestamp_followup_20261120.md) found exact `T+5m` matches in 96 other symbol-days. These results conflict; neither a global same-time mapping nor a global +5-minute shift is justified. Neither comparison establishes historical first-availability or publication latency.

## Fixed sample and integrity results

The sample was frozen in `PREREG_USDM_METRICS_SAMPLE_AUDIT_20261120.md` before downloads. It covered the 36-symbol cohort on five fixed in-period dates, two boundary-diagnostic dates outside the study end, and neighbors of nine previously inventoried missing daily files. The sample excluded the already-listed missing objects themselves.

- 268 requested ZIP/checksum pairs: **268/268 checksum and structural PASS**; total ZIP payload 3,114,735 bytes.
- Every file contained 288 rows. Sampled `create_time` values were unique and on a 5-minute UTC grid; no adjacent sampled daily pair shared a timestamp across 72 adjacent-pair checks.
- All OI numeric fields were non-null in the sample. Two nulls occurred only in `sum_taker_long_short_vol_ratio` (IMXUSDT 2026-06-25 and THETAUSDT 2026-05-30); they are counted, not filled.
- The nine pre-inventoried missing daily ZIPs remain missing; this sample did not attempt to repair them.
- The audit script preserves verified raw samples and publisher checksum files under `/private/tmp/cointrade-oi-sample-audit-20261120-v2`. Its full timestamp/hash manifest is `audit.json`; the compact `audit.csv` reports one row per sample file.

The two daily BTC files at the known convention boundary currently downloaded as 2026-06-24 `00:00`–`23:55 UTC` and 2026-06-25 `00:00`–`23:55 UTC`, with no repeated boundary label. This differs from the observations described in open Binance Public Data issue [#491](https://github.com/binance/binance-public-data/issues/491), whose author reported 2026-06-24 `00:05`–next-day `00:00` and a convention change on June 25. The downloaded BTC ZIPs matched the already-held sample hashes (`6bb5ab473189fa7c935b4d9a58d34b2c96cc329cd74fd6f9f17f8abc48ece649` and `56e0751dabd8108d61d1f9de86931ac68e901dad202d4dbac03173e2768be68e`). The disagreement remains unexplained; no global shift or deduplication is justified.

## Current-day open-interest alignment comparison

The preregistered supplement used BTCUSDT, 2026-11-19, and compared archived `sum_open_interest` and `sum_open_interest_value` with the public USD-M historical `/futures/data/openInterestHist` response. Binance's [USDⓈ-M market-data documentation](https://developers.binance.info/en/docs/catalog/core-trading-derivatives-trading-usd-s-m-futures/api/rest-api/market-data) documents the response timestamp as period end and limits this history endpoint to the latest month.

| Mapping from archive label T to REST timestamp | Rows matched | OI median / p95 relative error | OI-value median / p95 relative error | Result |
|---|---:|---:|---:|---|
| T - 5m | 288/288 | 0.000383 / 0.003223 | 0.000980 / 0.004114 | — |
| T | 288/288 | 0 / 0 | 0 / 0 | Exact field match |
| T + 5m | 288/288 | 0.000383 / 0.003220 | 0.000976 / 0.004050 | Preregistered +5m screen FAIL |

The same-label match means the current daily archive's OI values are identical to the REST history rows bearing the same timestamp for this one date. The preregistered +5-minute condition failed. This does **not** prove that the reported value was available to a live strategy at timestamp T, that the REST label's documented semantics are correct, or that any older date has the same convention. It cannot resolve the discrepancy with issue #491's independent snapshot polling for 2026-06.

Raw comparison inputs and response metadata are preserved at `/private/tmp/cointrade-oi-rest-alignment-20261120`. Archive SHA-256: `c07582aa5421219bc49c4531718c45d2e88cb7e178d4e00a9282c92601bbb657`; REST response SHA-256: `7107c7c6fc804ebc529203d7aeaaf6691c7e4a01278bd863c6532865fccb6926`. The 2026-11-19 archive response reported `Last-Modified: Fri, 20 Nov 2026 06:38:52 GMT` and was retrieved at `Fri, 20 Nov 2026 06:51:03 GMT`. REST returned 291 rows spanning 2026-11-18 23:55 through 2026-11-20 00:05 UTC; the 288 in-day archive rows had full exact matches.

## Execution attempts and limitations

The first sample-auditor execution was invalid: its parser treated the archive's ISO UTC datetime strings as millisecond integers, and it accidentally re-requested two prelisted missing XMR dates as neighbors. It recorded 270 failed attempts, retained at `/private/tmp/cointrade-oi-sample-audit-20261120/audit.json`; it is not a finding about source data. The corrected parser accepts ISO UTC labels, preserves downloaded bytes after checksum validation, and excludes prelisted missing objects. The corrected fixed sample returned 268/268 structural passes.

The public issue is a contributor's documented observation, not Binance confirmation. The official README says daily data are published the next day, but the exact historical first-availability time of each metrics field is not captured by these tests. Binance documents the historical REST OI endpoint as latest-month-only, so it cannot independently validate the older 2023–2026 history. No raw data were repaired, shifted, or deleted. No performance backtest was run.

## Disposition and next research order

1. Keep OI-derived features **ineligible for core or live signals** while field-specific historical timing and first-availability remain unresolved.
2. If pursuing the stop-hunt/OI-contraction concept, write a new preregistration with a deliberately lagged OI feature, explicit sweep/entry/stop/target/expiry rules, and missing-day treatment. Label it a new hypothesis, not a replication of the source video.
3. Run only an exploratory M2 screen on the already-exposed 36-symbol hourly history; a positive historical result cannot qualify as OOS. Then collect append-only future paper signals if it survives costs and the frozen sample/coverage gates.
4. Do not combine it in Phase 9 unless it independently passes the core criteria on a genuinely untouched forward sample.

Reproduction:

```sh
/opt/anaconda3/bin/python3 -m pytest -q tests/test_audit_usdm_metrics_sample.py tests/test_compare_usdm_oi_archive_rest.py tests/test_hourly_return_reversal_screen.py
/opt/anaconda3/bin/python3 scripts/research/audit_usdm_metrics_sample.py --coverage-json docs/research/inventory/usdm_archive_coverage_20261120.json --inventory-json /private/tmp/cointrade-oi-archive-inventory.json --output-dir /private/tmp/cointrade-oi-sample-audit-20261120-v2
/opt/anaconda3/bin/python3 scripts/research/compare_usdm_oi_archive_rest.py --output-dir /private/tmp/cointrade-oi-rest-alignment-20261120
```

The first command passed **13 tests**. The external data downloads are read-only historical/audit inputs; no exchange order, account credential, or service change occurred.
