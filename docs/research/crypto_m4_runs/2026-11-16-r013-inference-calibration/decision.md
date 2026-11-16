# R013 decision

Decision: `reject_all_six_methods_for_this_protocol; inference_blocker_retained`.

The preregistered synthetic calibration completed with 1,000 Monte Carlo datasets in each of 24 scenarios (24,000 datasets total), 499 synchronized moving-block resamples for each bootstrap method/dataset, six methods, and 12 timeframe tests per dataset. The program reported 165.959 seconds and no failed cells. Results are in `results.json` (SHA-256 `b494b6a2bd348894d6793a339ea8f64b308f777e14c8e4035fd1ed926897c3bc`).

| Method | Mean per-test false-positive point estimate across scenarios* | Mean Holm FWER | Largest scenario Holm-FWER lower 95% bound | Scenario producing that lower bound | Decision basis |
|---|---:|---:|---:|---|---|
| HAC Bartlett lag 7 | 11.55% | 25.00% | 71.40% | 365 days; mean count 40; rho 0.9; common 0 | Fail by Holm FWER |
| HAC Bartlett lag 14 | 10.34% | 22.28% | 63.01% | 365 days; mean count 8; rho 0.9; common 0 | Fail by Holm FWER |
| HAC Bartlett lag 30 | 9.85% | 21.69% | 58.14% | 365 days; mean count 8; rho 0.9; common 0 | Fail by Holm FWER |
| Circular MBB block 7 | 9.14% | 14.70% | 41.45% | 900 days; mean count 40; rho 0.9; common 0 | Fail by Holm FWER |
| Circular MBB block 14 | 7.41% | 9.76% | 21.65% | 365 days; mean count 40; rho 0.9; common 0 | Fail by Holm FWER |
| Circular MBB block 30 | 6.48% | 7.54% | 14.61% | 365 days; mean count 40; rho 0.9; common 0 | Fail by Holm FWER |

Every method fails the preregistered familywise screen: for each method, at least one scenario's Holm-FWER Wilson **lower** 95% bound is already above the allowed upper bound of 8.5%. This conclusion does not depend on the per-test interval calculation.

**Correction to the initial report:** the JSON's `per_test_95pct_wilson` intervals incorrectly treated all 12 timeframe rejection indicators within each Monte Carlo dataset as independent Bernoulli observations. The timeframes share common latent shocks; those bands are not valid 95% Monte Carlo confidence intervals. The JSON's `screen_qualified` flags and derived 40/144 pass count therefore must not be used. The per-test rates in the table above are point estimates only. The familywise Wilson intervals use one independent family-level FWER indicator per Monte Carlo dataset and remain the decision-valid evidence for rejecting all six methods. See `audit.md` for the full correction and reproduction basis.

## Interpretation limits

- These are synthetic null-rejection rates, not market forecast accuracy, trading performance, or evidence that any trading strategy has/does not have edge.
- Failure means the six specific algorithms failed the frozen finite-sample screening criteria under at least one of the tested DGP scenarios. It does not prove every possible procedure invalid.
- The DGP represents daily clustered outcomes with negative-binomial exposure, probit-normal heterogeneity, AR(1) persistence, and synchronized cross-timeframe shocks. Real forecast-label dependence may differ; this test cannot validate a market-data generating process.
- The initial interrupted run produced no retained results. The final registered code separated temporal persistence from fixed probability heterogeneity before the smoke and full run.

## Gate

Do not generate R012 labels, performance cells, p-values, confidence bounds, or pass/fail strategy claims. Do not retroactively enlarge blocks or change alpha, DGP, duration, or screening bounds and reuse this run as confirmatory. A follow-up method study requires a new preregistration, a genuinely different inference construction, and fresh simulation seeds; the R012 operational/data/right gates remain separate and unresolved.
