# Binance raw-trade event-density audit — frozen protocol v2

Status: frozen before the aggregate density run. Descriptive source-resolution audit only; no strategy, signal, or feature-sufficiency decision.

## Question and permitted conclusion

Measure the timestamped raw-trade event density in the fixed 20-symbol × four-UTC-date sample. Report measurements only. Do not conclude that event density is “sufficient” for microstructure features, execution, or prediction; trade prints do not provide order-book depth or spread.

## Fixed sample and input allowlist

- Read `/private/tmp/binance-trades-kline-audit-2026-11-19/results.json` only for the top-level `classification` and `rows` fields, then for each row only `symbol`, `utc_date`, `archive_sha256.trades`, and `failure_reasons`. Ignore every other key, including `sample`, `symbol_day_integrity_pass`, kline/trade comparison fields, diagnostics, and totals.
- Use exactly the 80 `(symbol, utc_date)` entries already present in `rows` (20 symbols, four UTC dates: 2025-01-01, 2025-04-01, 2025-07-01, 2025-10-01). Do not select or exclude rows based on prior cross-source volume comparisons. Report those prior failure labels descriptively without using them as an eligibility filter.
- For each entry, require archive filename `{symbol}-trades-{utc_date}.zip`, one CSV member named `{symbol}-trades-{utc_date}.csv`, SHA-256 equal to the allowlisted manifest digest and the adjacent `{archive}.CHECKSUM` sidecar. Sidecar format is exactly a 64-hex SHA-256 followed by whitespace and the matching archive filename (optional leading `*` before filename is accepted). Any mismatch aborts the complete run.
- Fail closed on malformed or duplicate sample keys, missing data, schema deviations, non-increasing trade IDs, decreasing timestamps, or timestamps outside the UTC day. No row dropping or replacement.

## Schema and fields

The Binance Public Data README documents USD-M `trades` from `/fapi/v1/trades` with columns, in order: `trade Id`, `price`, `qty`, `quoteQty`, `time`, `isBuyerMaker`; `time` is an integer Unix millisecond timestamp. Source: [Binance Public Data README](https://github.com/binance/binance-public-data/blob/master/README.md#trades).

Validate the exact six-column header and row field count, but interpret only `trade Id` as base-10 integer, `time` as base-10 integer milliseconds, and `isBuyerMaker` as case-insensitive `true` or `false`. Do not parse, retain, or compute with price/quantity/quoteQty. A missing header or empty data body is an error. Binance's maker flag means `false` counts buyer-initiated and `true` seller-initiated for this descriptive tally.

## Fixed measurements and invariants

Use UTC-day interval `[00:00:00.000, next day 00:00:00.000)`: include the start, reject next midnight. Assign bins relative to day start using widths 1,000 ms, 10,000 ms, and 60,000 ms. Denominators are exactly 86,400, 8,640, and 1,440 bins per symbol-day, including empty bins.

For every symbol-day and pooled across all 80, report total events, expected bins, nonempty-bin count/fraction, event-count p50/p95/p99/max over all bins including zeros, and the same percentiles over nonempty bins. Percentiles are nearest-rank `ceil(p*n)`, one-indexed. Report buyer-initiated and seller-initiated event counts. Enforce at each width: bin counts sum to accepted events; buyer + seller events equal accepted events; pooled expected bins equal 80 × bins per day.

## Scope and reproducibility

The script is deterministic, local-only, reads raw inputs without modifying them, saves aggregate JSON/Markdown only, and never saves raw rows. It does not calculate prices, returns, labels, PnL, M1/M2, signals, targets, stops, costs, or predictive performance. The four isolated dates are not a continuous or regime-representative panel. This audit is not a strategy trial and cannot satisfy the user's ≥80% target-first criterion. No live/manual signal or order execution is authorized. Preserve Binance attribution and applicable CC BY-NC-SA 4.0 terms; raw archives and the input manifest remain outside Git.

Tests must exercise all three bin widths and exact boundaries, UTC start/next-midnight behavior, empty bins, buyer-maker mapping, nearest-rank quantiles, archive and sidecar hash mismatch, and fixed-sample/manifest validation.
