# BTC 1m three-candle streak continuation — fixed test definition

Classification: exploratory. The first agent run occurred before this contract was saved. This file records the exact reproduction contract and does not retroactively make that first run preregistered or OOS.

## Data and rule

Use BTCUSDT completed 1-minute OHLC candles from the read-only chart_predictor/data/vision_dev.sqlite database, with open_ms < 2026-10-09T00:00:00Z. The stored development cache ends on 2026-06-30 and has no internal missing minutes for BTC. Keep only exact minute-aligned rows and do not interpolate.

Signal at minute t when the last three completed candles have strictly bullish bodies (close > open) or strictly bearish bodies (close < open); direction follows that streak. Require continuous minute timestamps across the three signal bars. Enter at the next 1m open. Compute signal-time ATR14 from 1m true ranges; a missing-minute gap invalidates the ATR warmup spanning it. Stop and target are both 1×ATR14 from entry in the signal direction. Hold no longer than 15 complete 1m bars. Resolve barrier touches in timestamp order; if stop and target are both touched in one minute, stop wins. If the open gaps through the stop, fill at the adverse open. If neither barrier is hit, exit at the 15th bar close. Enforce one open trade at a time.

Deduct 0.10% round-trip cost plus 0.04% round-trip slippage from directional return. Compare with always-long on the same selected anchors and identical 1×ATR barriers. Report target-first, Wilson 95% lower bound, expiry direction accuracy, net-positive rate, mean net return, and a 7-calendar-day circular moving-block bootstrap interval. Require at least 200 events and Wilson lower bound at least 80% for the numeric precision gate.

The 80% signal goal is not the same as target-first profitability. This unfiltered rule does not implement the SPEC's M4 confidence-selection/calibration step; no calibrated probability or coverage claim is allowed.
