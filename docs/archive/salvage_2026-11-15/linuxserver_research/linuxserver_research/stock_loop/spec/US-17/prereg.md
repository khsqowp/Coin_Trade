# US-17 - Hammer after gap-down (US, Round 2 prereg)

## Idea
A gap-down that is bought through the day and closes in the upper range shows exhausted selling; unlike US-01 (blind open buy) the intraday reversal is confirmed before entry.

## Signal (fixed defaults)
Signal at close t: open_t/close_{t-1}-1 <= -2.0% AND close_t > open_t AND (close-low)/(high-low) >= 0.70 AND close_{t-1} > SMA200_{t-1}.

## Execution
Buy close t, sell close t+3.

## Common (all round-2 US hypotheses)
Written 2026-11-13 by the US session BEFORE any run of this hypothesis. Data/universe/cost/interpretation rules: spec/US-ADDENDUM-data.md (harness cache, top-30 PIT default + top-100 breadth variant as separate trial, USCost RT 0.403%, 2x sensitivity, break-even cost reported, halves split at dev midpoint). Dev only; holdout untouched. Verdict per PLAN Stage 1 (net mean>0, clustered t>=3, both halves>0). Generated because Round 1 had 0 survivors: ideas are structurally different (market-state, regime, cross-sectional) rather than parameter tweaks. Motivation: round-1 gross edges below 0.4% cannot pay the cost, so these target larger-move events. No parameters are tuned in Stage 1.
