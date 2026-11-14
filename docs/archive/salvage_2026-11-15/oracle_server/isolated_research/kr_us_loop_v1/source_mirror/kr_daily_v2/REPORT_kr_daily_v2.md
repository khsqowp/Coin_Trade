# KR-daily-v2: full-universe Korean equities daily-bar research report

Generated 2026-11-06 00:04:17 UTC. Research only: no orders, no forward registration, and no strategy promotion beyond the registered IS-pick rule.

## Bottom line

**Overall pre-registered gate: FAIL. IS pick: `V6_XS_MOM_LOWVOL`.** The selection is mechanical (highest IS Sharpe among V1-V9); a failed gate means no strategy advances. OOS Sharpe is 0.380, versus B1 0.758 and B4 0.124; FULL DSR is 0.327 at N=17 and 0.076 at N=233. The post-hoc A3 random-portfolio results are diagnostic only and do not change this gate.

## 1. Registration, disclosure, and contamination

- Main protocol: `PREREG_kr_daily_v2.md`, written before v2 price data opened; A1 fixes the corporate-action/delisting repair rule; A2 merges market-transfer pairs and splits terminal delisting/re-listing spells.
- The owner disclosed prior exposure to KR-daily-v1 index history/results, a prior KR stock-rule study, and a large crypto strategy catalog. V2 OOS is new only for the specified cross-sectional rules; the market path is contaminated by prior observation.
- A3 is explicitly post-hoc, added because the main KR v2 registration omitted a random-portfolio null and per-trial p-value corrections that were used in US v2. It has selection count 0, is reported separately, and cannot override registered hypotheses or gates.
- QC/reporting fixes during execution: qc2.py failed because Addendum A2 market-transfer codes have duplicate listed/delisted rows; its status lookup now gives listed precedence. qc2.py only prints diagnostics, so this has no effect on backtest results. gate_report_v2.py also evaluated coverage against target before assigning it; the assignment was moved before use. The report also selects the newest QC stage log so it cites the successful rerun. These reporting fixes do not change engine calculations, methodology, or registered thresholds.
- No threshold, lookback, cost, universe rule, split, or gate was changed after registration. The only methodology addition is the separately labeled A3 diagnostic.

## 2. Coverage and data QC

- Universe target: 3,240 segmented instruments (2,588 listed + 652 terminally delisted). Fetch log has 3,240 unique instrument keys (2,588 listed-status records, 654 delisted-status records, 3 logged errors); data directory has 3,236 parquet files. Panel loaded by the engine: 3236 names, including 651 delisted histories.
- Fetch outcome: all target instruments logged before the deadline; no backfill is performed.
- A1 repair statistics from the strategy panel: {"names": 115, "events": 359, "factor_pctiles_5_50_95": [0.5, 1.315, 2.067], "examples": [["008080", [["2011-08-04", 2.0], ["2011-08-09", 0.5], ["2011-08-10", 2.0], ["2011-09-14", 0.5], ["2011-09-16", 2.0], ["2011-09-23", 0.5], ["2011-10-12", 2.0], ["2012-01-18", 0.5], ["2012-01-26", 2.0], ["2012-01-30", 0.5], ["2012-02-16", 2.0], ["2012-02-17", 0.5], ["2012-02-20", 2.0], ["2012-02-23", 0.5], ["2013-04-02", 0.0], ["2013-05-03", 0.0], ["2013-05-15", 0.0]]], ["041920", [["2013-10-01", 1.307], ["2013-12-24", 1.1845], ["2014-10-07", 0.8025]]], ["044990", [["2016-03-28", 1.4999]]], ["050540", [["2022-01-24", 0.3262]]], ["059120", [["2014-07-24", 0.7847]]], ["062580", [["2016-09-13", 1.3206]]], ["063840", [["2015-02-27", 0.7979], ["2015-04-08", 0.8212]]], ["064850", [["2013-12-11", 0.75], ["2013-12-23", 1.16], ["2014-01-20", 0.8193], ["2014-04-29", 0.8282], ["2014-05-20", 1.2825], ["2014-06-10", 0.8265], ["2014-09-05", 1.2398], ["2014-11-28", 1.2215]]], ["065160", [["2018-09-28", 0.0363]]], ["067770", [["2026-09-29", 0.6682]]], ["081200", [["2012-06-08", 0.8157], ["2013-04-09", 1.1573]]], ["082220", [["2014-05-22", 0.7463], ["2015-04-13", 0.7843]]], ["083600", [["2012-02-16", 1.1798]]], ["084440", [["2014-01-23", 0.7895], ["2014-01-28", 0.7917], ["2014-02-05", 0.7823], ["2014-02-07", 0.7906]]], ["084650", [["2014-12-16", 0.7559]]]]}
- QC stage output:
```text
[2026-11-05T23:20:48Z] attempt=1 command=qc2.py 
logged 3243 errors 3 zero-row 1
by status: {'delisted': 654, 'listed': 2589}
files 3236 names with limit-breaching non-gap jumps: 428
   ('052670', 1, '2026-02-09', 299.481)
   ('196490', 3, '2026-05-06', 29.0)
   ('101140', 1, '2024-11-13', 19.0)
   ('241820', 1, '2025-10-17', 19.0)
   ('001470', 1, '2026-09-01', 15.772)
   ('054180', 1, '2025-08-01', 14.0)
   ('352770', 1, '2025-04-28', 14.0)
   ('043220', 1, '2025-12-09', 9.0)
   ('074610', 1, '2025-12-29', 9.0)
   ('145210', 1, '2026-07-24', 9.0)
   ('046070', 4, '2026-09-04', 7.006)
   ('950010', 5, '2015-10-27', 5.522)
   ('060910', 5, '2017-02-15', 4.543)
   ('047600', 4, '2011-08-31', 4.065)
   ('009310', 1, '2026-05-11', 4.005)
   ('011000', 1, '2026-07-21', 4.0)
   ('106080', 1, '2026-04-16', 4.0)
   ('222810', 3, '2025-03-04', 4.0)
   ('033180', 3, '2025-05-16', 3.005)
   ('041590', 1, '2025-05-23', 2.004)
   ('019590', 2, '2025-04-14', 2.002)
   ('043090', 3, '2026-04-30', 2.0)
   ('111610', 4, '2016-01-15', 1.847)
   ('008020', 1, '2016-05-11', 1.537)
   ('446600', 4, '2025-02-14', 1.5)
delisted files 648 median rows 1233
```

## 3. Rules, windows, and execution

The nine fixed V-trials, point-in-time U500/eligibility rules, B1 (KODEX 200 buy-and-hold), B4 (monthly equal-weight U500), B5 (monthly equal-weight all eligible), execution deferrals, slippage tiers, 0.015% commission, 0.20% sell tax, and cash handling follow the main registration and A1/A2. IS is 2012-06-01 through 2019-12-31; OOS is 2020-01-01 through 2026-11-03; FULL is the registered evaluation window.

