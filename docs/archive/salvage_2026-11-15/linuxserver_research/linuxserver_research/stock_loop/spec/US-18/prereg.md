# US-18 - Momentum-leader dip (US, Round 2 prereg)

## Idea
Dips in the strongest relative-strength names in the universe snap back more reliably than dips in laggards (momentum + short-term reversal combination, cross-sectional).

## Signal (fixed defaults)
Signal at close t: 126-day return rank of the stock is within the top third of the day's eligible universe AND RSI(2)_t < 10 (no SMA200 filter).

## Execution
Buy close t; exit at the first close above SMA5 within 5 days, else close t+5 (same exit as US-05).

## Common (all round-2 US hypotheses)
Written 2026-11-13 by the US session BEFORE any run of this hypothesis. Data/universe/cost/interpretation rules: spec/US-ADDENDUM-data.md (harness cache, top-30 PIT default + top-100 breadth variant as separate trial, USCost RT 0.403%, 2x sensitivity, break-even cost reported, halves split at dev midpoint). Dev only; holdout untouched. Verdict per PLAN Stage 1 (net mean>0, clustered t>=3, both halves>0). Generated because Round 1 had 0 survivors: ideas are structurally different (market-state, regime, cross-sectional) rather than parameter tweaks. Motivation: round-1 gross edges below 0.4% cannot pay the cost, so these target larger-move events. No parameters are tuned in Stage 1.
