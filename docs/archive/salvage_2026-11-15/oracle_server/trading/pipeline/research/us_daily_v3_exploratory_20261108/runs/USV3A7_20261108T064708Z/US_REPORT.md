# US liquidity-universe strategy run report

- Run ID: USV3A7_20261108T064708Z
- Study dates: 2012-06-01 to 2026-08-18
- Run duration: 59.9 sec (successful attempt 3; attempts 1 and 2 stopped before metrics)
- Rules: RSI(2) trend-filtered reversal, one-day gap reversal, SPY residual momentum
- Dynamic liquidity universe: Top 50 / 100 / 200 by lagged 60-session median raw split-adjusted close x raw volume, with USD 5m floor
- Costs: 5 / 10 / 20 / 40 bp per side
- Portfolio: fixed K=20, 5% slots, unused cash retained
- Output: 36 strategy cells (3 rules x 3 universes x 4 costs), 3 equal-weight liquidity benchmarks, 1 SPY benchmark

## Primary result at 10 bp per side

Annualized return, Sharpe, and maximum drawdown are shown. All figures are historical exploratory results, not forward evidence.

| Strategy | Liquidity Top 50 | Liquidity Top 100 | Liquidity Top 200 |
|---|---:|---:|---:|
| RSI(2) trend reversal | 5.13%, 0.61, -19.79% | 5.13%, 0.51, -33.37% | 1.34%, 0.17, -37.44% |
| Gap reversal | -1.66%, -0.23, -25.57% | -1.91%, -0.19, -30.30% | -2.44%, -0.22, -36.70% |
| SPY residual momentum | 19.55%, 0.99, -29.20% | 18.06%, 0.89, -34.83% | 15.24%, 0.75, -37.40% |
| Equal-weight liquidity Top N | 17.13%, 0.95, -31.69% | 15.48%, 0.91, -34.12% | 14.79%, 0.89, -37.16% |

The SPY buy-and-hold reference returned 15.43% CAGR, 0.95 Sharpe, and -33.72% maximum drawdown over the same dates.

## Cost sensitivity

CAGR by per-side cost (5 / 10 / 20 / 40 bp):

| Strategy | Top 50 | Top 100 | Top 200 |
|---|---|---|---|
| RSI(2) | 7.11 / 5.13 / 1.28 / -6.01% | 8.28 / 5.13 / -0.90 / -11.96% | 5.54 / 1.34 / -6.56 / -20.59% |
| Gap reversal | -0.93 / -1.66 / -3.10 / -5.92% | -0.67 / -1.91 / -4.36 / -9.07% | -0.42 / -2.44 / -6.35 / -13.72% |
| Residual momentum | 19.88 / 19.55 / 18.71 / 17.05% | 18.54 / 18.06 / 17.04 / 15.14% | 15.82 / 15.24 / 14.04 / 11.71% |

Values are percent CAGR. The full results file contains each cell's total return, Sharpe, drawdown, fills, mean turnover, mean exposure, period splits, and descriptive regime results.

## Interpretation and limits

- Residual momentum was the strongest of these tested variants. At the primary 10 bp cost, Top 50 exceeded the equal-weight liquidity Top 50 reference by 2.42 percentage points CAGR (19.55% vs. 17.13%), with Sharpe 0.99 vs. 0.95 and drawdown -29.20% vs. -31.69%. This is a candidate for further validation, not a validated or promoted strategy.
- RSI(2) was cost-sensitive. At 20 bp, Top 100 and Top 200 had negative CAGR; at 40 bp all RSI universes were negative.
- Gap reversal was negative in all 10 bp base-cost universes and all 20/40 bp universes.
- The 2020-01-01 to 2026-08-18 split is reused OOS, not untouched OOS. Prior strategy and market-path observations make every result exploratory.
- Data are partial: 717 PIT symbols had parquet histories, 492 PIT symbols lacked them, and the final PIT snapshot had 503 members. Average eligible count was 419.8, minimum 334. The membership archive is manually maintained, and coverage has gaps. Do not call this a complete or survivorship-free US universe.
- Liquidity Top N means contemporaneous trailing dollar volume among available eligible PIT members, not market capitalization.
- The script assumes the reported cost schedule and does not model intraday path, market impact, taxes, or broker-specific execution. No live orders were sent.

## Run evidence

See RUN_MANIFEST.json, results.json, coverage.json, daily_returns.csv, daily_exposure.csv, and stdout_attempt1/2/3 logs in this run directory. A7 froze and checked us_v3.py and the three imported helpers. The metrics run used the hashed runner_a7.py only to bind the cached pickle's legacy __main__.Panel name; the frozen strategy code was not modified.