## 4. IS/OOS/FULL results

| Strategy | IS Sharpe | IS return | IS MDD | OOS Sharpe | OOS return | OOS MDD | FULL Sharpe | FULL CAGR | FULL MDD | DSR N17 | DSR N233 | DSR N1000 | round trips | cost/year | top-10 P&L share |
|---|---:|---:|---:|---:|---:|---:|---:|---:|---:|---:|---:|---:|---:|---:|---:|
| V1_XS_MOM12_1 | -0.524 | -81.3% | 86.9% | -0.246 | -75.3% | 88.8% | -0.367 | -19.7% | 97.5% | 0.001 | 0.000 | 0.000 | 1243 | 1.0% | n/a |
| V2_XS_MOM12_1_MF | -0.166 | -38.3% | 62.8% | -0.126 | -56.2% | 77.2% | -0.138 | -8.9% | 86.8% | 0.010 | 0.000 | 0.000 | 943 | 1.4% | n/a |
| V3_XS_MOM60_REPL | -0.721 | -91.4% | 93.4% | -0.819 | -94.0% | 96.6% | -0.769 | -31.3% | 99.6% | 0.000 | 0.000 | 0.000 | 547 | 1.1% | n/a |
| V4_XS_52WH | -0.158 | -37.3% | 66.1% | 0.119 | -12.5% | 61.4% | 0.002 | -4.2% | 76.2% | 0.034 | 0.002 | 0.001 | 2880 | 5.1% | n/a |
| V5_XS_LOWVOL | 0.264 | 18.2% | 29.5% | 0.444 | 51.5% | 36.8% | 0.361 | 4.2% | 52.2% | 0.318 | 0.073 | 0.029 | 434 | 1.1% | 83.7% |
| V6_XS_MOM_LOWVOL | 0.384 | 43.2% | 41.5% | 0.380 | 56.2% | 42.3% | 0.368 | 5.9% | 60.5% | 0.327 | 0.076 | 0.031 | 1234 | 4.0% | 145.3% |
| V7_TS_DONCHIAN_70_25 | -0.969 | -78.0% | 80.3% | 0.070 | -19.6% | 69.5% | -0.323 | -11.6% | 84.9% | 0.001 | 0.000 | 0.000 | 1840 | 1.1% | n/a |
| V8_EV_VOLSPIKE20 | -0.650 | -69.5% | 74.1% | -0.719 | -83.6% | 87.3% | -0.677 | -19.2% | 96.2% | 0.000 | 0.000 | 0.000 | 3495 | 2.8% | n/a |
| V9_XS_STREV_W | -0.996 | -91.6% | 92.6% | -0.837 | -88.1% | 91.9% | -0.916 | -28.0% | 99.2% | 0.000 | 0.000 | 0.000 | 13430 | 4.8% | n/a |
| B1_BH_069500 | 0.387 | 35.9% | 23.1% | 0.758 | 244.4% | 41.9% | 0.590 | 11.6% | 41.9% | 0.651 | 0.272 | 0.146 | — | n/a | n/a |
| B4_EW_U500 | -0.167 | -27.7% | 50.1% | 0.124 | -3.4% | 49.2% | 0.006 | -2.5% | 66.6% | 0.036 | 0.003 | 0.001 | 8731 | 1.0% | n/a |
| B5_EW_ALL_ELIG | -0.037 | -14.6% | 44.0% | 0.147 | 2.0% | 49.7% | 0.069 | -1.0% | 62.5% | 0.059 | 0.005 | 0.001 | 11385 | 1.3% | n/a |

**IS pick:** `V6_XS_MOM_LOWVOL` with IS Sharpe 0.384. Its OOS excess-return 90% block-bootstrap intervals are B1 [-0.2631, -0.0026] annualized and B4 [-0.0625, 0.1992] annualized.

## 5. Regime-window breakdown

