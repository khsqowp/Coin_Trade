# Local crypto candle inventory — 2026-11-20

## Scope and objective

Read-only inventory of the existing Binance Vision development candle databases to determine whether the current files support another strategy experiment. This is not an outcome analysis. The investment objective remains maximum after-cost compounded wealth across regimes; the target-first M2 >=80% condition is a separate signal-quality gate.

## Files examined

The source files are git-ignored local databases and were not modified or copied:

- `/Users/user/CODE/Coin_Trade/chart_predictor/data/vision_dev.sqlite`
- `/Users/user/CODE/Coin_Trade/chart_predictor/data/vision_dev_repaired.sqlite`

The repaired database's recorded repair manifest is `docs/chart_predictor/data_repair_20261115.json`. It documents 14,400 recovered 1-minute rows for SOLUSDT and XRPUSDT, 7,200 each, in two historical missing windows. The manifest records zero duplicate rows, zero invalid OHLCV rows, zero missing rows in the requested repair windows, and verified page payload hashes. Prior experiment outputs remain tied to whichever source snapshot they originally used; repair does not retroactively change their input identity.

## Direct read-only observations

SQLite schema inspection found only `archive_manifest`, `candles`, and `repair_pages` in `vision_dev_repaired.sqlite`; its `candles` table contains 1-minute OHLCV/trade-count/taker-buy fields and no funding or open-interest columns.

| Database | Rows | Symbols | Per-symbol internal 1m gaps | Last observed candle |
|---|---:|---:|---:|---|
| `vision_dev.sqlite` | 19,776,458 | 6 | SOL: 7,200 missing minutes; XRP: 7,200 missing minutes; other four: 0 | 2026-06-30 23:59 UTC |
| `vision_dev_repaired.sqlite` | 19,790,858 | 6 | 0 for each of the six symbols | 2026-06-30 23:59 UTC |

Repaired-database per-symbol counts and first timestamps were observed as follows: BTCUSDT 3,417,120 (2020-01-01 00:00 UTC), ETHUSDT 3,417,120 (2020-01-01 00:00), XRPUSDT 3,409,419 (2020-01-06 08:21), BNBUSDT 3,359,039 (2020-02-10 08:01), DOGEUSDT 3,141,540 (2020-07-10 09:00), and SOLUSDT 3,046,620 (2020-09-14 07:00). All end at 2026-06-30 23:59 UTC. The repaired database has 453 monthly manifest entries, but this does not imply a 20-symbol or point-in-time universe.

The checks queried schema, counts, symbol names, minimum/maximum timestamps, and minute-to-minute timestamp deltas. They did not retrieve OHLCV values, compute indicators, labels, trades, or strategy performance. Timestamp metadata was scanned across the full stored interval, including rows after 2023-12-31; consequently, this is not a claim that every sealed-period metadata field remained untouched. No price outcomes or return series from the sealed interval were opened or used to choose a strategy.

## Read-only archive-availability probe

Additional public metadata checks on 2026-11-20 found:

- A direct unauthenticated `GET /fapi/v1/exchangeInfo` response, filtered to `status=TRADING`, `contractType=PERPETUAL`, `quoteAsset=USDT`, and `underlyingType=COIN`, returned **519 current contracts**. The response was processed in memory and not saved. This proves the current candidate count exceeds 20; it does not prove these symbols existed in earlier periods, that the full set is coin-native rather than a broader token category, or that the archived history includes delisted contracts.
- A read-only paginated listing of the official Binance Vision bucket prefix `data/futures/um/monthly/klines/` returned **1,080 distinct symbol directory prefixes** (two pages). The count includes contract symbols outside the target filter and is not a count of eligible historical PIT instruments.
- HTTP `HEAD` returned 200 for four monthly funding archive objects: BTCUSDT 2020-01 and 2023-12, SOLUSDT 2020-09 and 2023-12. Their matching `.CHECKSUM` sidecars also returned 200 and 98-byte content length. No ZIP or sidecar body was downloaded, so row coverage, checksum matching, timestamp semantics, interval changes, and symbol-lifetime completeness remain unverified.
- The public `exchangeInfo` endpoint could not be fetched through the web-browsing proxy (HTTP 451), but the direct read-only shell request succeeded. This is a tool-path limitation, not evidence of Binance data unavailability.

## Research consequence

1. The repaired file is structurally suitable for deterministic 1-minute price-path research on these six current symbols, subject to separately validating the exact input window and checksum/fingerprint for each experiment.
2. It cannot satisfy the chart-prediction specification's >=20-symbol breadth gate for M2 success. Its six current symbols also do not establish a point-in-time tradable futures universe; do not interpret these exploratory results as broad-market evidence.
3. It cannot establish futures net profitability because historical funding is absent. The OI/metrics source remains ineligible until symbol/date coverage and effective-time semantics are resolved; see `binance-um-metrics-snapshot-audit-2026-11-19.md`.
4. A useful next step is a separate, predeclared data expansion and universe audit for >=20 eligible COIN-type USD-M instruments, including symbol lifetimes and archive checksums. The current 519-symbol metadata count and the 1,080 archive directory count make this technically plausible, but the historical intersection and delisted-instrument treatment have not been proven. Do not simply append current survivors and call the result unbiased. Preserve old databases and all existing experiment inputs.

## Reproduction queries

The audit used SQLite read-only connections. Representative queries:

```sql
SELECT COUNT(*), COUNT(DISTINCT symbol), MIN(open_ms), MAX(open_ms)
FROM candles;

SELECT symbol, COUNT(*), MIN(open_ms), MAX(open_ms), COUNT(DISTINCT open_ms)
FROM candles
GROUP BY symbol
ORDER BY symbol;

WITH ordered AS (
  SELECT symbol, open_ms,
         LAG(open_ms) OVER (PARTITION BY symbol ORDER BY open_ms) AS previous_open_ms
  FROM candles
)
SELECT symbol,
       COUNT(*) FILTER (WHERE open_ms - previous_open_ms <> 60000) AS abnormal_intervals,
       COALESCE(SUM(CASE WHEN open_ms - previous_open_ms > 60000
                         THEN (open_ms - previous_open_ms) / 60000 - 1 ELSE 0 END), 0) AS missing_minutes
FROM ordered
WHERE previous_open_ms IS NOT NULL
GROUP BY symbol;
```

SQLite `integrity_check`, repair-window checksum validation, and source/repair overlap checks are documented in `docs/chart_predictor/data_repair_20261115.json`; this turn did not rerun those checks.
