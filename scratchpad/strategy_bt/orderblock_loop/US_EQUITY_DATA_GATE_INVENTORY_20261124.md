# US Equity Data Gate Inventory — 2026-11-24

## Decision

The existing local files do **not** qualify a cross-sectional US stock strategy that selects from a changing constituent universe. They may support a narrowly scoped, preregistered test of one fixed ETF (for example, a single broad-market ETF) with no symbol selection or replacement, subject to footer-only verification that the exact instrument and action fields exist. No strategy was run in this task, and this note does not certify any candidate as profitable.

## Scope and evidence checked

- Read `data_sources/EQUITY_SOURCES.md`, `docs/STORAGE_RULES.md`, and the external equities `MANIFEST.csv` plus its split manifest metadata. A targeted `rg` also returned matching passages from two prior eligibility-audit documents; their full contents were not opened and they are not treated as independent current inventory evidence. Used file names, dates, row counts, byte counts, hashes, source descriptions, and documented access terms only.
- A Parquet footer-only schema read was attempted but unavailable because the available Python environments do not have `pyarrow`; no rows were substituted for that metadata check.
- Did not read any price rows, any row after 2026-06-01, `TRAIN_TRIALS.csv`, or secrets. Did not call APIs, download data, run a backtest, or edit the shared ledger or any existing report.

## Local evidence by gate

| Gate | Local evidence | Result |
|---|---|---|
| Historical point-in-time membership | `us/sp500_historical_components_fja05680.parquet`: 2,595 rows, 1996-01-02 through 2019-01-11; community-maintained source. `EQUITY_SOURCES.md` describes it as historical S&P 500 constituents. | Insufficient for a current/full-period constituent strategy; no verified official effective-date record or broader US universe. |
| Delisted daily OHLC and final value | `us/yahoo_daily_us_stocks.parquet`: 10,885,803 rows; source description says Yahoo daily unadjusted plus adjusted close, 1962-01-02 through 2026-11-19. Catalog explicitly says Yahoo serves currently listed names and removed-member prices are missing. No US delisted OHLC/final settlement file is listed. | Fails. Survivorship bias and missing terminal proceeds prevent complete stock returns. |
| Corporate actions / total return | Yahoo stock and ETF catalog descriptions include adjusted close and dividends/splits; ETF data manifest describes unadjusted prices plus adjusted close. Separate field-level footer inspection was unavailable in this turn. No US delisting proceeds or complete merger/spinoff settlement table is listed. | Partial for extant symbols; insufficient for delisted-stock total return. A fixed-ETF test can use adjusted close as a total-return cross-check only after exact field verification; raw next-open execution still requires an explicit split/distribution treatment. |
| Source rights | Catalog labels Yahoo as unofficial, personal-use only, rate-limited, and intended for personal backtesting research; catalog header says personal backtesting research, not resale. Treasury curve source is U.S. Treasury; macro/FRED can include third-party series restrictions; CBOE data requires personal use/attribution per catalog. | Conditional pass only for private personal research under the stated restrictions. No redistribution/publication of raw data; confirm terms before broader use. |
| Macro inputs | `macro/treasury_par_yield_curve.parquet`: 9,228 rows, 1990-01-02 through 2026-11-19, Treasury source. `vix/cboe_index_history.parquet`: 117,313 rows, 1986-06-20 through 2026-11-19. Manifest ends are metadata only; no post-cutoff rows were opened. | Adequate history for a single-ETF macro overlay input candidate after strict `date <= 2026-06-01` filtering and next-session execution. Do not use FRED revised series without a vintage/release-time contract. |

## Eligible research boundary

A candidate that can be preregistered without lowering the gates is a **single fixed ETF exposure overlay** using only that ETF's own history and a predeclared, legally usable market input. Since the instrument is fixed before the sample begins, historical index constituent membership and delisted-stock prices are not needed for that experiment. This boundary does not support ranking/selecting individual stocks, rotating among changing ETF symbols, or generalizing the result to the US equity universe.

The exact ETF name, its presence in the aggregated parquet, and its action-field schema were not verified because row inspection was prohibited and a footer reader was unavailable. Therefore this is a *data-scope candidate*, not a ready-to-run approval. Before preregistration, use footer-only metadata to verify the exact fixed symbol and required columns; then preregister with a `date <= 2026-06-01` hard filter, a next-session fill, distribution/split handling, held-out dates, baseline buy-and-hold, costs, and source-rights limits. If the selected source is Yahoo, keep the experiment private/personal and do not redistribute raw data.

## Exact contract missing for a US stock-universe test

1. Official, dated membership intervals for each security (`valid_from`, `valid_through`, announcement/effective date, exchange, stable ID) across the intended universe and full sample.
2. Daily executable OHLCV for active **and inactive/delisted** securities, keyed by stable IDs, with source lineage and coverage dates.
3. Complete dated corporate actions, including splits, cash/stock dividends, mergers, spin-offs, bankruptcies, cancellations, payment dates, and delisting final value/return; explicit handling for unpriced or unresolved terminal claims.
4. Written rights covering private research, storage, derived backtest results, and any later redistribution/publication, plus a version/hash manifest.
5. PIT macro/fundamental inputs with release/availability timestamps and historical vintages wherever the source revises prior values.

## Next admissible route

- For a fixed-ETF experiment: perform only a footer/schema check for the preselected ticker and action fields; if that passes, create a new preregistration before reading any eligible historical rows. Keep all rows after 2026-06-01 excluded.
- For individual-stock or rotating-universe research: do not run a strategy test from the current Yahoo/community combination. The next admissible route is an already-held institutional entitlement to a survivor-bias-free source (for example, CRSP/WRDS) with the five contract items above verified. If there is no such entitlement, remain data-blocked until the user authorizes an appropriately licensed source; this task did not seek access or pricing.

## Reproducibility note

This inventory is based on the catalog and manifest metadata available on 2026-11-24. The local manifest's file date ranges end on 2026-11-19, but that does not mean the task inspected those latest observations. No backtest metrics, schema claims beyond the source catalog descriptions, or live eligibility claims are asserted.
