# Group B third-pass re-evaluation

Final tags follow `verify2/SCENARIOS.md`. Frozen settings are used for B1, B2, B5, and B6. B3/B4 use the extended grid for diagnostic selection only.

| Candidate | B1 | B2 | B3 | B4 | B5 | B6 | Final tag |
|---|---|---|---|---|---|---|---|
| `jesse_simple_bollinger` | FAIL | PASS | PASS | PASS | PASS | PASS | **DOWNGRADED(B1)** |
| `btc-max10-nyse-close` | PASS | PASS | PASS | PASS | PASS | N/A | **PASS_ALL** |
| `btc-macd-15-41-12` | FAIL | PASS | PASS | PASS | PASS | N/A | **DOWNGRADED(B1)** |
| `turtle-system-2` | FAIL | PASS | PASS | PASS | PASS | N/A | **DOWNGRADED(B1)** |
| `btc-bollinger-37-16` | FAIL | FAIL | FAIL | PASS | PASS | N/A | **DOWNGRADED(B1,B2,B3)** |
| `btc-roc-36-9pct` | FAIL | FAIL | FAIL | PASS | PASS | N/A | **DOWNGRADED(B1,B2,B3)** |

## Scenario verdict evidence

| Candidate | B1 negative years / years; stress 2018, 2022 | B2 positive / available (strict / 5) | B3 selected TEST; edge-monotone | B4 WF / frozen | B5 years Sharpe <= BTC | B6 agreement; test-return signs |
|---|---|---|---|---:|---:|---|
| `jesse_simple_bollinger` | 1/10; 22.95, -2.43 | 3/5 (3/5) | 0.569285; no | 0.633674 | 0/0 | 99.983336%; 3.322564 vs 3.870871 |
| `btc-max10-nyse-close` | 1/10; 2.16, 0.49 | 4/5 (4/5) | 0.622072; no | 2.031992 | 0/0 | N/A |
| `btc-macd-15-41-12` | 1/10; 24.98, -6.23 | 4/5 (4/5) | 14.918206; no | 0.933872 | 3/10 | N/A |
| `turtle-system-2` | 4/10; -3.26, -2.11 | 3/5 (3/5) | 6.691885; no | 0.982407 | 3/10 | N/A |
| `btc-bollinger-37-16` | 2/10; 20.86, -10.37 | 2/5 (2/5) | 12.674108; yes | 0.92991 | 3/10 | N/A |
| `btc-roc-36-9pct` | 3/10; 44.79, -15.22 | 1/5 (1/5) | 10.095682; yes | 0.726515 | 3/10 | N/A |

## B1: calendar-year and stress-window returns

Harness trade returns are attributed by exit year and summed in percentage points. A year absent from the ledger had no closed trades.

| Candidate | 2017 | 2018 | 2019 | 2020 | 2021 | 2022 | 2023 | 2024 | 2025 | 2026 | 2018 stress | 2022 stress |
|---|---:|---:|---:|---:|---:|---:|---:|---:|---:|---:|---:|---:|
| `jesse_simple_bollinger` | 22.82 | 22.95 | 20.02 | 23.42 | 45.74 | -2.43 | 3.97 | 17.05 | 6.53 | 7.42 | 22.95 | -2.43 |
| `btc-max10-nyse-close` | 10.48 | 2.16 | 6.96 | 10.99 | 5.64 | 0.49 | 0.94 | 4.28 | 3.51 | -0.52 | 2.16 | 0.49 |
| `btc-macd-15-41-12` | 11.89 | 24.98 | 21.09 | 62.31 | 75.73 | -6.23 | 12.24 | 41.21 | 3.14 | 20.75 | 24.98 | -6.23 |
| `turtle-system-2` | -3.83 | -3.26 | 20.66 | 5.89 | 200.64 | -2.11 | -14.27 | 12.71 | 33.75 | 15.16 | -3.26 | -2.11 |
| `btc-bollinger-37-16` | 14.52 | 20.86 | 24.88 | 17.96 | 210.31 | -10.37 | 0.31 | 22.98 | 46.89 | -1.16 | 20.86 | -10.37 |
| `btc-roc-36-9pct` | -1.47 | 44.79 | 38.25 | 8.57 | 185.93 | -15.22 | -0.70 | 22.18 | 41.33 | 2.28 | 44.79 | -15.22 |