| Strategy | Window | Type | Dates | Strategy return | B1 return | Strategy Sharpe | B1 Sharpe |
|---|---|---|---|---:|---:|---:|---:|
| V1_XS_MOM12_1 | chop_IS_boxpi_2012_2016 | chop | 2012-06-01..2016-10-31 | -49.6% | 9.6% | -0.331 | 0.228 |
| V1_XS_MOM12_1 | bull_IS_2016_11_2018_01 | bull | 2016-11-01..2018-01-29 | -15.6% | 36.4% | -0.239 | 2.568 |
| V1_XS_MOM12_1 | bear_IS_2018_2019 | bear | 2018-01-30..2019-08-07 | -54.9% | -23.1% | -1.355 | -1.155 |
| V1_XS_MOM12_1 | bear_OOS_covid_2020 | bear | 2020-01-23..2020-03-19 | -44.0% | -34.6% | -6.292 | -7.766 |
| V1_XS_MOM12_1 | bull_OOS_2020_2021 | bull | 2020-03-20..2021-07-06 | 37.9% | 125.5% | 0.824 | 2.712 |
| V1_XS_MOM12_1 | bear_OOS_2021_2022 | bear | 2021-07-07..2022-09-30 | -67.7% | -34.3% | -2.672 | -1.907 |
| V1_XS_MOM12_1 | chop_OOS_2023_2024 | chop | 2023-01-02..2024-06-28 | 39.7% | 35.0% | 0.766 | 1.358 |
| V1_XS_MOM12_1 | bear_OOS_2024_2025 | bear | 2024-07-12..2025-04-09 | -34.1% | -21.6% | -1.199 | -1.376 |
| V1_XS_MOM12_1 | bull_OOS_2025_2026 | bull | 2025-04-10..2026-02-26 | 78.1% | 212.6% | 2.262 | 5.285 |
| V1_XS_MOM12_1 | bear_OOS_2026_03 | bear | 2026-02-27..2026-03-31 | -15.1% | -20.6% | -1.398 | -2.938 |
| V1_XS_MOM12_1 | bull_OOS_2026_04_06 | bull | 2026-04-01..2026-06-22 | 8.5% | 97.5% | 0.906 | 5.714 |
| V1_XS_MOM12_1 | bear_OOS_2026_07 | bear | 2026-06-23..2026-07-30 | -53.8% | -40.8% | -6.364 | -5.365 |
| V1_XS_MOM12_1 | bear_OOS_2026_10_ongoing | bear | 2026-09-24..2026-10-26 | -18.7% | -24.0% | -3.928 | -7.510 |
| V2_XS_MOM12_1_MF | chop_IS_boxpi_2012_2016 | chop | 2012-06-01..2016-10-31 | -9.3% | 9.6% | 0.001 | 0.228 |
| V2_XS_MOM12_1_MF | bull_IS_2016_11_2018_01 | bull | 2016-11-01..2018-01-29 | -15.7% | 36.4% | -0.244 | 2.568 |
| V2_XS_MOM12_1_MF | bear_IS_2018_2019 | bear | 2018-01-30..2019-08-07 | -14.7% | -23.1% | -0.554 | -1.155 |
| V2_XS_MOM12_1_MF | bear_OOS_covid_2020 | bear | 2020-01-23..2020-03-19 | -19.0% | -34.6% | -3.924 | -7.766 |
| V2_XS_MOM12_1_MF | bull_OOS_2020_2021 | bull | 2020-03-20..2021-07-06 | -18.1% | 125.5% | -0.253 | 2.712 |
| V2_XS_MOM12_1_MF | bear_OOS_2021_2022 | bear | 2021-07-07..2022-09-30 | -14.0% | -34.3% | -0.957 | -1.907 |
| V2_XS_MOM12_1_MF | chop_OOS_2023_2024 | chop | 2023-01-02..2024-06-28 | -14.3% | 35.0% | -0.104 | 1.358 |
| V2_XS_MOM12_1_MF | bear_OOS_2024_2025 | bear | 2024-07-12..2025-04-09 | -14.4% | -21.6% | -0.584 | -1.376 |
| V2_XS_MOM12_1_MF | bull_OOS_2025_2026 | bull | 2025-04-10..2026-02-26 | 63.1% | 212.6% | 2.004 | 5.285 |
| V2_XS_MOM12_1_MF | bear_OOS_2026_03 | bear | 2026-02-27..2026-03-31 | -15.1% | -20.6% | -1.403 | -2.938 |
| V2_XS_MOM12_1_MF | bull_OOS_2026_04_06 | bull | 2026-04-01..2026-06-22 | 8.3% | 97.5% | 0.894 | 5.714 |
| V2_XS_MOM12_1_MF | bear_OOS_2026_07 | bear | 2026-06-23..2026-07-30 | -53.8% | -40.8% | -6.359 | -5.365 |
| V2_XS_MOM12_1_MF | bear_OOS_2026_10_ongoing | bear | 2026-09-24..2026-10-26 | -18.7% | -24.0% | -3.934 | -7.510 |
| V3_XS_MOM60_REPL | chop_IS_boxpi_2012_2016 | chop | 2012-06-01..2016-10-31 | -81.2% | 9.6% | -0.737 | 0.228 |
| V3_XS_MOM60_REPL | bull_IS_2016_11_2018_01 | bull | 2016-11-01..2018-01-29 | 2.4% | 36.4% | 0.214 | 2.568 |
| V3_XS_MOM60_REPL | bear_IS_2018_2019 | bear | 2018-01-30..2019-08-07 | -55.2% | -23.1% | -1.503 | -1.155 |
| V3_XS_MOM60_REPL | bear_OOS_covid_2020 | bear | 2020-01-23..2020-03-19 | -7.4% | -34.6% | -3.525 | -7.766 |
| V3_XS_MOM60_REPL | bull_OOS_2020_2021 | bull | 2020-03-20..2021-07-06 | 1.5% | 125.5% | 0.297 | 2.712 |
| V3_XS_MOM60_REPL | bear_OOS_2021_2022 | bear | 2021-07-07..2022-09-30 | -42.3% | -34.3% | -1.949 | -1.907 |
| V3_XS_MOM60_REPL | chop_OOS_2023_2024 | chop | 2023-01-02..2024-06-28 | -50.0% | 35.0% | -0.968 | 1.358 |
| V3_XS_MOM60_REPL | bear_OOS_2024_2025 | bear | 2024-07-12..2025-04-09 | -24.7% | -21.6% | -2.019 | -1.376 |
| V3_XS_MOM60_REPL | bull_OOS_2025_2026 | bull | 2025-04-10..2026-02-26 | -62.3% | 212.6% | -2.071 | 5.285 |
| V3_XS_MOM60_REPL | bear_OOS_2026_03 | bear | 2026-02-27..2026-03-31 | -3.9% | -20.6% | 0.107 | -2.938 |
| V3_XS_MOM60_REPL | bull_OOS_2026_04_06 | bull | 2026-04-01..2026-06-22 | -10.8% | 97.5% | -0.448 | 5.714 |
| V3_XS_MOM60_REPL | bear_OOS_2026_07 | bear | 2026-06-23..2026-07-30 | 0.0% | -40.8% | 0.000 | -5.365 |
| V3_XS_MOM60_REPL | bear_OOS_2026_10_ongoing | bear | 2026-09-24..2026-10-26 | 0.0% | -24.0% | 0.000 | -7.510 |
| V4_XS_52WH | chop_IS_boxpi_2012_2016 | chop | 2012-06-01..2016-10-31 | 15.9% | 9.6% | 0.265 | 0.228 |
| V4_XS_52WH | bull_IS_2016_11_2018_01 | bull | 2016-11-01..2018-01-29 | -14.1% | 36.4% | -0.477 | 2.568 |
| V4_XS_52WH | bear_IS_2018_2019 | bear | 2018-01-30..2019-08-07 | -36.8% | -23.1% | -1.048 | -1.155 |
| V4_XS_52WH | bear_OOS_covid_2020 | bear | 2020-01-23..2020-03-19 | -37.2% | -34.6% | -8.296 | -7.766 |
| V4_XS_52WH | bull_OOS_2020_2021 | bull | 2020-03-20..2021-07-06 | 67.0% | 125.5% | 1.335 | 2.712 |
| V4_XS_52WH | bear_OOS_2021_2022 | bear | 2021-07-07..2022-09-30 | -33.7% | -34.3% | -1.007 | -1.907 |
| V4_XS_52WH | chop_OOS_2023_2024 | chop | 2023-01-02..2024-06-28 | 55.8% | 35.0% | 1.256 | 1.358 |
| V4_XS_52WH | bear_OOS_2024_2025 | bear | 2024-07-12..2025-04-09 | -23.5% | -21.6% | -1.244 | -1.376 |
| V4_XS_52WH | bull_OOS_2025_2026 | bull | 2025-04-10..2026-02-26 | 147.0% | 212.6% | 3.625 | 5.285 |
| V4_XS_52WH | bear_OOS_2026_03 | bear | 2026-02-27..2026-03-31 | -17.5% | -20.6% | -1.934 | -2.938 |
| V4_XS_52WH | bull_OOS_2026_04_06 | bull | 2026-04-01..2026-06-22 | 2.7% | 97.5% | 0.494 | 5.714 |
| V4_XS_52WH | bear_OOS_2026_07 | bear | 2026-06-23..2026-07-30 | -46.8% | -40.8% | -6.683 | -5.365 |
| V4_XS_52WH | bear_OOS_2026_10_ongoing | bear | 2026-09-24..2026-10-26 | -15.1% | -24.0% | -4.026 | -7.510 |
| V5_XS_LOWVOL | chop_IS_boxpi_2012_2016 | chop | 2012-06-01..2016-10-31 | 30.1% | 9.6% | 0.626 | 0.228 |
| V5_XS_LOWVOL | bull_IS_2016_11_2018_01 | bull | 2016-11-01..2018-01-29 | 15.3% | 36.4% | 1.246 | 2.568 |
| V5_XS_LOWVOL | bear_IS_2018_2019 | bear | 2018-01-30..2019-08-07 | -25.3% | -23.1% | -1.620 | -1.155 |
| V5_XS_LOWVOL | bear_OOS_covid_2020 | bear | 2020-01-23..2020-03-19 | -34.8% | -34.6% | -9.498 | -7.766 |
| V5_XS_LOWVOL | bull_OOS_2020_2021 | bull | 2020-03-20..2021-07-06 | 82.2% | 125.5% | 2.524 | 2.712 |
| V5_XS_LOWVOL | bear_OOS_2021_2022 | bear | 2021-07-07..2022-09-30 | -15.8% | -34.3% | -0.988 | -1.907 |
| V5_XS_LOWVOL | chop_OOS_2023_2024 | chop | 2023-01-02..2024-06-28 | 6.0% | 35.0% | 0.350 | 1.358 |
| V5_XS_LOWVOL | bear_OOS_2024_2025 | bear | 2024-07-12..2025-04-09 | -1.3% | -21.6% | -0.032 | -1.376 |
| V5_XS_LOWVOL | bull_OOS_2025_2026 | bull | 2025-04-10..2026-02-26 | 54.6% | 212.6% | 3.172 | 5.285 |
| V5_XS_LOWVOL | bear_OOS_2026_03 | bear | 2026-02-27..2026-03-31 | -11.2% | -20.6% | -2.896 | -2.938 |
| V5_XS_LOWVOL | bull_OOS_2026_04_06 | bull | 2026-04-01..2026-06-22 | -3.4% | 97.5% | -0.613 | 5.714 |
| V5_XS_LOWVOL | bear_OOS_2026_07 | bear | 2026-06-23..2026-07-30 | 4.4% | -40.8% | 1.899 | -5.365 |
| V5_XS_LOWVOL | bear_OOS_2026_10_ongoing | bear | 2026-09-24..2026-10-26 | -4.5% | -24.0% | -3.963 | -7.510 |
| V6_XS_MOM_LOWVOL | chop_IS_boxpi_2012_2016 | chop | 2012-06-01..2016-10-31 | 68.1% | 9.6% | 0.817 | 0.228 |
| V6_XS_MOM_LOWVOL | bull_IS_2016_11_2018_01 | bull | 2016-11-01..2018-01-29 | 20.6% | 36.4% | 1.351 | 2.568 |
| V6_XS_MOM_LOWVOL | bear_IS_2018_2019 | bear | 2018-01-30..2019-08-07 | -31.7% | -23.1% | -1.315 | -1.155 |
| V6_XS_MOM_LOWVOL | bear_OOS_covid_2020 | bear | 2020-01-23..2020-03-19 | -36.1% | -34.6% | -7.303 | -7.766 |
| V6_XS_MOM_LOWVOL | bull_OOS_2020_2021 | bull | 2020-03-20..2021-07-06 | 147.5% | 125.5% | 2.855 | 2.712 |
| V6_XS_MOM_LOWVOL | bear_OOS_2021_2022 | bear | 2021-07-07..2022-09-30 | -22.7% | -34.3% | -1.059 | -1.907 |
| V6_XS_MOM_LOWVOL | chop_OOS_2023_2024 | chop | 2023-01-02..2024-06-28 | -13.1% | 35.0% | -0.347 | 1.358 |
| V6_XS_MOM_LOWVOL | bear_OOS_2024_2025 | bear | 2024-07-12..2025-04-09 | -11.4% | -21.6% | -0.676 | -1.376 |
| V6_XS_MOM_LOWVOL | bull_OOS_2025_2026 | bull | 2025-04-10..2026-02-26 | 91.2% | 212.6% | 3.447 | 5.285 |
| V6_XS_MOM_LOWVOL | bear_OOS_2026_03 | bear | 2026-02-27..2026-03-31 | -20.8% | -20.6% | -3.276 | -2.938 |
| V6_XS_MOM_LOWVOL | bull_OOS_2026_04_06 | bull | 2026-04-01..2026-06-22 | 66.6% | 97.5% | 4.816 | 5.714 |
| V6_XS_MOM_LOWVOL | bear_OOS_2026_07 | bear | 2026-06-23..2026-07-30 | -40.7% | -40.8% | -5.975 | -5.365 |
| V6_XS_MOM_LOWVOL | bear_OOS_2026_10_ongoing | bear | 2026-09-24..2026-10-26 | -13.9% | -24.0% | -7.417 | -7.510 |
| V7_TS_DONCHIAN_70_25 | chop_IS_boxpi_2012_2016 | chop | 2012-06-01..2016-10-31 | -61.4% | 9.6% | -1.074 | 0.228 |
| V7_TS_DONCHIAN_70_25 | bull_IS_2016_11_2018_01 | bull | 2016-11-01..2018-01-29 | 8.8% | 36.4% | 0.514 | 2.568 |
| V7_TS_DONCHIAN_70_25 | bear_IS_2018_2019 | bear | 2018-01-30..2019-08-07 | -46.2% | -23.1% | -1.726 | -1.155 |
| V7_TS_DONCHIAN_70_25 | bear_OOS_covid_2020 | bear | 2020-01-23..2020-03-19 | -20.8% | -34.6% | -4.317 | -7.766 |
| V7_TS_DONCHIAN_70_25 | bull_OOS_2020_2021 | bull | 2020-03-20..2021-07-06 | 158.6% | 125.5% | 2.150 | 2.712 |
| V7_TS_DONCHIAN_70_25 | bear_OOS_2021_2022 | bear | 2021-07-07..2022-09-30 | -59.7% | -34.3% | -2.604 | -1.907 |
| V7_TS_DONCHIAN_70_25 | chop_OOS_2023_2024 | chop | 2023-01-02..2024-06-28 | 16.0% | 35.0% | 0.538 | 1.358 |
| V7_TS_DONCHIAN_70_25 | bear_OOS_2024_2025 | bear | 2024-07-12..2025-04-09 | -26.4% | -21.6% | -1.369 | -1.376 |
| V7_TS_DONCHIAN_70_25 | bull_OOS_2025_2026 | bull | 2025-04-10..2026-02-26 | 92.7% | 212.6% | 2.736 | 5.285 |
| V7_TS_DONCHIAN_70_25 | bear_OOS_2026_03 | bear | 2026-02-27..2026-03-31 | -25.5% | -20.6% | -3.496 | -2.938 |
| V7_TS_DONCHIAN_70_25 | bull_OOS_2026_04_06 | bull | 2026-04-01..2026-06-22 | 50.5% | 97.5% | 3.732 | 5.714 |
| V7_TS_DONCHIAN_70_25 | bear_OOS_2026_07 | bear | 2026-06-23..2026-07-30 | -39.4% | -40.8% | -7.133 | -5.365 |
| V7_TS_DONCHIAN_70_25 | bear_OOS_2026_10_ongoing | bear | 2026-09-24..2026-10-26 | -20.7% | -24.0% | -7.442 | -7.510 |
| V8_EV_VOLSPIKE20 | chop_IS_boxpi_2012_2016 | chop | 2012-06-01..2016-10-31 | -54.5% | 9.6% | -0.788 | 0.228 |
| V8_EV_VOLSPIKE20 | bull_IS_2016_11_2018_01 | bull | 2016-11-01..2018-01-29 | -13.1% | 36.4% | -0.535 | 2.568 |
| V8_EV_VOLSPIKE20 | bear_IS_2018_2019 | bear | 2018-01-30..2019-08-07 | -19.1% | -23.1% | -0.440 | -1.155 |
| V8_EV_VOLSPIKE20 | bear_OOS_covid_2020 | bear | 2020-01-23..2020-03-19 | -33.6% | -34.6% | -6.738 | -7.766 |
| V8_EV_VOLSPIKE20 | bull_OOS_2020_2021 | bull | 2020-03-20..2021-07-06 | 46.3% | 125.5% | 1.223 | 2.712 |
| V8_EV_VOLSPIKE20 | bear_OOS_2021_2022 | bear | 2021-07-07..2022-09-30 | -57.9% | -34.3% | -2.881 | -1.907 |
| V8_EV_VOLSPIKE20 | chop_OOS_2023_2024 | chop | 2023-01-02..2024-06-28 | -41.6% | 35.0% | -1.450 | 1.358 |
| V8_EV_VOLSPIKE20 | bear_OOS_2024_2025 | bear | 2024-07-12..2025-04-09 | -30.4% | -21.6% | -1.384 | -1.376 |
| V8_EV_VOLSPIKE20 | bull_OOS_2025_2026 | bull | 2025-04-10..2026-02-26 | 39.5% | 212.6% | 1.510 | 5.285 |
| V8_EV_VOLSPIKE20 | bear_OOS_2026_03 | bear | 2026-02-27..2026-03-31 | -17.3% | -20.6% | -2.193 | -2.938 |
| V8_EV_VOLSPIKE20 | bull_OOS_2026_04_06 | bull | 2026-04-01..2026-06-22 | 4.8% | 97.5% | 0.719 | 5.714 |
| V8_EV_VOLSPIKE20 | bear_OOS_2026_07 | bear | 2026-06-23..2026-07-30 | -32.8% | -40.8% | -5.303 | -5.365 |
| V8_EV_VOLSPIKE20 | bear_OOS_2026_10_ongoing | bear | 2026-09-24..2026-10-26 | -9.3% | -24.0% | -2.720 | -7.510 |
| V9_XS_STREV_W | chop_IS_boxpi_2012_2016 | chop | 2012-06-01..2016-10-31 | -80.2% | 9.6% | -1.116 | 0.228 |
| V9_XS_STREV_W | bull_IS_2016_11_2018_01 | bull | 2016-11-01..2018-01-29 | -15.6% | 36.4% | -0.341 | 2.568 |
| V9_XS_STREV_W | bear_IS_2018_2019 | bear | 2018-01-30..2019-08-07 | -44.7% | -23.1% | -1.152 | -1.155 |
| V9_XS_STREV_W | bear_OOS_covid_2020 | bear | 2020-01-23..2020-03-19 | -28.7% | -34.6% | -4.632 | -7.766 |
| V9_XS_STREV_W | bull_OOS_2020_2021 | bull | 2020-03-20..2021-07-06 | 25.5% | 125.5% | 0.794 | 2.712 |
| V9_XS_STREV_W | bear_OOS_2021_2022 | bear | 2021-07-07..2022-09-30 | -62.5% | -34.3% | -2.659 | -1.907 |
| V9_XS_STREV_W | chop_OOS_2023_2024 | chop | 2023-01-02..2024-06-28 | -17.6% | 35.0% | -0.407 | 1.358 |
| V9_XS_STREV_W | bear_OOS_2024_2025 | bear | 2024-07-12..2025-04-09 | -44.1% | -21.6% | -2.005 | -1.376 |
| V9_XS_STREV_W | bull_OOS_2025_2026 | bull | 2025-04-10..2026-02-26 | 21.2% | 212.6% | 0.975 | 5.285 |
| V9_XS_STREV_W | bear_OOS_2026_03 | bear | 2026-02-27..2026-03-31 | -7.3% | -20.6% | -1.033 | -2.938 |
| V9_XS_STREV_W | bull_OOS_2026_04_06 | bull | 2026-04-01..2026-06-22 | -17.9% | 97.5% | -1.844 | 5.714 |
| V9_XS_STREV_W | bear_OOS_2026_07 | bear | 2026-06-23..2026-07-30 | -30.7% | -40.8% | -4.502 | -5.365 |
| V9_XS_STREV_W | bear_OOS_2026_10_ongoing | bear | 2026-09-24..2026-10-26 | -11.5% | -24.0% | -4.826 | -7.510 |
| B1_BH_069500 | chop_IS_boxpi_2012_2016 | chop | 2012-06-01..2016-10-31 | 9.6% | 9.6% | 0.228 | 0.228 |
| B1_BH_069500 | bull_IS_2016_11_2018_01 | bull | 2016-11-01..2018-01-29 | 36.4% | 36.4% | 2.568 | 2.568 |
| B1_BH_069500 | bear_IS_2018_2019 | bear | 2018-01-30..2019-08-07 | -23.1% | -23.1% | -1.155 | -1.155 |
| B1_BH_069500 | bear_OOS_covid_2020 | bear | 2020-01-23..2020-03-19 | -34.6% | -34.6% | -7.766 | -7.766 |
| B1_BH_069500 | bull_OOS_2020_2021 | bull | 2020-03-20..2021-07-06 | 125.5% | 125.5% | 2.712 | 2.712 |
| B1_BH_069500 | bear_OOS_2021_2022 | bear | 2021-07-07..2022-09-30 | -34.3% | -34.3% | -1.907 | -1.907 |
| B1_BH_069500 | chop_OOS_2023_2024 | chop | 2023-01-02..2024-06-28 | 35.0% | 35.0% | 1.358 | 1.358 |
| B1_BH_069500 | bear_OOS_2024_2025 | bear | 2024-07-12..2025-04-09 | -21.6% | -21.6% | -1.376 | -1.376 |
| B1_BH_069500 | bull_OOS_2025_2026 | bull | 2025-04-10..2026-02-26 | 212.6% | 212.6% | 5.285 | 5.285 |
| B1_BH_069500 | bear_OOS_2026_03 | bear | 2026-02-27..2026-03-31 | -20.6% | -20.6% | -2.938 | -2.938 |
| B1_BH_069500 | bull_OOS_2026_04_06 | bull | 2026-04-01..2026-06-22 | 97.5% | 97.5% | 5.714 | 5.714 |
| B1_BH_069500 | bear_OOS_2026_07 | bear | 2026-06-23..2026-07-30 | -40.8% | -40.8% | -5.365 | -5.365 |
| B1_BH_069500 | bear_OOS_2026_10_ongoing | bear | 2026-09-24..2026-10-26 | -24.0% | -24.0% | -7.510 | -7.510 |
| B4_EW_U500 | chop_IS_boxpi_2012_2016 | chop | 2012-06-01..2016-10-31 | -5.3% | 9.6% | 0.005 | 0.228 |
| B4_EW_U500 | bull_IS_2016_11_2018_01 | bull | 2016-11-01..2018-01-29 | 15.7% | 36.4% | 0.901 | 2.568 |
| B4_EW_U500 | bear_IS_2018_2019 | bear | 2018-01-30..2019-08-07 | -41.3% | -23.1% | -1.553 | -1.155 |
| B4_EW_U500 | bear_OOS_covid_2020 | bear | 2020-01-23..2020-03-19 | -42.5% | -34.6% | -6.855 | -7.766 |
| B4_EW_U500 | bull_OOS_2020_2021 | bull | 2020-03-20..2021-07-06 | 136.5% | 125.5% | 2.791 | 2.712 |
| B4_EW_U500 | bear_OOS_2021_2022 | bear | 2021-07-07..2022-09-30 | -38.8% | -34.3% | -1.667 | -1.907 |
| B4_EW_U500 | chop_OOS_2023_2024 | chop | 2023-01-02..2024-06-28 | 11.1% | 35.0% | 0.502 | 1.358 |
| B4_EW_U500 | bear_OOS_2024_2025 | bear | 2024-07-12..2025-04-09 | -24.0% | -21.6% | -1.268 | -1.376 |
| B4_EW_U500 | bull_OOS_2025_2026 | bull | 2025-04-10..2026-02-26 | 88.8% | 212.6% | 3.595 | 5.285 |
| B4_EW_U500 | bear_OOS_2026_03 | bear | 2026-02-27..2026-03-31 | -12.4% | -20.6% | -1.551 | -2.938 |
| B4_EW_U500 | bull_OOS_2026_04_06 | bull | 2026-04-01..2026-06-22 | 2.9% | 97.5% | 0.514 | 5.714 |
| B4_EW_U500 | bear_OOS_2026_07 | bear | 2026-06-23..2026-07-30 | -29.3% | -40.8% | -4.668 | -5.365 |
| B4_EW_U500 | bear_OOS_2026_10_ongoing | bear | 2026-09-24..2026-10-26 | -14.0% | -24.0% | -4.754 | -7.510 |
| B5_EW_ALL_ELIG | chop_IS_boxpi_2012_2016 | chop | 2012-06-01..2016-10-31 | 7.6% | 9.6% | 0.187 | 0.228 |
| B5_EW_ALL_ELIG | bull_IS_2016_11_2018_01 | bull | 2016-11-01..2018-01-29 | 15.1% | 36.4% | 0.865 | 2.568 |
| B5_EW_ALL_ELIG | bear_IS_2018_2019 | bear | 2018-01-30..2019-08-07 | -38.7% | -23.1% | -1.415 | -1.155 |
| B5_EW_ALL_ELIG | bear_OOS_covid_2020 | bear | 2020-01-23..2020-03-19 | -42.8% | -34.6% | -6.839 | -7.766 |
| B5_EW_ALL_ELIG | bull_OOS_2020_2021 | bull | 2020-03-20..2021-07-06 | 168.6% | 125.5% | 3.279 | 2.712 |
| B5_EW_ALL_ELIG | bear_OOS_2021_2022 | bear | 2021-07-07..2022-09-30 | -38.6% | -34.3% | -1.612 | -1.907 |
| B5_EW_ALL_ELIG | chop_OOS_2023_2024 | chop | 2023-01-02..2024-06-28 | 9.1% | 35.0% | 0.440 | 1.358 |
| B5_EW_ALL_ELIG | bear_OOS_2024_2025 | bear | 2024-07-12..2025-04-09 | -23.5% | -21.6% | -1.265 | -1.376 |
| B5_EW_ALL_ELIG | bull_OOS_2025_2026 | bull | 2025-04-10..2026-02-26 | 79.8% | 212.6% | 3.568 | 5.285 |
| B5_EW_ALL_ELIG | bear_OOS_2026_03 | bear | 2026-02-27..2026-03-31 | -11.1% | -20.6% | -1.568 | -2.938 |
| B5_EW_ALL_ELIG | bull_OOS_2026_04_06 | bull | 2026-04-01..2026-06-22 | -4.8% | 97.5% | -0.363 | 5.714 |
| B5_EW_ALL_ELIG | bear_OOS_2026_07 | bear | 2026-06-23..2026-07-30 | -23.7% | -40.8% | -4.107 | -5.365 |
| B5_EW_ALL_ELIG | bear_OOS_2026_10_ongoing | bear | 2026-09-24..2026-10-26 | -12.8% | -24.0% | -4.639 | -7.510 |

