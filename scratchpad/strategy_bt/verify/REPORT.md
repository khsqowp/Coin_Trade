# Adversarial backtest verification

All returns are pooled trade net PnL as percent of $10,000 capital. “Reproduced” requires both test-return and test-trade-count differences <=15%; `reproduce.csv` separately flags >15% train-return, test-return, and trade-count gaps. Relative-return denominator is absolute source return. Exposure is occupied bars divided by test bars; benchmark is simple close/open return at $1,000 per symbol. Subperiod trade PnL is attributed to exit time. Concentration shares are largest positive contributor divided by positive contributors’ sum, calculated separately across symbols, test halves, and calendar years; the reported subperiod share is the maximum half/year share. Neighbor medians use independent per-axis ±30% values, up to 5 values; >3 parameters uses 3 values per axis.

| Candidate | Reproduced? | Long / short | B&H-scaled | Top-symbol | Top-subperiod | Neighbor profitable | 2x cost | Final tag |
|---|---:|---:|---:|---:|---:|---:|---:|---|
| btc-max10-nyse-close | yes (0.0%) | 12.75 / 0.00 | -3.12 | 32% | 100% | 100% | 7.79% | FRAGILE |
| btc-bollinger-37-16 | yes (0.0%) | 67.65 / 0.00 | 12.23 | 48% | 100% | 100% | 66.76% | FRAGILE |
| btc-ema-5-30 | yes (0.0%) | 60.47 / 1.85 | 31.86 | 24% | 100% | 100% | 58.79% | FRAGILE |
| btc-roc-36-9pct | yes (0.0%) | 57.59 / 0.00 | 11.16 | 46% | 100% | 100% | 55.32% | FRAGILE |
| jesse_turtle | yes (0.0%) | 51.91 / -4.28 | 23.57 | 57% | 95% | 100% | 44.88% | FRAGILE |
| btc-macd-15-41-12 | yes (0.0%) | 70.65 / 9.65 | 29.96 | 34% | 94% | 100% | 77.35% | FRAGILE |
| c4-ema-supertrend | yes (0.0%) | 4.56 / 0.00 | -7.95 | 45% | 100% | 54% | 1.34% | FRAGILE |
| c4-strategy-myth-busting-12-osgfc-supertrend-myn | no (185.3%) | -11.11 / -6.53 | -14.49 | 100% | 0% | 0% | -42.11% | IRREPRODUCIBLE |
| turtle-system-1 | no (19.4%) | 53.83 / -3.22 | 22.73 | 51% | 100% | 100% | 47.63% | IRREPRODUCIBLE |
| btc-adx-di-24-9 | yes (0.0%) | 61.06 / 2.81 | 31.37 | 46% | 100% | 100% | 60.27% | FRAGILE |
| turtle-system-2 | yes (0.0%) | 51.01 / 4.63 | 18.31 | 32% | 100% | 100% | 54.57% | FRAGILE |
| jesse_simple_bollinger | yes (0.0%) | 13.79 / 0.00 | -5.03 | 47% | 60% | 88% | 3.16% | ROBUST_ALPHA |

## Cluster result

Mark-to-market daily returns are calculated from position open/close price changes, with entry and exit friction on event days, pooled across symbols and resampled to UTC dates. At corr >0.7 connected components: 5 components among 12 strategies: btc-adx-di-24-9, btc-bollinger-37-16, btc-ema-5-30, btc-macd-15-41-12, btc-roc-36-9pct, jesse_turtle, turtle-system-1, turtle-system-2; btc-max10-nyse-close; c4-strategy-myth-busting-12-osgfc-supertrend-myn; c4-ema-supertrend; jesse_simple_bollinger. Correlation with equal-weight five-coin daily buy-and-hold is in `cluster.csv`; full matrix in `correlation.csv`.

## Definitions and limitations

- Reimplementation is independent of harness imports. `c4-strategy-myth-busting...` specification does not encode executable OSGFC/Supertrend equations; its independent causal smoothed-slope proxy is not a reproduction of plugin source logic.
- Turtle signals use prior-bar channels and a stop, but do not implement hypothetical prior-breakout winner state or pyramiding. Fixed notional follows the harness rather than original risk-unit sizing.
- The supplied split is per symbol at `int(len*0.6)`. Test halves and years use exit-time trade attribution. Benchmarks use open of first test bar to close of last test bar and are not fee adjusted.
- `beta_only` requires long pnl in [70%,130%] of exposure-scaled B&H and short pnl <=0. FRAGILE concentration >70%, neighbor profit share <60%, or doubled-cost return <=0. IRREPRODUCIBLE takes precedence.

## Per-candidate notes

- `btc-max10-nyse-close`: Return and trade count within 15% Train reimplementation return 33.41% vs harness 33.41%; test 12.75%.
- `btc-bollinger-37-16`: Return and trade count within 15% Train reimplementation return 489.96% vs harness 489.96%; test 67.65%.
- `btc-ema-5-30`: Return and trade count within 15% Train reimplementation return 602.03% vs harness 602.03%; test 62.31%.
- `btc-roc-36-9pct`: Return and trade count within 15% Train reimplementation return 408.80% vs harness 408.80%; test 57.59%.
- `jesse_turtle`: Return and trade count within 15% Train reimplementation return 329.16% vs harness 329.56%; test 47.63%.
- `btc-macd-15-41-12`: Return and trade count within 15% Train reimplementation return 363.31% vs harness 363.31%; test 80.30%.
- `c4-ema-supertrend`: Spec JSON is lossy; implemented source-derived EMA rule. Inspect plugin shows explicit recovered Pine rule. Train reimplementation return 86.86% vs harness 86.86%; test 4.56%.
- `c4-strategy-myth-busting-12-osgfc-supertrend-myn`: Spec JSON omits executable equations; independent proxy is not equivalent to plugin source-derived OSGFC/Supertrend; discrepancy is reimplementation limitation. Train reimplementation return -13.83% vs harness 58.43%; test -17.63%.
- `turtle-system-1`: Plugin uses a hypothetical prior-trade winner filter plus always-active 55-day fallback; independent literal channel proxy omits that state machine, causing the mismatch. This is an independent reimplementation gap, not evidence of a plugin defect. Train reimplementation return 350.94% vs harness 345.76%; test 50.61%.
- `btc-adx-di-24-9`: Return and trade count within 15% Train reimplementation return 571.34% vs harness 571.34%; test 63.87%.
- `turtle-system-2`: Return and trade count within 15% Train reimplementation return 366.08% vs harness 366.62%; test 55.65%.
- `jesse_simple_bollinger`: Return and trade count within 15% Train reimplementation return 35.61% vs harness 35.61%; test 13.79%.