## B2: untouched symbols

Untouched symbols present in the cache directory are ADA, DOGE, LINK, LTC, and AVAX. The daily candidates use cached 1h bars resampled to daily. The result uses the available-symbols threshold (at least 60% positive); strict denominator is always five and missing symbols are explicitly flagged.

| Candidate | ADA | DOGE | LINK | LTC | AVAX | Available positive | Strict five positive |
|---|---:|---:|---:|---:|---:|---|---|
| `jesse_simple_bollinger` | -1.43 | 1.43 | 4.97 | -4.81 | 3.64 | 3/5 | 3/5 |
| `btc-max10-nyse-close` | 3.14 | 4.47 | 4.84 | -3.53 | 4.78 | 4/5 | 4/5 |
| `btc-macd-15-41-12` | -3.53 | 9.71 | 12.13 | 1.17 | 3.32 | 4/5 | 4/5 |
| `turtle-system-2` | -6.00 | 3.98 | 1.92 | -2.98 | 0.38 | 3/5 | 3/5 |
| `btc-bollinger-37-16` | -3.33 | 0.06 | 8.01 | -3.14 | -1.55 | 2/5 | 2/5 |
| `btc-roc-36-9pct` | -1.66 | -4.69 | 2.83 | -6.61 | -3.63 | 1/5 | 1/5 |

## B3/B4: parameter-surface summary

Full per-symbol, per-parameter TRAIN/TEST values are in [`results/b3_surfaces.csv`](results/b3_surfaces.csv); raw observations are in [`results/group_b.csv`](results/group_b.csv). Numeric axes extend two original-grid steps in both directions. B3 selects the pooled TRAIN maximum; inspect the full surface for edge and monotonicity by axis.

| Candidate | TRAIN maximum | TEST at selection | Selected parameters | Walk-forward / frozen TEST |
|---|---:|---:|---|---:|
| `jesse_simple_bollinger` | 24.444689 | 0.569285 | `{"bb_k": 2.0, "bb_len": 30}` | 0.633674 |
| `btc-max10-nyse-close` | 23.397009 | 0.622072 | `{"n": 6}` | 2.031992 |
| `btc-macd-15-41-12` | 30.131207 | 14.918206 | `{"fast": 21, "slow": 59}` | 0.933872 |
| `turtle-system-2` | 49.363905 | 6.691885 | `{"entry_n": 10, "exit_n": 50}` | 0.982407 |
| `btc-bollinger-37-16` | 62.74794 | 12.674108 | `{"k": 1.0, "n": 53}` | 0.92991 |
| `btc-roc-36-9pct` | 66.619795 | 10.095682 | `{"n": 36, "thr": 0.05}` | 0.726515 |

Per-axis boundary analysis uses the pooled TRAIN return at each grid value, summed across symbols and all other parameter combinations. `Edge` means the selected maximum is at either newly added boundary. `Monotone` means pooled TRAIN return improves at every adjacent step toward that boundary.

| Candidate | Axis | New grid min–max | Optimum | Edge | Monotone toward edge |
|---|---|---:|---:|---|---|
| `jesse_simple_bollinger` | `bb_k` | 0.5–3.5 | 2.5 | no | no |
| `jesse_simple_bollinger` | `bb_len` | 5–35 | 25 | no | no |
| `btc-max10-nyse-close` | `n` | 4–16 | 6 | no | no |
| `btc-macd-15-41-12` | `fast` | 6–24 | 21 | no | no |
| `btc-macd-15-41-12` | `slow` | 23–59 | 59 | yes | no |
| `turtle-system-2` | `entry_n` | 10–100 | 10 | yes | no |
| `turtle-system-2` | `exit_n` | 10–50 | 40 | no | no |
| `btc-bollinger-37-16` | `k` | 1–2.2 | 1 | yes | yes |
| `btc-bollinger-37-16` | `n` | 14–61 | 53 | no | no |
| `btc-roc-36-9pct` | `n` | 18–54 | 36 | no | no |
| `btc-roc-36-9pct` | `thr` | 0.03–0.15 | 0.03 | yes | yes |

