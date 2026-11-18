# Binance USD-M aggTrades ↔ 1m kline pilot

Date checked: 2026-11-19 (local read-only analysis)

## Scope

- 20 USD-M perpetual symbols, UTC day 2025-01-01.
- Compared official Vision `aggTrades` archives with same-symbol 1-minute kline archives.
- All 40 ZIP archives and their official SHA-256 sidecars had already passed checksum verification before this analysis.
- This is a one-day data-reconciliation pilot, not a strategy test or a claim about 80% signal accuracy.

## Results

- 6,635,887 parsed aggregate-trade rows and 28,800 parsed one-minute candles; one header row per file was excluded from the parsed counts.
- Every symbol had 1,440 minutes in each source; there were no missing or extra minute buckets.
- Aggregate-trade IDs were monotonic and contiguous within each daily file: zero observed reversals and zero ID gaps.
- Minute-level OHLC disagreed in 311 of 28,800 candles (1.08%); volume disagreed in 988 (3.43%), taker-buy volume in 501 (1.74%), quote volume in 990 (3.44%), and underlying trade-count reconstruction in 1,236 (4.29%).
- Daily aggregate quantity and quote volume reconciled to floating-point tolerance for 19/20 symbols. SOLUSDT did not: aggTrades was 18 base units and 3,442.31994 quote units below the 1m-kline totals. This discrepancy is unresolved and must not be normalized away.
- BTCUSDT examples showed minute volume shifted between adjacent candles while OHLC matched; SOLUSDT showed additional opening-price and volume discrepancies in high-activity minute boundaries. The data does not prove the exact cause, so boundary aggregation is a plausible explanation, not a confirmed one.

## Decision

Do not treat minute-bucketed `aggTrades` as an exact reconstruction of Binance 1m klines or as a validated basis for minute-level aggressor-flow labels. Use native klines for candle-derived labels. Keep aggTrades as a separate event dataset; before using it for predictive features, investigate timestamp/group boundary semantics and the SOLUSDT daily discrepancy, then repeat reconciliation across multiple days and symbols. No target labels, returns, win rates, or strategy rankings were calculated in this pilot.

## Reproduction notes

Input archives were staged outside the repository at `/private/tmp/binance-aggtrades-pilot-20250101/`. The analysis streamed each ZIP CSV in memory and wrote no extracted CSVs or result artifacts into the input directory. The staging files remain available for follow-up inspection.