**Aggregated regime types (Sharpe / total return):**

| Strategy | Bull | Bear | Chop |
|---|---|---|---|
| V1_XS_MOM12_1 | 0.787 / 125.1% | -2.213 / -98.3% | -0.002 / -29.6% |
| V2_XS_MOM12_1_MF | 0.335 / 22.0% | -1.343 / -83.8% | -0.036 / -22.3% |
| V3_XS_MOM60_REPL | -0.384 / -65.0% | -1.368 / -82.7% | -0.795 / -90.6% |
| V4_XS_52WH | 1.333 / 263.7% | -1.792 / -92.5% | 0.548 / 80.6% |
| V5_XS_LOWVOL | 2.060 / 213.8% | -1.575 / -64.2% | 0.534 / 37.8% |
| V6_XS_MOM_LOWVOL | 2.732 / 850.5% | -1.947 / -87.9% | 0.460 / 46.1% |
| V7_TS_DONCHIAN_70_25 | 2.021 / 716.3% | -2.462 / -95.5% | -0.576 / -55.2% |
| V8_EV_VOLSPIKE20 | 0.796 / 85.9% | -1.926 / -92.1% | -0.971 / -73.4% |
| V9_XS_STREV_W | 0.195 / 5.3% | -2.111 / -95.3% | -0.956 / -83.7% |
| B1_BH_069500 | 3.406 / 1798.6% | -2.171 / -90.8% | 0.561 / 47.9% |
| B4_EW_U500 | 2.149 / 431.7% | -2.031 / -91.6% | 0.136 / 5.1% |
| B5_EW_ALL_ELIG | 2.239 / 429.6% | -1.964 / -90.3% | 0.252 / 17.4% |

