# Crypto micro-data readiness — 2026-11-19

**Decision: historical development data exists, but no fresh confirmatory M2 panel is currently evidenced.** This was a metadata-only audit; no candle values, trade outcomes, or strategy labels were opened and no market data was downloaded.

## Local 1-minute development database

`chart_predictor/data/vision_pit_dev_sample.sqlite` contains an `archive_manifest` with 5,522 symbol-month entries across 86 symbols, covering 2021-01 through 2026-10. The manifest records 241,389,061 candle rows and 7,857,838,912 compressed source-archive bytes; 67 symbols have all 70 months, while only 74 symbols have an archive entry in 2026-10. The candle schema is 1-minute OHLCV with trade count and taker-buy base/quote aggregates.

This is a development database whose history is already exposed to prior Phase 0–8 research. Its availability does not create untouched OOS evidence. Missing symbol-months must remain missing; the aggregate manifest counts do not establish row-level continuity or independently verified source hashes.

## 20-symbol live-capture pilot

`chart_predictor/data/crypto_l2_pilots/20symbol-feasibility-20261117/20261117T060240Z-1424c652/` contains a 120-second, 20-symbol capture. The manifest records 9,760 events and a 10,569,425-byte complete segment; the manifest SHA-256 matches the captured file (`7e4c8171ddea6e95bf1a7a559ef59e864d9d0d69bb24c4562e89fbd479be588e`). The manifest reports at least 99% coverage for every requested symbol and `signals_or_orders=false`.

The pilot requested no disconnect injection, recorded no reconnect during capture, and has no observed recovery result. It proves only that a short capture completed with the stated file integrity and coverage diagnostics; it proves neither strategy performance nor recovery behavior. Two minutes is not a target-first OOS sample.

## Storage and next gate

At audit time, `/Volumes/HDD2TB/Trade` was not mounted, so no claim is made about files on that NAS or the Linux server. Do not start a long capture that can accumulate locally without its intended archive destination. Before any new prospective shadow/OOS run, restore and verify the archive destination, freeze the symbol/time contract and required fields, and set an explicit size/retention cap. Keep the already exposed 1-minute database for development only; reserve newly collected data for untouched, chronological validation.

## Source-use boundary

The current Binance Vision Dataset Terms v1.0 (updated 2026-08-26) apply when datasets are downloaded, cached, queried, or used. They grant CC BY-NC-SA 4.0 subject to the additional Vision terms and describe permitted use as personal, non-production historical backtesting and other listed non-commercial uses; they expressly exclude commercial licensing and prohibit live proprietary trading execution. The user's prior approval is historical-backtest-only. Therefore, Vision data and its derived outputs stay inside offline historical research; do not use them to generate live/manual trading signals or orders. Any production or live/manual signal path requires a separately eligible data source and its own rights review.

The official `binance-public-data` schema documents USD-M futures `aggTrades` fields including aggregate trade ID, price, quantity, first/last trade IDs, timestamp, and `isBuyerMaker`. These are the minimum raw fields for signed taker-flow reconstruction; the local 120-second capture does not provide a historical multi-regime OOS panel. See the [official data format](https://github.com/binance/binance-public-data/blob/master/README.md) and [Vision Dataset Terms](https://github.com/binance/binance-public-data/blob/master/TERMS_AND_CONDITIONS.md).

## 20-symbol archive size screen

On 2026-11-19, read-only HTTP `HEAD` requests to the official USD-M monthly `aggTrades` archive were made for the frozen 20-symbol live-capture cohort, month `2026-10`. All 20 object URLs returned HTTP 200. Their advertised compressed `Content-Length` totals **2,040,955,218 bytes (1.90 GiB)**; BTCUSDT is 400,633,308 bytes and ETHUSDT is 419,091,552 bytes. No archive body was downloaded. This is a single month only; do not extrapolate it to other months or years.

The local 1m archive manifest already contains 2026-10 price bars for 18 of these 20 symbols, so this month is not an untouched confirmatory period for the frozen cohort. The metadata check establishes that a 20-symbol event-level historical source is published and gives one-month storage scale; it does not establish a novel signal, full-history completeness, or OOS readiness. Because the NAS path remains unmounted and no distinct event-level candidate has passed review, **do not download these files yet**.

## Historical BBO limitation for conditional event-run candidate

The conditional “last three medium-notional aggTrades with one aggressor sign” candidate requires the next executable bid/ask and subsequent bid/ask path for faithful entry and target/stop evaluation. The [official Binance public-data README](https://github.com/binance/binance-public-data/blob/master/README.md) documents `aggTrades` fields but does not document a historical USD-M `bookTicker` schema. The official repository has an issue reporting many USD-M `bookTicker` archives missing from 2024-04-01 onward. In this audit, standard-path HEAD requests for BTCUSDT monthly 2026-10 and BTCUSDT/ETHUSDT daily 2026-10-31 returned HTTP 404; BTCUSDT monthly 2024-03 returned HTTP 200 with 6,712,517,585 bytes. No body was downloaded.

This is not a complete 20-symbol archive audit, but it is enough to reject the assumption that 2026 executable BBO history is available from the standard path. Do not claim exact historical BBO fills or infer a complete book dataset from `aggTrades`. A different permitted BBO source, or a pre-registered prospective live-feed capture with an available archive destination, is required before this candidate can be tested as an executable target-first strategy.
