# Binance USD-M aggTrades ↔ 1m kline multi-day integrity audit

Audit date: 2026-11-19
Preregistration: [binance-aggtrades-multiday-audit-prereg-2026-11-19.md](binance-aggtrades-multiday-audit-prereg-2026-11-19.md)
Machine-readable details and per-archive SHA-256 values: [JSON report](binance-aggtrades-multiday-audit-2026-11-19.json)

## Result

The sample does **not** certify minute-bucketed `aggTrades` as an exact reconstruction of native USD-M 1-minute klines. All tested archives passed publisher checksums and had complete day coverage, but minute-level volume/count differences and 31 unresolved daily-volume discrepancies remain. This is a source-integrity finding, not a strategy or predictive-signal result.

## Frozen sample and integrity

- 20 preregistered USD-M symbols × four fixed UTC dates (`2025-01-01`, `2025-04-01`, `2025-07-01`, `2025-10-01`) = 80 symbol-days.
- 160 ZIP archives plus 160 `.CHECKSUM` sidecars; all 160 ZIP SHA-256 values matched the publisher sidecars.
- Parsed 24,112,530 aggregate-trade rows and 115,200 native 1-minute candles.
- Every symbol-day had all 1,440 expected minutes in both sources: 115,200 shared minutes, zero one-sided minutes.
- Malformed rows: 0; timestamps outside the requested UTC date: 0; duplicate/non-monotonic aggregate IDs: 0; missing aggregate-ID values between adjacent rows: 0.

## Minute-level comparison

Tolerance was fixed before acquisition: relative `1e-8`, absolute floor `1e-10`; underlying trade-count estimate had to match exactly.

| Metric reconstructed from aggTrades | Mismatches / shared minutes | Mismatch rate |
|---|---:|---:|
| Open | 1,344 / 115,200 | 1.167% |
| High | 35 / 115,200 | 0.030% |
| Low | 76 / 115,200 | 0.066% |
| Close | 0 / 115,200 | 0.000% |
| Base volume | 4,317 / 115,200 | 3.747% |
| Quote volume (`price × quantity`) | 4,321 / 115,200 | 3.751% |
| Taker-buy base volume | 2,112 / 115,200 | 1.833% |
| Taker-buy quote volume | 2,112 / 115,200 | 1.833% |
| Underlying trade-count estimate (`last_id − first_id + 1`) | 20,308 / 115,200 | 17.628% |

The data was grouped using `transact_time // 60,000`; quantities were not redistributed between minutes. A matching close price does not remove the open, volume, or count discrepancies.

## Daily volume discrepancies

Under the preregistered daily tolerance, base and quote volume both matched for 49/80 symbol-days. The same 31 symbol-days failed both comparisons; exact signed deltas are in the JSON report.

| UTC date | Symbol-days with unresolved base and quote totals |
|---|---|
| 2025-01-01 | SOLUSDT |
| 2025-04-01 | BTCUSDT, ETHUSDT, SOLUSDT, ADAUSDT, DOGEUSDT, TRXUSDT, AVAXUSDT, FILUSDT, APTUSDT |
| 2025-07-01 | BTCUSDT, ETHUSDT, SOLUSDT, XRPUSDT, ADAUSDT, DOGEUSDT, LTCUSDT, DOTUSDT, ETCUSDT, FILUSDT, UNIUSDT, NEARUSDT |
| 2025-10-01 | BTCUSDT, ETHUSDT, SOLUSDT, ADAUSDT, DOGEUSDT, XLMUSDT, FILUSDT, NEARUSDT, APTUSDT |

All 31 discrepancies are unresolved. This audit does not infer their cause or normalize them away. In particular, the July 2025 ADAUSDT base-volume difference is `-61,117` units and requires source-level investigation before any use of these archives as a volume-flow feature.

## Decision and limits

- Use native klines for candle-derived labels and OHLCV backtests in this tested scope.
- Keep `aggTrades` separate; do not call minute-bucketed aggressor/volume features validated from this audit.
- The audit covers four quarterly calendar anchors, 20 selected contracts, and 2025 only. It does not certify other dates, symbols, archive revisions, or predictive usefulness.
- No forecasts, labels, returns, accuracy, M2, parameter search, or strategies were calculated.
- Raw archives remain outside Git at `/private/tmp/binance-aggtrades-multiday-2025/`.

Source: Binance Vision historical USD-M archives. This derived report is provided under CC BY-NC-SA 4.0 with attribution to Binance Vision. No raw archive data is included.
