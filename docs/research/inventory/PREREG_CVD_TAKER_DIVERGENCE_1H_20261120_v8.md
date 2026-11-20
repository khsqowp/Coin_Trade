# Preregistration v8 amendment: funding settlement completeness

> This amendment is frozen before candidate outcomes are read. Read v2-v8 as the full rule chain. It does not change signal generation, horizons, barriers, costs, or the historical-only disposition.

- Frozen: 2026-11-20, before outcome scoring.
- v8 responds to an independent red-team finding that nonempty funding archives and adjacent-row checks alone do not establish coverage at archive boundaries.
- Before scoring, all 864 funding symbol-month archives (36 symbols × 24 months) must pass the input audit with `utc_grid_checked=true` and `boundary_checked=true`.
- Every recorded funding timestamp must lie within 1 second of the UTC settlement grid implied by its row's `funding_interval_hours` (1h, 4h, or 8h intervals in this cohort). Adjacent rows must continue to match one of their recorded neighboring intervals.
- For each symbol-month, compare the first and last settlement against that month’s first observed hourly candle open and last observed hourly candle close. The first observed settlement must be the first expected UTC-grid settlement at or after the first candle. For the one approved partial initial listing, a first settlement up to one recorded interval before the first observed candle is allowed; this does not authorize missing interior settlements. The last settlement must equal the last expected UTC-grid settlement at or before the final candle close.
- The known ARBUSDT 2023-03 partial listing is the only allowed first-candle boundary exception; its actual first candle and settlement timestamps must still be independently recorded in the audit. Any other exception or mismatch fails the pre-score gate.
- The runner must require exactly 36 × 24 = 864 funding-month boundary checks and verify the per-archive boundary/grid flags before loading feature or outcome data.
- Any missing, off-grid, unverified, or boundary-incomplete settlement makes input QA fail; the affected funding charge is never imputed as zero. Do not score unless both the full archive audit and the independent code review pass on exact hashes.
- This is a completeness check for the frozen historical archive only. It does not validate source publication latency, funding-accounting semantics beyond the frozen model, or any future/live feed.
- This historical interval remains previously exposed development data. Passing this amendment permits at most one exploratory development score; it cannot establish OOS, a core strategy, paper promotion, production, Phase 9 combination, or any live/manual signal.
