# R016 — interim result: candidate interval procedure rejected

## Result

The synchronized stationary-block bootstrap maximum-standardized-error lower-bound method **fails** the registered 6% Wilson-upper calibration gate, even on an independent Bernoulli null. Do not use it for confirmatory market inference.

| Mean block length | False family promotions | Rate | 95% Wilson interval | Replication errors |
|---:|---:|---:|---:|---:|
| 1 | 58 / 500 | 10.8% | 9.1–14.7% | 0 |
| 2 | 60 / 500 | 12.0% | 9.4–15.1% | 0 |
| 5 | 66 / 500 | 13.2% | 10.5–16.4% | 0 |

The null marginal target-first probability was 80%. In this simplest diagnostic, each claim's synthetic outcomes and issuance were independent across anchor steps; the 48-claim family retained both all-emitted and outcome-blind non-overlap branches. Median sample counts were 766 all-emitted and 319.5 non-overlap events. Every replication had N≥200 and all 20 symbols represented in every branch; mean raw coverage was 10.50%. The false-promotion confidence intervals are well above the preregistered 6% upper bound, so Monte Carlo uncertainty does not explain the failure.

The 80% lower-bound test here is an inference-method stress test, **not a new user acceptance criterion**. The user's strategy rule remains OOS target-first point estimate ≥80%, with deadline-close direction accuracy separate. The existing SPEC's baseline comparison, costs, coverage, symbol, and sealed-evaluation gates remain unchanged.

## Independent code review and corrections

Two statistical reviewers independently reviewed the code. The first caught three implementation/specification defects before this definitive simple-null rerun: outcome windows started at the anchor rather than after it; the minimum 20-symbol eligibility gate was missing; and the code's `screen_pass` used the false-pass point estimate instead of the plan's Wilson-upper ≤6% gate. These were corrected. Tests now explicitly assert future-only window behavior, outcome-blind non-overlap selection, both sample branches, fail-closed eligibility, and independent-null marginal calibration.

The second reviewer found the family-array order internally consistent and independently reported a pre-correction simple-null diagnostic of 67/500 false promotions. That run was not persisted and is not included as an authoritative result. The corrected persisted run above independently reproduces the method failure.

## Scope and limitations

- The persisted 500-replication run is synthetic-only; it reads no market candles or labels and tests no trading candidate.
- Outcomes are synthetic Bernoulli labels, not actual price paths with target/stop/deadline first-touch. The run validates only a candidate confidence-bound procedure under a simple null.
- The method uses a fixed bootstrap standard error per claim rather than a fully studentized bootstrap-t statistic. Its empirical failure is sufficient to reject it under this registered screen.
- Persistent, overlapping-window and unresolved-label stress tests still need to be rerun using the corrected code. A pass on any later DGP cannot override this failure; a different method iteration requires a new preregistration.
- N=200 interpretation is still awaiting the user's selection. Both denominator branches are included jointly here to prevent favorable-branch selection. No market outcomes or performance labels were opened.

## Preserved exploratory iterations

The directory also preserves the iteration trail. `results_365d_pilot.json`, `results_iid_ar_diagnostic.json`, and `results_iid_anchor_sanity.json` predate the code audit and are superseded. `results_iid_anchor_sanity_v2.json` is a 100-rep corrected-code pilot, not a decision run. `results_iid_anchor_sanity_v3.json` is a 500-rep corrected-code diagnostic with zero serial AR and no overlapping outcome windows, but it retains same-time common/symbol/frame factors; its family false-pass rates were 10.8%, 12.0%, and 13.2% at block lengths 1/2/5. It is supporting evidence of failure under cross-sectional dependence, not an independent Bernoulli test. The authoritative IID Bernoulli result above is stored separately and has its own source hash.

## Reproducibility

- Plan: [`plan.md`](plan.md)
- Persisted result: [`results_iid_bernoulli_baseline.json`](results_iid_bernoulli_baseline.json)
- Script SHA-256 recorded in result: `045baa14c8b7728557a4446a9e541d0e6a8b7c00572231ccab43b77899558333`
- Seed: `20261121`; 500 independent replications; 199 bootstrap resamples; block lengths 1, 2, 5.
- Runtime: 55.767 seconds; Python 3.13.5; NumPy 2.2.6.
- Tests: `chart_predictor/tests/test_r016_synthetic_event_calibration.py` — 7 passed.
