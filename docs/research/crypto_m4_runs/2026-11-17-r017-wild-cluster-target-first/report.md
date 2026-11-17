# R017 — interim result: wild-cluster method does not pass calibration

## Result

The Mammen wild-cluster bootstrap max-t procedure **fails the registered screen** on the independent Bernoulli(.80) null. It is not approved for confirmatory market inference.

| Temporal cluster length | Family false promotions | Rate | 95% Wilson interval | Errors |
|---:|---:|---:|---:|---:|
| 1 anchor bin | 28 / 500 | 5.6% | 3.9–8.0% | 0 |
| 2 anchor bins | 28 / 500 | 5.6% | 3.9–8.0% | 0 |
| 5 anchor bins | 43 / 500 | 8.6% | 6.4–11.4% | 0 |

The preregistered gate requires the Wilson upper bound to be ≤6% for every block setting. None passes. The 5-bin lower bound also exceeds 6%. Each replication had 20 symbols, 12 timeframes × 10/20 horizons, and both all-emitted/non-overlap branches in the family. The synthetic null rate was 80%; mean raw coverage was approximately 10.50%; all 500 replications met N≥200 in both branches, and a replay of the deterministic issuance stream confirmed all claims represented at least 20 symbols. There were zero failed replications.

## Interpretation

R017 is a new candidate method, not an adjustment to the rejected R016 procedure. It aggregates the score `wins - 0.80 × count` by temporal clusters and applies synchronized Mammen multiplier weights across the full eligible family. The result shows that this method, in its current form and under this test, does not meet the project's conservative calibration gate. Do not promote it based on the 5.6% point rate at block lengths 1/2: the confidence upper bound is 8.0%, and block length 5 fails more strongly.

The metric remains the user's target-first point-rate objective ≥80%; this test's null-boundary false-promotion screen is a diagnostic for inference, not a replacement success rule. No market data, price paths, strategy signals, performance labels, costs, or sealed OOS results were read.

## Reproducibility

- Plan: [`plan.md`](plan.md)
- Result JSON: [`results_iid_bernoulli_screen.json`](results_iid_bernoulli_screen.json)
- Seed `20261122`; 500 replications; 999 multiplier draws; 365 synthetic anchor bins.
- Python 3.13.5; NumPy 2.2.6; runtime 93.222 seconds.
- Script SHA-256: `37d3098fc5c0c20c4cf381d8b8344f0d4f3c707db0120e2d2fa6db688aabe06c`.
- Generator SHA-256: `045baa14c8b7728557a4446a9e541d0e6a8b7c00572231ccab43b77899558333`.
- R017/R016 focused tests: 11 passed before the run; full chart-predictor suite verification remains to be recorded after integration.
