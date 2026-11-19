# Crypto forward 1m kline capture readiness — 2026-11-19

## Decision

The next-candle microresearch has not shown a material, robust accuracy gain from adding taker-flow aggregates to OHLCV. Reusing the already exposed historical labels for more threshold tuning would increase selection bias, not create new evidence. The next admissible step is to preserve a fresh chronological market-data panel, then preregister one candidate before inspecting its outcomes. This capture utility records data only; it does not issue predictions, alerts, or orders.

## Prior exploratory comparison

The already committed comparison in [`micro-candle-flow-incremental-results-2026-11-19.md`](micro-candle-flow-incremental-results-2026-11-19.md) evaluated one-minute next-close direction on exposed historical data:

- OHLCV accuracy: 51.3059%.
- OHLCV plus taker-buy-flow accuracy: 51.3174%.
- Paired improvement: +0.0115 percentage points; synchronized 7-day block-bootstrap 95% interval −0.0290 to +0.0458 percentage points.
- Reversal baseline: 51.3081%; 748,540 scored rows after 29,054 exact-flat labels were excluded.

This is exploratory development evidence, not sealed OOS, target-first M2, or net trading performance. The increment does not justify widening to higher timeframes or claiming an accuracy improvement.

## Collector contract and verification

[`scripts/research/crypto_kline_forward_capture.py`](../../scripts/research/crypto_kline_forward_capture.py) selects the top eligible COIN-underlying USDT perpetuals once at startup, subscribes to public USDⓈ-M 1m kline streams, and persists only closed bars. It preserves OHLC, base/quote volume, taker-buy base/quote volume, trade count, source event time, and local receive time. It records gaps, duplicates, out-of-order messages, reconnects, a SHA-256 manifest, and a capped output file. Open candles are ignored; zero-volume closed candles are retained but explicitly marked feature-ineligible. The tool emits no labels, forecasts, alerts, or orders.

The parser and append/manifest tests pass: `PYTHONPATH=. /opt/anaconda3/bin/python3 -m pytest chart_predictor/tests/test_crypto_kline_forward_capture.py -q` → **14 passed**. This verifies local validation logic only.

A prior public-stream canary ran 95.65 seconds on 20 symbols and captured 2 closed bars per symbol (40 total), with zero reconnects, duplicates, or observed minute gaps. The manifest reports 17,425 bytes and SHA-256 `ea9a88d087eafb4200eafd2225275ef27350355e14b3d1a1c0f634c28d0976cb`; the independently recalculated file digest matched. This proves only that the short sample completed and its bytes match the manifest. It does not prove strategy accuracy, continuity beyond the sample, reconnect recovery, or signal performance.

## Gates before using any captured data

1. Confirm durable storage and a verified backup destination before a longer run. Do not commit raw market data or rely on an ephemeral `/tmp` canary as research history.
2. Freeze the candidate rule, entry reference, stop, target, timeout, eligible universe, cost model, and all-issued M2 accounting before opening outcomes.
3. Preserve strict chronological separation. The already exposed development period cannot serve as confirmatory OOS. Count timeouts as target-first failures; report deadline direction separately.
4. Require the pre-agreed OOS gates: all-issued M2 target-first ≥80%, a separate outcome-blind non-overlap N≥200 across ≥20 symbols, coverage ≥10%, positive cost-adjusted expectancy, and dependence-adjusted inference against frozen baselines. A high raw hit rate alone is insufficient.
5. Any eventual multi-timeframe expansion must follow a passed, independently evaluated micro gate; do not add broader context to rescue a failed next-candle hypothesis.

## Independent review and hardening

Four read-only research roles reviewed this stage: KR equity data gate, US equity data gate, crypto candidate novelty/data gate, and crypto collector red team. The three market reviewers found no currently eligible stock/ETF backtest panel and no novel crypto candidate with executable fresh M2 labels. The red team found three collector risks: first/last-window gaps could escape gap counters; reaching the 128 MiB cap could prevent a manifest; and `complete` could be misread as proof of continuous feed data.

The collector was hardened after that review. It now counts gaps from the first successful connection to a symbol's first closed candle, records per-symbol first/last candle times and unobserved tail-minute counts at finalization, allows a 15-second delivery grace before counting the final candle as missing, keeps the partial artifact when the size cap is reached, writes a separate atomic manifest with the cap termination reason, and explicitly sets `feed_completeness_verified=false`. The legacy `complete` field is now accompanied by `capture_window_elapsed`; its meaning is that the requested duration elapsed, not that all market messages were received. These checks still cannot repair a missed candle: any observed or edge gap disqualifies the affected continuity claim unless a separately approved and verified reconciliation source is added.

The expanded focused suite passes **15 tests**, including synthetic initial-gap, tail-gap boundary/grace, and size-cap artifact/manifest cases. No live reconnect, forced disk-full, rights review, storage backup, or long-run test was performed. The Mac reports `/Volumes/HDD2TB` absent in the current environment; process listing was denied by macOS permissions. A long capture was therefore not started. Binance Vision historical terms do not themselves grant rights for a separate stream capture, retention, or dual-host copy; that rights status remains unverified.

## Current status

**Forward capture code is implemented and locally tested; continuous capture and fresh strategy validation have not been run.** The prior canary is a transport smoke test only. No validated crypto signal has reached the user's ≥80% target-first criterion. The latest market inventory also found no qualifying KR or US stock/ETF strategy; those studies remain gated by point-in-time, inactive-security, corporate-action, cost, and data-rights requirements. No Oracle deployment was performed.
