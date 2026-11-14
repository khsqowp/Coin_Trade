# Generation 11 — US equity-index ETF dual-momentum allocation

Status: frozen exploratory candidate; **no signal table, ranking output, or performance statistic has been generated**. Frozen 2026-11-06 12:52 UTC. This is one predeclared rule, not a parameter sweep and not an investment recommendation.

## Data inventory performed before strategy work

Local read-only mirror: `../data_mirror/us_daily/`. Availability was read from the four symbol metadata files; SHA-256 was computed over each parquet and metadata file. No OHLC rows, returns, scores, rankings, or strategy performance were read/calculated during this inventory.

| Instrument | Rows | First | Last | Parquet SHA-256 | Metadata SHA-256 |
|---|---:|---|---|---|---|
| SPY | 8,498 | 1993-01-29 | 2026-11-02 | `533ea8cccbd302d3f5faa771f0ceb461f697e1f75302497ca053a6b3d98b09ba` | `77b6d96fb26099efdbc8e5957f2b4744dfddd2083eb19d7b9598b690bc97dc5c` |
| QQQ | 6,956 | 1999-03-10 | 2026-11-02 | `62d7e3baa09b3c8b1b6a019b228c093f3402758c03799a79fb3f4013612266c8` | `52fb9ad4df29171a8c742924b084263938bbc4adb0e2918ed82dfd895591fcaa` |
| IWM | 6,648 | 2000-05-26 | 2026-11-02 | `a8c20a7fae3062dfb6da973696d83def502b8e42d948852a07ccc6b13fa344e3` | `9e99736e9cf1b8f75fe1eddd9e8fb4c172b123cf67274155a2038888f83a71b0` |
| DIA | 7,242 | 1998-01-20 | 2026-11-02 | `36af44bd5f8da7ec6006280baab991016958f018cc57edd6a5f13f20cd7a708a` | `12e4c501b15c5f41b661c9c100d14b2b00acf6bc8084013195450575ac2277e2` |

The common-start bottleneck is IWM (2000-05-26); the fixed universe's usable start is later still because the rule requires a 252-common-session lookback. Exact first eligible date is to be computed mechanically by the frozen runner, not chosen after seeing results. These are Yahoo chart v8 unofficial-vendor snapshots. PIT ETF membership is not applicable to these four funds, but instrument-survival, inception, index-reconstitution, dividend-adjustment, and vendor-data risks remain. These are four correlated US equity exposures, **not** a diversified multi-asset universe; bonds, commodities, cash-equivalent ETFs, and international assets are absent from the local mirror.

## Candidate and source lineage

One US allocation hypothesis: at each common-calendar month-end, rank four fixed broad-index ETFs by 12-to-1-month adjusted-close momentum, allocate 100% to the single leader if its absolute momentum is positive, otherwise hold cash. This is portfolio-level relative selection plus an absolute trend gate.

Source lineage: `trading/app/new_strategy_screening.py` defines a `12-Month Relative Momentum` catalog entry (`CatalogStrategy` 15) and its cross-sectional momentum implementation (`cs_momentum`, a 126-session return rank). House US daily v2 separately tested X1, monthly top-50 12-1 single-stock momentum, and X2 with an SPY 200-day gate (`source_mirror/us_daily_v2/PREREG_us_daily_v2.md`, rules X1/X2). Those rules and prior market-level US research have already been inspected. The present candidate changes the object from a PIT single-stock cross-section to a four-ETF, one-position-or-cash allocation; it remains in the **same momentum family** and is not independent evidence. Results from prior momentum-family trials must count toward any multiplicity adjustment. This is not claimed as novel or uncorrelated.

## Frozen rule

- Fixed instruments, no substitutions or missing-asset universe shrinkage: `SPY`, `QQQ`, `IWM`, `DIA`.
- Construct a shared calendar from the intersection of their observed dates. Reject duplicate or non-monotonic dates, missing/non-finite/non-positive open, close, or adjusted-close values on the shared calendar, or malformed input. Do not forward-fill.
- Signal at the final shared session of each calendar month. For each ETF at zero-based shared row `t`, score `adjclose[t-21] / adjclose[t-252] - 1`. This skips the most recent 21 common sessions and uses exactly one predeclared 12-to-1-month window. Require all four scores; no fallback or alternate lookback.
- If the highest score is strictly greater than zero, target 100% in that ETF. If all scores are non-positive, target 100% cash. Exact ties are broken by ascending ticker symbol. No leverage, shorting, volatility scaling, stops, or discretionary overrides.
- Execute the new target at the next shared-session adjusted open after the signal. Hold until the next scheduled monthly execution. Adjusted open is raw open multiplied by that session's `adjclose/close` factor. No close-to-close fills, same-close execution, or intramonth signals.
- Charge 10 bp per traded side multiplicatively on portfolio equity. Same-ETF rebalance has zero turnover; equity-to-cash or cash-to-equity costs one side; switching ETF costs one sell plus one buy. Charge terminal liquidation once if invested. No financing return on cash, taxes, market impact, borrow, or tax-lot effects are included. Fixed costs are only a screening assumption; results do not establish executable fills.
- Benchmark: SPY adjusted-open buy-and-hold over exactly the candidate return intervals, with 10 bp entry and 10 bp terminal exit costs. It is not a risk-matched benchmark and does not neutralize the ETF strategy's cash exposure.
- Report the full mechanically available period, 2001-01-01 through 2016-12-31, and 2017-01-01 onward through last complete common data date. Window boundaries are descriptive, not virgin OOS: market behavior and related momentum tests have already been inspected. Recompute each window's drawdown from its own starting equity. Report CAGR, annualized Sharpe (252), max drawdown, exposure, turnover/rebalances, and benchmark counterparts.
- One run only after an independent reviewer records GO. No parameter variants, reruns, post-hoc alternate universes, or rule edits in this generation. If data, tests, hashes, or causality fail, record the failure and do not calculate performance.

## Interpretation limits and gates

This candidate can fail, lag SPY, or only appear favorable in a contaminated historical interval. A pass on these descriptive summaries alone does not validate alpha, robustness, expected future returns, investor suitability, or live tradability. The instruments are equity-index ETFs and share equity-market risk; cash gating can create prolonged underexposure, whipsaw, and taxable turnover. Vendor adjusted prices may have survivorship/repair issues and cannot establish the historical tradability of the full rule.

The cumulative historical trial count and appropriate family-wide DSR/PSR/BH correction must be reconciled from the archived trial ledgers before any inferential claim. Missing or unreliable multiplicity accounting means no statistical-validation claim, even if descriptive returns look favorable. Since this hypothesis overlaps prior US X1/X2 and other momentum research, an attractive result would still require a genuinely untouched external period or independently sourced data before any later promotion. No production, order, server, commit, or deployment activity is authorized.

## Frozen local input/source hashes

- Candidate-source file `trading/app/new_strategy_screening.py`: `27cfd55ff2d6158e6b3002be1652a5279f53371e7c5b517fb3ca99ccf0efdb8f`.
- Parquet and metadata hashes are listed in the inventory table above. They are expected to match at run time; mismatch aborts before reading performance data.
- Before any run, `FREEZE.json` must bind this preregistration, source, runner, tests, and all eight input artifacts; the independent review record must bind the same hashes. A durable attempt ledger must record a STARTED state before loading price values and COMPLETED/FAILED after the outcome.
