# R018 — Binance Vision terms and local-data eligibility audit

Date: 2026-11-16
Parent: `2026-11-16-r017-source-access-audit`
Status: source/data gate audit; **not a strategy performance trial**

## Scope and question

Determine whether the Binance Vision terms currently permit this user's personal, non-production historical research, and whether the price databases currently available on the Mac contain the fields needed to preregister a cost-aware USDT-M futures strategy test.

This audit does not calculate indicators, inspect returns, select strategies, open a sealed split, download archive data, or alter any market-data database. It uses public source documentation, read-only SQLite schema/metadata queries, and one HTTP HEAD request to verify a single archive object's existence without retrieving its contents.

## Why this differs from R017

R017 correctly left the intended data-use scope unresolved. This round verifies the current official terms' exact non-commercial scope and distinguishes historical personal research from live signal use. It also checks the actual schemas rather than treating a database path in an older report as evidence that required cost fields are present.

## Frozen audit checks

1. Read current official Binance Vision terms and repository README/downloader docs; verify one representative monthly archive URL with HTTP HEAD only.
2. Inspect only the schemas and aggregate coverage metadata of local `candles.sqlite` and `vision_dev_repaired.sqlite`, opened read-only.
3. Check whether funding, mark/premium, fees, or point-in-time listing membership are represented in those databases.
4. Do not calculate strategy results. A quantitative run is admissible only after its own plan identifies complete eligible inputs, exact splits, costs, baseline, trial family, and multiple-testing procedure.

## Data inspected

- `/Users/user/CODE/Coin_Trade/chart_predictor/data/vision_dev_repaired.sqlite` (outside this research checkout; opened SQLite read-only).
- `/Users/user/CODE/Coin_Trade/chart_predictor/data/candles.sqlite` (outside this research checkout; opened SQLite read-only).
- Public Binance Vision `TERMS_AND_CONDITIONS.md` and repository `README.md`, accessed 2026-11-16.
- Official Binance Vision downloader documentation for futures kline, premium-index, mark-price, and index-price archive families; official USDⓈ-M REST market-data documentation for funding-rate history.
- One HTTP HEAD request to `https://data.binance.vision/data/futures/um/monthly/premiumIndexKlines/BTCUSDT/1h/BTCUSDT-1h-2025-01.zip`; no archive bytes were retrieved.

No source DB was copied, updated, or committed.
