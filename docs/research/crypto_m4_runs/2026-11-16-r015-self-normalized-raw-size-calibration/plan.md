# R015 — Corrected calibration of self-normalized inference

Status: `preregistered_synthetic_method_test`; no market-data or strategy-outcome test.

## Question

When the self-normalized recursive-mean Brownian-pivot test is evaluated as registered in R014, but raw per-timeframe rejections are separated from the Holm family decision, do one-test size and 12-frame familywise error meet the frozen thresholds over the same 24 dependence scenarios?

## Relationship to R014 and R013

R014's post-run audit found that its per-frame rate was calculated from Holm-adjusted rejections. The R014 Holm-FWER itself was independently recorded at the family replication level and remains valid for that implementation; it did not qualify under R014's FWER screen. R015 does not change the self-normalized statistic, Brownian pivot, null DGP, scenario grid, Holm procedure, confidence family, or thresholds. It corrects only the evaluation bookkeeping by keeping two separate outcomes: `raw_reject[t] = (p[t] <= 0.05)` and `family_reject = any(Holm(p)[t])`. It uses fresh fixed seeds and is not a reanalysis of R014 outcomes.

The method is the scalar mean version of the recursive self-normalization in Shao (2010), https://arxiv.org/abs/1005.2137, equations (3)–(4), under the stated weak-dependence/FCLT conditions. The result remains a finite-sample synthetic calibration, not empirical strategy validation.

## Frozen method and DGP

Reuse R014's method core and R013's unchanged synthetic DGP, identified by source SHA-256 in `manifest.json`. Per timeframe, compute `U_n = n*xbar_n^2 / [n^-2 sum(k^2*(xbar_k-xbar_n)^2)]`. Convert its upper-tail rank in the 250,000-path Brownian-bridge pivot reference to a one-sided p-value using sign independence; apply Holm to the full 12-frame family. Record unadjusted per-frame size and the Holm-family event independently.

Grid: 365/900 days × mean 8/40 opportunities × AR rho 0/0.5/0.9 × common shock fraction 0/0.75; negative-binomial size 2, null precision 0.80, heterogeneity 0.75; 1,000 datasets/scenario. Evaluation seed `20261119`; Brownian reference seed `20261120`; 250,000 paths × 2,048 increments. Cost: not applicable to this synthetic statistical method test.

## Frozen screen and uncertainty

Compute one-sided Wilson upper bounds for each of the 288 raw per-frame scenario rates and 24 scenario-level FWER rates using the same Bonferroni `z = Φ^-1(1 - 0.05/312)`, providing at least 95% simultaneous coverage over all 312 bounds without assuming timeframe independence. A method qualifies only if every raw per-frame upper bound is ≤7.5%, every scenario FWER upper bound is ≤8.5%, and there are zero failed replications. Any single failure means not qualified. No post-result changes to seeds, grid, p-value method, thresholds, or DGP.

## Scope

No raw candles, L2/trades, market signals, labels, exchange API, network, account, secret, order, or deployment. Synthetic arrays stay in memory; commit only aggregate results and reproducibility artifacts. Passing would only nominate the procedure for independent statistical review; it would not authorize R012 labels or establish 80% strategy precision.
