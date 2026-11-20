# Preregistration: 1h taker-volume CVD divergence with confirmed price turn

> Superseded before outcome scoring by `PREREG_CVD_TAKER_DIVERGENCE_1H_20261120_v2.md` after Blue/Red/Methods/Judge review. No candidate performance outcomes were accessed under this version.

- Frozen: 2026-11-20, before this candidate's outcome calculation.
- Status: proposed for independent methods/red-team review; do not run the outcome scorer until that review accepts the rule and input data.
- Source idea: public TradingView CVD-divergence indicator family; this is an independent Python hypothesis, not a reproduction of or endorsement by the script authors.
- Hypothesis: at confirmed same-day price swing points, aggressor-side cumulative volume delta may diverge from price; a subsequent price-turn confirmation may improve target-first outcomes over the exact same price-only divergence setup.
- Trial count: one CVD rule, one matched price-only ablation, two fixed time barriers (10 and 20 hourly bars), long and short reported separately. No parameter search or post-result adjustment.

## Universe and data boundary

- Instruments: the exact frozen 36-symbol USD-M cohort in `docs/research/inventory/usdm_archive_coverage_20261120.json`, not a newly selected top-volume list.
- Data: checksum-manifested hourly USD-M contract klines, hourly mark-price klines, and funding-rate archives under `/private/tmp/cointrade-50_50-data`.
- Development-only interval: UTC `[2023-03-23 00:00, 2025-03-01 00:00)`. Later rows are not read by the candidate scorer. The interval is historical and has been exposed to other strategy research; it is exploratory only, not OOS, sealed, or forward evidence.
- No raw archives or database are committed. Missing symbol-months, gaps, and incomplete bars are retained in an input-coverage report and not interpolated.
- This is personal historical backtesting only. Binance Vision data must not be used to send live/manual trading signals, execute orders, or support production.

## Fixed feature and signal definition

1. Read complete hourly candles. Require valid OHLC invariants, a unique strictly increasing UTC open-time grid, valid taker-buy base volume, and `0 <= taker_buy_base <= volume`. Missing/nonconsecutive bars break pivot sequences; do not fill them.
2. Per-hour signed taker delta is `delta[t] = 2 * taker_buy_base[t] - volume[t]`. It estimates buyer-initiated minus seller-initiated base volume using the publisher's taker-buy candle field; do not call it full order-book CVD.
3. Reset cumulative delta at each UTC midnight: `CVD[t] = sum(delta[u])` from 00:00 UTC through the close of hour `t`. A pivot pair must be on the same UTC date.
4. A strict price swing low at bar `i` is valid only when its low is strictly below each of the three immediately preceding and three immediately following hourly lows. A strict swing high is the mirrored strict-greater rule. The pivot becomes available only at the close of bar `i+3`; never time-stamp it at bar `i` as a usable signal.
5. Compare consecutive confirmed same-day pivots. Bullish divergence requires `low[i2] < low[i1]` and `CVD[i2] > CVD[i1]`; bearish divergence requires `high[i2] > high[i1]` and `CVD[i2] < CVD[i1]`. Equality is not divergence. The CVD condition is the only difference between treatment and price-only ablation.
6. Starting with the first fully completed bar after the second pivot's confirmation, allow at most three completed bars for confirmation. Long confirmation: `close[t] > high[t-1]` and `delta[t] > 0`. Short confirmation: `close[t] < low[t-1]` and `delta[t] < 0`. Use the first qualifying bar only. If none qualifies, expire the setup. If long and short confirmations coincide, discard the setup.
7. Enter at the next hourly contract-kline open after confirmation. Signals are unavailable while the symbol has an open trade; no pyramiding. A new signal cannot reuse the same pivot pair.

## Exits and scoring

- ATR: Wilder ATR(14), computed only from completed contract candles through the confirmation bar.
- Long stop: second-pivot low minus `0.25 * ATR14` at confirmation. Short stop: second-pivot high plus `0.25 * ATR14` at confirmation. If the stop is on the wrong side of the next-open entry or ATR is unavailable, discard the signal before scoring.
- Target: exactly 1.0 initial-risk unit from entry in the trade direction. Do not optimize target/stop multiples.
- Time barriers: test both 10 and 20 complete hourly bars after entry, independently, as the required 10x/20x timeframe horizons. At expiry, M2 is failure; report M1 as direction-correct only when expiry close is strictly favorable to entry.
- Path replay uses chronological contract OHLC. If stop and target are both touched in the same candle, stop wins. If a candle opens through the stop, fill at the adverse open; if it opens through the target, fill conservatively at the target. If neither level is touched, exit at the close of the final allowed bar.
- Funding is summed only for actual funding timestamps in `(entry_time, exit_time]`; payment sign is long `+1`, short `-1`, so positive rates cost longs and credit shorts. Missing required funding coverage makes the trade unevaluable; it is not assigned zero.
- Fee scenarios: fixed legacy round-trip 10 bp base and 30 bp stress from `comparable_evaluation_protocol_v1.md`. Spread/market impact remain unmodeled and must be named as limitations.
- M2 is target before stop; timeout and same-bar ambiguity count as failures. Report total issued events and a separate market-wide non-overlap event sample; never call repeated or correlated symbol events independent.
- Report M1 expiry direction separately, per-symbol counts/rates, target/stop/timeout counts, coverage over every complete eligible symbol-hour, fee/funding-adjusted mean return and R, Wilson intervals, strongest valid frozen baseline, and missing-data coverage.

## Decision gates and restrictions

- The strategy's final core gate remains frozen in `docs/chart_predictor/SPEC.md`: M2 point estimate at least 80%; total issued signal outcomes plus separate non-overlap N at least 200; at least 20 symbols; at least 10% coverage; positive net expectancy in both cost scenarios after timestamp-aligned funding; Wilson lower bound above the preregistered baseline; and final evaluation on genuinely untouched forward data.
- The proposed run is development-only and cannot pass the core gate regardless of its historical score. Do not tune after reading it. A promising result may justify only an append-only, future-only paper evaluation using a separately authorized live-data source, not Binance Vision signals.
- If existing archive validation finds missing taker fields, invalid row timing, or unresolved funding coverage, stop the affected scoring before reading outcomes and mark the result `NOT EVALUABLE`.
- Prefix-invariance and deliberate future-mutation tests are mandatory for any scorer implementation. Never use pivot anchors before right-side confirmation or same-close fills.
- No Phase 9 mixing, live signals, Telegram publication, Oracle deployment, service restart, account credentials, API keys, or real orders.
