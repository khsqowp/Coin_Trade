# R19-P partial-null power and missingness report

Date: 2026-11-18
Market data read: no
Frozen preregistration: `r19p_prereg_20261117.md`
Seed: 20261125
Simulations per profile: 5,000; multiplier draws per scale: 1,999; block lengths: 1, 2, 5, 10, 20.

## Alternative and partial-null calibration

| Profile | Partial-null paired false events | Rate (Wilson 95%) | Full-rule false promotions | Rate (Wilson 95%) | All-claim eligibility | Family coverage | Failed panels | Decision |
|---|---:|---:|---:|---:|---:|---:|---:|---|
| A | 0/5,000 | 0.00% (0–0.077%) | 0/5,000 | 0.00% (0–0.077%) | 99.98% | 84.56% | 0 | PASS |
| B | 1/5,000 | 0.02% (0.0035–0.113%) | 1/5,000 | 0.02% (0.0035–0.113%) | 100.00% | 85.28% | 0 | PASS |
| C | 2/5,000 | 0.04% (0.011–0.146%) | 1/5,000 | 0.02% (0.0035–0.113%) | 99.96% | 84.92% | 0 | PASS |

Full-rule hit rates by synthetic alternative `(candidate, baseline)`:

| Profile | (0.79, 0.50) | (0.80, 0.50) | (0.80, 0.80), true partial null | (0.85, 0.50) | (0.85, 0.80) |
|---|---:|---:|---:|---:|---:|
| A | 0.052% | 50.58% | 0/25,000 | 100.00% | 100.00% |
| B | 7.97% | 50.18% | 1/25,000 | 100.00% | 100.00% |
| C | 8.60% | 49.64% | 1/24,999 | 100.00% | 100.00% |

The `(0.79,0.50)` detection rate varies substantially by profile; treat it as a sensitivity result, not a market-performance estimate. Partial-null paired errors are the preregistered primary familywise diagnostic; full-rule promotions additionally apply the M2 and eligibility gates.

## Missingness diagnostics

Preregistration wording note: it calls these “six fixed missingness cells,” but its enumerated design has five applicable cells (three independent-1% profiles and B/C common-shock-5%); A common-shock is explicitly structurally inapplicable. The five listed applicable cells were run, with no substitution.

| Profile | Simulations | All-claim eligibility | Unresolved promotions | Failed panels | Decision |
|---|---:|---:|---:|---:|---|
| A independent 1% | 5,000 | 0% | 0 | 0 | DIAGNOSTIC_ONLY |
| B independent 1% | 5,000 | 0% | 0 | 0 | DIAGNOSTIC_ONLY |
| C independent 1% | 5,000 | 0% | 0 | 0 | DIAGNOSTIC_ONLY |
| B common shock 5% | 5,000 | 0% | 0 | 0 | DIAGNOSTIC_ONLY |
| C common shock 5% | 5,000 | 0% | 0 | 0 | DIAGNOSTIC_ONLY |

Zero eligibility is not a pass and does not show that missingness is harmless. Under the frozen rule, these missing-data profiles cannot be promoted; their zero coverage makes the inference unusable. A future market-data run must therefore classify unresolved outcome paths as inconclusive and report coverage, without dropping them from the denominator to inflate the hit rate.

## Decision and boundary

The three no-missingness synthetic profiles pass the frozen partial-null calibration. All five missingness profiles are diagnostic-only because eligibility is zero. This validates neither divergence alpha nor any trading signal. Market labels remain closed until the independent OHLC path-resolution tests and source review pass. Next: complete the method audit, verify the eligible dataset and time coverage, then run the preregistered divergence grid only if those gates pass.

Per-cell machine results are in each adjacent `results.json`; the 40,000 synthetic panel records are archived separately with a manifest and SHA-256 verification.
