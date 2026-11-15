# Crypto BTC macro → 5m sweep/MSS candidate: preregistration

Status: one fixed exploratory development test. This protocol is not a sealed/OOS test and cannot establish the 80% target. The historical interval was already exposed to earlier research, but this exact sequential rule has not been tested. The purpose is a falsifiable triage: decide whether the rule is clearly unworthy of any prospective collection, not select parameters.

## Hypothesis

When BTC's latest confirmed 4-hour structure has HH+HL (or LH+LL), a coin's later 5-minute liquidity sweep and distinct close-confirmed market-structure shift in the same direction may have greater target-first precision and net R than matched momentum and random-direction entries.

## Frozen data and universe

- Source: local `chart_predictor/data/candles.sqlite`, opened read-only. Score universe rows only when `2026-07-17T00:00:00Z <= t_open_ms < 2026-10-09T00:00:00Z`. BTC alone may use earlier rows, if present, from the immediately preceding 3 UTC days as 4h macro warm-up; these rows cannot generate scored anchors. The first available BTC data may not cover all warm-up; insufficient history means neutral/no signal. Do not read, hash, or score later rows.
- Universe: every symbol returned by `SELECT DISTINCT symbol` with at least one row in the frozen window, sorted lexicographically; no volume ranking or signal-based exclusion. The database cohort is current-collection/survivor selected and is suitable only for development triage.
- Build complete UTC-aligned 5-minute and 4-hour candles from 1-minute bars. Every constituent minute must exist exactly once; never forward-fill, interpolate, or use incomplete buckets. Reset all rolling/pivot state across gaps.
- Exclusive cutoff and source DB were inspected in earlier work; no data after the cutoff is an untouched holdout. The run is development-only even if the measured statistic is high.

## Frozen causal signal

1. Macro state is derived from BTC 4-hour completed candles only. A pivot high at bar `i` is confirmed only after bars `i+1` and `i+2` close, and requires `high[i]` strictly greater than the highs of `i-2,i-1,i+1,i+2`; pivot low is the strict inverse. The five-bar neighborhood must be continuous. At any decision close, use only pivots whose two right bars are already complete. Bullish means the latest two confirmed pivot highs and latest two confirmed pivot lows are both higher; bearish means both pairs are lower; all other states are neutral.
2. On a completed 5-minute bar, a long sweep requires bullish BTC macro, low below the minimum low of the prior 12 complete 5-minute bars, and close strictly inside that prior 12-bar range. A short is symmetric: bearish macro, high above prior maximum, close strictly inside. The bar itself is excluded from the range.
3. A sweep only arms one setup for that symbol. Starting on the next completed 5-minute bar, search at most the next 12 continuous 5-minute bars for the first MSS. Long MSS is a close above the maximum high of the four preceding completed bars; short MSS is a close below their minimum low. The BTC macro must remain in the same direction on every subsequent bar through MSS confirmation. A neutral/opposite regime cancels the armed setup. No same-bar sweep/MSS is allowed. No confirmation means expiry and no trade.
4. Enter at the next 5-minute open after MSS. Stop is the sweep-bar extreme. Reject nonpositive risk or an entry already through the stop. Target is exactly 2R. Resolve the following 10 complete 5-minute bars (50 minutes) from the entry using the raw 1-minute OHLC path. Same-minute stop+target touches resolve stop-first; a stop gap fills at the adverse minute open; target fills at its level. If neither barrier is hit, exit at the close of the tenth 5-minute bar. Incomplete or discontinuous paths are unscorable and excluded from hit-rate denominator but remain reported as unscorable.
5. At most one armed setup or position per symbol; after a signal, suppress new setups through its full 10-bar outcome horizon, independent of outcome. This conservative rule makes events non-overlapping without using outcome-dependent selection.

## Comparators, costs, and metrics

- Matched baseline A: same accepted entry times, entry prices, stop distances, minute paths, and horizon, with direction equal to the traded symbol's last completed 5-minute close-to-close momentum at the MSS confirmation.
- Matched baseline B: same accepted entries and risk, deterministic SHA-256 direction keyed by fixed seed `20261115`, symbol, and entry timestamp.
- Flat/abstain baseline has zero coverage; directional precision is undefined, not zero.
- Costs: 0.10% round-trip base and 0.30% round-trip stress, retained from prior project screens as assumed scenarios. Funding, slippage, spread, depth, order-fill probability, leverage, and liquidation are unavailable in this price-only run; net R is therefore fee-only and cannot satisfy the final positive-realistic-expectancy gate.
- Report target/stop/timeout/unscorable counts; candidate target-first precision with Wilson 95% and 7-calendar-day circular block interval; baseline target-first rates and paired precision differences with block intervals; base/stress net-positive rates and mean net R point estimates; candidate mean net R and paired base-cost net-R differences with block intervals; total eligible directional-regime 5-minute decision anchors; coverage; symbol count and largest-symbol share; per-symbol rows; exact trial count (one); source-window row fingerprint; and causal checks.
- Report precision as `target / (target + stop + timeout)`. Timeout is a non-hit. Do not call this calibrated M4 confidence: this deterministic rule has no fitted probability model. M4 remains unproven until calibration is learned without opening the final future evaluation.

## Interpretation gates

- This run can only reject or retain the rule as a prospectively collectable candidate. It cannot pass validation because the data are exposed, only about 84 days long, and fees/funding/execution are incomplete.
- The user's final target remains unchanged: on a genuinely future sealed set, M4 point precision at least 80%, at least 10% coverage, at least 200 non-overlapping events across at least 20 symbols, dependence-aware lower confidence bound above registered baselines, and positive expectancy after realistic costs. No threshold is weakened by this preregistration.
- Do not run another parameter/timeframe/RR grid on this interval. Do not retune this rule after seeing the result. Any changed rule is a new trial and needs a new prospective evaluation period.

## Execution checks before any outcomes

The probe's synthetic tests must establish completed-HTF pivot confirmation, no future-dependent regime changes, no same-bar sweep/MSS, missing-bar reset, next-open entry, 1-minute stop-first tie handling, adverse stop-gap fill, timeout, and immutable pre-cutoff data selection. If any fails, do not run the price outcome probe.
