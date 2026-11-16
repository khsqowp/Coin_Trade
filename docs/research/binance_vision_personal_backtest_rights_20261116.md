# Binance Vision personal backtest rights and data gate — 2026-11-16

## Purpose and scope

This is a source-and-terms review only. No Binance Vision market-data archive was downloaded, queried, cached, or backtested in this review. No terms were accepted on the user's behalf. The review is limited to whether Binance Vision can be considered for historical, personal, non-production research; it does not decide whether a future live discretionary signal workflow is permitted.

## Primary-source findings

- Binance's official `binance-public-data` repository links a separate dataset terms document. Its repository MIT license applies to repository code and must not be mistaken for a data license. Source: [official README](https://github.com/binance/binance-public-data/blob/master/README.md).
- The Vision Dataset Terms, version 1.0 last updated 2026-08-26, state that downloading, caching, querying, or otherwise using the datasets constitutes agreement to the terms. They license datasets under CC BY-NC-SA 4.0 unless otherwise specified.
- The terms list algorithmic historical backtesting for purely personal, non-production research as a permitted non-commercial use. They exclude live proprietary trading execution, automated commercial order generation, compensated signal distribution, and commercial exploitation. Derivative works must include attribution and remain under the same license.
- The official archive README says USD-M Futures klines are sourced from `/fapi/v1/klines`; the official downloader documentation provides historical futures kline and index/mark/premium-kline download options. This documents archive formats and endpoints, not point-in-time universe completeness or error-free data.

Sources: [Vision Dataset Terms](https://github.com/binance/binance-public-data/blob/master/TERMS_AND_CONDITIONS.md), [official archive README](https://github.com/binance/binance-public-data/blob/master/README.md), [official futures downloader README](https://github.com/binance/binance-public-data/blob/master/python/README.md).

## Decision

**Conditional source eligibility for historical personal research; not eligible by default for the eventual live-signal workflow.** The published terms provide a clear historical-backtest permission category, subject to the user's actual non-commercial, personal, non-production use and the attribution/share-alike obligations. Whether a later live manual-trading signal derived from these data falls within the terms is not determined here; do not infer that permission from the historical-backtest clause.

The terms review removes one uncertainty for an isolated personal historical backtest, but it does not close the data-quality gates:

1. A point-in-time USD-M contract universe must be reconstructed, including each contract's first/last tradable time and delisted contracts; current exchange metadata alone is insufficient.
2. Per-symbol archive availability, gaps, duplicates, revisions, timestamps, and checksums must be audited before metrics are generated.
3. Funding history and execution-cost assumptions must align with each contract and timestamp.
4. The exact data and code fingerprints, frozen split, selection procedure, and untouched final-evaluation policy must be registered before opening outcomes.
5. The raw archive and all derived artifacts must follow attribution and share-alike requirements; no dataset may be committed to Git.

## Next action

Do not repeat an exposed strategy on the existing six-symbol development data. Before any new acquisition, write a narrow data manifest specifying the symbols/universe reconstruction, exact fields, date range, expected archive size, costs (zero download fee; storage/compute still measured locally), checksums, and the personal non-production research purpose. Then test archive completeness and point-in-time eligibility without calculating strategy outcomes. If the archive cannot establish the required historical contract universe, stop before the strategy grid.

For KR/US equities, this crypto-specific terms review does not alter the separate KRX/US source-rights and point-in-time gates.
