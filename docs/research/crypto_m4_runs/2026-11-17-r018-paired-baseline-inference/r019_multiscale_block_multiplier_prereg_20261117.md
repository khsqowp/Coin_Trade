# R019 — Multi-scale block-multiplier paired inference

Status: **PRE-REGISTERED METHOD CANDIDATE; NOT YET RUN; market-label access remains closed.**

This is a distinct inference-rule iteration after R018's registered Profile-B, 20-day stationary-bootstrap cell exceeded its Wilson upper-bound gate. R018 remains rejected and unchanged. R019 does not choose a favorable R018 block, shorten the failing block, or use R018 market outcomes. R019 uses fresh panel seeds and a different resampling construction plus a predeclared intersection rule across all dependence scales.

## 1. Estimand and family

- Synthetic design remains 24 claims = 12 timeframes × two separate deadlines (10 and 20 bars), two same-anchor paired signal baselines per claim, 48 contrasts, 20 fixed symbols, 365 UTC calendar days.
- For claim `c`, baseline `b∈{momentum, random}`, UTC day `d`, let `n[d,c,b]` be matched resolved same-anchor emitted events and `x[d,c,b]` the sum of candidate-win minus baseline-win indicators. Estimate `Δ[c,b]=sum_d x[d,c,b]/sum_d n[d,c,b]`.
- Primary directional contrast is one-sided candidate superiority. The full family is all 48 registered contrasts. No timeframe, deadline, baseline, scale, or eligible claim may be selected after results.
- The user’s target-first point gate `M2≥0.80`, 10/20 deadline separation, all-emitted denominator, outcome-blind non-overlap `N≥200`/20-symbol eligibility, coverage≥10%, and fail-closed unresolved handling remain intact. These are not replaced by this paired inference method.

## 2. Proposed block-multiplier statistic

For each registered stationary sensitivity length `ℓ∈{1,2,5,10,20}` UTC days, separately:

1. Calculate the daily influence vector `ψ[d,j] = x[d,j] − Δ[j] n[d,j]`, for all 48 contrasts, with the same-anchor pairing and cross-contrast dependence kept in the vector. Do not discard zero-event days.
2. Form every overlapping contiguous block sum `B[s,j]=sum_{d=s}^{s+ℓ−1} ψ[d,j]`, for `s=1,…,D−ℓ+1`, `D=365`.
3. Let `S=D−ℓ+1` be the number of overlapping starts. Estimate the Bartlett-window long-run covariance scale by `Ωhat[j,k]=(Sℓ)⁻¹ sum_s B[s,j]B[s,k]`. The ratio standard error is `se[j]=sqrt(D Ωhat[j,j])/sum_d n[d,j]`. Nonfinite, zero, or materially negative diagonal estimates are a replicate error; no clipping to a successful result.
4. For each bootstrap draw, sample independent standard-normal multipliers `ξ[s]` over overlapping block starts. Apply each day/block multiplier to the complete 48-vector, never independently per contrast. Compute `T*[j] = (sum_s ξ[s] B[s,j])/sqrt(sum_s B[s,j]²)`; the draw statistic is the one-sided maximum across all eligible contrasts. Use 1,999 draws and NumPy `method='higher'` for the 95th percentile `c[ℓ]`.
5. Compute simultaneous one-sided lower bounds `LB[j,ℓ]=Δ[j]−c[ℓ] se[j]` for the complete 48-contrast family.

The overlapping block-sum multiplier is an implementation candidate motivated by blockwise multiplier methods for maxima in weakly dependent high-dimensional time series; this exact finite-sample adaptation is **not** assumed valid from literature alone. It must pass the registered empirical calibration below. See Zhang & Cheng (2014), Sections 2.1 and 4.1, for the primary blockwise multiplier/maxima framework: <https://arxiv.org/abs/1406.1037>.

## 3. Frozen multi-scale decision rule

- For claim `c`, robust paired superiority requires both baseline lower bounds positive at **every** registered length: for each `ℓ`, `LB[2c,ℓ]>0 AND LB[2c+1,ℓ]>0`.
- The robust paired family rejects only if at least one eligible claim satisfies that two-baseline condition at all five lengths. The full user-rule promotion additionally requires that claim’s all-emitted `M2≥0.80` and its separate eligibility gate.
- No per-scale result is promoted alone; no “best block length” is selected. Per-scale FWER, interval coverage, and error counts are diagnostics. The inferential claim is restricted to the **predeclared all-scale intersection decision**, and only across the tested synthetic DGPs.
- Report both the paired-only multi-scale false-superiority rate and the full user-rule false-promotion rate. The calibration does not establish that a point M2 of 80% has 5% type-I error, nor does it prove profitability.

