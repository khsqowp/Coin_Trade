# R013 handoff

- Frozen plan: `plan.md`; preregistration fingerprints and execution settings: `manifest.json`; aggregate simulation output: `results.json`; decision: `decision.md`.
- The study used synthetic seeded arrays only. No market data, candle database, signal labels, or backtest outcomes were read.
- Final workload: 24 scenarios × 1,000 datasets; 499 bootstrap draws; six procedures; 12 synchronized timeframe tests. Runtime: 165.959s. Result hash: `b494b6a2bd348894d6793a339ea8f64b308f777e14c8e4035fd1ed926897c3bc`.
- All six registered procedures failed at least one frozen size/FWER screen. The inference blocker remains; no strategy labels or performance test is authorized.
- Post-run audit correction: do not use the JSON's per-test Wilson bands, `screen_qualified` flags, or 40/144 screen count. Those bands treated correlated timeframe tests as independent. Every method nevertheless fails based on at least one valid family-level Holm-FWER interval whose lower 95% bound exceeds 8.5%; see `audit.md` and the corrected `decision.md`.
- The interrupted first run ended before writing output and is excluded. The final preregistered DGP has fixed outcome heterogeneity 0.75 separate from temporal AR persistence.
- Suggested next step: if continuing method research, preregister a genuinely different finite-sample inference family and fresh random streams; do not tune these six procedures against R013 output. Independently, finish R012 baseline-estimand, rights, data-integrity, and recorder gates before any market-outcome work.
