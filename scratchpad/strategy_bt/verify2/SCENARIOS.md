# Round-2 weakness scenarios

Candidates under test: `jesse_simple_bollinger` (1h), `btc-max10-nyse-close` (15m), and the
daily trend cluster represented by `btc-macd-15-41-12`, `turtle-system-2`, `btc-bollinger-37-16`,
`btc-roc-36-9pct` (1d). Frozen params from `results/slice_*/summary.csv`. No re-selection.

Each scenario states the weakness, the test, and a pre-registered failure rule. A candidate that
meets any failure rule is downgraded; nothing is re-tuned to rescue it.

## Group A — statistics and benchmarks (verify2a/)

| ID | Weakness seen in round 1 | Test | Fails if |
|----|--------------------------|------|----------|
| A1 | 149 strategies tried; 5% null bar guarantees ~7 chance passes | White Reality Check + Hansen SPA over ALL implemented rows' TEST return series (stationary bootstrap, 2000 draws). Deflated Sharpe per candidate with N = ledger candidate count | RC/SPA p > 0.10 for the best row, or DSR < 0.95 |
| A2 | Null percentile is meaningless for high-frequency rows (percentile 100 with negative return) and the exposure-scaled B&H counted shorts as exposure | Replace with (a) long-only/short-only B&H per leg, (b) block-shuffled signal-timing null that preserves the strategy's trade durations and number of trades (circular shift of the position series, 1000 draws) | Candidate return below the 95th pctl of circular-shift null, or long leg below leg-wise B&H scaled by time in market |
| A3 | Fills assume next-open with fixed 0.02% slippage | Execution stress: 1-bar extra delay; slippage 0.05%, 0.10%; fee 0.06%/side | Test return <= 0 at delay=1 or slippage 0.05% |
| A4 | Perp funding ignored (longs pay in bull markets) | Pull Binance USDT-M funding history (public API) for the 5 majors; charge funding on every held bar per side; report net | Net test return <= 0 after funding |
| A5 | Sum of percent returns, no capital model | Portfolio equity curve: 5 symbols share 10k, each trade 1000 notional capped by free capital; report CAGR-like return, max drawdown, Sharpe, exposure | Max DD / return > 1.0 on TEST |

## Group B — regime, universe, parameter edges (verify2b/)

| ID | Weakness | Test | Fails if |
|----|----------|------|----------|
| B1 | TEST window is mostly a bull market; 94-100% of profit in one half-year | Download longer history (BTC, ETH, BNB, XRP, since listing; from 2017) into `data_long/`; evaluate frozen params over every calendar year and over stress windows 2018, 2022 | Loses money in 2 or more calendar years, or no positive result in 2018 and 2022 windows each |
| B2 | Pooled universe hides symbol dependence; some specs claim BTC only | Per-symbol breakdown; plus untouched universe ADA DOGE LINK LTC AVAX with frozen params | Fewer than 60% of untouched symbols positive on TEST |
| B3 | Winners sat on grid edges (bollinger k=1.4,n=45; roc thr=.07; adx_min=7) | Extend each axis 2 steps beyond the winner on both sides, report TRAIN and TEST surface; select on TRAIN only | Surface monotonically improving toward the new edge (optimum still outside), or TEST negative at selected point |
| B4 | One TRAIN/TEST split | Expanding-window walk-forward (retune on grid every 6 months, evaluate next 6) vs frozen params | Walk-forward return < 50% of frozen TEST return or negative |
| B5 | Eight daily candidates are one bet | Merge cluster into equal-weight basket; evaluate basket vs BTC buy-and-hold on drawdown-adjusted basis in each calendar year | Basket Sharpe <= B&H Sharpe in more than half of the years |
| B6 | `jesse_simple_bollinger` Ichimoku displacement convention unverified | Compare plugin signals to Jesse source semantic (cloud shifted forward 26 vs backward) using the cited repo; report signal agreement | Agreement < 99% or sign of test result flips under the alternative convention |

## Reporting

Per candidate: one tag from PASS_ALL / DOWNGRADED(<IDs>) / FAIL. No tuning after seeing results.
Forward test (paper) of `jesse_simple_bollinger` 1h runs in parallel as the out-of-sample judge.
