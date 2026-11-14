# US-20 - Small-cap lag catch-up (KR-12 analogue) (US, Round 2 prereg)

## Idea
Cross-market analogue of KR-12 (KOSDAQ lagging KOSPI by >=3% over 3 days): IWM lagging SPY badly rebounds.

## Signal (fixed defaults)
Signal at close t: ret3_IWM - ret3_SPY <= -2.0% (ret3 = close_t/close_{t-3}-1). ETF IWM only (single trial).

## Execution
Buy IWM close t, sell close t+3.

## Common (all round-2 US hypotheses)
Written 2026-11-13 by the US session BEFORE any run of this hypothesis. Data/universe/cost/interpretation rules: spec/US-ADDENDUM-data.md (harness cache, top-30 PIT default + top-100 breadth variant as separate trial, USCost RT 0.403%, 2x sensitivity, break-even cost reported, halves split at dev midpoint). Dev only; holdout untouched. Verdict per PLAN Stage 1 (net mean>0, clustered t>=3, both halves>0). Generated because Round 1 had 0 survivors: ideas are structurally different (market-state, regime, cross-sectional) rather than parameter tweaks. Motivation: round-1 gross edges below 0.4% cannot pay the cost, so these target larger-move events. No parameters are tuned in Stage 1.
