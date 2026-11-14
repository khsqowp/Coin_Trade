# US-16 - Breakout-day continuation (US, Round 2 prereg)

## Idea
A large-cap that surges on huge volume and closes near its high continues for a week (not earnings-gap-specific; no gap requirement).

## Signal (fixed defaults)
Signal at close t: close_t/close_{t-1}-1 >= +5.0% AND volume_t >= 2.5x mean(volume_{t-20..t-1}) AND (close-low)/(high-low) >= 0.75.

## Execution
Buy close t, sell close t+5.

## Common (all round-2 US hypotheses)
Written 2026-11-13 by the US session BEFORE any run of this hypothesis. Data/universe/cost/interpretation rules: spec/US-ADDENDUM-data.md (harness cache, top-30 PIT default + top-100 breadth variant as separate trial, USCost RT 0.403%, 2x sensitivity, break-even cost reported, halves split at dev midpoint). Dev only; holdout untouched. Verdict per PLAN Stage 1 (net mean>0, clustered t>=3, both halves>0). Generated because Round 1 had 0 survivors: ideas are structurally different (market-state, regime, cross-sectional) rather than parameter tweaks. Motivation: round-1 gross edges below 0.4% cannot pay the cost, so these target larger-move events. No parameters are tuned in Stage 1.
