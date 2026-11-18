# Micro-magnitude Phase 1 preregistration — 2026-11-19

Status: frozen development diagnostic; not a trading signal, M2 claim, or confirmation study. The historical corpus has already been exposed by prior research.

## Question

At a completed 1-minute candle, does the immediately prior 1-minute absolute log return improve a one-step forecast of the next 1-minute absolute log return over a per-symbol training-median baseline? This isolates the smallest movement-size target before trying direction, a trade setup, adjacent-candle patterns, or broader context.

## Frozen definitions

- Target at minute `t+1`: `y[t+1] = abs(log(close[t+1] / close[t]))`.
- Candidate forecast at the close of `t`: `p[t+1] = abs(log(close[t] / close[t-1]))`.
- Baseline forecast: for each symbol, the median of valid one-minute absolute log returns in the fixed training interval. The median is computed once and frozen before the evaluation interval; there is no rolling refit.
- Eligibility: three positive finite closes at consecutive one-minute opens; exclude any row with invalid OHLCV, duplicate/off-grid timestamps, or a missing minute in the required sequence. Do not interpolate or forward-fill.
- Primary metric: equal-symbol-weighted relative MAE improvement. For each eligible symbol, compute paired candidate and baseline MAE over identical evaluation anchors, then compute `1 - MAE(candidate)/MAE(baseline)`; the primary estimate is the arithmetic mean across eligible symbols. Positive is better. Secondary: equal-symbol-weighted relative MSE improvement, all-observation-pooled relative MAE, and per-symbol MAE differences. This prevents the most densely observed symbols from dominating the primary estimate.
- Inference: paired seven-UTC-day circular moving-block bootstrap, 5,000 replicates, seed `20261119`; sample the same date blocks for all symbols. Report point estimate and 95% interval. Also report every eligible symbol; pooled rows are not independent sample size.

## Data and chronological split

- Input: `chart_predictor/data/vision_pit_dev_sample.sqlite`, table `candles`, read-only.
- Frozen file size: `30,363,320,320` bytes. Frozen SHA-256: `bb64efa272bab6c5bed258ec7284f9212165c8912cfcd824f51863ae5d88fafa` (recomputed from the full file before outcome scoring).
- Archived cohort: 86 contract symbols, 5,522 symbol-month manifest entries, 70 months from 2021-01 through 2026-10; previous metadata audit found 37 symbols with all 70 expected monthly minute-row counts. This does not establish a complete point-in-time exchange universe. The required eligibility count is checked without selecting on evaluation scores.
- Train return endpoints: `[2021-01-01T00:00:00Z, 2026-01-01T00:00:00Z)`; both closes defining each training return must be in this interval. No training target may cross the boundary.
- Evaluation target-candle close times: `[2026-01-01T00:00:00Z, 2026-04-01T00:00:00Z)`. Each scored target is a completed candle within this interval; its anchor and prior candle must also be within the interval, so no feature or target crosses the split boundary. Evaluation endpoint is defined by target availability, not forecast-anchor time.
- Preserve the entire stored symbol cohort; no symbol selection based on evaluation outcomes. Publish eligibility and counts by symbol before the score table.
- A symbol is score-eligible only with at least 10,000 valid training returns and 10,000 valid evaluation forecasts under the consecutive-bar rule. The threshold is applied before viewing its score. Include all ineligible symbols and reasons in the report.
- Before any target scoring, record exact file size, SHA-256, schema, row/time coverage, and outcome-blind OHLC/timestamp quality counts for the rows needed by the split. Any invalid source row or unexplained integrity issue is reported and excluded only under the frozen eligibility rule. Exact invalid/gap counts and eligible symbols are reported with results.
- This split is for development only. It is not sealed or independent OOS; historical research already touched the source corpus.

## Advancement gate

Continue this magnitude-diagnostic branch only if (a) at least 20 symbols meet the frozen data-eligibility minimum, (b) equal-symbol primary relative MAE improvement is positive with the entire paired 95% block interval above zero, and (c) more than half of eligible symbols have positive MAE improvement. Otherwise stop this branch. A pass may motivate a separately preregistered question about volatility-conditioned candidate coverage; it does not authorize a directional pattern, target-first outcome test, or M2 evaluation. Passing this diagnostic does not pass or modify the user's crypto gate: all-issued target-first M2 at least 80%, separate outcome-blind non-overlap N at least 200 across at least 20 symbols, and any required robustness gates.

## Prior exposure and status

P4b previously tested a thresholded future-movement expansion label and broad features; P4c closed that classifier family after walk-forward/multiplicity/cost review. This continuous one-step loss target is a distinct estimand but a close relative within an already explored volatility-prediction family. The hypothesis was selected after prior reports were available, and a reviewer saw those published report metrics while auditing novelty. Therefore this preregistration freezes only this one new diagnostic run; it cannot create independent confirmation or support a new-family claim. The report must state this exposure explicitly.

## Prohibited changes

No threshold search, alternate lookbacks, symbol/timeframe cherry-picking, direction/macro features, target/stop tuning, or evaluation-window changes after scoring. Any deviation is a new exploratory trial and cannot be used as confirmation. Do not inspect a future or sealed evaluation set; this registered interval is explicitly exposed development data.
