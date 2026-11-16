# R021 — Funding crowding + BTC macro + pullback/re-entry

Status: preregistered exploratory development trial. No performance results were inspected when this plan was written.

## Question and distinct hypothesis

Does a funding-crowding contrarian side, allowed only in the matching completed-BTC-4h EMA50 regime and entered after a separate ATR-sized pullback followed by a 3-bar close breakout, improve target-first accuracy and net expectancy over the same mechanical re-entry trigger without the funding and/or macro filters?

This differs from R004 (MACD zero cross/RSI long entries), prior P5-P9 chart-pattern/volume/VWAP/BB families, the 4-setup consensus trial, and the H3 order-book pilot. The mechanism is positioning-extreme exhaustion followed by price-confirmed re-entry, not an indicator cross or static setup label. It is a hypothesis, not a live signal specification.

## Inputs and eligibility

- Price source: read-only `/Users/user/CODE/Coin_Trade/chart_predictor/data/vision_dev_repaired.sqlite`, `candles` table; six fixed current survivors: BNBUSDT, BTCUSDT, DOGEUSDT, ETHUSDT, SOLUSDT, XRPUSDT.
- Funding source: already captured public USDⓈ-M `/fapi/v1/fundingRate` pages in the R004 `screen-through-2025-01-01` snapshot in this worktree. They are REST history, not Binance Vision archive files. No new download, account access, API key, or order endpoint.
- Source scope: the user authorized historical backtests only. No live or manual-trading signal will be generated from these files.
- Evaluation: 2020-10-01T00:00:00Z through 2024-01-01T00:00:00Z, end exclusive. This interval is development data and already exposed by R004; it is not validation or holdout. Do not open 2025+ data.
- Universe limitation: six current contracts; no point-in-time active/delisted universe. Any outcome is survivor-biased exploratory evidence. This input cannot satisfy the M4 project gate requiring ≥20 symbols.

## Frozen candidate rule (one configuration; no parameter search)

1. Process each settlement separately and each of 1m, 3m, 5m, 10m, 15m, 30m and 60m bars. All bars are UTC epoch-aligned, complete bars only.
2. At settlement `t`, compare the just-settled funding rate with the 10th/90th percentile of that contract's previous 180 calendar days of settlements only; require at least 60 prior observations. At or below q10 means crowded shorts and a long setup; at or above q90 means crowded longs and a short setup. Current event is excluded from its own threshold history.
3. Require the latest BTC 4h bar whose close timestamp is ≤ `t` to agree with direction: close > EMA50 for long; close < EMA50 for short. EMA is computed causally from completed 4h closes. Neutral or unavailable regime rejects the event.
4. Starting after `t`, use the event-time last fully completed close as reference and Wilder ATR20 (repository indicator implementation) of the target timeframe as frozen pullback scale. Require a distinct later, fully post-event bar to retrace at least 0.5×ATR20 against the proposed side. Within the following 20 completed target-timeframe bars, trigger on the first close above the preceding 3 highs (long) or below the preceding 3 lows (short). Trigger is known only at bar close; enter at the next 1m open. No same-bar pullback-and-break entry. Skip any timeframe candle that began before the funding timestamp, even if it closes after it.
5. Stop is 1.0×signal ATR adverse to entry; target is 1.5×signal ATR favorable to entry. Evaluate first touch at 10 and 20 target-timeframe bars using 1m OHLC after entry. If stop and target touch in the same 1m candle, stop wins. A stop gap fills at the worse open; a target gap receives no better than the limit. If no barrier hits, exit at the last available close in the horizon.
6. At most one trade per symbol/timeframe per funding event; no overlapping position in the same symbol/timeframe. Signals without a complete forward horizon are censored, not counted as wins or losses.
7. Base costs: 5 bp taker fee and 2 bp adverse slippage per side (14 bp round trip). Stress: double both (28 bp round trip). These are assumptions, not measured fills. Apply settlements crossed during each open position using the recorded funding rate and the latest prior 1m close as a mark proxy where exact mark is absent; disclose proxy and missing-mark fraction.

## Comparators and outputs

- Candidate: funding extreme + BTC macro + micro re-entry.
- Matched ablation A: same re-entry after every funding settlement, no funding-tail filter, still BTC macro.
- Matched ablation B: funding-tail + same re-entry, no BTC macro filter.
- Matched ablation C: same re-entry after every funding event, without funding-tail or BTC macro filters; funding sign supplies direction only so the event-time denominator stays comparable.
- For each timeframe and 10/20-bar horizon: trigger count, matured count, target-first/stop-first/timeout/censored, win rate, Wilson 95% interval, gross/net mean R, median R, costs, funding, and symbol/side/year stratification. Report candidate versus each ablation on event-conditioned and all-trigger denominators separately.
- No portfolio CAGR claim: this event study is not a funded portfolio simulator and has only six survivors. Do not label an M4 candidate or tune the rule after viewing outcomes.

## Decision rules

- Reject if no incremental benefit versus matched ablations, negative mean net R under base costs, or result is concentrated in one symbol/year/direction.
- Even if descriptive accuracy is ≥80%, this trial cannot qualify the project target: universe <20, no point-in-time membership, development interval already exposed, and no independent sealed evaluation.
- If missing funding timestamps, candle gaps, or timestamp ambiguity prevent causal matching, stop before performance calculation and record the data gate failure.

## Reproducibility and safety

- Write only new R021 source/tests/docs and ignored run outputs. Price DB and R004 raw funding pages remain unchanged; do not alter `trials.sqlite` or prior run directories.
- No internet, `.env`, secret, account, order, server, deploy, or live/manual signal access.
- Validate timestamp joins, prefix invariance, future-mutation invariance, same-minute stop-first ordering, gap fills, and censored horizons with synthetic tests before evaluating outcomes.
- Record code SHA-256, price DB SHA-256 (reuse R004 fingerprint only if independently confirmed), all source page hashes, command, environment and output hashes in the run manifest.

## Execution amendment log

- The first full execution (`data/strategy_lab/2026-11-16-r021-funding-macro-reentry/`) was audited after completion. Four trade rows had an exit after the exclusive development cutoff; the input query also read two minutes beyond that cutoff. The whole first run is retained as **INVALID / DO NOT USE**.
- Root cause: the runner screened settlement timestamps against the horizon but did not require the *triggered entry's full maximum outcome horizon* to finish before the split boundary. A trade can trigger up to 20 bars after settlement, so the settlement-only guard was insufficient.
- Corrective change: read the price DB with `open_ms < END_MS` and reject an entry unless `entry_time + maximum_horizon <= END_MS`. Added a synthetic boundary regression test. No strategy threshold, outcome definition, or cost assumption changed.
- Corrected one-time replay ID: `2026-11-16-r021b-funding-macro-reentry-boundary-corrected/`. Its full trade log has zero entries at/after the cutoff and zero exits after it. The original output remains preserved separately; only the corrected replay is used in the decision report.
