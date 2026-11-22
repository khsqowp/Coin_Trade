# Community 2 deduplication notes

Retrieved and classified on 2026-11-20. Only `strategy_archive/community2/` was written.

## Existing community strategies excluded

The existing community archive was read before collection. No duplicate JSON files were copied into this archive. The following already-covered rules were skipped: BTC rolling N-day highs/lows (all available N variants), BTC MAX(10) overnight and NYSE-close rules, Monday effect, IBS range-break mean reversion, close-near-low next-day dip, four consecutive lower highs reversal, and SPY opening-range breakout.

## Grouping and merge decisions

- Numeric lookback/threshold choices for one underlying signal family are grouped in a single record where the source presents them as a parameter grid. Examples include the Upbit VWAP dip thresholds, BTC/QQQ breakout horizons, and the source's MACD settings.
- Turtle System 1 and System 2 remain separate because the entry channel, skip filter, and exit channel produce different trade logic.
- The BTC and ETH session strategies remain separate where the asset, UTC session boundary, or position logic differs. The 25 combinations of cash, fixed long, fixed short, lagged momentum, and lagged reversal over the BTC 08:00 UTC daytime/nighttime split are individually archived because the paper defines and evaluates these as 25 different position mappings, not merely different lookback parameters. Six mappings already captured by earlier session records were removed from the matrix to avoid duplicates; 19 additional mappings remain.
- Similar carry labels are retained separately only when the position construction differs (dated-futures basis, perp funding, cross-venue funding spread, basket hedge, synthetic-perp oracle/skew exposure, and trend-conditioned carry). Catalog entries with missing thresholds are flagged `mechanical_spec_complete: false` and are not presented as ready-to-run rules.
- The full-source data does not always expose all parameters. Missing indicators, thresholds, or exit logic are called out in each record rather than inferred.

## Count

The archive contains 81 JSON records. The existing community archive remains untouched. No parameter-only copies of existing community strategies were added.
- During final deduplication, the generic delta-neutral perpetual carry record was merged into `btc-spot-long-perp-short-carry`; the generic Hyperliquid funding harvest record was merged into the catalog's existing funding-rate harvest record. Two records were added from the opened systematic-rules page: an always-in long/short SMA cross and a fixed-horizon Wilder RSI(7) reversal. The latter is mechanically distinct from Connors RSI(2).
