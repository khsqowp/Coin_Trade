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

An offline deterministic reducer now replays the raw segment using the existing sequence-checked `LocalBook`, waits for snapshots to bridge buffered updates, preserves feed events and possible aggregate-trade ID gaps, and joins each eligible trade to the latest book state received before it. Two replays of the same one-hour source produced the same 208,165-row output hash, synchronized both books, preserved two connection events, and recorded zero invalidations or possible trade-ID gaps.

An event-time aggregator then produced 718 UTC-aligned 10-second windows (359 each for BTCUSDT and ETHUSDT). It withheld four incomplete tail windows, counted zero late input rows and zero disconnects, and marked 716 windows data-quality-ready; the two remaining windows lacked pre-window depth. The feature rows preserve each depth update's top-five executable quote path (up to 20 samples in a window), one-second trade/quote sub-paths, high/low event timestamps, and the monotonic receive time when all included features became available. A strict decision-anchor comparator rejects same-time and later-arriving features. A second replay produced the same output hash.

The new 10-second aggregate is 13,745,958 bytes uncompressed and 2,091,272 bytes with Zstandard. Linear scaling projects to about 183.20 decimal GB/year for 20 symbols. This estimate is from a single two-symbol hour and does not prove sustained collection capacity. It is higher than the earlier feature-only projection because executable quote paths are retained.

The new full test run passed 231 tests with one environment warning. A pre-existing pilot manifest-size fixed-point calculation flaked during two full-suite runs; it was repaired by reserving bounded JSON whitespace and then passed the full suite. No strategy-performance cells were run. This remains infrastructure validation only, not signal evidence.

The required bounded feature/path recorder is still incomplete: the comparator is unit-tested but not yet applied to every T/H decision anchor, and the retained top-five depth may be insufficient for the fixed 1,000 USDT notional under all spread/depth conditions. Funding/cost snapshots, multi-day reconnect capture, and 20-symbol capacity testing remain open. Do not begin live continuous collection or signal scoring on this result.

## Required before performance testing

Implement a compact recorder that preserves exchange event/receive times, depth update sequence validity, aggTrade IDs, gap/reconnect intervals, per-window feature data, execution quotes, funding events, and content hashes. Demonstrate bounded disk use and deterministic replay on synthetic data and the existing one-hour pilot. Then finalize exact data rights, frozen universe snapshot, model/calibration rules and sample counts, chronological partitions, fee/slippage assumptions, final-access controls, and hashes. Do not use R004's unopened final period or exposed OHLCV history as an independent L2 result.

The wider goal remains active: zero M4-validated crypto signals and zero qualifying KR/US strategies are established by this run.
