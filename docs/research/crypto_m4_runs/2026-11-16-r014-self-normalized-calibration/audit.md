# R014 post-run audit — correction 1

## Finding

The result generator stored the Holm-adjusted rejection vector in `rejection_matrix`, then used that same matrix for the per-timeframe type-I rates and bounds. Thus those per-timeframe values estimate each frame's contribution after the 12-test Holm procedure, not the raw one-test size `P(p_t <= 0.05)` required by the plan. The per-timeframe `type1_rate`, its upper bound, and the combined `screen_qualified` field are withdrawn. The source artifact and original output remain unchanged for auditability.

## What remains usable

The scenario-level `holm_fwer` and its Wilson upper bound are based on whether each independent Monte Carlo dataset had any Holm rejection. They are valid family-level empirical metrics for the implemented p-values and synthetic DGP. Across 24 scenarios, FWER ranged from 5.4% to 31.3%; maximum occurred at 365 days, mean count 40, rho 0.9, common shock fraction 0. The lowest registered simultaneous upper bound was still 8.59%, slightly above the 8.5% screen; strongly persistent cases were far above it. Therefore R014 does not qualify its method for use. This result is specific to the synthetic DGP and implemented pivot approximation.

## Correction path

Do not patch or replace this completed result. R015 reuses the same frozen self-normalized test but explicitly stores both (1) unadjusted per-timeframe `p <= 0.05` rejection indicators and (2) the Holm family decision. It uses fresh Monte Carlo and Brownian reference seeds. Its preregistration and result are separate.

No market rows, signal outcomes, or trading metrics were read or generated.
