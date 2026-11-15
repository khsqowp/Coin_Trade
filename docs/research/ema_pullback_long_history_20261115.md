# EMA20/50/200 pullback reversal — development probe

**Decision: exploratory only; no edge is established by this report.**

## Fixed design

- Read-only DB: `/Users/user/CODE/Coin_Trade/chart_predictor/data/vision_dev.sqlite`; exact table/columns: `candles(symbol, open_ms, open, high, low, close, volume, ...)`.
- The SQL predicate is `open_ms < cutoff`; additionally, source 1m candles must close no later than cutoff. No row at/after cutoff enters indicators, signal, entry, or outcome.
- Exclusive cutoff: `2026-10-09T00:00:00+00:00`.
- Symbols: BNBUSDT, BTCUSDT, DOGEUSDT, ETHUSDT (the four symbols retained in prior local continuity-screened long-history probes; SOL/XRP are excluded).
- Timeframes: 1, 3, 5, 10, 15, 30, 60, 120, 240, 360, 480, 720, 1440 minutes (1m through 1d). One predeclared rule per TF; horizons 10/20 TF bars.
- Regime: EMA20>EMA50>EMA200 and EMA200 rising for long; strict inverse and falling EMA200 for short. EMAs are close-based, adjust=False.
- Pullback + confirmation is a single candle: long low lies in [EMA20−1ATR14, EMA20], bullish candle closes above prior high; short high lies in [EMA20, EMA20+1ATR14], bearish candle closes below prior low.
- Entry next TF candle open; stop is 1 ATR14 from entry, target 2 times that entry-to-stop distance; timeout after 10/20 full TF candles.
- Stop/target path checked against original 1m OHLC. If both touch in the same minute, stop wins. At timeout, exit at final TF close.
- Separate chronological non-overlap selection for each symbol/TF/horizon; both directions compete, selection uses timestamps only, not outcomes.
- Fee scenarios are round-trip costs of 0.10% and 0.30%, deducted from unlevered return. No additional slippage, spread, funding, or margin model.
- Accuracy is target-first outcome rate (not candle-direction accuracy); net-positive rate is reported separately after costs. Coverage is directional signals / complete TF bars; both-side coverage can exceed 100%.
- Uncertainty: 95% UTC-day cluster bootstrap (2,000 replicates) and Wilson interval for target-first/net-positive proportions. Cells with fewer than 30 non-overlapping trades are NOT_EVALUABLE.
- No whole-DB hash was computed. No M4 confidence calibration, no leverage PnL, no sealed-data evaluation, and no post-result tuning.

## Source 1m continuity (strict gaps are excluded from aggregate bars and trade paths)

| Symbol | Cutoff rows | Missing 1m intervals | Gap count | Largest gap (minutes) |
|---|---:|---:|---:|---:|
| BNBUSDT | 3359039 | 0 | 0 | 0 |
| BTCUSDT | 3417120 | 0 | 0 | 0 |
| DOGEUSDT | 3141540 | 0 | 0 | 0 |
| ETHUSDT | 3417120 | 0 | 0 | 0 |

## Results

