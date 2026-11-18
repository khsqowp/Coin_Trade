# Historical candle gap repair — 2026-11-15

Status: **complete**. The source DB is preserved; repairs are stored in a separate patch database.

- Source: `/Users/user/CODE/Coin_Trade/chart_predictor/data/vision_dev.sqlite` (2,558,599,168 bytes; metadata fingerprint `ad676e414a4f5f0b88a726519acd1bf3c2a99840d97b16dd7c56c10beeacbbe8`)
- Patch: `/Users/user/CODE/Coin_Trade/chart_predictor/data/vision_gap_repair.sqlite` (3,694,592 bytes)
- Endpoint: `https://fapi.binance.com/fapi/v1/klines`
- Retrieved rows: 14,400 (SOLUSDT 7,200; XRPUSDT 7,200)
- Requests: 10; each raw response page retained; payload SHA-256 values are in the JSON manifest.
- Quality inside requested gaps: 0 missing minutes, 0 duplicate keys, 0 off-grid timestamps, 0 invalid OHLCV rows, 0 null rows.
- Overlap with source DB: 0 keys. Source DB was not modified.
- Merged snapshot: `chart_predictor/data/vision_dev_repaired.sqlite` (19,790,858 rows; 0 gaps across observed symbol spans; 0 invalid rows; 10 raw source pages retained in `repair_pages`).

## Recovered windows

|Symbols|UTC start|UTC end (exclusive)|Rows per symbol|
|---|---|---|---:|
|SOLUSDT, XRPUSDT|2022-02-26 00:00|2022-03-01 00:00|4,320|
|SOLUSDT, XRPUSDT|2022-04-01 00:00|2022-04-03 00:00|2,880|

## Use and limitation

The patch is intentionally separate because historical inputs should remain immutable. Consumers that need the repaired history should explicitly use `vision_dev_repaired.sqlite`. `vision_dev.sqlite` remains the original input for every earlier study. Do not overwrite the original database. The full request/page hashes and timestamps are in `data_repair_20261115.json`.
