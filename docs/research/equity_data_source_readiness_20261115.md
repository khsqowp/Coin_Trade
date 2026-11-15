# KR/US equity data-source readiness audit — 2026-11-15

Status: source-feature audit only. No account was created, data were purchased/downloaded, provider was contacted, or backtest run. The findings below establish plausible acquisition paths, not a locally available or fully verified dataset.

## Decision

The present KR/US strategy cache remains unsuitable for another performance study. A more credible path exists for each market, but neither is ready for research until the exact data bundle, sample, coverage, terms, and adjusted-return semantics are verified. The US CRSP stock database is the clearest advertised fit for daily stock/ETF survivorship and corporate-action coverage; KRX exposes several potentially composable datasets, but their joint historical coverage is not established. Do not spend or register an account without separate approval.

## Local starting point

The local inventory previously found 118 daily-OHLCV files (54 US, 64 KR), zero intraday timestamps, and no proof that current symbols represent the historical investible universe. Delisted/merged names, distribution and corporate-action provenance, and historical ETF listing states remain unresolved. This audit did not reread external data files or change that inventory. See [`equity_transfer_2026-10/DATA_AVAILABILITY.md`](equity_transfer_2026-10/DATA_AVAILABILITY.md).

## Korea — KRX building blocks, completeness unproven

- KRX's delisted-issue status screen exposes code, name, market, security type, listing date, delisting date and reason. Its separate delisted-price-history screen exposes date, code, OHLC, volume, turnover and market capitalization. These screens prove that delisted instruments and some delisted price history are represented in KRX products; the public page does not establish full daily history from each issue's listing through delisting, the maximum query range, bulk-download/API access, or the matching corporate-action-adjusted total-return panel. [Delisted status](https://data.krx.co.kr/contents/MDC/STAT/issue/MDCSTAT238.jsp), [delisted price history](https://data.krx.co.kr/contents/MDC/STAT/issue/MDCSTAT239.jsp).
- KRX advertises index information products with closing/next-day index and constituent files, constituent shares, prices, weights, float ratios, and corporate-action/index-membership changes. That is promising for a strategy whose universe is a specific KRX index, not proof of a complete point-in-time universe of all Korean listed stocks and ETFs. KRX states that index-linked product use requires an index-license contract; real-time index quote service is handled separately. [KRX index-license/product description](https://openapi.krx.co.kr/contents/OPP/DATA/OPPDATA005.jsp).
- KRX's data-purchase process states that product period, fields, delivery, sample and price are shown in the detailed product view; the customer selects and pays, then the order is reviewed before delivery. The public guide does not expose a price quote or sample bundle directly. [KRX data purchase guide](https://openapi.krx.co.kr/contents/OPP/DATA/OPPDATA001.jsp).

**KR gate:** before a backtest, verify a sample package that joins stable identifiers, full daily history for active and inactive issues, date-valid stock/ETF eligibility, split/dividend/distribution events and adjustment rules, delisting/merger outcomes, and usage rights. Confirm whether the KRX index product is needed for the chosen universe and whether its license covers private research. The current public evidence does not pass this gate.

## United States — CRSP is a plausible, subscription-based daily panel

- CRSP describes its current US Stock Database as daily and monthly prices plus corporate actions for 32,000+ active and inactive US securities across NYSE, NYSE American, NYSE Arca, Nasdaq and Cboe BZX, with permanent security/company identifiers. Its product page labels its histories survivor-bias-free and provides CIZ-format data. These are vendor claims about product scope, not a validation of a dataset we have obtained. [CRSP US Stock Databases](https://www.crsp.org/research/crsp-us-stock-databases-2025-layout/).
- The CRSP CIZ guide distinguishes equity/fund security types and COM/ETF/ETN subtypes; it also defines active status, trading status, delisting reason/payment, delisting return, and distribution fields. This suggests the product can support a historical daily stock/ETF universe and return reconstruction, subject to exact table coverage, release vintage and licensing. [CIZ database guide](https://www.crsp.org/wp-content/uploads/guides/CRSP_US_Stock_%26_Indexes_Database_Guide_Flat_File_Format_2.0.pdf).
- CRSP lists monthly, quarterly, or annual release cadence and SAS/ASCII/R formats, with third-party access through WRDS, Snowflake, MOVEit or SASECRSP. The product page offers subscription information, not a public price. No account or subscription was initiated.

**US gate:** verify that the proposed subscription includes daily data, the target common-stock and ETF subtypes, historical inactive security records, distributions and delisting outcomes, and the necessary research/private-use rights. Request a sample schema and small sample with full security/date coverage before committing. CRSP stock/index membership products may be needed only if the strategy universe is defined by a historical index; do not equate a current S&P 500 membership file with point-in-time membership.

## Common research gate after data is authorized

1. Freeze the strategy universe and market scope: all eligible listed securities versus a named index universe; stocks and ETFs remain separate security classes.
2. Record provider, product/version, permitted use, retrieval timestamp, release vintage, sample and full-file hashes.
3. Reconcile listing/delisting spans, identifier changes, suspensions, mergers, splits, dividends and ETF distributions. Preserve inactive instruments and unresolved delisting cases as explicit exclusions or adverse outcomes, never silently drop them.
4. Verify execution-price semantics, trading calendars, currency, price adjustments and dividend/total-return treatment. The current daily cache cannot be used for intraday strategies; obtain and audit intraday bars separately if those strategies remain in scope.
5. Before autonomous strategy evaluation, freeze maximum acceptable drawdown, benchmark, position sizing, rebalance/holding rules and measured or conservative transaction-cost assumptions. The user's maximum drawdown remains unspecified; no risk-adjusted “best” portfolio can be selected without it.
6. Only after the data gate passes, preregister a small number of economically motivated hypotheses and reserve a genuinely untouched chronological test set. Do not rerun the already-exposed caches as confirmation.

## Next decision boundary

The next high-information step is to compare official product specifications, sample coverage, legal-use terms, and an actual quoted cost for one KR and one US candidate. This audit gathered public specifications only; it did not request quotes or initiate purchase. Until the user authorizes a provider/account action and the data pass the common gate above, further KR/US strategy backtests on the current cache are low-information.