| TF | Horizon | Side | Raw n | Independent N | Coverage | Target-first (cluster 95% CI) | Stop | Timeout | Net-positive base | Mean net base % (cluster CI) | Net-positive stress | Mean net stress % (cluster CI) | Status |
|---:|---:|---|---:|---:|---:|---|---:|---:|---:|---|---:|---|---|
| 1m | 10 | long | 313339 | 187763 | 4.6% | 27.9% [27.7%, 28.1%] | 59.4% | 12.7% | 25.6% | -0.099 [-0.100, -0.098] | 6.7% | -0.299 [-0.300, -0.298] | EXPLORATORY |
| 1m | 10 | short | 298240 | 176279 | 4.6% | 29.1% [28.8%, 29.4%] | 58.7% | 12.2% | 27.1% | -0.097 [-0.099, -0.096] | 8.6% | -0.297 [-0.299, -0.296] | EXPLORATORY |
| 1m | 10 | both | 611579 | 364042 | 4.6% | 28.5% [28.3%, 28.7%] | 59.0% | 12.5% | 26.3% | -0.098 [-0.099, -0.097] | 7.6% | -0.298 [-0.299, -0.297] | EXPLORATORY |
| 1m | 20 | long | 313339 | 139315 | 4.6% | 32.3% [32.0%, 32.6%] | 64.9% | 2.8% | 26.9% | -0.100 [-0.102, -0.098] | 7.8% | -0.300 [-0.301, -0.298] | EXPLORATORY |
| 1m | 20 | short | 298240 | 130574 | 4.6% | 33.5% [33.2%, 33.8%] | 63.8% | 2.7% | 28.5% | -0.097 [-0.099, -0.095] | 9.9% | -0.297 [-0.299, -0.295] | EXPLORATORY |
| 1m | 20 | both | 611579 | 269889 | 4.6% | 32.9% [32.7%, 33.1%] | 64.4% | 2.7% | 27.7% | -0.099 [-0.100, -0.097] | 8.8% | -0.299 [-0.300, -0.297] | EXPLORATORY |
| 3m | 10 | long | 115524 | 67216 | 5.0% | 26.7% [26.3%, 27.1%] | 58.2% | 15.1% | 31.9% | -0.101 [-0.104, -0.097] | 16.9% | -0.301 [-0.304, -0.297] | EXPLORATORY |
| 3m | 10 | short | 108786 | 62462 | 5.0% | 28.2% [27.7%, 28.7%] | 57.7% | 14.0% | 32.8% | -0.093 [-0.098, -0.089] | 19.2% | -0.293 [-0.298, -0.289] | EXPLORATORY |
| 3m | 10 | both | 224310 | 129678 | 5.0% | 27.4% [27.1%, 27.7%] | 58.0% | 14.6% | 32.4% | -0.097 [-0.100, -0.094] | 18.0% | -0.297 [-0.300, -0.294] | EXPLORATORY |
| 3m | 20 | long | 115524 | 49140 | 5.0% | 31.8% [31.4%, 32.3%] | 64.4% | 3.8% | 32.4% | -0.101 [-0.104, -0.097] | 19.3% | -0.301 [-0.305, -0.297] | EXPLORATORY |
| 3m | 20 | short | 108783 | 45448 | 5.0% | 32.8% [32.3%, 33.3%] | 63.6% | 3.6% | 33.4% | -0.094 [-0.099, -0.089] | 21.4% | -0.294 [-0.300, -0.289] | EXPLORATORY |
| 3m | 20 | both | 224307 | 94588 | 5.0% | 32.3% [31.9%, 32.6%] | 64.0% | 3.7% | 32.9% | -0.098 [-0.101, -0.094] | 20.3% | -0.298 [-0.301, -0.294] | EXPLORATORY |
| 5m | 10 | long | 71085 | 40982 | 5.1% | 26.1% [25.5%, 26.5%] | 57.7% | 16.2% | 33.4% | -0.101 [-0.107, -0.097] | 22.1% | -0.301 [-0.307, -0.296] | EXPLORATORY |
| 5m | 10 | short | 65977 | 37596 | 5.1% | 27.5% [27.0%, 28.1%] | 57.6% | 14.9% | 33.9% | -0.091 [-0.098, -0.085] | 23.8% | -0.291 [-0.298, -0.284] | EXPLORATORY |
| 5m | 10 | both | 137062 | 78578 | 5.1% | 26.8% [26.4%, 27.1%] | 57.6% | 15.6% | 33.7% | -0.096 [-0.101, -0.092] | 22.9% | -0.296 [-0.301, -0.292] | EXPLORATORY |
| 5m | 20 | long | 71085 | 29827 | 5.1% | 31.5% [30.9%, 32.1%] | 64.2% | 4.3% | 33.2% | -0.101 [-0.108, -0.094] | 24.7% | -0.301 [-0.307, -0.294] | EXPLORATORY |
| 5m | 20 | short | 65976 | 27367 | 5.1% | 32.5% [31.9%, 33.2%] | 63.5% | 3.9% | 34.2% | -0.088 [-0.097, -0.079] | 26.3% | -0.288 [-0.296, -0.280] | EXPLORATORY |
| 5m | 20 | both | 137061 | 57194 | 5.1% | 32.0% [31.5%, 32.4%] | 63.9% | 4.2% | 33.7% | -0.095 [-0.100, -0.090] | 25.5% | -0.295 [-0.300, -0.289] | EXPLORATORY |
| 10m | 10 | long | 36402 | 20566 | 5.3% | 25.4% [24.8%, 26.1%] | 57.0% | 17.5% | 35.0% | -0.096 [-0.106, -0.085] | 27.3% | -0.296 [-0.306, -0.285] | EXPLORATORY |
| 10m | 10 | short | 33790 | 19003 | 5.3% | 27.0% [26.2%, 27.7%] | 57.6% | 15.4% | 34.4% | -0.092 [-0.105, -0.078] | 28.1% | -0.292 [-0.306, -0.278] | EXPLORATORY |
| 10m | 10 | both | 70192 | 39569 | 5.3% | 26.2% [25.7%, 26.7%] | 57.3% | 16.5% | 34.7% | -0.094 [-0.102, -0.085] | 27.7% | -0.294 [-0.303, -0.285] | EXPLORATORY |
| 10m | 20 | long | 36402 | 14962 | 5.3% | 30.9% [30.1%, 31.8%] | 64.0% | 5.1% | 33.9% | -0.098 [-0.112, -0.082] | 29.3% | -0.298 [-0.312, -0.282] | EXPLORATORY |
| 10m | 20 | short | 33789 | 13758 | 5.3% | 31.4% [30.5%, 32.3%] | 64.2% | 4.4% | 33.5% | -0.099 [-0.117, -0.083] | 29.9% | -0.299 [-0.316, -0.281] | EXPLORATORY |
| 10m | 20 | both | 70191 | 28720 | 5.3% | 31.2% [30.6%, 31.8%] | 64.1% | 4.8% | 33.7% | -0.098 [-0.109, -0.087] | 29.6% | -0.298 [-0.309, -0.287] | EXPLORATORY |
| 15m | 10 | long | 24308 | 13597 | 5.3% | 25.2% [24.4%, 26.0%] | 57.0% | 17.8% | 35.4% | -0.092 [-0.108, -0.076] | 30.0% | -0.292 [-0.308, -0.276] | EXPLORATORY |
| 15m | 10 | short | 22577 | 12544 | 5.3% | 27.6% [26.6%, 28.6%] | 56.4% | 16.0% | 35.7% | -0.085 [-0.107, -0.064] | 31.1% | -0.285 [-0.306, -0.263] | EXPLORATORY |
| 15m | 10 | both | 46885 | 26141 | 5.3% | 26.4% [25.7%, 27.0%] | 56.7% | 17.0% | 35.6% | -0.089 [-0.101, -0.076] | 30.5% | -0.289 [-0.302, -0.275] | EXPLORATORY |
| 15m | 20 | long | 24308 | 9839 | 5.3% | 30.6% [29.5%, 31.6%] | 63.8% | 5.6% | 34.1% | -0.100 [-0.121, -0.079] | 31.4% | -0.300 [-0.322, -0.279] | EXPLORATORY |
| 15m | 20 | short | 22572 | 9116 | 5.3% | 32.2% [31.0%, 33.4%] | 63.5% | 4.3% | 34.6% | -0.095 [-0.123, -0.068] | 32.3% | -0.295 [-0.322, -0.267] | EXPLORATORY |
| 15m | 20 | both | 46880 | 18955 | 5.3% | 31.4% [30.6%, 32.1%] | 63.7% | 5.0% | 34.3% | -0.098 [-0.115, -0.081] | 31.8% | -0.298 [-0.315, -0.281] | EXPLORATORY |
| 30m | 10 | long | 11984 | 6685 | 5.2% | 25.5% [24.3%, 26.7%] | 55.4% | 19.1% | 37.6% | -0.079 [-0.110, -0.047] | 33.7% | -0.279 [-0.312, -0.247] | EXPLORATORY |
| 30m | 10 | short | 11128 | 6246 | 5.2% | 26.5% [25.1%, 27.8%] | 56.6% | 16.9% | 35.7% | -0.078 [-0.122, -0.031] | 32.6% | -0.278 [-0.322, -0.232] | EXPLORATORY |
| 30m | 10 | both | 23112 | 12931 | 5.2% | 26.0% [25.1%, 26.9%] | 56.0% | 18.0% | 36.7% | -0.079 [-0.105, -0.052] | 33.2% | -0.279 [-0.306, -0.250] | EXPLORATORY |
| 30m | 20 | long | 11984 | 4848 | 5.2% | 31.7% [30.2%, 33.3%] | 62.3% | 6.0% | 35.7% | -0.062 [-0.105, -0.019] | 34.7% | -0.262 [-0.306, -0.219] | EXPLORATORY |
| 30m | 20 | short | 11127 | 4559 | 5.2% | 32.2% [30.6%, 33.9%] | 62.9% | 4.8% | 34.6% | -0.076 [-0.132, -0.013] | 33.4% | -0.276 [-0.335, -0.214] | EXPLORATORY |
| 30m | 20 | both | 23111 | 9407 | 5.2% | 32.0% [30.8%, 33.1%] | 62.6% | 5.4% | 35.2% | -0.069 [-0.105, -0.031] | 34.1% | -0.269 [-0.306, -0.233] | EXPLORATORY |
| 60m | 10 | long | 5990 | 3313 | 5.1% | 25.8% [24.1%, 27.6%] | 55.4% | 18.7% | 38.0% | -0.094 [-0.160, -0.026] | 35.5% | -0.294 [-0.360, -0.229] | EXPLORATORY |
| 60m | 10 | short | 5437 | 3133 | 5.1% | 25.8% [23.8%, 27.7%] | 55.7% | 18.5% | 36.6% | -0.137 [-0.216, -0.054] | 34.0% | -0.337 [-0.416, -0.260] | EXPLORATORY |
| 60m | 10 | both | 11427 | 6446 | 5.1% | 25.8% [24.6%, 27.1%] | 55.6% | 18.6% | 37.4% | -0.115 [-0.166, -0.064] | 34.7% | -0.315 [-0.366, -0.266] | EXPLORATORY |
| 60m | 20 | long | 5990 | 2407 | 5.1% | 31.6% [29.4%, 33.8%] | 63.4% | 5.0% | 35.3% | -0.131 [-0.222, -0.045] | 34.6% | -0.331 [-0.419, -0.246] | EXPLORATORY |
| 60m | 20 | short | 5437 | 2286 | 5.1% | 30.9% [28.6%, 33.3%] | 63.3% | 5.7% | 34.4% | -0.148 [-0.243, -0.050] | 33.6% | -0.348 [-0.444, -0.241] | EXPLORATORY |
| 60m | 20 | both | 11427 | 4693 | 5.1% | 31.3% [29.7%, 32.9%] | 63.3% | 5.4% | 34.9% | -0.139 [-0.205, -0.074] | 34.1% | -0.339 [-0.408, -0.273] | EXPLORATORY |
| 120m | 10 | long | 2920 | 1642 | 5.0% | 25.7% [23.4%, 28.2%] | 56.2% | 18.1% | 37.4% | -0.127 [-0.266, 0.017] | 35.9% | -0.327 [-0.467, -0.187] | EXPLORATORY |
| 120m | 10 | short | 2652 | 1551 | 5.0% | 24.9% [22.1%, 27.6%] | 56.1% | 19.0% | 36.6% | -0.143 [-0.291, 0.004] | 34.7% | -0.343 [-0.487, -0.211] | EXPLORATORY |
| 120m | 10 | both | 5572 | 3193 | 5.0% | 25.3% [23.6%, 27.0%] | 56.2% | 18.5% | 37.0% | -0.134 [-0.228, -0.030] | 35.3% | -0.334 [-0.432, -0.240] | EXPLORATORY |
| 120m | 20 | long | 2920 | 1205 | 5.0% | 31.3% [28.5%, 34.4%] | 63.1% | 5.6% | 35.6% | -0.112 [-0.269, 0.053] | 35.4% | -0.312 [-0.475, -0.152] | EXPLORATORY |
| 120m | 20 | short | 2642 | 1126 | 5.0% | 31.2% [27.9%, 34.7%] | 62.8% | 6.0% | 35.4% | -0.048 [-0.251, 0.163] | 35.0% | -0.248 [-0.439, -0.027] | EXPLORATORY |
| 120m | 20 | both | 5562 | 2331 | 5.0% | 31.2% [29.1%, 33.3%] | 62.9% | 5.8% | 35.5% | -0.081 [-0.206, 0.050] | 35.2% | -0.281 [-0.407, -0.158] | EXPLORATORY |
| 240m | 10 | long | 1361 | 799 | 4.8% | 25.2% [21.9%, 28.6%] | 54.3% | 20.5% | 39.0% | -0.040 [-0.324, 0.243] | 38.7% | -0.240 [-0.517, 0.041] | EXPLORATORY |
| 240m | 10 | short | 1319 | 781 | 4.8% | 25.7% [22.0%, 29.7%] | 55.2% | 19.1% | 37.4% | -0.142 [-0.412, 0.139] | 36.1% | -0.342 [-0.604, -0.065] | EXPLORATORY |
| 240m | 10 | both | 2680 | 1580 | 4.8% | 25.4% [23.0%, 27.9%] | 54.7% | 19.8% | 38.2% | -0.091 [-0.279, 0.095] | 37.4% | -0.291 [-0.485, -0.093] | EXPLORATORY |
| 240m | 20 | long | 1361 | 572 | 4.8% | 33.2% [28.9%, 37.7%] | 60.0% | 6.8% | 38.1% | -0.070 [-0.428, 0.297] | 37.9% | -0.270 [-0.632, 0.080] | EXPLORATORY |
| 240m | 20 | short | 1315 | 564 | 4.8% | 31.2% [26.7%, 35.9%] | 61.9% | 6.9% | 35.5% | -0.073 [-0.423, 0.285] | 35.1% | -0.273 [-0.614, 0.081] | EXPLORATORY |
| 240m | 20 | both | 2676 | 1136 | 4.8% | 32.2% [29.1%, 35.5%] | 60.9% | 6.9% | 36.8% | -0.071 [-0.310, 0.181] | 36.5% | -0.271 [-0.517, -0.025] | EXPLORATORY |
| 360m | 10 | long | 901 | 517 | 4.7% | 25.0% [20.8%, 29.2%] | 58.6% | 16.4% | 36.4% | -0.152 [-0.589, 0.327] | 35.4% | -0.352 [-0.789, 0.090] | EXPLORATORY |
| 360m | 10 | short | 836 | 499 | 4.7% | 24.8% [20.2%, 29.3%] | 57.1% | 18.0% | 36.7% | -0.232 [-0.586, 0.144] | 35.3% | -0.432 [-0.803, -0.067] | EXPLORATORY |
| 360m | 10 | both | 1737 | 1016 | 4.7% | 24.9% [21.9%, 28.0%] | 57.9% | 17.2% | 36.5% | -0.191 [-0.470, 0.100] | 35.3% | -0.391 [-0.674, -0.087] | EXPLORATORY |
| 360m | 20 | long | 901 | 390 | 4.7% | 27.2% [22.9%, 31.8%] | 66.7% | 6.2% | 31.3% | -0.405 [-0.880, 0.128] | 31.0% | -0.605 [-1.105, -0.075] | EXPLORATORY |
| 360m | 20 | short | 836 | 371 | 4.7% | 28.0% [22.7%, 33.5%] | 66.0% | 5.9% | 32.3% | -0.486 [-0.942, -0.022] | 32.1% | -0.686 [-1.126, -0.210] | EXPLORATORY |
| 360m | 20 | both | 1737 | 761 | 4.7% | 27.6% [24.2%, 31.2%] | 66.4% | 6.0% | 31.8% | -0.444 [-0.787, -0.088] | 31.5% | -0.644 [-0.990, -0.302] | EXPLORATORY |
| 480m | 10 | long | 700 | 393 | 4.5% | 27.7% [22.8%, 32.7%] | 54.7% | 17.6% | 40.2% | -0.087 [-0.629, 0.460] | 39.9% | -0.287 [-0.844, 0.267] | EXPLORATORY |
| 480m | 10 | short | 559 | 351 | 4.5% | 27.4% [21.1%, 33.2%] | 51.0% | 21.7% | 39.9% | 0.003 [-0.555, 0.604] | 38.7% | -0.197 [-0.805, 0.425] | EXPLORATORY |
| 480m | 10 | both | 1259 | 744 | 4.5% | 27.6% [23.6%, 31.6%] | 53.0% | 19.5% | 40.1% | -0.045 [-0.454, 0.377] | 39.4% | -0.245 [-0.634, 0.167] | EXPLORATORY |
| 480m | 20 | long | 700 | 291 | 4.5% | 33.3% [27.9%, 39.1%] | 59.1% | 7.6% | 38.1% | 0.087 [-0.574, 0.805] | 37.8% | -0.113 [-0.809, 0.577] | EXPLORATORY |
| 480m | 20 | short | 559 | 269 | 4.5% | 32.0% [24.8%, 39.6%] | 59.5% | 8.6% | 38.7% | -0.163 [-0.874, 0.525] | 38.3% | -0.363 [-1.020, 0.316] | EXPLORATORY |
| 480m | 20 | both | 1259 | 560 | 4.5% | 32.7% [28.3%, 37.3%] | 59.3% | 8.0% | 38.4% | -0.033 [-0.525, 0.475] | 38.0% | -0.233 [-0.739, 0.282] | EXPLORATORY |
| 720m | 10 | long | 515 | 291 | 4.8% | 28.2% [22.4%, 33.7%] | 49.5% | 22.3% | 43.0% | 0.513 [-0.293, 1.268] | 41.9% | 0.313 [-0.430, 1.077] | EXPLORATORY |
| 720m | 10 | short | 374 | 233 | 4.8% | 25.3% [18.9%, 31.7%] | 54.9% | 19.7% | 39.5% | -0.056 [-0.766, 0.656] | 39.5% | -0.256 [-0.968, 0.481] | EXPLORATORY |
| 720m | 10 | both | 889 | 524 | 4.8% | 26.9% [22.7%, 31.4%] | 51.9% | 21.2% | 41.4% | 0.260 [-0.293, 0.838] | 40.8% | 0.060 [-0.470, 0.647] | EXPLORATORY |
| 720m | 20 | long | 515 | 212 | 4.8% | 31.1% [25.0%, 37.3%] | 62.7% | 6.1% | 35.4% | 0.237 [-0.918, 1.397] | 35.4% | 0.037 [-1.050, 1.262] | EXPLORATORY |
| 720m | 20 | short | 370 | 168 | 4.8% | 33.9% [26.6%, 41.5%] | 63.1% | 3.0% | 36.3% | -0.174 [-1.112, 0.733] | 36.3% | -0.374 [-1.275, 0.574] | EXPLORATORY |
| 720m | 20 | both | 885 | 380 | 4.8% | 32.4% [27.5%, 37.3%] | 62.9% | 4.7% | 35.8% | 0.056 [-0.717, 0.850] | 35.8% | -0.144 [-0.895, 0.654] | EXPLORATORY |
| 1440m | 10 | long | 228 | 141 | 4.2% | 29.1% [20.9%, 37.6%] | 52.5% | 18.4% | 42.6% | 0.657 [-0.856, 2.261] | 41.8% | 0.457 [-0.994, 2.112] | EXPLORATORY |
| 1440m | 10 | short | 165 | 101 | 4.2% | 24.8% [14.9%, 35.6%] | 56.4% | 18.8% | 36.6% | 0.178 [-1.488, 1.925] | 36.6% | -0.022 [-1.783, 1.757] | EXPLORATORY |
| 1440m | 10 | both | 393 | 242 | 4.2% | 27.3% [20.6%, 34.2%] | 54.1% | 18.6% | 40.1% | 0.458 [-0.679, 1.649] | 39.7% | 0.258 [-0.883, 1.388] | EXPLORATORY |
| 1440m | 20 | long | 228 | 98 | 4.2% | 34.7% [24.3%, 45.1%] | 62.2% | 3.1% | 35.7% | -0.108 [-2.084, 1.868] | 35.7% | -0.308 [-2.217, 1.590] | EXPLORATORY |
| 1440m | 20 | short | 162 | 75 | 4.2% | 28.0% [17.6%, 38.9%] | 65.3% | 6.7% | 30.7% | -0.211 [-2.122, 1.717] | 30.7% | -0.411 [-2.219, 1.649] | EXPLORATORY |
| 1440m | 20 | both | 390 | 173 | 4.2% | 31.8% [24.3%, 39.3%] | 63.6% | 4.6% | 33.5% | -0.152 [-1.473, 1.227] | 33.5% | -0.352 [-1.672, 0.998] | EXPLORATORY |

