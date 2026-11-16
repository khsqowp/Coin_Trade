# R010 plan — Fresh L2 pilot after finalization diagnostics

Status: `integrity_pilot_completed`; no predictive performance evaluation.

## Objective

After R009's one-hour capture body was complete but its process emitted only `RuntimeError` and no manifest, preserve that raw file and add a bounded finalization-failure diagnostic. Run a fresh one-hour public BTCUSDT/ETHUSDT depth@500ms + aggTrade capture under a new run ID. Validate the run manifest against the segment, then replay raw→compact→10-second windows twice and compare deterministic output hashes.

## Frozen scope and boundary

- Public data only; no credentials, account calls, signals, trades, labels, or strategy metrics.
- No strategy parameters, candidate rules, or performance outcomes inspected.
- The previous failed run remains preserved and is not relabeled.
- A one-hour, two-symbol capture does not establish multi-day recovery or 20-symbol production capacity.
