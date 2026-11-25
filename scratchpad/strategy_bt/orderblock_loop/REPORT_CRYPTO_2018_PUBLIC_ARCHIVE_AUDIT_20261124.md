# 2018 Crypto Public Archive Audit

**Checked:** 2026-11-24  
**Scope:** Public source documentation and archive/API availability metadata only. No strategy data was downloaded or read.

## Findings by source

| Source | Evidence checked | Finding | G relevance |
|---|---|---|---|
| BitMEX public archive | Opened `https://public.bitmex.com/` and the `?prefix=data/trade/` index. Both redirected to `https://www.bitmex.com/`, which displayed the exchange closure page. Metadata-only HTTP `HEAD` requests for plausible 2018 daily keys under `data/trade/`, `data/quote/`, and `data/funding/` returned **403**. No response bodies were read. | Current public index/object paths do not expose the requested archive. The 403s do **not** prove that historical objects never existed or are absent. Exact daily key naming for funding was not verified. BitMEX documentation still describes public `trade/bucketed` intervals (1m, 5m, 1h, 1d) and a funding-history endpoint, but metadata-only `HEAD` requests to both API paths also returned **403** after the exchange closure. The privacy notice says de-identified market/trade records are published on `public.bitmex.com` for research; it does not establish a clear onward reuse license. | Not currently usable evidence. No verified 2018 price/funding files, data completeness, or reuse rights. The SEC filing below is separate historical evidence, not proof of current access. |
| SEC filing on crypto futures data | Read the NYSE Arca filing at `https://www.sec.gov/files/rules/sro/nysearca/2021/34-93445-ex3a.pdf`. | It states BitMEX was the only platform in its comparison that existed and had data available from the CME BTC futures inception period (2017-12-17). | Supports BitMEX as a historical research lead only. It does not show that the archive is accessible now, that funding and complete OHLC are available, or that a broad multi-coin panel exists. |
| Bybit | Opened the public directory listing `https://public.bybit.com/trading/BTCUSD/`; inspected filenames only. | The first listed BTCUSD trade file is `BTCUSD2019-10-01.csv.gz`. Bybit's official API documentation describes historical funding queries with time filters but does not promise retention back to 2018. Bybit's official launch announcement says its first BTC perpetual launched on 2018-12-01. | Current public BTCUSD trade archive listing does not cover 2018. Funding-history start date remains unverified. Not a 2018 validation source. |
| Deribit | Read Deribit Insights' public funding-history description at `https://insights.deribit.com/dev-hub/deribit-perpetual-funding-python/`. | It identifies May 2019 as the first full month of funding data for the oldest BTC and ETH perpetual contracts. | Starts after 2018; cannot validate that regime. |
| OKX | Read its historical market data page at `https://www.okx.com/en-us/historical-data`. | The page lists trade history from September 2021, candles from July 2023, and perpetual funding history from March 2022. | Starts after 2018; cannot validate that regime. |

## Metadata-only checks performed

- Web page access was limited to provider documentation, directory listings, and exchange status pages.
- HTTP `HEAD` requests were sent for BitMEX archive index/prefixes, plausible 2018 daily object paths, and documented trade/funding API paths. No GET request for a price, trade, candle, or funding record was made.
- The current BitMEX public archive index redirected to the exchange closure page. Candidate S3 objects and API paths returned HTTP 403. These responses establish present access failure through the checked paths, not historical nonexistence.
- No credentials, account registration, API-key application, or access-control bypass was used.
- No strategy price records were fetched or downloaded. `TRAIN_TRIALS.csv` and other shared trial ledgers were not accessed.

## Conclusion

There is no currently verified public 2018 futures-and-funding source in this audit that can satisfy Coin_Trade's multi-coin G validation. A BitMEX BTC-only 2018 bear-regime stress check remains a possible **separate** diagnostic only if an authorized local copy is already available or official public access is restored and its fields, completeness, and usage rights are verified. Until then, count no 2018 BTC stress result and do not treat any candidate as having passed that gate. This source cannot substitute for the required multi-coin validation.

## Sources

- BitMEX public archive index: <https://public.bitmex.com/>
- BitMEX privacy notice: <https://www.bitmex.com/es/privacy-notice>
- BitMEX trade-bucketed API documentation: <https://docs.bitmex.com/api-explorer/get-trade-bucketed>
- BitMEX funding API documentation: <https://docs.bitmex.com/api-explorer/get-funding>
- SEC NYSE Arca filing: <https://www.sec.gov/files/rules/sro/nysearca/2021/34-93445-ex3a.pdf>
- Bybit BTCUSD archive listing: <https://public.bybit.com/trading/BTCUSD/>
- Bybit funding-history API documentation: <https://bybit-exchange.github.io/docs/v5/market/history-fund-rate>
- Bybit launch announcement: <https://medium.com/bybit/a-cryptocurrency-trading-platform-built-for-fairness-and-transparency-2c9bc7f85549>
- Deribit funding-history description: <https://insights.deribit.com/dev-hub/deribit-perpetual-funding-python/>
- OKX historical market data: <https://www.okx.com/en-us/historical-data>
