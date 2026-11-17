# R037 decision — NO-GO for performance testing

MarketParquet is a stronger data-access lead than the previously inspected unlicensed GitHub panel: its official pages describe stock, ETF, and futures OHLCV, recent delisted symbols, and a no-account sample. It is **not yet an admitted backtest panel**.

Blocking reasons:

1. The terms say the no-account sample exists, while the linked license describes a per-account grant on purchase of an archive. The interaction between those statements does not clearly grant the same research/storage rights for the free files. Do not infer a legal right beyond what is explicit.
2. The no-account daily files cover only the newest week; broader free daily access is described as about one year and requires account/API credentials. Neither horizon supplies a credible multi-regime OOS test for the fixed US stock/ETF objective.
3. The OHLCV is split-adjusted but excludes cash dividends. Total-return portfolio comparisons need a separately authorized, time-aligned dividend/corporate-action series and proper cash handling.
4. The provider describes delisted-name retention and a detailed correction process, but point-in-time ETF eligibility, ticker reuse, merger consideration, and delisting return semantics have not been independently checked against sample bytes.
5. The methodology changelog itself documents substantial corrected historical defects. This is useful transparency, but increases the need for an immutable sample snapshot, file hashes, and local audit before any strategy metrics.

The official sample-file size could not be verified. A HEAD request redirected but returned 403; a subsequent byte-range request failed DNS resolution. No sample market data was retained. No account, key, contact, purchase, strategy run, or performance statistic was produced.

**Disposition:** retain as a promising free-sample feasibility lead only. Reopen source audit only after sample rights are explicit and a no-account file can be retrieved; then pin hashes and validate schema, universe, delisted/ETF history, corporate actions, and defects. Broader strategy testing still requires adequate licensed history and a frozen OOS boundary. The $79 archive and paid services were not authorized and were not purchased.
