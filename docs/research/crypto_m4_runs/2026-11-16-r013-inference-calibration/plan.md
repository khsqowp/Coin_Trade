# R013 — Synthetic calibration of overlapping-forecast precision inference

Status: `preregistered_synthetic_method_test`; this is a methodology test only. It is not a strategy backtest, market-data analysis, signal-quality estimate, or authorization to generate labels.

## Question

Can a calendar-day score test of forecast precision against 80% control false-positive risk at nominal one-sided alpha 5% when outcomes are serially dependent and forecasts overlap? Can any candidate procedure support Holm correction over the 12 frozen timeframes?

## Why this differs from R012

R012 has no valid confirmatory inference procedure and therefore blocks all label generation. R013 uses only seeded synthetic Bernoulli outcome paths, generated counts, and shared latent shocks; it reads no market database or forecast labels. It tests inferential calibration, not whether the R005 signal has edge.

## Frozen estimand and tests

For each timeframe `t`, daily emitted count is `N[d,t]`, wins are `W[d,t]`, and score is `S[d,t] = W[d,t] - 0.80*N[d,t]`. The target is the pooled emitted-forecast precision, with the null `E[sum_d S[d,t]] <= 0`. Daily blocks are the unit of aggregation; no individual forecast is treated as independent. The 12 tests share a common calendar and latent shocks.

Compare one-sided studentized HAC tests with Bartlett weights and fixed lags 7, 14, and 30 days, plus synchronized circular moving-block bootstrap tests with fixed block lengths 7, 14, and 30 days. Bootstrap draws resample the same calendar block starts for all 12 timeframes, center each timeframe's daily score under its null, omit only the incomplete trailing block, and studentize the bootstrap mean using the sampled block-total standard error. Use a fixed seed and 499 bootstrap draws. Apply Holm to all 12 per-run p-values; no timeframe is selected after observing results.

## Synthetic data-generating processes

The complete grid is fixed in `manifest.json`: sample spans 365 and 900 days; outcome persistence `rho` 0, 0.5, 0.9; common-shock fraction 0 and 0.75; and per-timeframe daily opportunities with mean 8 and 40 (negative-binomial overdispersion fixed at size 2). Daily outcome-probability heterogeneity is separately fixed at 0.75 and is not conflated with temporal persistence. Under the null the stationary marginal target probability is exactly 0.80. The latent Gaussian AR(1) process is transformed through a probit conditional probability calibrated to marginal 0.80, with timeframe paths sharing the configured common component. Opportunity counts are generated independently of outcome shocks so pooled null precision remains 0.80 in expectation. The Cartesian grid is fully enumerated in the manifest.

The alternative is excluded from acceptance decisions: calibration under the null is the primary question. Any power estimate is descriptive only and must not be interpreted as strategy power.

## Decisions and failure criteria

For each method and scenario, record empirical per-test type-I rate, 12-test Holm familywise error rate (FWER), 95% binomial Monte Carlo intervals, and simulation failures. A procedure is *not qualified* if any tested scenario's upper 95% Monte Carlo bound exceeds 7.5% for nominal 5% per-test size or 8.5% for nominal 5% FWER, if p-values are non-finite, or if any implementation/test fails. Thresholds are screening tolerances, not proof of validity outside these DGPs. If no method qualifies, retain R012's inference blocker. If a method qualifies, it is only a candidate for independent statistical review; it does not authorize outcome labels or confirmatory claims.

## Reproducibility and boundaries

- Seed: `20261116`; deterministic outputs.
- No external data, network, exchange keys, orders, `.env`, market DB, or existing outcome files.
- Code and small aggregate results only; no large simulation arrays committed.
- Full scenario/method/replicate grid, runtime, code hash, environment versions, and output hash are recorded in the manifest.
- Smoke tests are implementation checks only and are excluded from the calibration report.
