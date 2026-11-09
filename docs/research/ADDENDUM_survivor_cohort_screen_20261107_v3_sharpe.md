# SUPERSEDED — Survivor-cohort screen Sharpe convention draft (v3)

> Status: superseded before execution by the integrated arithmetic addendum `ADDENDUM_survivor_cohort_screen_20261107_v2.md` (current SHA-256 `34373a8424a5fbf2fab7a35cbadc903bccf7f8efc89411458289cf195283d8c0`). Do not use this file as the controlling registration. Retained for audit trail; no deletion performed.

Base registration SHA-256: `c7629106db58f414caad82e78fccb27494ef5403b5a2cbcc6232cf262092adab`  
Execution-semantics addendum SHA-256: `417fed19507e7f22d339e0fc2186f9a59b42782af8b6c1e7a434ba31a1843bb5`  
Addendum time: 2026-11-07 Asia/Seoul.

This addendum freezes the Sharpe calculation only; it does not change the cohort, signals, fills, costs, segment boundaries, or exploratory-only status.

- Use simple daily NAV returns: `r_t = NAV_t / NAV_(t-1) - 1`.
- Use zero risk-free return; cash earns no interest under the base registration.
- Use the arithmetic mean of daily returns divided by their population standard deviation (`ddof=0`), annualized by `sqrt(252)`.
- Include every consecutive observed market date in the segment's NAV series, including zero-return cash days. Do not include a return before the segment's initial NAV of 1.0.
- If the population standard deviation is zero or fewer than two NAV observations exist, report Sharpe as undefined rather than zero.

Every comparison using Sharpe must cite this addendum. Results remain `SURVIVOR-COHORT / exploratory only`, not valid S&P 500/KOSPI 200 point-in-time evidence.
