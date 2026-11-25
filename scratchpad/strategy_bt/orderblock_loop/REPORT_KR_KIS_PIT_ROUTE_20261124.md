# KR KIS cache route check — 2026-11-24

## Verdict

`PREREG_KR_TR_ETF_TREND_V1` remains `DATA_BLOCKED`. No existing, no-purchase/no-new-key local route was evidenced that satisfies the registered provenance, return-treatment, rights, and corporate-action gates. No preregistered gate was relaxed.

## Read-only evidence

- `data_sources/EQUITY_SOURCES.md` says the KIS cache contains KR daily OHLCV files for 184 tickers, describes KIS as account + app-key access, and labels that source `SKIP: key/already held`. It documents daily API pagination (100 rows/call) but does not document source-specific data retention/research rights, adjustment rules, or any point-in-time/delisted coverage.
- The current `/Users/user/CODE/trading_data/market_data/kis-cache/` directory has 92 `KR_*.csv` files. `KR_278530.csv` is absent. The directory has no README, catalog, or manifest. An older compressed cache archive exists in the parent `market_data` directory, but its contents were not inspected; its availability alone cannot prove that it contains 278530 or that its use is licensed.
- The catalog separately says FDR/Naver has adjusted daily OHLCV and current ETF listings, but its documented permission is only personal-use/scraping guidance; it does not provide a rights proof for local backtesting. The catalog reports KRX delisted prices were returned for only 1,190 of 4,229 codes. `data_sources/kr_pit/README.md` says the KRX-dependent delisted-price collector stopped because it required KRX credentials; the local lightweight membership output contains no delisted prices.
- The registered candidate requires an official source and reuse-rights evidence, a KOSPI200 total-return or distribution-reinvested series, known corporate-action handling, and daily bars through 2026-05-31. No KIS cache source metadata or sidecar was found to prove those items for 278530. No KIS or other API was called and no price rows were opened.

## Missing inputs and next admissible input

The blocked fields are: (1) actual 278530 daily OHLC including next-open execution prices through 2026-05-31, (2) official evidence that the series is total-return or a dated distribution/dividend and split adjustment history plus its methodology, (3) instrument identity/listing history and handling of suspension, merger, delisting, or code change, and (4) source URL, collection provenance, and written license covering personal local backtesting, storage, and derived statistics.

The next input that could unlock this preregistration is a user-provided, already-held and rights-cleared official dataset (or its official documentation and entitlement record) that covers those four requirements for 278530. If no such entitlement already exists, the next acceptable input is a written no-cost official permission/license plus a locally supplied dataset satisfying the same fields. Do not use the current KIS/FDR/Naver files for performance testing until that evidence is supplied and checked against the preregistration.

## Scope

Read only source/catalog and preregistration documents, and filesystem names/metadata for the KIS cache directory. Did not read price rows, extract the archive, call APIs, log in, request credentials, download, contact a provider, alter source/data/preregistration files, run a backtest, or change the shared trial ledger. This report is the only file created.
