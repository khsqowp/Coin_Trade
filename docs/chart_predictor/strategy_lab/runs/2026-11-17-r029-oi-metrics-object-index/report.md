# R029 — USD-M daily metrics object-index coverage

**Decision: proceed to a bounded content/timestamp audit, not a strategy trial.** The public object index shows broad daily OI-metrics archive presence for much of the 37-symbol OHLCV seed cohort from December 2021 onward. It does not establish valid archive contents, point-in-time contract eligibility, the time OI became observable, executable costs, or strategy performance.

## Scope and method

- Queried the public S3-compatible Binance Vision bucket index at `https://s3-ap-northeast-1.amazonaws.com/data.binance.vision/` with prefix `data/futures/um/daily/metrics/{symbol}/`.
- The symbol cohort was derived read-only from `chart_predictor/data/vision_pit_dev_sample.sqlite`: 37 symbols with complete expected 1-minute monthly candle row counts in each of 70 months, 2021-01 through 2026-10.
- Followed all continuation tokens and retained keys ending in `.zip` containing `-metrics-`. The audit made 146 paginated list requests for 37 symbols. It did not download archive bodies, request credentials, or place orders.
- Counted calendar dates from object names and month buckets. Object-index presence is not a checksum/content validation.

## Findings

- The index returned **65,363 daily metrics ZIP keys** across the cohort. The key-date span is **2020-09-01 through 2026-11-15**; BTCUSDT begins in 2020-09, while all 36 other symbols begin on 2021-12-01.
- No metrics ZIP keys were listed for the 36 non-BTC symbols in **2021-01 through 2021-11**. Therefore the 37-symbol OHLCV panel does not translate into a 37-symbol OI-metrics panel over the full price-history interval.
- **27 of 37 symbols** have a date-contiguous sequence of daily object keys across their observed first-to-last date span: BTCUSDT and 26 symbols from 2021-12-01 through 2026-11-15, each with 1,811 keys. BTCUSDT has 2,267 keys from 2020-09-01 through 2026-11-15.
- Ten symbols have incomplete or shorter observed sequences: ALPHAUSDT (ends 2026-01-23), BALUSDT (ends 2025-06-05), BLZUSDT (182 missing dates within its first-to-last span; ends 2025-09-09), ICXUSDT (9 missing dates; ends 2026-10-15), RENUSDT (1 missing date; ends 2025-03-10), RUNEUSDT (1 missing date), SNXUSDT (1), THETAUSDT (1), XMRUSDT (2), and XTZUSDT (1).
- Monthly bucket presence is broader than daily completeness. For example, 37 symbols have at least one key in each month from 2021-12 through 2025-03; that is not evidence that every day in each month is present.

## Limits and next gate

1. Download a fixed, small set of representative daily archives and verify publisher checksums, CSV row counts, timestamp grid, OI nulls/finite values, duplicate dates, and internal missing days. Keep this separate from key-existence counts.
2. Expand content checks only after the representative audit passes; retain per-symbol/date/field availability masks and quarantine every failed archive.
3. Independently establish each contract's listing/termination/ticker identity and the OI observation-availability timestamp. Existing `create_time + 5m` evidence is limited to prior BTC/ETH samples and is not generalized by this index audit.
4. Only after those source gates pass, freeze a distinct candidate and a no-OI baseline, costs, stops/targets/deadlines, and untouched OOS boundary. Crypto promotion remains target-first precision ≥80% with at least 200 non-overlapping OOS events; deadline-close direction accuracy is reported separately. Current qualifying signal count remains zero.

This was a source-coverage audit, not a registered or scored strategy experiment. It must not be counted as an outcome trial.
