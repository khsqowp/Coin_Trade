# R014 — Self-normalized inference calibration for overlapping precision

Status: `preregistered_synthetic_method_test`; this is not a strategy backtest or a market signal evaluation.

## Research question

Does a literature-based self-normalized test for the daily precision score, followed by Holm correction across 12 timeframe claims, achieve acceptable null-size screening under the same 24 synthetic dependence scenarios that rejected all six R013 procedures?

## Why this is a distinct, non-tuned method

R013 tested Bartlett-HAC normal tests and circular moving-block bootstrap-t tests. R014 instead uses recursive partial-sample means and a self-normalizing denominator, with a Brownian-pivot reference distribution and no HAC bandwidth or bootstrap block-length selection. R014 uses a new Monte Carlo seed stream and does not alter or re-score R013 output.

Shao (2010), *A self-normalized approach to confidence interval construction in time series*, defines a recursive-estimate self-normalizer and derives an asymptotically pivotal statistic under a functional central limit theorem and remainder conditions. R014 applies the univariate mean-score form to `S[d,t] = W[d,t] - 0.80*N[d,t]`. This theorem is asymptotic, not a guarantee for these finite spans; calibration below is a screening study only. Primary source: https://arxiv.org/abs/1005.2137, especially equations (3)–(4) and Section 2.

## Frozen estimand and test

For each timeframe, the estimand is the calendar-day mean of `S[d,t]`, equivalent to pooled forecast precision minus 0.80 only when counts are independent of the success probability as in this synthetic design. Null: `E[S] <= 0`; alternative: `E[S] > 0`.

For a series `x[1..n]`, let `xbar_k` be its first-k sample mean and `xbar_n` its full-sample mean. Use

`W_n = n^-2 * sum(k^2 * (xbar_k - xbar_n)^2, k=1..n)`

and `U_n = n * xbar_n^2 / W_n`. Build a fixed pivot reference by simulating 250,000 standard Brownian paths on 2,048 equal increments. For each path compute `U = B(1)^2 / integral_0^1 (B(r)-r*B(1))^2 dr` using the frozen discrete-grid Riemann sum. Estimate the upper-tail probability with the plus-one correction. Since the Brownian endpoint sign is independent of its bridge, the one-sided p-value is `tail(U)/2` when `xbar_n>0`, and `1-tail(U)/2` otherwise. Holm is applied to the complete 12-timeframe family for each Monte Carlo dataset.

## Synthetic grid and decision thresholds

Reuse R013's exact frozen null generator by importing its versioned source without modifying it. The 24 scenarios remain: 365/900 days × mean 8/40 daily opportunities × AR persistence 0/0.5/0.9 × common shock fraction 0/0.75; negative-binomial size 2, marginal null precision 0.80, and separately fixed outcome heterogeneity 0.75. Run 1,000 independent datasets per scenario. The new seed is `20261117`; Brownian reference seed is `20261118`.

Report per-timeframe type-I rate and one-sided Wilson upper bound across the 1,000 independent Monte Carlo replications, 12-test Holm FWER and its one-sided Wilson upper bound, p-value/reference resolution, and runtime for each scenario. Use one-sided Bonferroni bounds with `z = Φ^-1(1 - 0.05/312)` so the 288 per-timeframe scenario bounds plus 24 scenario FWER bounds jointly have at least 95% Monte Carlo coverage without treating timeframes as independent. The predeclared candidate screen is the same numerical threshold as R013: every per-timeframe upper bound must be ≤7.5% and every scenario Holm-FWER upper bound ≤8.5%. A method failing any scenario/timeframe is not qualified. Passing would only make it a candidate for independent review; it would not validate the real-market dependence process or authorize outcome labels.

## Boundaries and reproducibility

- No market database, signal labels, exchange/API data, network call, keys, `.env`, orders, or deployment.
- Synthetic arrays exist only in memory; only compact aggregate JSON is saved.
- R013 generator source fingerprint is recorded in the manifest so DGP changes cannot silently enter this iteration.
- Separate reference and evaluation seed streams; deterministic runs; all registered scenarios/methods executed with failures retained.
- The 80% precision target is only the synthetic null used to calibrate inference. This run does not estimate empirical strategy accuracy.