## 6. Sensitivity and robustness results

| Scenario | Trial | IS Sharpe | OOS Sharpe | FULL Sharpe |
|---|---|---:|---:|---:|
| Slippage x2 | V1_XS_MOM12_1 | -0.576 | -0.272 | -0.404 |
| Slippage x2 | V2_XS_MOM12_1_MF | -0.225 | -0.147 | -0.173 |
| Slippage x2 | V3_XS_MOM60_REPL | -0.813 | -0.864 | -0.837 |
| Slippage x2 | V4_XS_52WH | -0.330 | 0.036 | -0.116 |
| Slippage x2 | V5_XS_LOWVOL | 0.214 | 0.416 | 0.325 |
| Slippage x2 | V6_XS_MOM_LOWVOL | 0.286 | 0.336 | 0.305 |
| Slippage x2 | V7_TS_DONCHIAN_70_25 | -1.056 | 0.033 | -0.378 |
| Slippage x2 | V8_EV_VOLSPIKE20 | -0.896 | -0.885 | -0.874 |
| Slippage x2 | V9_XS_STREV_W | -1.598 | -1.315 | -1.460 |
| Slippage x2 | B4_EW_U500 | -0.214 | 0.098 | -0.028 |
| Sell tax 0.30% | V1_XS_MOM12_1 | -0.536 | -0.255 | -0.377 |
| Sell tax 0.30% | V2_XS_MOM12_1_MF | -0.180 | -0.134 | -0.148 |
| Sell tax 0.30% | V3_XS_MOM60_REPL | -0.743 | -0.836 | -0.788 |
| Sell tax 0.30% | V4_XS_52WH | -0.200 | 0.090 | -0.032 |
| Sell tax 0.30% | V5_XS_LOWVOL | 0.251 | 0.436 | 0.351 |
| Sell tax 0.30% | V6_XS_MOM_LOWVOL | 0.360 | 0.366 | 0.350 |
| Sell tax 0.30% | V7_TS_DONCHIAN_70_25 | -1.000 | 0.051 | -0.346 |
| Sell tax 0.30% | V8_EV_VOLSPIKE20 | -0.704 | -0.760 | -0.723 |
| Sell tax 0.30% | V9_XS_STREV_W | -1.136 | -0.975 | -1.056 |
| Sell tax 0.30% | B4_EW_U500 | -0.176 | 0.118 | -0.001 |
| Rebalance phase +5 | V1_XS_MOM12_1 | -0.645 | -0.361 | -0.480 |
| Rebalance phase +5 | V2_XS_MOM12_1_MF | -0.231 | -0.145 | -0.172 |
| Rebalance phase +5 | V4_XS_52WH | -0.457 | 0.048 | -0.167 |
| Rebalance phase +5 | V5_XS_LOWVOL | 0.307 | 0.452 | 0.382 |
| Rebalance phase +5 | V6_XS_MOM_LOWVOL | 0.363 | 0.390 | 0.366 |
| Unrepaired data (IS pick) | V6_XS_MOM_LOWVOL | 0.395 | 0.380 | 0.372 |

