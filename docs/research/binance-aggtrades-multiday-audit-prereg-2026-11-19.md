# Binance USD-M aggTrades ↔ 1m kline multiday integrity audit preregistration

Registered: 2026-11-19, before downloading the additional dates or calculating their reconciliation results.

## Question and scope

Determine whether the minute-bucket discrepancies observed in the 2025-01-01 pilot persist across a fixed, time-stratified sample of Binance USD-M perpetual contracts and dates. This is a source-integrity audit only: no forecasts, target labels, returns, M2, or strategy outcomes will be calculated.

The official Binance Public Data README identifies USD-M `aggTrades` as data from `/fapi/v1/aggTrades`, USD-M klines as data from `/fapi/v1/klines`, and provides `.CHECKSUM` sidecars for archives. Its current Vision Dataset Terms permit personal, non-production historical backtesting, exclude live execution/commercial signal use, and require attribution and CC BY-NC-SA 4.0 for redistributed derivatives. This audit stays historical and non-production. Sources: [Binance Public Data README](https://github.com/binance/binance-public-data/blob/master/README.md), [Binance Vision Dataset Terms](https://github.com/binance/binance-public-data/blob/master/TERMS_AND_CONDITIONS.md).

## Frozen sample

- Market: Binance USD-M perpetuals only.
- Symbols, unchanged from the 2025-01-01 pilot: `BTCUSDT`, `ETHUSDT`, `BNBUSDT`, `SOLUSDT`, `XRPUSDT`, `ADAUSDT`, `DOGEUSDT`, `TRXUSDT`, `LTCUSDT`, `BCHUSDT`, `LINKUSDT`, `DOTUSDT`, `AVAXUSDT`, `XLMUSDT`, `ETCUSDT`, `FILUSDT`, `UNIUSDT`, `AAVEUSDT`, `NEARUSDT`, `APTUSDT`.
- UTC dates: `2025-01-01`, `2025-04-01`, `2025-07-01`, `2025-10-01`. These are fixed quarterly calendar anchors, not dates selected from observed performance. January 1 is the existing pilot and will be revalidated against current official sidecars; three additional dates will be acquired.
- Files per symbol/date: daily `aggTrades` archive and daily `1m` kline archive, plus each archive's `.CHECKSUM` sidecar. Expected sample: 160 ZIPs and 160 sidecars across the four dates.
- Raw archives stay outside Git at `/private/tmp/binance-aggtrades-multiday-2025/`. Do not commit raw Binance data.

## Frozen parsing and comparisons

Parse the official CSV schemas by named header, skip the header row, and reject malformed/non-finite/non-positive price or quantity rows. Assign each aggregate trade to `floor(transact_time_ms / 60,000)` in UTC. For each minute calculate, in timestamp order, open/high/low/close; total base quantity; quote quantity as `price × quantity`; taker-buy base/quote quantity where `is_buyer_maker` is false; and an underlying-trade-count estimate as `last_trade_id − first_trade_id + 1`. Compare these values with the corresponding native kline fields.

For every archive record SHA-256 verification, CSV header, parsed row count, minute coverage, timestamps outside the UTC day, aggregate-ID non-monotonicity and gaps within each daily file, malformed rows, and symbol/date identity. Report all minutes with both sources, one-sided minutes, and daily totals. Do not backfill, redistribute aggregate quantities across minutes, or adjust tolerances after seeing the results.

Use relative tolerance `1e-8` with absolute floor `1e-10` for floating-point quantity/quote/OHLC comparisons; trade counts must match exactly. Report both tolerance-based matches and raw maximum absolute differences. Compare daily totals separately, using relative tolerance `1e-10` and absolute floor `1e-8` for floating-point volume totals. Any unexplained checksum, date coverage, ID, or daily-total discrepancy remains an explicit failure; it is not silently normalized.

## Decision rules

1. A file missing, checksum failure, malformed CSV/header, off-day timestamp, duplicate/non-monotonic aggregate ID, or unexplained within-file ID gap is a source-integrity failure for that symbol/date.
2. Any minute-level mismatch means these minute-bucketed `aggTrades` are **not certified as an exact reconstruction** of native klines for that metric. State the fraction and distribution by symbol/date; do not call all aggregate data invalid solely from a bucket mismatch.
3. Any unexplained daily base/quote total discrepancy leaves the corresponding symbol/date unresolved and blocks using that sample as a validated minute-flow feature source.
4. Passing this data audit only establishes the tested archive integrity/reconciliation scope. It does not validate a predictive feature, strategy, signal accuracy, or any M2 claim. No strategy is promoted by this audit.

## Reporting and attribution

Save a machine-readable summary and a concise report with exact sample counts, file checksums, row/coverage metrics, reconciliation rates, unresolved cases, and the decision. Raw ZIPs remain untracked. Any redistributed derivative summary must attribute Binance Vision and carry CC BY-NC-SA 4.0; no real-time data, signals, or commercial use is in scope.
