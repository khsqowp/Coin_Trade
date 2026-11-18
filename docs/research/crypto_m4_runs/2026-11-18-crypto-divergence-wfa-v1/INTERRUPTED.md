# Interrupted run — no result

This run was started with the frozen RSI/MACD divergence WFA configuration, then stopped by the user. The database SHA-256 matched the preregistered value and the archive manifest contained the expected 86 symbols.

The process handle was later re-polled and returned `Unknown process id`; the output directory contains only `manifest.json`. The process had completed the first 17 symbols of the training pass and was partway through BTCUSDT when it stopped. It had no per-symbol checkpointing, and no aggregate training, OOS, Monte Carlo, WFA, or plateau output was persisted. The partial work is not recoverable as strategy results and must not be reported as a backtest outcome.

This abandoned macro-filter-first study is superseded for current research sequencing by the micro-candle phase 0 in `docs/research/micro-candle-phase0-preregistration-2026-11-18.md`. Do not resume it under the micro-candle trial identity.
