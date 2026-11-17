# R017 — wild-cluster bootstrap calibration for target-first rate claims

Status: preregistered synthetic-only method test. R016's stationary-bootstrap maximum-standardized-error procedure is rejected; R017 is a distinct method iteration, not a retune of R016.

## Estimand and null

For each synthetic claim, let daily cluster score be `G_t = wins_t - 0.80 * emitted_t`. The boundary null is marginal target-first probability 0.80. The one-sided alternative is a rate above 0.80. This is a method-calibration statistic only; the user's actual strategy criterion remains the target-first point estimate ≥80%, and deadline-close direction accuracy remains a separate report.

## Data-generating test

Use the deterministic R016 synthetic panel generator with no market data: 20 symbols, 12 timeframe claims, separate 10/20 horizon claims, and both all-emitted and outcome-blind non-overlap branches in one 48-slot family. The primary sanity DGP is independent Bernoulli(.80) outcomes and independent ~10% signal issuance. Separate stress profiles retain overlapping future windows, common shocks, AR persistence and clustered issuance. Coverage is measured on all scheduled synthetic symbol×timeframe×anchor opportunities. A branch is eligible only at coverage≥10%, N≥200 and ≥20 represented symbols.

## Candidate method

Aggregate consecutive anchor-time score rows into calendar clusters of length L. For each claim, test the sum of centered cluster scores using a studentized cluster statistic. Generate synchronized Mammen two-point multiplier weights per temporal cluster, applying each weight to the full cross-claim vector to preserve same-time cross-symbol and cross-claim dependence. Use the bootstrap 95th percentile of the maximum studentized statistic across eligible claims. A family false promotion occurs if any eligible observed statistic exceeds that critical value. All eligible denominator branches and claims are included together; do not select the favorable branch or horizon.

The initial sanity profile uses L∈{1,2,5} anchor bins. Later overlap/persistent stresses use L∈{10,20,40,60,90,180} bins. Do not choose a block length by favorable observed rejection rate. Do not call the procedure fully valid solely because it passes a synthetic profile.

## Frozen gates

- 500 independent replications for the first screening run; 999 synchronized multiplier draws per replication.
- Per block setting, report replication-level family false-promotion rate, 95% Wilson interval, eligible-claim count, coverage/N eligibility rates and failed replications.
- Method fails if errors occur or the 95% Wilson upper bound for family false promotions exceeds 6% in any registered profile/block length.
- Any screen pass requires a later independent seed and ≥2,000 replications; uncertainty/coverage and baseline estimands must still be reviewed before market labels.
- R017 uses both N interpretations jointly only as a conservative diagnostic; it does not resolve the pending user choice.

## Limitations

The generator's outcomes are Bernoulli labels, not OHLC first-touch price paths. The first screen does not include unresolved labels, realistic per-timeframe bar cadence, costs, or a valid matched trading baseline. It cannot authorize performance scoring or strategy promotion. A failed R017 is retained as a failed method attempt; no criteria will be relaxed.
