# Micro-candle phase 4 — single-bar close-location M2 preregistration

Status: exploratory development study on an already exposed historical archive. This cannot establish sealed OOS performance or authorize live use. The previous one-bar study measured next-close direction only; this phase tests the distinct target-first outcome, without adding macro filters or longer patterns.

## Frozen question and rule

Does a completed 1-minute candle closing in the upper (lower) 20% of its high-low range forecast a 1R target before a 1R stop within the next 10 or 20 minutes?

- At the close of minute `t`, emit long when `(close-low)/(high-low) >= 0.80`; emit short when the value is `<= 0.20`. Zero-range, malformed, non-minute-aligned, or feature windows crossing a missing minute do not emit.
- Entry is the next contiguous 1-minute bar open. The side is fixed at issuance. Every emitted signal remains in the all-issued denominator, including invalid entries and overlapping forecasts.
- Risk distance is the causal 14-minute simple-average true range at `t`, requiring 14 consecutive valid minutes. Stop and target are each one risk unit from entry, mirrored for short. An entry already through either barrier is a resolved failure.
- Score separate 10-minute and 20-minute claims. The entry minute is the first observed path bar. First barrier wins; if both barriers are touched in the same 1-minute OHLC bar, stop wins. A stop gap exits at the adverse open; target fills at its level. Timeout is a failure. A missing/malformed required path bar is unresolved, never silently removed.
- M2 is target-first / all emitted signals with resolved outcomes. Also report unresolved ratio and a conservative all-unresolved-as-failure sensitivity. The required outcome-blind non-overlap selector is per symbol, chronological, skipping until each signal's registered horizon ends; it is used only for N and portfolio-risk diagnostics.
- Report M1 direction at deadline separately. Matched same-anchor baselines use the signal candle's close-to-open direction (zero uses deterministic SHA-256 fair side) and an independently keyed deterministic SHA-256 fair side, with identical entry, ATR distance, horizon, and barrier resolver.

## Fixed comparisons and costs

- Primary rule is exactly close-location 0.80/0.20, stop 1.0R, target 1.0R. Both 10- and 20-minute horizons are separate claims; neither is selected after observing outcomes.
- Sensitivity-only neighboring cells are close-location thresholds 0.16, 0.18, 0.22, 0.24 paired with 0.8R and 1.2R target distances, keeping stop 1R and both horizons fixed. The primary cell is included. No cell is promoted by the sensitivity table; the full cell family is reported.
- Costs follow the immediately preceding fixed micro-candle phase protocol: 14 bp round trip base (5 bp fee + 2 bp slippage per side) and 28 bp stress. Funding is zero unless a recorded settlement is crossed; if funding is unavailable, state it is unmodeled. Costs apply to executable-price returns, not to the binary M2 label.
- Required scheduled-bar denominator is every eligible symbol × contiguous completed minute anchor after the ATR warm-up. Coverage is emitted forecasts / scheduled anchors, not share of directional candles.

## Data and temporal evaluation

- Read-only input: `chart_predictor/data/vision_pit_dev_sample.sqlite`; frozen fingerprint recorded in the prior data audit: SHA-256 `bb64efa272bab6c5bed258ec7284f9212165c8912cfcd824f51863ae5d88fafa`, 86 archived symbols, ending 2026-10-31 UTC. Keep the complete archive universe; do not select symbols by outcomes. This is not a proven complete point-in-time futures universe.
- Re-audit schema, OHLC validity, minute continuity, and emitted-path resolution before scoring. Inputs and feature values stop at the completed anchor; outcomes begin at the following minute open.
- Use five chronological, shared-calendar 504-day train / 252-day test windows advanced by 252 days, fixed by the crypto research protocol (2022-01-01 start; last test ends 2026-10-31 exclusive). Since the rule has no fitted parameters, training windows are causal reproduction/eligibility checks; never tune on test folds. Report each fold and pooled OOS separately.
- This exposed archive is development-only. A passing result remains exploratory and cannot meet the sealed/forward promotion gate.

## Decision gates and reporting

Report each horizon and fold: issued/eligible, coverage, symbols, resolved/unresolved/invalid/timeout, all-issued M2, direction-at-deadline, both same-anchor baselines, paired differences, non-overlap N and symbol count, and base/stress mean net return and net R. Do not treat minute observations as independent.

The first decision gate is the frozen primary screen: M2 point estimate >=80%, positive net expectancy after frozen costs, and no material disadvantage versus either same-anchor signal baseline. If any of those fail clearly, reject without an optimization grid; Monte Carlo and plateau work cannot rescue the failed rule and would add no decision value. Only a primary-screen survivor proceeds to all remaining gates: separate non-overlap N>=200 across >=20 symbols, coverage >=10%, >=95% path resolution, dependence-aware baseline inference with exact-family synthetic calibration, 1,000 deterministic reorderings of the non-overlap net-R sequence with historical and P95 MDD, adjacent-parameter plateau, prefix invariance, and deliberate future-peeking tests. Monte Carlo does not model overlapping positions. Any missing/under-sampled sensitivity neighbor fails.

No parameter or timeframe expansion is authorized by an attractive result. If the primary single-candle family fails, retain the failure and move to one structurally distinct two-candle mechanism only after its feature frequency is screened without outcomes.
