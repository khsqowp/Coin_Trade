# Kraken Spot archive route eligibility — 2026-11-24

## Verdict

Kraken publishes an official, free, no-account/no-key-download route for historical spot OHLCVT and trade data. Its published archive format and history range could support separate Kraken Spot research for pairs that existed at the time. It cannot satisfy the existing Binance USDⓈ-M order-block 2018/2022/30-symbol or G requirements: the fixed 35-symbol universe contains at least eight assets whose Kraken trading began after 2022, so at most 27 of that set can be eligible for all of 2022; the 2018 count is lower. Rights for automated bulk acquisition and internal research transformation are not fully clear from the terms and require resolution before use. No eligibility is granted by this report.

## Official archive facts

- Kraken Support's historical OHLCVT article (last updated 2026-11-02) says the full downloadable archive covers every currency pair from that pair's first Kraken trade through 2026-09-30. The archive is split into five approximately 2 GB parts and the article provides direct asset links and SHA-256 values; no account or API key is described as required for those links.
- The archive includes 1m, 5m, 15m, 60m, 240m, 720m, and 1440m OHLCVT. Each row is timestamp, open, high, low, close, volume, trades. It contains only intervals with trades; missing candles are not zero-filled. It includes a `MANIFEST.json`. This supports native 1h/4h bars when present; it does not establish gap-free candles or continuous underlying trades for each pair.
- Kraken also documents downloadable time-and-sales for every public trade, from each pair's first trade through 2026-09-30. This could be aggregated into other intervals, but it is a distinct, much larger data route and was not inspected or downloaded.
- Kraken's REST OHLC route itself is limited to the latest 720 candles. The downloadable archive, not OHLC REST pagination, is the plausible long-history route.

## Fixed 35-symbol overlap by period

The reviewed project universe is `universe/CRYPTO_35.csv`; it is the existing Binance USDⓈ-M symbol set, not a Kraken listing universe.

- **2018:** Fails the 30-common-assets threshold. Several fixed-universe assets were listed on Kraken only years later. Examples from Kraken's own listing records include ARB (March 2023), SUI (May 2023), SEI (August 2023), TIA (October 2023), ENA (May 2024), and TON (October 2024). PEPE and WLD were also listed after 2018. Eight of the fixed 35 are therefore unavailable in 2018, leaving an upper bound of 27 even before pair-quote and archive-continuity checks.
- **2022:** Also fails the 30-common-assets threshold. The same eight post-2022 Kraken listings alone bound the fixed set to at most 27 assets with a full-year 2022 history. Exact pair-by-pair overlap and gap counts remain unverified because the archive manifest and data were not opened.
- **Pair history and delistings:** Kraken describes archives as all currency pairs from first trade and maintains a Delistings Archive, including pair-removal records. However, this research did not establish that every retired pair is retained in the full OHLCVT archive or prove its exact historical start/end timestamp. The data article's `MANIFEST.json` and pair-specific CSV filenames would need inspection after lawful access is established.

## Scope compatibility and limits

- Spot has no USDⓈ-M funding cashflows, perpetual basis, or futures order-book execution. Kraken Spot prices, liquidity, quote currencies, fees, and market microstructure differ from Binance USDⓈ-M. A Kraken Spot result is a separate instrument/venue study and cannot be substituted for the current order-block strategy, treated as funding=0, or counted toward its G, 2018, 2022, or 30-symbol gates.
- The archive includes base/quote currency pairs, not a guarantee of identical `USDT`-quoted markets for every fixed asset. `1000SHIBUSDT`/`1000PEPEUSDT` also use a different unit scale from Kraken's SHIB/PEPE spot markets; POL/MATIC migration identity needs an explicit mapping. Do not equate same-base candles without fixing quote, unit, and migration handling in a new preregistration.
- Kraken says its public market-data API endpoints are accessible without a Kraken account, but the archive does not state an open data license. Kraken's Global Terms say platform content includes pricing data, grants use only for one's own benefit, and require prior permission for other uses; they prohibit copying/modifying content and automated extraction. The downloadable-data article expressly allows CSVs to be used in code and converted to other formats. These sources do not clearly resolve bulk automated retrieval and local backtest transformation together. Thus an internal personal study may fit the “own benefit” language, but the rights question is **not cleared** for automated harvesting, durable research storage, or derived/reported results.

## Next input required

Before any acquisition, obtain either a written Kraken permission/terms clarification that explicitly covers personal internal backtesting, automated download of the official archive, local retention, and derived statistics, or an already-held dataset plus entitlement record covering those uses. Then, under a new Spot-only preregistration, inspect only data through 2026-05-31, verify pair-specific start/end and gap coverage against the archive manifest and delisting records, choose a consistent quote asset and token-unit mapping, and freeze eligible assets before testing. If the available count remains below 30 for either 2018 or 2022, that period remains ineligible; do not relax the threshold.

## Sources reviewed

- [Kraken historical OHLCVT download guide](https://support.kraken.com/in/articles/360047124832-downloadable-historical-ohlcvt-open-high-low-close-volume-trades-data)
- [Kraken historical time-and-sales download guide](https://support.kraken.com/articles/360047543791-downloadable-historical-market-data-time-and-sales-)
- [Kraken API overview and use notice](https://docs-legacy.kraken.com/api/docs/guides/global-intro/)
- [Kraken Global Terms of Service](https://www.kraken.com/legal/global-terms)
- Kraken's official listings and asset notes: [ARB](https://blog.kraken.com/product/trading-for-arbitrum-arb-starts-now-for-usa), [SUI](https://blog.kraken.com/product/trading-for-sui-sui-starts-now), [SEI](https://blog.kraken.com/product/trading-for-sei-sei-starts-august-15-deposit-now), [TIA](https://blog.kraken.com/product/asset-listings/trading-for-celestia-tia-starts-now), [ENA](https://blog.kraken.com/product/asset-listings/trading-for-aevo-arkm-ena-and-more-available-now), [TON](https://blog.kraken.com/product/asset-listings/ton-is-available-for-trading), [WLD](https://blog.kraken.com/product/asset-listings/aero-and-wld-are-available-for-trading), [PEPE launch timing](https://blog.kraken.com/product/expanded-margin-pairs-available-for-pepe-near-sei-and-shib)
- [Kraken spot-pair delistings archive](https://support.kraken.com/in/articles/notice-of-spot-trading-pairs-removal)

## Scope performed

Reviewed official Kraken documentation, terms, listing/delisting notices, and the local fixed-universe symbol list only. No API calls, account/login/key activity, download, data rows, or archive manifest inspection. No shared ledger, R4, or existing reports changed. This report is the only file created.