**Capacity/participation at 10M, 100M, and 1bn KRW:**

| Trial | 100M p95 participation / median traded value | 100M max | 10M/1bn values |
|---|---:|---:|---|
| V1_XS_MOM12_1 | 0.2% | 154095095.0% | See IS-pick capacity row below for 10M and 1bn. |
| V2_XS_MOM12_1_MF | 0.3% | 0.9% | See IS-pick capacity row below for 10M and 1bn. |
| V3_XS_MOM60_REPL | 0.6% | 1.5% | See IS-pick capacity row below for 10M and 1bn. |
| V4_XS_52WH | 0.3% | 541434516.3% | See IS-pick capacity row below for 10M and 1bn. |
| V5_XS_LOWVOL | 0.4% | 0.7% | See IS-pick capacity row below for 10M and 1bn. |
| V6_XS_MOM_LOWVOL | 0.5% | 3.4% | See IS-pick capacity row below for 10M and 1bn. |
| V7_TS_DONCHIAN_70_25 | 0.1% | 248341767.0% | See IS-pick capacity row below for 10M and 1bn. |
| V8_EV_VOLSPIKE20 | 0.2% | 302141447.2% | See IS-pick capacity row below for 10M and 1bn. |
| V9_XS_STREV_W | 0.1% | 503220951.0% | See IS-pick capacity row below for 10M and 1bn. |