## B5: daily basket versus buy-and-hold

Basket daily return is equal-weighted across the four daily strategies; each strategy is equal-weighted across available symbols. Returns are marked to market using harness trade entry/exit intervals. Sharpe is annualized with √365. Failure is basket Sharpe less than or equal to BTC buy-and-hold Sharpe in more than half the years.

| Candidate | Year | Basket return % | Basket Sharpe | BTC B&H Sharpe | 5-coin B&H Sharpe |
|---|---:|---:|---:|---:|---:|
| `btc-macd-15-41-12` | 2017 | 108.034959 | 4.051891 | 3.378436 | 4.086756 |
| `btc-macd-15-41-12` | 2018 | 18.286414 | 0.620919 | -1.154198 | -0.373552 |
| `btc-macd-15-41-12` | 2019 | 37.703248 | 1.095475 | 1.307822 | 0.771438 |
| `btc-macd-15-41-12` | 2020 | 145.974581 | 2.011838 | 2.252635 | 1.843896 |
| `btc-macd-15-41-12` | 2021 | 292.922911 | 2.435697 | 0.981426 | 2.239973 |
| `btc-macd-15-41-12` | 2022 | -17.152552 | -0.494326 | -1.28792 | -0.898507 |
| `btc-macd-15-41-12` | 2023 | 19.874972 | 0.88036 | 2.349069 | 1.670475 |
| `btc-macd-15-41-12` | 2024 | 67.972657 | 1.769975 | 1.756296 | 1.952385 |
| `btc-macd-15-41-12` | 2025 | 21.001536 | 0.958142 | 0.050741 | 0.330395 |
| `btc-macd-15-41-12` | 2026 | 23.073491 | 1.076845 | -0.645495 | -0.780695 |
| `turtle-system-2` | 2017 | 108.034959 | 4.051891 | 3.378436 | 4.086756 |
| `turtle-system-2` | 2018 | 18.286414 | 0.620919 | -1.154198 | -0.373552 |
| `turtle-system-2` | 2019 | 37.703248 | 1.095475 | 1.307822 | 0.771438 |
| `turtle-system-2` | 2020 | 145.974581 | 2.011838 | 2.252635 | 1.843896 |
| `turtle-system-2` | 2021 | 292.922911 | 2.435697 | 0.981426 | 2.239973 |
| `turtle-system-2` | 2022 | -17.152552 | -0.494326 | -1.28792 | -0.898507 |
| `turtle-system-2` | 2023 | 19.874972 | 0.88036 | 2.349069 | 1.670475 |
| `turtle-system-2` | 2024 | 67.972657 | 1.769975 | 1.756296 | 1.952385 |
| `turtle-system-2` | 2025 | 21.001536 | 0.958142 | 0.050741 | 0.330395 |
| `turtle-system-2` | 2026 | 23.073491 | 1.076845 | -0.645495 | -0.780695 |
| `btc-bollinger-37-16` | 2017 | 108.034959 | 4.051891 | 3.378436 | 4.086756 |
| `btc-bollinger-37-16` | 2018 | 18.286414 | 0.620919 | -1.154198 | -0.373552 |
| `btc-bollinger-37-16` | 2019 | 37.703248 | 1.095475 | 1.307822 | 0.771438 |
| `btc-bollinger-37-16` | 2020 | 145.974581 | 2.011838 | 2.252635 | 1.843896 |
| `btc-bollinger-37-16` | 2021 | 292.922911 | 2.435697 | 0.981426 | 2.239973 |
| `btc-bollinger-37-16` | 2022 | -17.152552 | -0.494326 | -1.28792 | -0.898507 |
| `btc-bollinger-37-16` | 2023 | 19.874972 | 0.88036 | 2.349069 | 1.670475 |
| `btc-bollinger-37-16` | 2024 | 67.972657 | 1.769975 | 1.756296 | 1.952385 |
| `btc-bollinger-37-16` | 2025 | 21.001536 | 0.958142 | 0.050741 | 0.330395 |
| `btc-bollinger-37-16` | 2026 | 23.073491 | 1.076845 | -0.645495 | -0.780695 |
| `btc-roc-36-9pct` | 2017 | 108.034959 | 4.051891 | 3.378436 | 4.086756 |
| `btc-roc-36-9pct` | 2018 | 18.286414 | 0.620919 | -1.154198 | -0.373552 |
| `btc-roc-36-9pct` | 2019 | 37.703248 | 1.095475 | 1.307822 | 0.771438 |
| `btc-roc-36-9pct` | 2020 | 145.974581 | 2.011838 | 2.252635 | 1.843896 |
| `btc-roc-36-9pct` | 2021 | 292.922911 | 2.435697 | 0.981426 | 2.239973 |
| `btc-roc-36-9pct` | 2022 | -17.152552 | -0.494326 | -1.28792 | -0.898507 |
| `btc-roc-36-9pct` | 2023 | 19.874972 | 0.88036 | 2.349069 | 1.670475 |
| `btc-roc-36-9pct` | 2024 | 67.972657 | 1.769975 | 1.756296 | 1.952385 |
| `btc-roc-36-9pct` | 2025 | 21.001536 | 0.958142 | 0.050741 | 0.330395 |
| `btc-roc-36-9pct` | 2026 | 23.073491 | 1.076845 | -0.645495 | -0.780695 |

