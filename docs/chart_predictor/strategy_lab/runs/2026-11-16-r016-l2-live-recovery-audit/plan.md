# R016 — Controlled live L2 recovery audit

## Preregistered question

After one deliberate client-side close of the public Binance USD-M depth websocket, can the collector reconnect, obtain fresh REST depth snapshots, bridge buffered updates, and restore both BTCUSDT and ETHUSDT books within 30 seconds while retaining at least 99% book coverage during a complete 60-minute capture?

This is an operational data-integrity test, not a trading strategy, signal-accuracy study, or performance backtest. It does not test router/ISP/server failures, exchange-side completeness, or order execution.

## Why this differs from previous work

Two preserved 60-minute captures completed without any reconnect. Their stream integrity and coverage do not demonstrate recovery. Existing mock tests exercised recovery logic, but no live recovery event had been observed. R016 adds an explicit, once-only client close at a fixed elapsed time and records whether the injection actually occurred.

## Frozen configuration

- Public-only streams: BTCUSDT and ETHUSDT `depth@500ms` plus `aggTrade`; REST depth snapshots are unauthenticated.
- Capture window: 3,600 synchronized seconds; maximum wall time 4,500 seconds.
- Hard total output cap: 536,870,912 bytes, including manifest.
- Fault: close the currently connected depth websocket once, 300 seconds after synchronized capture begins, with websocket close code 1012. Do not inject if the socket is not online; record `not_triggered` rather than silently passing.
- No credentials, account endpoints, order endpoints, orders, strategy signals, or trading.
- Input data: live public stream only. No historical performance database is read by the pilot.

## Pass/fail criteria

Pass this operational gate only if all conditions hold:

1. The 60-minute capture completes under the 512 MiB total output cap and its manifest hash/count verification succeeds.
2. The preregistered close is recorded as triggered exactly once.
3. Both books recover after the injected disconnect, each within 30 seconds from its own invalidation to snapshot bridge.
4. Each symbol's book coverage over the synchronized capture is at least 99%.
5. No buffer-cap failure, sequence-integrity failure, or missing final manifest occurs.

Any unmet condition is `HOLD`/failure for this gate. A pass would only authorize considering a longer prospective development-data capture; it would not validate a strategy or the 80% directional-accuracy goal.

## Resource and preservation rules

- Use the existing ignored pilot root `chart_predictor/data/crypto_l2_pilots/`; never overwrite, repair, or delete previous captures or partials.
- New output is bounded to 512 MiB. Stop and retain an explicitly incomplete artifact if the cap or wall deadline is reached.
- Do not inspect raw event payloads for market forecasts. Review only manifest metadata, hash/count verification, and required connection/book-state records.
- Record the source script hash, test command/results, run ID, output size, and result decision.