**IS-pick capacity at 10M / 100M / 1bn KRW (95th-percentile participation / max):** V6_XS_MOM_LOWVOL: 0.0% / 0.5% / 4.5%; max 0.3% / 3.4% / 34.2%. Gate (g) uses only the registered 100M p95 value.

**Top-10-contributor-removed rerun:**

| Trial | Removed instruments | IS Sharpe | OOS Sharpe | FULL Sharpe |
|---|---|---:|---:|---:|
| V1_XS_MOM12_1 | 008290, 009240, 014470, 015020, 016100, 018310, 020180, 079370, 123690, 128940 | -0.771 | -0.231 | -0.467 |
| V2_XS_MOM12_1_MF | 001570, 003160, 004770, 008290, 016100, 019170, 079430, 090460, 108490, 155650 | -0.366 | -0.296 | -0.315 |
| V3_XS_MOM60_REPL | 003160, 010050, 016100, 035620, 048870, 051980, 054210, 074150, 900050, 900100 | -1.400 | -0.747 | -1.061 |
| V4_XS_52WH | 003160, 003520, 016100, 027050, 028300, 030530, 048260, 069080, 347700, 402340 | -0.392 | 0.028 | -0.145 |
| V5_XS_LOWVOL | 000100, 001120, 005940, 017670, 024110, 051600, 053800, 068240, 088980, 316140 | 0.189 | 0.285 | 0.239 |
| V6_XS_MOM_LOWVOL | 000660, 005930, 009150, 011200, 012510, 034730, 035720, 039840, 081660, 090430 | 0.037 | 0.175 | 0.116 |
| V7_TS_DONCHIAN_70_25 | 000660, 009150, 011200, 016100, 019170, 048260, 078340, 090430, 096530, 285130 | -1.219 | -0.373 | -0.695 |
| V8_EV_VOLSPIKE20 | 005690, 006910, 027050, 042040, 064240, 067630, 078130, 200230, 224060, 900100 | -1.175 | -0.727 | -0.898 |
| V9_XS_STREV_W | 004710, 004770, 013810, 019570, 035600, 044380, 049480, 052420, 093520, 111610 | -1.140 | -0.790 | -0.964 |

