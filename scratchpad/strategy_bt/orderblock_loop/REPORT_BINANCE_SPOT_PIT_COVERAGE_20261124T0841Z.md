# Binance Spot 2018/2022 PIT coverage audit

**Date:** 2026-11-24 08:41 UTC  
**Scope:** Binance official public-data documentation, a small sample of official dated listing/delisting announcements, and existing local spot manifest metadata only. No archive-index request, API call, data download, price-row access, backtest, ledger/R4 edit, or other report edit was performed. Manifest entries after 2026-05-31 were excluded.

## Decision

**The spot route is lawful for purely personal, non-production historical backtesting under the currently published Vision Dataset Terms, but it does not presently establish a preregisterable 30-asset point-in-time cohort. Keep the existing 30-symbol gate unchanged.** The Binance Vision README says all symbols are supported and spot klines are monthly archives, but neither that README nor a static complete archive index enumerates every symbol-month object or proves a complete historical listing universe. The local downloaded subset has only four symbols with all twelve 2018 monthly files, so it cannot meet the 30-symbol requirement.

## Evidence

### Official archive capability and limits

- Binance Public Data documentation describes monthly and daily public-market-data files, says “All symbols are supported,” and identifies spot kline columns including open time, OHLC, volume, trade count, and taker-buy volume. This establishes the data type and archive delivery pattern, not guaranteed coverage for every symbol and month. [Official README](https://github.com/binance/binance-public-data/blob/master/README.md)
- The official helper script constructs each symbol-month URL and checks for a 404 response. That is evidence that actual month coverage must be checked file by file; it is not a static inventory. No such URL checks were made in this audit. [Official monthly download script](https://github.com/binance/binance-public-data/blob/master/shell/download-klines.sh)
- The README notes that archives can be updated after errors and documents a 2022 spot kline correction. Thus file presence alone does not prove candle-level continuity or establish which historical version an earlier backtest would have seen. [Archive update notes](https://github.com/binance/binance-public-data/blob/master/README.md#updates)

### Local manifest subset, metadata only

Filtered `/Users/user/CODE/trading_data/external/crypto/MANIFEST.csv` strictly to `spot_klines_1m` paths, parsed symbol and `YYYY-MM` from paths, and discarded months after 2026-05 before counting. No row values or data files were opened.

| Year | Symbols with any monthly files | Symbols with all Jan–Dec files | Symbol-month files present |
|---|---:|---:|---:|
| 2018 | 8 | 4 | 79 |
| 2022 | 25 | 23 | 286 |

The full-year 2018 set is BNBUSDT, BTCUSDT, ETHUSDT, and LTCUSDT. All four also occur in the 2022 full-year set. The manifest subset contains 33 symbols and 2,249 in-scope symbol-month files total. These are **file-month counts only**; they do not prove complete minute candles, row continuity, or the whole exchange’s available archive. The local subset does not have 30 full-year 2018 symbols.

### Point-in-time universe evidence

- Binance’s current public spot `exchangeInfo` is described by the official docs as current exchange metadata; a current symbol list cannot prove what was listed and tradable at each historical date. The official archive downloader likewise obtains current symbols before trying archives, not a historical constituent snapshot. [Official API docs](https://github.com/binance/binance-spot-api-docs/blob/master/rest-api.md#exchange-information), [official downloader docs](https://github.com/binance/binance-public-data/blob/master/python/README.md)
- Binance does publish dated, pair/asset-specific listing and delisting notices. For example, its 2018-10-09 delisting notice says trading in all pairs for BCN, CHAT, ICN, and TRIG would cease on 2018-10-12; an official USDC notice also records opening dates and specific pairs in November 2018. Such notices prove individual events, not that the captured notice set is exhaustive enough to reconstruct the entire exchange universe without omissions. [2018 delisting notice](https://www.binance.com/en/support/announcement/detail/360017720731), [2018 USDC listing notice](https://www.binance.com/en/support/announcement/detail/360019828831)
- Therefore neither today’s active symbols nor a sample of notices establishes a point-in-time eligible population of at least 30 assets active in both 2018 and 2022. Renames, quote-asset/pair changes, delistings, and partial-year trading also need explicit identity and tradability rules fixed in the preregistration.

### License

The currently published Vision Dataset Terms grant access free of charge, apply CC BY-NC-SA 4.0, and expressly permit “algorithmic historical backtesting for purely personal non-production research.” Commercial use, live trading execution, compensated signal distribution, and commercial exploitation are excluded; redistributed derivatives require attribution and the same license. This permission fits private research only, subject to the exact current terms and any changes before a future download. [Official Vision Dataset Terms](https://github.com/binance/binance-public-data/blob/master/TERMS_AND_CONDITIONS.md)

## Relationship to the active futures work

This is a distinct spot-market possibility. Spot candles do not provide USDⓈ-M perpetual contract history or funding payments and cannot substitute for the existing 35-symbol USDⓈ-M futures cohort or relax its 2018/2022 gates. No R4 status, preregistration, code, or trial record was changed.

## Next admissible step

Before any spot pilot, separately preregister the instrument definition, point-in-time asset/pair inclusion rule, symbol-rename policy, 2018 and 2022 full-year coverage tests, 30-symbol minimum, and archive version/checksum handling. Then use only an allowed official metadata inventory procedure to confirm every required symbol-month object and verify downloaded file integrity before opening price rows. If an exhaustive PIT listing record and 30 qualifying assets cannot be proven, classify this path as insufficient for the required cohort; do not replace missing assets with later survivors or count partial years as full years.

## Verification limits

- No remote bucket/index listing or per-symbol archive URL request was made, so the complete live archive’s 2018/2022 coverage remains **unconfirmed**.
- No row-level continuity or candle quality check was made.
- The local manifest is a selected 33-symbol collection, not a complete historical Binance spot universe.
- Official dated announcements were sampled as proof that event-specific records exist; announcement completeness was not established.
