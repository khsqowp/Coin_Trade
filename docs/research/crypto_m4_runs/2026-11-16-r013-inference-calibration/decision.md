# R013 decision

Decision: `reject_all_six_methods_for_this_protocol; inference_blocker_retained`.

The preregistered synthetic calibration completed with 1,000 Monte Carlo datasets in each of 24 scenarios (24,000 datasets total), 499 synchronized moving-block resamples for each bootstrap method/dataset, six methods, and 12 timeframe tests per dataset. The program reported 165.959 seconds and no failed cells. Results are in `results.json` (SHA-256 `b494b6a2bd348894d6793a339ea8f64b308f777e14c8e4035fd1ed926897c3bc`).

| Method | Mean per-test false-positive rate across scenarios | Mean Holm FWER | Worst per-test 95% upper bound | Worst Holm-FWER 95% upper bound | Screen |
|---|---:|---:|---:|---:|---|
| HAC Bartlett lag 7 | 11.55% | 25.00% | 23.08% | 76.82% | Fail |
| HAC Bartlett lag 14 | 10.34% | 22.28% | 19.81% | 68.87% | Fail |
| HAC Bartlett lag 30 | 9.85% | 21.69% | 17.96% | 64.17% | Fail |
| Circular MBB block 7 | 9.14% | 14.70% | 17.94% | 47.60% | Fail |
| Circular MBB block 14 | 7.41% | 9.76% | 12.75% | 26.95% | Fail |
| Circular MBB block 30 | 6.48% | 7.54% | 10.21% | 19.24% | Fail |

Every method exceeded at least one predeclared per-test upper-bound (7.5%) or FWER upper-bound (8.5%) in at least one scenario. Across all 144 scenario-method combinations, 40 passed both screening bounds and 104 failed; no method passed every scenario. The better aggregate average of MBB block 30 does not qualify it: maximum serial persistence (`rho=0.9`) and common-shock cases remain materially miscalibrated. The per-test error appears worst in the 365-day, `rho=0.9`, common fraction 0.75, mean count 40 scenario. Holm FWER also remains too high in several scenarios.

## Interpretation limits

- These are synthetic null-rejection rates, not market forecast accuracy, trading performance, or evidence that any trading strategy has/does not have edge.
- Failure means the six specific algorithms failed the frozen finite-sample screening criteria under at least one of the tested DGP scenarios. It does not prove every possible procedure invalid.
- The DGP represents daily clustered outcomes with negative-binomial exposure, probit-normal heterogeneity, AR(1) persistence, and synchronized cross-timeframe shocks. Real forecast-label dependence may differ; this test cannot validate a market-data generating process.
- The initial interrupted run produced no retained results. The final registered code separated temporal persistence from fixed probability heterogeneity before the smoke and full run.

## Gate

Do not generate R012 labels, performance cells, p-values, confidence bounds, or pass/fail strategy claims. Do not retroactively enlarge blocks or change alpha, DGP, duration, or screening bounds and reuse this run as confirmatory. A follow-up method study requires a new preregistration, a genuinely different inference construction, and fresh simulation seeds; the R012 operational/data/right gates remain separate and unresolved.