## 7. Post-hoc Addendum A3 random-portfolio null

This is a diagnostic added after registration; selection count = 0. Statistic: annualized Sharpe of daily strategy returns minus B1 daily returns. Each null draw matches eligible pool, rebalance/event dates, target constituent counts/weights, cash decisions, slot timing, and `bt2.simulate` costs. P-values use `(1 + #null >= observed)/(1 + draws)`. Bonferroni and BH q-values cover the nine OOS trials.

| Trial | Draws | IS active Sharpe | IS p | OOS active Sharpe | OOS p | Bonferroni p | BH q | Null OOS median | Null OOS p95 |
|---|---:|---:|---:|---:|---:|---:|---:|---:|---:|
| V1_XS_MOM12_1 | 200 | -0.707 | 0.3085 | -0.972 | 0.2488 | 1.0000 | 0.3731 | -1.138 | -0.787 |
| V2_XS_MOM12_1_MF | 200 | -0.364 | 0.0299 | -0.837 | 0.3483 | 1.0000 | 0.4478 | -0.899 | -0.626 |
| V3_XS_MOM60_REPL | 200 | -0.817 | 0.5274 | -1.208 | 0.9851 | 1.0000 | 1.0000 | -0.660 | -0.178 |
| V4_XS_52WH | 200 | -0.388 | 0.0498 | -0.672 | 0.0249 | 0.2239 | 0.0746 | -1.106 | -0.799 |
| V5_XS_LOWVOL | 200 | -0.207 | 0.0050 | -0.594 | 0.0100 | 0.0896 | 0.0448 | -1.124 | -0.778 |
| V6_XS_MOM_LOWVOL | 200 | 0.081 | 0.0050 | -0.652 | 0.0100 | 0.0896 | 0.0448 | -1.097 | -0.732 |
| V7_TS_DONCHIAN_70_25 | 100 | -1.311 | 1.0000 | -0.674 | 0.1386 | 1.0000 | 0.2507 | -0.962 | -0.591 |
| V8_EV_VOLSPIKE20 | 100 | -0.948 | 0.8416 | -1.753 | 1.0000 | 1.0000 | 1.0000 | -1.032 | -0.679 |
| V9_XS_STREV_W | 200 | -1.219 | 0.0050 | -1.791 | 0.1393 | 1.0000 | 0.2507 | -2.038 | -1.681 |

These p-values and corrections do not enter gates (a)-(g), the IS selection, or the final registered PASS/FAIL.

## 8. Hypotheses H1-H7

| Hypothesis | Verdict | Evidence |
|---|---|---|
| H1 | **SUPPORTED** | V1 OOS Sharpe -0.246 vs B4 0.124. |
| H2 | **SUPPORTED** | IS MDD/Sharpe 29.5%/0.264 vs B4 50.1%/-0.167; OOS 36.8%/0.444 vs 49.2%/0.124. |
| H3 | **SUPPORTED** | V8 OOS Sharpe -0.719 vs B4 0.124. |
| H4 | **SUPPORTED** | V9 IS total return -91.6%; OOS -88.1%. |
| H5 | **SUPPORTED** | V7 chop Sharpe -0.576 vs B4 0.136. |
| H6 | **REJECTED** | V3 PRE2018 Sharpe -0.740; POST2018 -0.787. |
| H7 | **SUPPORTED** | No trial evaluated against the registered gate criteria (a)-(g) passes. |

H7 evaluates whether any V trial would satisfy all seven numerical gate conditions as a diagnostic; only the IS pick is eligible for the actual registered gate and no alternative trial is promoted.

## 9. Pre-registered gate for the IS pick

| Item | Registered criterion | Observed value | Verdict |
|---|---|---|---|
| (a) | OOS Sharpe >= 0.5 | 0.380 | **FAIL** |
| (b) | OOS Sharpe >= both B1 and B4 | pick 0.380; B1 0.758; B4 0.124 | **FAIL** |
| (c) | FULL DSR N=17 >= 0.90 and N=233 >= 0.80 | 0.327; 0.076 | **FAIL** |
| (d) | FULL MDD <= 35% | 60.5% | **FAIL** |
| (e) | Sharpe > 0 in at least 2/3 regime types and bear return > B1 bear return | positive Sharpe types 2/3; bear -87.9% vs B1 -90.8% | **PASS** |
| (f) | Slippage-x2 OOS Sharpe >= 0.4 and top-10-removed FULL Sharpe >= B4 FULL Sharpe | slip-x2 0.336; robust 0.116; B4 0.006 | **FAIL** |
| (g) | 100M KRW 95th percentile participation <= 5% of median traded value | 0.5% | **PASS** |

**Overall registered gate: FAIL.** No alternative IS trial is promoted if the pick fails.

## 10. Limitations and interpretation

- Prices and traded values come from the KIS paper quotation path. Dividends are excluded; KIS data quality and corporate-action repair uncertainty remain relevant.
- The fetch may stop at its fixed deadline with less than the 3,240 target. The random fetch order makes that subset pre-specified, but smaller coverage reduces breadth and power; the exact realized coverage above governs this report.
- Market-path contamination is explicit: the researcher had already seen index history and prior-round results. DSR at N=233 and N=1000 is a sensitivity, not a complete count of all historical research choices.
- The random-portfolio test is post-hoc and schedule-matched. It is not evidence of prospective performance and does not rescue a failed registered gate.

## 11. What was touched

- Files written under `research/kr_daily_v2/`: A3 addendum and timestamp, `null_test_v2.py`, `gate_report_v2.py`, orchestration script, timestamped stage logs, result JSONs, report, and completion/failure marker as applicable.
- Containers: only hardened disposable `tp-pipeline:local` offline analysis containers are launched by the orchestration script. The dedicated `kr2fetch` container is observed only; no other running service is stopped, restarted, or modified.
- No secrets file was read, printed, or modified. The analysis containers use `--network none`. No git add, commit, or push is performed.

## Reproduction artifacts

`results_main.json`, `results_sens.json`, `results_robust.json`, `results_null.json`, `qc2` stage log, `fetch_log.jsonl`, and `PIPELINE_DONE.marker` (if successful).