## Availability and limits

| Symbol | TF | Complete bars | Direction signals | Availability |
|---|---:|---:|---:|---|
| BNBUSDT | 1m | 3359039 | 149653 | OK |
| BNBUSDT | 3m | 1119679 | 54860 | OK |
| BNBUSDT | 5m | 671807 | 32680 | OK |
| BNBUSDT | 10m | 335903 | 16923 | OK |
| BNBUSDT | 15m | 223935 | 11276 | OK |
| BNBUSDT | 30m | 111967 | 5775 | OK |
| BNBUSDT | 60m | 55983 | 3004 | OK |
| BNBUSDT | 120m | 27991 | 1459 | OK |
| BNBUSDT | 240m | 13995 | 669 | OK |
| BNBUSDT | 360m | 9330 | 422 | OK |
| BNBUSDT | 480m | 6997 | 329 | OK |
| BNBUSDT | 720m | 4665 | 238 | OK |
| BNBUSDT | 1440m | 2332 | 113 | OK |
| BTCUSDT | 1m | 3417120 | 160417 | OK |
| BTCUSDT | 3m | 1139040 | 59244 | OK |
| BTCUSDT | 5m | 683424 | 36258 | OK |
| BTCUSDT | 10m | 341712 | 18373 | OK |
| BTCUSDT | 15m | 227808 | 12412 | OK |
| BTCUSDT | 30m | 113904 | 6057 | OK |
| BTCUSDT | 60m | 56952 | 2904 | OK |
| BTCUSDT | 120m | 28476 | 1392 | OK |
| BTCUSDT | 240m | 14238 | 655 | OK |
| BTCUSDT | 360m | 9492 | 441 | OK |
| BTCUSDT | 480m | 7119 | 296 | OK |
| BTCUSDT | 720m | 4746 | 218 | OK |
| BTCUSDT | 1440m | 2373 | 90 | OK |
| DOGEUSDT | 1m | 3141540 | 138353 | OK |
| DOGEUSDT | 3m | 1047180 | 50991 | OK |
| DOGEUSDT | 5m | 628308 | 31664 | OK |
| DOGEUSDT | 10m | 314154 | 16518 | OK |
| DOGEUSDT | 15m | 209436 | 11083 | OK |
| DOGEUSDT | 30m | 104718 | 5401 | OK |
| DOGEUSDT | 60m | 52359 | 2622 | OK |
| DOGEUSDT | 120m | 26179 | 1387 | OK |
| DOGEUSDT | 240m | 13089 | 665 | OK |
| DOGEUSDT | 360m | 8726 | 423 | OK |
| DOGEUSDT | 480m | 6544 | 299 | OK |
| DOGEUSDT | 720m | 4363 | 220 | OK |
| DOGEUSDT | 1440m | 2181 | 88 | OK |
| ETHUSDT | 1m | 3417120 | 163156 | OK |
| ETHUSDT | 3m | 1139040 | 59217 | OK |
| ETHUSDT | 5m | 683424 | 36460 | OK |
| ETHUSDT | 10m | 341712 | 18379 | OK |
| ETHUSDT | 15m | 227808 | 12115 | OK |
| ETHUSDT | 30m | 113904 | 5883 | OK |
| ETHUSDT | 60m | 56952 | 2898 | OK |
| ETHUSDT | 120m | 28476 | 1335 | OK |
| ETHUSDT | 240m | 14238 | 695 | OK |
| ETHUSDT | 360m | 9492 | 453 | OK |
| ETHUSDT | 480m | 7119 | 335 | OK |
| ETHUSDT | 720m | 4746 | 213 | OK |
| ETHUSDT | 1440m | 2373 | 102 | OK |

- “Direction signals” counts raw candidates before entry-path availability and non-overlap selection. Coverage denominator is pooled complete bars across the four symbols.
- Cross-timeframe events are not deduplicated. The daily and long TF cells may be weakly supported because EMA200 requires a long warm-up and the local archive has finite history.
- Directional return accuracy, M4 calibration, leverage-adjusted PnL, liquidation risk, and generalization beyond this dev slice are not established.
- This is one uncalibrated hypothesis evaluation, not a sealed test. Do not treat the best-looking cell as selected evidence.
