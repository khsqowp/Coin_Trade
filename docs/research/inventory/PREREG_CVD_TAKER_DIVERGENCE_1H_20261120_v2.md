# Preregistration v2: 1h taker-volume CVD divergence

> Superseded before outcome scoring by `PREREG_CVD_TAKER_DIVERGENCE_1H_20261120_v3.md` after the second independent review. No strategy outcome was opened or calculated under v2.

- Frozen: 2026-11-20, before any outcome scoring for this candidate.
- Supersedes v1 only for future execution; v1 is retained as the reviewed initial draft. No CVD candidate outcomes have been calculated.
- Gate before scoring: independent reviewers must accept the rules, and a pre-outcome archive/feature QA must pass.
- Source idea: public TradingView CVD-divergence indicator family. This is an independent Python hypothesis, not a reproduction of or endorsement by the script authors.
- Hypothesis: on a fixed price-divergence event stream, a same-day aggressor-side CVD divergence filter improves target-first outcomes over the matched price-only stream.
- Trial family is frozen: CVD treatment, price-only ablation, four direction baselines on treatment anchors, horizons 10h and 20h, long/short strata. No parameter grid, post-result changes, or winner selection across horizons/directions.

## Universe, period, data and prior exposure

- Universe: exact 36-symbol USD-M cohort in `usdm_archive_coverage_20261120.json`.
- Development interval: UTC `[2023-03-23T00:00:00Z, 2025-03-01T00:00:00Z)`. This is historical and previously exposed to other research; exploratory reject/debug only. It is not validation, sealed OOS, or forward evidence.
- Inputs: hourly contract klines and funding-rate archives in `/private/tmp/cointrade-50_50-data`. Mark-price archives are excluded from this experiment; barriers use contract OHLC only. The run is not a liquidation/mark-trigger simulation.
- Binance Vision data are for permitted personal, non-commercial, non-production historical backtesting only. Do not derive, publish, or send live/manual signals from these archives; no orders, API keys, or production use.
- Pre-score data QA must verify all required file hashes against the preserved manifest, ZIP/CSV integrity, required kline fields, unique sorted UTC opens, `close_time=open_time+3,599,999`, finite OHLC/volume/taker fields, `0 <= taker_buy_base <= volume`, and complete funding rows/timestamps/intervals for the frozen interval. No outcome statistics may be inspected during this gate. Missing rows are not filled.
- Per-symbol eligibility and missing months are frozen from the manifest before outcomes. Historical symbol survivorship and selection of a currently defined 36-symbol cohort remain unresolved; result cannot establish universe robustness.

## Causal feature and event rules

1. Signed hourly base-volume delta is `delta[t] = 2*taker_buy_base[t] - volume[t]`. This is aggressor-side volume from the completed candle, not full order-book CVD.
2. Reset CVD at each UTC midnight. `CVD[t]` is the running sum of `delta` through the close of hour `t`. A pair must be on the same UTC date.
3. A strict swing low at index `i` requires `low[i]` strictly below all lows at `i-3:i` and `i+1:i+4`; swing high is the mirrored strict-greater condition. It is known only at the close of `i+3`. Compute `CVD[i]` from deltas through the pivot candle close, but do not expose or timestamp it as a signal until `i+3` closes.
4. Use consecutive same-type price pivots on the same UTC date. Bullish price setup: `low[i2] < low[i1]`; bearish: `high[i2] > high[i1]`. Equality is not divergence. Bullish CVD filter additionally requires `CVD[i2] > CVD[i1]`; bearish filter additionally requires `CVD[i2] < CVD[i1]`.
5. At the close of the second pivot's confirmation bar `i2+3`, create the price-only setup; create the CVD-treatment setup only when the CVD condition also passes. The CVD filter is the only treatment/control difference. Confirmation is price-only for both arms: on one of the next three fully completed, consecutive hourly bars, long requires `close[t] > high[t-1]`, short requires `close[t] < low[t-1]`. First qualifying bar wins; entry is next hourly open. Do not require a same-bar delta sign in either arm.
6. Confirmation bars must remain on the pivot pair's UTC date and be exactly consecutive hourly observations. A gap or date change expires the pending setup. Each newly confirmed same-side price-pivot pair supersedes every older pending pair for that symbol and direction in both arms; create a CVD-treatment setup for the new pair only if its CVD condition passes. If both long and short confirmation occurs for one symbol at the same hour, discard both. If multiple same-direction events resolve on one hour, keep the event with the most recent second pivot. Never reuse a pivot pair.
7. Event generation is independent of outcome horizon; do not lock out later forecasts because a previous forecast is still being labeled. Overlapping outcomes remain in total issued-signal results and are separately de-overlapped as specified below. Signals are generated separately for price-only and CVD arms; do not merge their counts.

## Barrier construction, execution and scoring

