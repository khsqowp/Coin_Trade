# Minute collector

`yf_collect` downloads Yahoo Finance OHLCV with `auto_adjust=False`; stored OHLC is raw unadjusted data and `adjusted` is always `False`. Tick-derived KR bars have unknown volume (stored as zero) and are sampled-subset observations, not replacements for Yahoo coverage. `src` identifies `yf` versus `tick`.

Data lives under `data/minute/<market>/<interval>/date=YYYY-MM-DD/batch=NN.parquet`; timestamps are UTC bar-start values, while partition dates use America/New_York for US and Asia/Seoul for KR. Files use zstd compression, sorted rows, and atomic replacement. Universe snapshots live in `collect/universe/`.

Limits documented for 2026-11-13: Yahoo 1m covers the last 30 days with at most about 8 days per request; 5m covers 60 days; 1h covers 2 years. Yahoo KR regular-session bars cover 09:00–14:59 KST and omit the 15:00–15:30 closing auction. Current constituents create survivorship bias; daily snapshots accumulate constituent history.

Known limitation: provider history and current constituent lists do not establish point-in-time membership or delisted-symbol completeness. Remove the cron entry with `crontab -l | grep -v STOCK_LOOP_COLLECT | crontab -`.

The Nasdaq-100 supplement is approximate and may be stale. Non-S&P 500 names that Yahoo does not recognize appear in `universe_missing`.
