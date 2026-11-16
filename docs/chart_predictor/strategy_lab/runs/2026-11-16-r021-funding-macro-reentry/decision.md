# R021 decision — reject as strategy, keep as evidence

## Outcome

**Reject this fixed rule. Continue the project; do not use it for manual or live signals.** In the corrected 10–20 bar study, every timeframe's candidate target-first rate was 34.1–48.3%, far below the 80% target. Mean net R was negative in every timeframe under both base and doubled costs. The rule does not qualify as either a crypto M4 signal or a portfolio strategy.

## Corrected candidate results

Evaluation is the exposed development interval 2020-10-01 to 2024-01-01 UTC, end exclusive. Stop = 1 ATR20, target = 1.5 ATR20, maximum horizon = 10 or 20 timeframe bars. Costs are assumed 5 bp fee + 2 bp adverse slippage per side; stress doubles both. Wilson intervals are ordinary row-level intervals and understate uncertainty because trades cluster by symbol, funding event, and date.

| Timeframe | N (20 bars) | Target first | Wilson 95% | Mean gross R | Cost R | Funding R | Mean net R | Doubled-cost net R |
|---:|---:|---:|---:|---:|---:|---:|---:|---:|
| 1m | 2,128 | 48.31% | 46.19–50.43% | +0.219 | 1.527 | 0.000 | -1.308 | -2.835 |
| 3m | 2,045 | 43.52% | 41.39–45.68% | +0.111 | 0.791 | 0.000 | -0.679 | -1.470 |
| 5m | 2,059 | 43.32% | 41.20–45.47% | +0.105 | 0.593 | 0.000 | -0.488 | -1.082 |
| 10m | 1,967 | 40.62% | 38.47–42.81% | +0.049 | 0.412 | 0.000 | -0.363 | -0.776 |
| 15m | 1,968 | 39.08% | 36.94–41.25% | +0.005 | 0.325 | +0.000002 | -0.320 | -0.645 |
| 30m | 1,900 | 40.47% | 38.29–42.70% | +0.036 | 0.226 | +0.000017 | -0.190 | -0.416 |
| 60m | 1,568 | 40.37% | 37.97–42.82% | +0.031 | 0.151 | +0.000047 | -0.120 | -0.271 |

For the 10-bar horizon, target-first rates were 45.77%, 39.17%, 38.81%, 35.08%, 34.08%, 35.69%, and 36.15% for 1m through 60m, respectively. No timeframe approached 80%.

## Ablation interpretation

The full candidate did not consistently beat its event-matched controls. At 10m, 15m, and 60m, the no-funding-tail control had a higher target-first rate; the candidate's net R remained negative in every timeframe and was sometimes worse than controls. The BTC macro filter reduced trade counts but did not establish a robust incremental edge. These are descriptive comparisons, not independent statistical evidence.

The 1m–5m costs are especially damaging after risk normalization: the assumed 14 bp round trip is 0.59–1.53 R on average. This is not an exchange quote; it exposes how ATR-sized stops at those horizons make small fixed friction large relative to the intended risk. Even the 60m candidate remains negative after base and stress costs.

## Integrity and limits

- A first run was found to have four exits beyond the exclusive cutoff and had read two minutes past it. It is marked invalid and preserved. Corrected replay code reads only `< 2024-01-01T00:00:00Z` and requires every trade's maximum horizon to end by that cutoff. The corrected 761,988-row output has zero entry or exit boundary violations.
- Corrected run: 112 cells; six symbols; seven timeframes; four event-matched variants; 10/20-bar outcomes; base/stress costs. The complete output is in the ignored local artifact directory referenced in `manifest.json`.
- Price gaps and duplicate keys in the evaluation interval: zero for each of six symbols. The six-symbol panel is still survivor-biased and lacks point-in-time contract membership.
- Funding history is public Binance USDⓈ-M REST data, not Vision archive data. About 72–73% of records have blank `markPrice`; the prior 1m close proxy is approximate. Funding cashflows are near zero for short holds and do not repair the negative result.
- The interval is already exposed by R004. No validation or final holdout claim is possible. The final 2025+ period was not opened by this trial.
- The row-level Wilson interval ignores event/day dependence. The six-symbol design cannot meet the project M4 rule requiring at least 20 symbols, N≥200, ≥10% coverage, and a sealed evaluation.
- This event study does not simulate a funded portfolio, so it makes no CAGR/MDD or Buy-and-Hold claim.

## Decision

Reject the candidate unchanged. Do not tune thresholds against this exposed interval. Carry the null forward: funding crowding + BTC regime + ATR pullback/re-entry did not produce a high-precision, cost-positive edge under the fixed 10/20-bar contract. Project status remains 0/2 portfolio strategies and 0 qualified crypto M4 signals.