## B6: Jesse source convention

Source files read: `/private/tmp/claude-501/-Users-user-CODE-Ochestration/ee6baff2-9664-4b9e-9a9e-5f263219aa7c/scratchpad/jesse_old/ichimoku_old.py`, `.../scratchpad/jesse_ex/SimpleBollinger/__init__.py`, and `/private/tmp/claude-501/-Users-user-CODE-Ochestration/ee6baff2-9664-4b9e-9a9e-5f263219aa7c/scratchpad/ichimoku_cloud.py`. Jesse-old uses `candles[:-(displacement-1)]`; default displacement 26 computes cloud from 25 bars earlier, including conversion/base windows ending at that earlier bar. Candle layout is `[ts, open, close, high, low, volume]`. Agreement is calculated over the full long 1h history and the chronological final 40% TEST window. Shift 0 is a reference.

| Window | Shift-26 vs shift-25 agreement | Shift-26 vs shift-0 agreement |
|---|---:|---:|
| Full long 1h | 99.983336% | 99.826571% |
| TEST | 99.969142% | 99.785534% |

TEST return under shift 26: 3.322564%; under shift 25: 3.870871%. Direct-port cloud max absolute error against vectorized shift 25: 0.0.

Jesse SimpleBollinger uses Bollinger defaults source=hl2, period=20, devup/devdn=2, SMA, and TA-Lib standard deviation ddof=0. `common.indicators.bollinger` is a separate local implementation; equivalence is not assumed. The current wrapper delegates to closed `jesse_rust`; its internal semantics remain unverifiable. A pytest directly ports Jesse-old and compares rolling 80-candle output with the shift-25 vectorized series.

## Data coverage and limitations

- B1 long data begins 2017-08 for BTC/ETH, 2017-11 for BNB, and 2018-05 for XRP. Long 15m data exists only for BTC and ETH.
- Cached rows after long-data endpoints are appended in memory only. Long parquet files are not modified.
- B2 flags the available-symbols rule when fewer than five symbols are evaluated; strict-five result remains shown separately.
- B3/B4 use expanded grids and are diagnostics, not updates to frozen settings. The full CSV records every per-symbol TRAIN/TEST point and the report states edge and monotonicity by axis.
- B5’s 5-coin benchmark is equal-weighted across symbols available on each date.
- No network access was used. `results/group_b.csv` contains observations and final tags.
