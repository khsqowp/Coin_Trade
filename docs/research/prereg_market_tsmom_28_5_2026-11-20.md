# Preregistration — BTC-major basket time-series momentum 28/5

Status: frozen before any candidate outcome calculation. This is a single, literature-motivated development test, not a parameter search or investment recommendation.

## Objective and rationale

The optimization target is after-cost compounded wealth across market regimes. Accuracy is not the objective for this portfolio timing rule. A published crypto study reports that market-level time-series momentum was strongest for a 28-day lookback and five-day holding period; long-only outperformed long-short, while short-only portfolios were frequently unprofitable. The study also warns about liquidation, tails, and data snooping. This test evaluates one fixed long-only adaptation on a small, fixed major-coin basket. It is structurally distinct from the already-tested short-horizon BTC impulse/alt lag-flow and cross-sectional reversal trials, but it is not a new strategy family.

Reference: Han, Kang & Ryu, “Time-Series and Cross-Sectional Momentum in the Cryptocurrency Market: A Comprehensive Analysis under Realistic Assumptions,” [full paper](https://acfr.aut.ac.nz/__data/assets/pdf_file/0009/918729/Time_Series_and_Cross_Sectional_Momentum_in_the_Cryptocurrency_Market_with_IA.pdf), especially §§4.2–4.3. The paper’s 28/5 result was selected after examining multiple pairs, so it is treated as a potentially selection-biased candidate, not independent confirmation.

## Frozen instrument, data and split

- Data: read-only Binance Vision USD-M 1-minute candles in `vision_dev_repaired.sqlite`; only `BTCUSDT, ETHUSDT, BNBUSDT, DOGEUSDT, SOLUSDT, XRPUSDT`.
- Fixed common window: 2020-09-15 00:00 UTC through 2024-01-01 00:00 UTC. SOL’s source starts during 2020-09-14, so the first full common day is 2020-09-15. The six-symbol common start avoids changing the basket during this development test; it does not remove survivorship or current-universe selection bias.
- Development only. Do not query or score data from 2024-01-01 onward unless every development continuation gate below passes. The database has later data, but it remains unopened for this trial.
- Daily UTC OHLC bars must each contain exactly 1,440 minute rows on the expected contiguous minute grid for all six symbols. Do not interpolate, repair, or silently drop an incomplete day; any incomplete day blocks this preregistered run.
- Binance Vision historical data is used only for personal, non-production backtesting. Do not use this output for real-time or manual-trading signals, or redistribute source-derived metrics without the required attribution/license notice.

## Exact rule

1. From each symbol’s daily close-to-close return, create a synthetic equal-weight market-return series (daily equal-weight rebalance across the six fixed symbols). No leverage or short exposure.
2. At each UTC daily close, calculate the compounded 28-day market return. Rank it against the expanding history of prior 28-day market returns only. Do not include the current observation in its threshold. Require at least 252 prior valid 28-day observations; thereafter, enter the long state only when the current return is at or above the prior-history 66⅔ percentile. Otherwise the signal is cash.
3. Each daily signal starts at the next UTC daily open and occupies one of five equal sleeves for five full UTC days. The total target exposure is the average of the last five already-known daily signals; each active sleeve is long the six-coin equal-weight basket. This creates a fixed 0–100% gross exposure and no shorts.
4. Daily equal-weight basket returns are earned from one UTC open to the next. Holdings are rebalanced to the target basket at each UTC open. Rebalance costs apply to the sum of absolute changes in portfolio asset weights, including sleeve entries/exits, basket rebalances, and final liquidation.
5. Base cost is 5 bp taker fee + 4 bp adverse slippage per traded side. Stress cost is 5 bp fee + 8 bp adverse slippage per traded side. Funding is unavailable in the source database and is therefore omitted; results are an optimistic futures-price proxy and cannot establish futures profitability. The basket’s 1x gross exposure avoids leverage/liquidation claims but does not remove this funding limitation.

## Fixed comparison and diagnostics

- Main comparator: same six symbols, equal-weight buy-and-hold from the same first common UTC open, with entry and final-liquidation base/stress costs.
- Additional comparators: BTC buy-and-hold on the same interval and cash at NAV 1.0.
- Report after-cost final NAV, total return, CAGR, daily Sharpe, close-marked MDD, daily exposure, turnover/cost drag, signal count, calendar-year returns, and benchmark-relative terminal wealth under both cost cases.
- The one primary test is 28-day lookback / 5-day hold. Predeclared robustness-only neighbors are (25,4), (25,6), (31,4), and (31,6); they may diagnose local fragility but may not replace or tune the primary rule. Count all five configurations as one preregistered family and correct interpretation for that multiplicity.
- Run 1,000 deterministic random reorderings of the primary daily net-return series and report 95th-percentile MDD. Also report 7-day block-bootstrap confidence interval for annualized mean net return using 1,000 deterministic resamples. Reordering is a path-risk diagnostic, not evidence that daily returns are independent.
- Walk-forward report is the frozen-rule chronology by calendar year and half-sample (no fitting or parameter selection). It is not called an optimized walk-forward test. No validation opening or post-result rule changes.

## Continue / reject gate

Continue to the single sealed 2024+ confirmation only if the primary 28/5 configuration has (a) positive net CAGR and Sharpe under both base and stress costs; (b) higher terminal wealth than six-coin buy-and-hold, BTC buy-and-hold, and cash under both cost cases; (c) lower MDD than six-coin buy-and-hold under both costs; (d) no single calendar year contributes more than 60% of total positive log growth; and (e) all data, causality, accounting, and future-mutation tests pass. Otherwise reject this candidate and leave 2024+ unopened. Even a development pass would be exploratory because the six-coin universe is current-survivor selected and funding is absent; it could not authorize deployment.

## Required causal and accounting tests

- Signals are invariant to mutating every candle strictly after the anchor.
- Threshold history excludes the current return and all future returns.
- First eligible signal requires exactly 252 prior returns; holding exposure uses only the previous five completed signals.
- No trade occurs before the next UTC open; five-sleeve exposure remains within [0,1].
- Missing/duplicate/out-of-grid minute rows block daily aggregation; daily OHLC and NAV/turnover/cost ledgers reconcile to manual synthetic examples.
- Source SQLite opens read-only; output contains aggregates only, never copied market rows.
