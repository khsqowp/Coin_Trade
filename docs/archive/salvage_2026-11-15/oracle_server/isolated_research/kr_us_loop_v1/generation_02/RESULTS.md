# Generation 02 — exploratory results

Run: `GEN02-20261106T092448-5390` · 2026-11-06 UTC  
Preregristration: `PREREG.md`  
Ledger: `attempts_GEN02-20261106T092448-5390.jsonl` · Curves: `equity_curves_GEN02-20261106T092448-5390.csv.gz`

## Outcome

All 12 planned executions completed: six fixed candidates in each market, 12 starts, 12 finishes, 12 unique IDs, no runtime failures. All are `COMPLETED_EXPLORATORY`. No valid strategy was found. These later partitions have already been inspected and cannot serve as untouched confirmation. The KR comparison benchmark and PIT/data snapshot have the limits recorded in Generation 01.

**All six KR results are invalid for performance comparison.** Gen02 uses the same KR price-repair loader, for which an independent reproduction showed nonpositive prices and infinite/NaN volumes arising from rows with volume but zero close. Keep the KR values below only as an execution record; do not infer an edge from them. Gen02 US results are not affected by that specific KR defect but remain exploratory.

Annualized net CAGR (%). US SPY benchmark: 5.22 IS / 14.84 later. KR provisional available-universe equal-weight proxy: 0.13 / 1.99. Monthly decisions: 192 IS + 119 later for US; 91 IS + 83 later for KR.

| Candidate | US IS | US later | KR IS | KR later |
|---|---:|---:|---:|---:|
| TS63_KENDALL | 6.40 | 10.10 | -1.76 | 1.55 |
| OLS_MULTI_3OF4 | 9.38 | 10.05 | -14.54 | -7.73 |
| SIGN_FLIP63 | 2.82 | 3.64 | -26.47 | -26.90 |
| KALMAN_DRIFT63 | 6.88 | 12.63 | 1.56 | 7.21 |
| EHLERS_SSF40_SLOPE5 | 4.08 | 12.00 | -1.02 | -0.25 |
| BREADTH_60_40_BASKET | 9.45 | 7.40 | -1.87 | 3.87 |

US candidates all lagged SPY in the later screening partition. KR Kalman Drift and Breadth exceeded the provisional KR proxy, but that is only a screening observation, not evidence of a valid edge: the benchmark is a non-index proxy and the KR data coverage/universe/adjustment limitations remain unresolved. The KR KALMAN result is a possible candidate for a correctly sourced future test, not a pass.

## Attempt history and verification

- `attempts_preflight.jsonl` preserves the initial synthetic pass, independent review hold (monthly state, Ehlers gap initialization, and weak causal perturbation test), and corrected synthetic pass. Corrections were completed before market-data execution.
- Six candidate paths passed synthetic finiteness, long-only/unlevered bounds, next-open simulation, and randomized post-cutoff perturbation checks. Monthly-state tests also passed. These tests validate implementation invariants only, not live-market behavior.
- Run artifacts pin the preregistration/runner hashes, per-attempt metrics, daily curves, market sizes and benchmark values. Cumulative historical trial count remains unknown; no DSR/PSR/global multiplicity claim is made.