## 4. Calibration run order and gates

### Stage R19-N: equality-null size calibration

- Reuse the fixed synthetic outcome generator/profile definitions from R018 only; do not read market candles or labels. Fresh master seed: `20261124`. Run all three null profiles A, B, C; each profile has 5,000 independent panels, 1,999 multiplier draws per panel/length, all 24 claims and all 48 contrasts, all five lengths.
- Derive child seeds from `(master, R019 version, profile, panel, length)` using `SeedSequence`. Store a manifest and checksummed panel results; deterministic replay is mandatory.
- For each profile, the multi-scale paired-only false-family-superiority rate and full-rule false-promotion rate are reported with 95% Wilson intervals. **PASS** requires: (a) paired-only Wilson upper bound ≤6%; (b) full-rule false-promotion Wilson upper bound ≤6%; (c) at least 95% of panels have all 24 claims eligible; (d) zero runtime/numerical/invalid-covariance errors. Any failure rejects R019 before alternatives, missingness, OHLC path, or market outcome scoring. Ineligible panels remain non-promotions for unconditional error rates and are separately reported.
- Also report each individual length’s paired FWER, Wilson interval, simultaneous coverage, cross-length overlap of false rejections, median/max critical value, and joint error count. These diagnostics cannot override the primary multi-scale gate.

### Stage R19-P: power and unresolved-label diagnostics (only after all R19-N profiles pass)

- Run every fixed R018 alternative pair `(0.79,0.50)`, `(0.80,0.50)`, `(0.80,0.80)`, `(0.85,0.50)`, `(0.85,0.80)` under profiles A/B/C with fresh indexed child seeds; report point-M2 gate and multi-scale paired/full-rule promotion separately. These are power diagnostics, not a threshold-selection set.
- The `(0.80,0.80)` cells create a partial-null family. For the registered true-null contrasts only, compute multi-scale paired FWER and its 95% Wilson interval. Require Wilson upper ≤6%, all-claim eligibility ≥95%, and zero runtime/numerical errors for every profile before proceeding. Non-null contrasts do not enter that partial-null FWER numerator, but remain in the simultaneous maximum family as registered.
- Run independent 1% and common-shock 5% missingness under profiles allowed by the generator. Any unresolved emitted event makes its claim inconclusive under the frozen rule; report all-unresolved-as-loss sensitivity. Do not silently count missingness as a trade loss or remove affected claims.
- Run the separately registered OHLC-path method-only test for executable next-bar entry, stop-first ties, gaps, fees, and stress costs. R019-N/P cannot validate path labels or actual trading costs.

Only if all required R19-N, partial-null, alternative, unresolved, and OHLC-path method gates pass and an independent review confirms the exact code/config/data fingerprints may market outcomes be considered. Such permission is still development-only and does not establish sealed OOS performance.

## 5. Failure conditions and interpretation

- Any null profile failing either Wilson gate, eligibility floor, deterministic replay, or error-free execution rejects R019. Do not adjust `ℓ`, bootstrap draws, seed, quantile method, thresholds, DGP, or family after looking at results. Preserve all outputs.
- A rejection authorizes no market-label scoring and no claim that the strategy itself is bad; it means this inference procedure has not been shown reliable for its registered synthetic DGPs.
- A pass validates only the measured Monte Carlo operating characteristics under the three registered synthetic profiles. It is not proof for real crypto data’s dependence, regime changes, tails, missingness, fees, or execution.
- Strategy-specific 1,000 trade-order Monte Carlo/P95 MDD, 504/252-day five-window WFA, and adjacent-parameter plateau remain separate mandatory gates. No risk-sizing recommendation is made because the user’s maximum portfolio drawdown cap is unset.

## 6. Primary references

- X. Zhang and G. Cheng (2014), “Bootstrapping High Dimensional Time Series,” arXiv:1406.1037, especially Sections 2.1 and 4.1: <https://arxiv.org/abs/1406.1037>.
- P. Hall, J. L. Horowitz, and B.-Y. Jing (1995), “On blocking rules for the bootstrap with dependent data,” *Biometrika* 82(3), 561–574, DOI: <https://doi.org/10.1093/biomet/82.3.561>. Their analysis emphasizes that appropriate block size depends on the inferential target; it does not justify selecting a favorable length after seeing test outcomes.

## 7. Status

No R019 code, simulation, or market-result test has run as of this preregistration. This document must be committed before starting Stage R19-N. The rejected R018 artifacts remain immutable.