- ATR is Wilder ATR(14) on contract OHLC and uses only complete bars through the confirmation close. At any missing/nonconsecutive hourly bar, clear ATR state and require 14 consecutive valid bars before re-enabling eligibility.
- Long stop is `low[i2] - 0.25 * ATR14[confirmation]`; short stop is `high[i2] + 0.25 * ATR14[confirmation]`. Entry is next contract-kline open. Initial risk distance is absolute entry-to-stop distance; target is exactly 1.0 risk unit from entry in the signal direction.
- If stop is not on the adverse side of next-open entry, retain it as an issued signal, label outcome `INVALID_ENTRY` and count it as M2 failure and in coverage; net realized return is zero because no position is opened. Do not silently drop it.
- Evaluate two separate fixed horizons, 10 and 20 bars. The entry candle is bar 1; the expiry close is the close of bar 10 or 20. No exit at a same-close entry price.
- Walk contract OHLC in time order. If stop and target are both touched in a bar, stop is first. If open gaps through stop, fill at the adverse open. If open gaps through target, fill conservatively at target. At timeout, exit at the final allowed bar close and M2 is failure. M1 is favorable only if expiry close is strictly in the predicted direction from entry; ties are misses.
- Any missing bar in a signal's path is `DATA_GAP`: M2 failure, no imputed fill, net expectancy unavailable for the affected cell; such a cell cannot pass. Keep the record in denominators and coverage.
- Funding events use their `calc_time` and actual signed rate. Include settlements with timestamp strictly after entry and no later than the exit bar close. Let `side_sign=+1` for long and `-1` for short. For settlements before the exit candle, directional funding cost is `side_sign * rate`; for settlements inside the exit candle, primary net cost is `max(side_sign * rate, 0)` because the intrabar exit ordering is unknown and ambiguous credits are not counted. Report actual signed funding and a sensitivity excluding settlements in the exit candle. A missing funding event/interval in an otherwise eligible trade is a data-gate failure, not zero funding.
- Fee proxies are fixed legacy round-trip 10 bp base and 30 bp stress. Net return is directional contract price return minus the fee proxy and conservative funding payment; net R is net return divided by initial risk fraction. Spread and market impact are unknown and remain limitations.
- M2 success means target before stop. Timeouts, same-bar ambiguity, invalid entries, and data gaps count as failure. Report counts by target/stop/timeout/invalid-entry/gap and raw issued versus data-evaluable outcomes.

## Controls, baselines and denominators

- **Price-only ablation:** same price-pivot pairs, price-only confirmation and exit rules, without any CVD divergence filter. It has its own complete signal stream and coverage. This is the primary incremental-value comparison.
- **Direction baselines on every CVD-treatment entry anchor:** (a) always long, (b) always short, (c) previous one-hour close-to-close direction ending at the second pivot's availability bar `i2+3` (zero return abstains; this predates the later price-turn confirmation), and (d) deterministic 50/50 direction from SHA-256 of frozen seed `20261120|symbol|entry_open_ms`. All use the same entry time, absolute initial-risk distance, 1R target, horizon, funding and costs as that treatment event. `Always flat` is reported as zero coverage with M2 not applicable.
- The strongest valid direction baseline for each horizon is the highest M2 point estimate among (a)-(d), selected by this fixed rule; ties use the order listed above. Report all baselines and do not select a favorable one after seeing results. Treat this maximum selection as part of the preregistered multiple-comparison family.
- Eligible-bar coverage denominator is the count of all complete hourly rows for the fixed 36-symbol cohort in the development interval after 14-bar ATR warmup and required-field validation. It is identical across arms; no-signal, superseded, and overlapping bars remain in the denominator. Coverage numerator is issued directional events. Report abstentions, superseded setup counts, and duplicate-signal suppressions separately.
- **Market-wide non-overlap sample:** for each arm, horizon and baseline separately, sort by `(entry_open_ms, symbol, side)`; greedily retain an event only when its entry time is strictly later than the previous retained event's exit-bar close time. This deterministic de-overlap does not imply statistical independence; also report symbol/day-cluster uncertainty. Requirements of N>=200 and >=20 symbols apply to both total issued outcomes and this non-overlap subset for any future core evaluation.
- Report long and short separately and the combined directional stream. No horizon or side can be selected post hoc as the winner. Both horizons must meet the frozen M2/coverage/sample/cost gates for a future core claim.

## Fixed gates and consequence

- The frozen core gate from `docs/chart_predictor/SPEC.md` and `comparable_evaluation_protocol_v1.md` remains: M2 point estimate >=80%; Wilson 95% lower bound above the strongest preregistered baseline; total and market-wide non-overlap N>=200; at least 20 symbols in each; coverage >=10%; positive net expectancy in base and stress after aligned funding. M1 is separate. The gate is required independently at both 10h and 20h horizons.
- This historical development interval cannot satisfy final OOS/forward requirements irrespective of its score. A favorable historical result only allows a separate, future-only paper evaluation using an explicitly permitted live-data source; it is not a core, deploy, or live-signal approval.
- Do not proceed to Phase 9 portfolio mixing unless a candidate later passes the immutable core gate on genuinely untouched forward data and Phase 7 robustness.
