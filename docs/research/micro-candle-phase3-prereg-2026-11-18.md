# Micro-candle phase 3 preregistration — 2026-11-18

Status: candidate rules frozen before the label-blind frequency screen. No target/stop path, realized return, or target-first label may be queried in phase 3a. This is not an independent preregistration: adjacent historical outcome summaries had already been exposed during repository research.

## Objective and sequence

Continue from one-candle direction diagnostics to the smallest additional candle morphology: a two-candle impulse-and-opposite-acceptance pattern on 1m bars. No macro, higher-timeframe, market-regime, cross-symbol, or indicator filters are used. A later timeframe or wider pattern family is permitted only after the fixed feasibility gates pass; this screen itself cannot establish an edge.

## Frozen hypothesis

For a completed impulse candle `A=t-1` and completed inside candle `B=t`:

1. Compute true range for each bar as `max(H-L, abs(H-prev_close), abs(L-prev_close))`.
2. Let `M` be the median true range of the 20 completed bars immediately before `A`; neither `A` nor `B` enters this median.
3. `A` is an impulse when `(H_A-L_A) >= M` and `abs(C_A-O_A)/(H_A-L_A) >= 0.60`.
4. `B` is inside when `H_B <= H_A` and `L_B >= L_A`.
5. Emit LONG when `A` is bearish and `(C_B-L_A)/(H_A-L_A) >= 0.75`.
6. Emit SHORT when `A` is bullish and `(C_B-L_A)/(H_A-L_A) <= 0.25`.
7. Equal-open/close bars, zero-range bars, non-finite fields, non-consecutive one-minute timestamps, and rows outside the fixed data window are ineligible, not signals.

The candidate is exploratory and not globally novel. Its intended distinction from ordinary inside-bar breakout is an opposite-direction close-location acceptance after a large-body impulse; local prior-art must still be reviewed before any outcome access.

## Data and feasibility-only gates

- Fixed input: read-only `chart_predictor/data/candles.sqlite`, file SHA-256 `cac23a3d18be66e226bdf8c3dbc0d08f5c6c185d4f18ed2a8687f08d2b6f67b1`.
- Fixed universe: all 100 symbols present in this snapshot; no outcome-based symbol selection. Contract metadata was not captured with the DB, so compliance with the product's COIN-underlying-only rule is unverified; report this as the recorded 100-symbol collection cohort, not a verified coin-only universe.
- Fixed time window: full observed input, 2026-07-16 18:10 UTC through 2026-11-14 00:28 UTC, subject to complete per-symbol data and 21-bar warm-up. Count qualifying opportunities per symbol.
- The only allowed phase-3a measurements are scheduled anchor count, feature-eligible count, raw event count, raw coverage, event counts by symbol, and a fixed 10-minute per-symbol cooldown count used only to estimate non-overlap sample availability. Coverage denominator is every timestamp-valid completed 1m anchor with 20-bar warm-up, including doji/zero-range bars as non-signals. Do not read forward OHLC paths or calculate entry/stop/target labels.
- Continue to M2 only if raw coverage is at least 10% of all scheduled anchors, cooldown-filtered events are at least 200 across at least 20 symbols, and no prior-art duplication is identified. Otherwise reject before outcome access.
- If eligible, a separate preregistration and independent review are required before any M2 evaluation. Minimum later gates remain M2 target-first >=80% over all issued signals, non-overlap N>=200 over >=20 symbols, coverage >=10%, and positive net expectancy after frozen costs. The phase-3a screen does not test any of those performance gates.

## Data-quality caveat

The 2026-11-18 read-only audit found 17,142,161 rows, 100 symbols, and zero observed gaps, duplicate keys, off-grid timestamps, invalid OHLCV, or nulls. The DB's page-level collection provenance is absent and prior collector logs reconcile row counts for only 97/100 symbols. This is already-exposed development history, not an untouched or sealed OOS sample. Any result is feasibility-only and does not qualify as strategy validation.
