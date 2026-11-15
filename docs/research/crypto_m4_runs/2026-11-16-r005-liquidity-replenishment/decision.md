# R005 decision — candidate retained, performance test blocked

Decision: `candidate_spec_pending_data_pipeline`. No strategy-performance cells were run and no accuracy or profitability claim is supported.

## Why this candidate remains worth preparing

The proposed mechanism is distinguishable from the rejected taker-imbalance breakout: it requires displayed liquidity on the consumed side to recover after an opposite-side aggressive burst, and only takes the signal in the latest completed higher-timeframe BTC regime. One independent researcher proposed this as a falsifiable mechanism; an independent adversarial reviewer did not endorse its performance, but agreed that a fixed evaluation protocol is the next valid action. The candidate must still be treated as unproven.

## Current data evidence

The existing BTCUSDT/ETHUSDT capture covers about one hour and passed its file-integrity recheck: SHA-256 `ee337e99a4f3060ec7f56889f35eb4ed213839356a7efc1533ff7a97904d057e`, 208,224 parseable newline-terminated records, 230,845,049 bytes. Its original manifest reports no natural reconnect during capture; the mocked recovery path is a separate test. This is data-integrity evidence only, not M4 evidence.

The raw uncompressed capture rate extrapolates to about 2.3 GB/hour, or 20.2 TB/year, for 20 symbols. The extrapolation is linear from two symbols and one hour, not a measured production rate. Starting a year-long raw capture with the existing implementation is therefore rejected. A compact event/feature recorder with replayable sequence and hash evidence is required first.

Streaming the same JSONL through Zstandard 1.5.7 produced 44,188,758 bytes from 230,845,049 bytes (19.14% of original; 80.86% reduction). No archive file was created. Applying that single-run ratio to the 20-symbol yearly projection still yields about 3.87 decimal TB/year. This is a measured compression result for one sample, not a guaranteed long-run ratio, and it does not make raw retention viable on its own.

## Work completed and limits

- Four parallel agents reviewed the KR/US data gates, a crypto candidate, and a crypto adversarial protocol. KR/US reviews found no eligible current price panel for a new performance test without user-controlled data/rights steps. The crypto designer proposed the replenishment mechanism; the adversarial reviewer highlighted threshold-selection, event dependence, sample size, and cost hazards.
- The full `chart_predictor/tests` suite passed: 225 passed, one environment warning. These are software tests, not signal trials.
- The raw one-hour capture's hash, size, line count, JSON parseability, and newline termination were independently recomputed and matched its manifest.
- No backtest, outcome scoring, market order, credential access, or data download was performed for this candidate. A later offline-only reducer prototype was implemented and replayed against the existing file; it generated no signal or strategy metric.

## Follow-on replay prototype (engineering only)

An offline deterministic reducer now replays the raw segment using the existing sequence-checked `LocalBook`, waits for snapshots to bridge buffered updates, and joins each eligible aggregate trade to the latest book state received before it. The one-hour source replay produced 208,163 compact rows from 208,224 raw records, synchronized both books, recorded zero invalidations, and reproduced the same output hash on a second run. Focused reducer/book tests passed; the full chart-predictor suite passed 228 tests with one environment warning.

This is not yet the required bounded feature/path recorder. The compact JSONL is still 104.5 MB/hour for the two-symbol sample; Zstandard produced 9.94 MB/hour, linearly projecting to about 0.87 decimal TB/year for 20 symbols. That projection is not a measured sustained rate. The aggregation design, delayed-event policy, production hard-cap tests, reconnect capture, and multi-day capacity test remain open. Do not begin continuous multi-symbol recording or signal scoring on this result.

## Required before performance testing

Implement a compact recorder that preserves exchange event/receive times, depth update sequence validity, aggTrade IDs, gap/reconnect intervals, per-window feature data, execution quotes, funding events, and content hashes. Demonstrate bounded disk use and deterministic replay on synthetic data and the existing one-hour pilot. Then finalize exact data rights, frozen universe snapshot, model/calibration rules and sample counts, chronological partitions, fee/slippage assumptions, final-access controls, and hashes. Do not use R004's unopened final period or exposed OHLCV history as an independent L2 result.

The wider goal remains active: zero M4-validated crypto signals and zero qualifying KR/US strategies are established by this run.
