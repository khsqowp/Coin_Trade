# R019-N multi-scale null calibration

Status: **A/B/C synthetic null calibration passed; market labels remain closed.**

## Frozen run

- Master seed `20261124`; each profile: 5,000 panels × 1,999 shared-vector Gaussian multiplier draws at each block length `1, 2, 5, 10, 20` UTC days.
- 24 claims, 48 paired contrasts, 365 synthetic calendar days. Profiles A/B/C and generator are inherited unchanged from R018; runner SHA-256 `4361240d26a5b04661f4b06c4a307d566c8bba12b1a6d048b6d1a3f5c4015b09`; R018 generator SHA-256 `829663f4d197ef19637880acf7b627b33e2b47260d10d5de7b00503fc85a0d99`.
- No historical market candles, price labels, or strategy outcomes were read. The result is method-only synthetic calibration.

## Primary preregistered gates

| Profile | Paired false-family events | Rate | Wilson 95% interval | Full-rule false promotions | Rate | Wilson 95% interval | All-claim eligibility | Errors | Gate |
|---|---:|---:|---:|---:|---:|---:|---:|---:|---|
| A | 8/5,000 | 0.16% | 0.081%–0.315% | 2/5,000 | 0.04% | 0.011%–0.146% | 100% | 0 | PASS |
| B | 5/5,000 | 0.10% | 0.043%–0.234% | 1/5,000 | 0.02% | 0.004%–0.113% | 100% | 0 | PASS |
| C | 6/5,000 | 0.12% | 0.055%–0.262% | 0/5,000 | 0.00% | 0.000%–0.077% | 100% | 0 | PASS |

Each paired event requires both same-claim comparator lower bounds to be positive at every registered scale. Full-rule promotions additionally require that claim's `M2≥0.80`. Every profile met the preregistered Wilson upper-bound limit of 6%, the eligibility floor of 95%, and zero numerical/runtime errors.

## Critical caveat: single-scale diagnostics

The predeclared promotion rule is the intersection across all five scales; individual scales are not accepted on their own. In the three null profiles, standalone single-scale contrast-family false-positive rates were above 5% at most/all longer lengths:

| UTC block length | A | B | C |
|---:|---:|---:|---:|
| 1 day | 5.74% | 5.50% | 5.04% |
| 2 days | 6.00% | 5.76% | 5.48% |
| 5 days | 6.94% | 6.62% | 6.46% |
| 10 days | 8.90% | 8.66% | 8.14% |
| 20 days | 13.92% | 13.52% | 12.90% |

Therefore this result does **not** validate any selected block length as a standalone confidence procedure. Only the frozen all-scale, two-baseline intersection met the registered empirical null gate. This conservative intersection can suppress false promotions; it does not repair or certify each individual-scale interval.

## What remains before market labels

1. R19-P fixed alternatives/power and unresolved-label diagnostics.
2. The `(0.80,0.80)` partial-null family gate in A/B/C, including FWER over true-null contrasts while retaining all contrasts in each max family.
3. Missingness diagnostics and the separately registered OHLC path/execution-method tests.
4. Independent red-team review of the exact frozen runner, manifests, and outputs.

Only after those method gates may the separately preregistered divergence study inspect market outcomes. Its three strategy-level robustness tests remain mandatory: 1,000 trade-order permutations with P95 MDD, five 504/252-day walk-forward windows with purging, and adjacent-cell plateau sensitivity. No strategy result, win rate, profitability, or live-readiness claim is made here.

## Files

- `profile-{A,B,C}-null/manifest.json`: exact configuration and source hashes.
- `profile-{A,B,C}-null/results.json`: profile-level counts, rates, uncertainty, diagnostics, and decision.
- `profile-{A,B,C}-null/panel_*.json`: 15,000 checksummed synthetic panel records; archive checksum is recorded in the adjacent `r19n_panels.tar.gz.sha256` file.
