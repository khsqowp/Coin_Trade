# US-19 - RSI2 dip in high-volatility market state (US, Round 2 prereg)

## Idea
Short-term oversold bounces pay more when the market itself is in a high-volatility regime (market-state conditioning of the US-05 sign-consistent near miss).

## Signal (fixed defaults)
Signal at close t: US-05 signal (RSI(2)_t < 10 AND close_t > SMA200) AND SPY 10-day realized vol (std of daily SPY returns over t-9..t) >= its median over the last 250 bars (including t).

## Execution
Buy close t; exit first close above SMA5 within 5 days, else close t+5.

## Common (all round-2 US hypotheses)
Written 2026-11-13 by the US session BEFORE any run of this hypothesis. Data/universe/cost/interpretation rules: spec/US-ADDENDUM-data.md (harness cache, top-30 PIT default + top-100 breadth variant as separate trial, USCost RT 0.403%, 2x sensitivity, break-even cost reported, halves split at dev midpoint). Dev only; holdout untouched. Verdict per PLAN Stage 1 (net mean>0, clustered t>=3, both halves>0). Generated because Round 1 had 0 survivors: ideas are structurally different (market-state, regime, cross-sectional) rather than parameter tweaks. Motivation: round-1 gross edges below 0.4% cannot pay the cost, so these target larger-move events. No parameters are tuned in Stage 1.
