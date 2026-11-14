# US-15 - Idiosyncratic capitulation (US, Round 2 prereg)

## Idea
A stock that dropped much more than the market over 3 days, on heavy volume, in an uptrend, rebounds.

## Signal (fixed defaults)
Signal at close t: (ret3_stock - ret3_SPY) <= -6.0% where ret3 = close_t/close_{t-3}-1, AND close_t > SMA200 AND volume_t >= 1.5x mean(volume_{t-20..t-1}).

## Execution
Buy close t, sell close t+5.

## Common (all round-2 US hypotheses)
Written 2026-11-13 by the US session BEFORE any run of this hypothesis. Data/universe/cost/interpretation rules: spec/US-ADDENDUM-data.md (harness cache, top-30 PIT default + top-100 breadth variant as separate trial, USCost RT 0.403%, 2x sensitivity, break-even cost reported, halves split at dev midpoint). Dev only; holdout untouched. Verdict per PLAN Stage 1 (net mean>0, clustered t>=3, both halves>0). Generated because Round 1 had 0 survivors: ideas are structurally different (market-state, regime, cross-sectional) rather than parameter tweaks. Motivation: round-1 gross edges below 0.4% cannot pay the cost, so these target larger-move events. No parameters are tuned in Stage 1.
