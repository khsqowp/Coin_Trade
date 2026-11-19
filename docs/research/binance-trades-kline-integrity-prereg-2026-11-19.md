# Binance USD-M raw trades ↔ 1m kline integrity audit preregistration

Version 4 — frozen 2026-11-19, before archive acquisition. Versions 1 and 2 were rejected by independent red-team review; version 3 was conditional. Version 4 received PASS before any source archive or outcome label was accessed. This is a source-integrity audit only, not a strategy, prediction, or performance test.

## Question

Can Binance Vision's individual USD-M `trades` archives reconstruct the corresponding native 1-minute USD-M klines more faithfully than the previously audited `aggTrades` archives, for the same fixed sample?

## Frozen sample

- Market: Binance USD-M futures.
- Symbols: `BTCUSDT`, `ETHUSDT`, `BNBUSDT`, `SOLUSDT`, `XRPUSDT`, `ADAUSDT`, `DOGEUSDT`, `TRXUSDT`, `LTCUSDT`, `BCHUSDT`, `LINKUSDT`, `DOTUSDT`, `AVAXUSDT`, `XLMUSDT`, `ETCUSDT`, `FILUSDT`, `UNIUSDT`, `AAVEUSDT`, `NEARUSDT`, `APTUSDT`.
- UTC dates: `2025-01-01`, `2025-04-01`, `2025-07-01`, `2025-10-01`.
- Denominator: 80 symbol-days. Do not replace missing or defective items.
- Required source pairs per symbol-day: daily raw `trades` ZIP + publisher `.CHECKSUM`; native daily `1m` klines ZIP + publisher `.CHECKSUM`.
- Raw downloads remain outside Git. Do not access forecast/target labels or calculate strategy outcomes.

## Frozen parser and checks

1. Each ZIP must contain exactly one CSV whose basename is `<symbol>-trades-<date>.csv`. Require one header row. After applying only these fixed aliases (`trade Id`→`id`, `quoteQty`→`quote_qty`, `isBuyerMaker`→`is_buyer_maker`), its six columns must be exactly `id,price,qty,quote_qty,time,is_buyer_maker`; reject missing, duplicate, or undocumented extra columns. Do not guess headerless positional data. Parse `id` and `time` as base-10 integers; parse price, qty, and quote_qty as finite decimals greater than zero; accept the buyer-maker flag only as case-insensitive `true` or `false`. Reject malformed rows, invalid values, symbol/date mismatches, duplicate IDs, and non-monotone IDs. Do not deduplicate or repair. Equal timestamps are allowed and ordered by `(time, id)`.
2. For each native kline ZIP, require exactly one CSV whose basename is `<symbol>-1m-<date>.csv`, with exactly one header row containing these columns in this order: `open_time,open,high,low,close,volume,close_time,quote_volume,count,taker_buy_volume,taker_buy_quote_volume,ignore`. Reject alternate/headerless layouts, duplicate or unordered minute keys, non-minute-aligned `open_time`, off-day rows, non-finite OHLCV values, or non-integer/negative count. Require `close_time == open_time + 59,999` for each row. Verify every archive SHA-256 against its publisher sidecar. Record missing ZIP and sidecar separately, checksum mismatch, parse failure, row counts, ID range, and timestamp range. The allowed raw-trade timestamp range for a UTC day is `[00:00:00.000, next day 00:00:00.000)` in milliseconds; every timestamp outside it fails that symbol-day.
3. Key native klines by `open_time` and raw trades by `floor(time / 60,000)`. Build the full 1,440-minute grid and require one native kline row for every minute. A minute is active when its native kline `count > 0` or it contains at least one valid raw trade. Report native-active and raw-active sets, both set differences, and their union; a one-sided active minute is a mismatch, never removed from the denominator. When neither source is active, require native count, base/quote volume, and taker-buy volume fields all to equal zero; do not synthesize OHLC from absent trades.
4. For each shared active minute reconstruct OHLC using `(time, id)` order; sum raw `qty`, archived `quote_qty`, valid raw-row count, and taker-buy base/quote volume where `is_buyer_maker == false`. Compare both `sum(quote_qty)` and the diagnostic `sum(price × qty)` with native quote volume; only `sum(quote_qty)` is the preregistered primary quote-volume reconstruction. The minute trade count is the number of valid raw trade rows, not an aggregate-ID estimate. If any ID is duplicated or non-monotone, fail the symbol-day and do not remove the row to improve reconciliation.
5. Compare OHLC only on native-active minutes, requiring raw and native active-minute sets to be identical first. Compare base/quote volume, trade count, and taker-buy base/quote on every minute in the full 1,440-minute grid; inactive-both minutes therefore have an explicit zero-field check. Use exact integer equality for trade counts and relative tolerance `1e-8` with absolute floor `1e-10` for numeric values. Report each field's denominator, raw maxima, active-minute set differences, and every mismatch by symbol/date/field. Do not adjust tolerance after seeing results.

## Decision rules

- Any missing archive/checksum, checksum failure, malformed data, duplicate ID, off-day timestamp, or unexplained empty native-active minute remains a failed symbol-day; no substitution or imputation.
- Certification is field-specific: OHLC requires at least one native-active minute in each of the 80 symbol-days, zero mismatches across every native-active minute, and identical active-minute sets. A symbol-day with zero native-active minutes fails OHLC certification for the full sample because it supplies no OHLC comparison observation. Volume/count/taker fields require zero mismatches over all 1,440 minutes for every symbol-day. All fields additionally require complete files/checksums and no unresolved row-level integrity failures. Partial passes do not certify a broader feature panel.
- Passing establishes data integrity only for the tested sample; it does not establish predictive usefulness, point-in-time contract membership, or out-of-sample performance.
- Regardless of the result, no signal/outcome labels are opened until a separate independent review confirms that one exact within-minute feature is novel versus prior taker-flow and R005 work, and its M2 claim family is preregistered.

## Attribution and rights

The Binance Vision Terms page, last updated 2026-08-26 and reviewed on 2026-11-19, states that permitted non-commercial uses include purely personal, non-production historical backtesting; it prohibits live proprietary execution and compensated third-party signal distribution and requires attribution/CC BY-NC-SA 4.0 for redistributed derivative work. The user separately authorized historical backtests only. Recheck the official terms before acquisition. Before redistributing data-derived results, confirm the license applies to the specific derivative and is compatible with the repository; do not silently relicense unrelated code. Never include raw market archives in Git.

## Official references

- Binance Public Data README: <https://github.com/binance/binance-public-data/blob/master/README.md>
- Binance Public Data downloader documentation: <https://github.com/binance/binance-public-data/blob/master/python/README.md>
- Binance Vision Dataset Terms: <https://github.com/binance/binance-public-data/blob/master/TERMS_AND_CONDITIONS.md>

Review record: version 1 was rejected for underspecified CSV schema, active-minute denominator, raw-row count definition, UTC boundary, and source-terms qualification. Version 2 was rejected for missing native-kline parser rules and inconsistent treatment of inactive-minute OHLC. Version 3 was conditional because zero-active symbol-days had no OHLC comparison denominator. Version 4 fixed the remaining denominator rule and received independent red-team PASS on 2026-11-19. No archive has been acquired and no audit has run.
