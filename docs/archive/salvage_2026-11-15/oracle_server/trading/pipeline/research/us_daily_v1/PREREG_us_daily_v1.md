# Pre-registration, US daily v1: rule-based US equity ETF exposure management (written BEFORE any strategy backtest was run)
Scope: backtest research only. No orders, no keys, no broker. Nothing goes to the forward tracker / export from this round.
Author: investment-expert agent #2 (US). Date: 2026-11-03 (UTC). Hash + timestamp recorded in PREREG_us_daily_v1.timestamp.

## What has been looked at before writing this (disclosure)
* Data-quality checks only (research/us_daily_v1/data_quality.json): OHLC consistency, gaps vs the SPY calendar, adjustment factors,
  SPY adjusted total return vs ^SP500TR, ^IRX sanity.
* Benchmark-only facts: SPY drawdown episodes >= 10% since 1999 and SPY calendar-year total returns 2017-2026 (used to fix the regime windows below).
* NO strategy return, signal or equity curve has been computed on this data.
* PRIOR KNOWLEDGE (cannot be removed, must be disclosed): the author knows the published literature behind every rule below and the broad shape
  of US market history up to 2025 (dot-com bust, GFC, 2018 Q4, COVID V-shape, 2022 bear, 2023-25 AI rally, April 2025 tariff shock).
  The rules are taken with their canonical published parameters to limit this, but the choice of families is not blind.

## Data and universe
* Source: Yahoo Finance chart API v8 (unofficial, key-less) via tp.usdata; cache data/us_daily/. Daily OHLCV, split-adjusted OHLC, dividend+split
  adjusted close. Total-return-adjusted OHLC = OHLC x adjclose/close. T-bill: ^IRX (13-week T-bill yield, %), forward-filled for NaN.
  Stooq was tried first and is now behind a JavaScript proof-of-work page (unusable headless).
* Universe (fixed, 14 ETFs, chosen for structure not for past returns):
  - SPY (S&P 500), the trading vehicle for single-asset rules and the main benchmark; QQQ second benchmark.
  - The 9 ORIGINAL Select Sector SPDRs (XLB XLE XLF XLI XLK XLP XLU XLV XLY), all listed 1998-12-22 and all still trading: a complete
    partition of the S&P 500 at inception, so there is no survivorship selection among them (they cannot be "delisted losers").
    XLRE (2015) and XLC (2018) are excluded because they lack history; the 2018 GICS change that moved GOOGL/META from XLK/XLY into XLC changes
    sector composition mid-sample (limitation).
  - DIA, IWM, MDY fetched for context only; not traded in v1.
* No single stocks: picking today's mega-caps would be survivorship selection on the symbol. Fractional ETF shares are assumed (limitation for small accounts).

## Periods (fixed)
* Warm-up from data start. Common evaluation start 2000-01-03 (sector ETFs need ~253 days of history for 12-month signals).
* IN-SAMPLE (selection): 2000-01-03 .. 2016-12-30. Contains dot-com bust, 2003-07 bull, GFC, 2009-15 bull, 2015-16 chop.
* OUT-OF-SAMPLE (touched once, after selection): 2017-01-03 .. 2026-11-02 (last complete bar).
* Regime windows (from SPY drawdown dates in the data, close basis):
  IS: dotcom_bust 2000-03-24..2002-10-09; bull_03_07 2002-10-10..2007-10-09; gfc 2007-10-10..2009-03-09; bull_09_15 2009-03-10..2015-07-20; chop_15_16 2015-07-21..2016-12-30.
  OOS: q4_2018 2018-09-21..2018-12-24; covid_crash 2020-02-20..2020-03-23; covid_recovery 2020-03-24..2020-08-10; bull_2021 2021-01-04..2022-01-03;
  bear_2022 2022-01-04..2022-10-12; recovery_bull_2023plus 2022-10-13..2026-11-02 (contains tariff_2025 2025-02-20..2025-04-08, reported separately).

## Execution and cost model (primary)
* Decision on the close of day t using data up to and including close t. Fill at the OPEN of t+1 (market-on-open). Overnight t->t+1 is earned with the
  OLD weights, the t+1 open->close with the NEW weights. Holdings drift with prices between rebalances (unit-based simulation).
* Cost per side on traded notional: 5 bp = 1 bp commission+regulatory (IBKR-style $0.0035/share, SEC Sec.31 fee ~0.3 bp on sells, FINRA TAF) +
  4 bp slippage/half-spread vs the official open (SPY's half-spread is < 0.2 bp; sector SPDRs 0.5-3 bp; 4 bp is deliberately conservative).
  Sensitivity (selection = 0): 0, 2, 10, 25 bp per side; and fill at t+1 CLOSE instead of open.
* Cash (un-invested weight) earns ^IRX/100/252 per trading day (previous day's value). No leverage, no shorting -> no borrow cost. Max gross exposure 1.0.
* Taxes, FX (KRW/USD) and minimum-commission effects at small sizes are NOT modelled (limitations).
* No stop-losses in any rule: the exit logic of each rule IS its risk control; adding stops would add parameters.

## Strategy rules (7 selection trials, parameters are the canonical published ones, nothing will be tuned)
Month-end = last trading day of the calendar month in the SPY calendar. Week-end = last trading day of the ISO week. All prices total-return adjusted.
* T1 `spy_sma200_m` (Faber 2007 timing model, 10-month SMA ~ 200 days): at each month-end, SPY weight = 1 if close > SMA200(close) else 0.
* T2 `spy_absmom12_m` (Antonacci absolute momentum / Moskowitz-Ooi-Pedersen TSMOM): at month-end, weight = 1 if SPY 252-day total return >
  compounded T-bill return over the same 252 days, else 0.
* T3 `spy_voltgt_w` (Moreira-Muir 2017 volatility-managed portfolios, long-only, no leverage): at week-end, sigma = std of the last 20 daily
  simple returns x sqrt(252); target weight = min(1, 0.15 / sigma). Rebalance only if |target - current weight| >= 0.05 (turnover band).
* T4 `spy_sma200_voltgt_w`: at week-end, weight = T3 target if the T1 state (as of the latest month-end decision) is ON, else 0. Same 0.05 band.
* T5 `sector_dm3_m` (sector momentum, Moskowitz-Grinblatt 1999; Faber 2010 top-3 rotation; with Antonacci absolute filter): at month-end,
  score_i = close_i[t-21] / close_i[t-252] - 1 for the 9 sectors (12-1 momentum, skip the last month). Rank descending; the top 3 get 1/3 each,
  but a slot is held in cash if score_i <= compounded T-bill return over the same window. Ties broken alphabetically.
* T6 `sector_dm3_trend_m`: T5, but all slots in cash when SPY close <= SMA200 at the decision (T1 state OFF).
* T7 `spy_rsi2_mr` (Connors short-term mean reversion, 2008): daily. RSI2 = Wilder RSI with period 2 on close. If flat and close > SMA200 and RSI2 < 10:
  weight 1. If long and close > SMA5: weight 0. Otherwise unchanged.
Benchmarks (selection = 0): B1 SPY buy-and-hold; B2 QQQ buy-and-hold (from 2000); B3 equal-weight 9 sectors, monthly rebalanced, same costs;
B4 T-bills (cash).

## Selection rule (fixed)
* Primary metric: annualised Sharpe of daily EXCESS returns over the T-bill (ppy = 252), net of primary costs.
* The trial with the highest IS excess Sharpe is THE selected strategy. It is evaluated once on OOS. All other trials are also reported OOS but
  labelled hindsight; switching to a better-OOS trial after the fact is not allowed in this round.
* All 7 trials are logged as selection trials (study US1) in a SEPARATE registry runs/research/us_daily_v1/trials.sqlite (not the crypto registry:
  cross-asset Sharpe ratios are not exchangeable and would distort the crypto deflation). Sensitivity runs are logged with selection = 0.

## Evaluation
* Per period: CAGR, total return, ann. vol, excess Sharpe, raw Sharpe, max drawdown, exposure (avg weight), number of trades (rebalance fills),
  round-trip win rate (for T1/T2/T7 entry->exit episodes), turnover per year, cost drag per year.
* Multiple testing: deflated Sharpe (tp.research.dsr_ann logic replicated; null variance 1/years and the robust empirical variance) over the 7
  selection trials, computed on the IS series (where selection happened). OOS: PSR(0) of the selected trial; DSR also recomputed with n = 7 + number of
  sensitivity runs as an extra-conservative reference.
* Paired test vs SPY: block bootstrap (block 21 days, 2000 draws) CI of the mean daily excess-return difference, OOS.
* Per-regime: return, MDD, Sharpe (where >= 40 days) for each window above, strategy vs SPY.
* Phase sensitivity (selection = 0): month-end rules re-run with decision day shifted to month-end minus 5 and minus 10 trading days; weekly rules to
  Wednesday decisions.
* Look-ahead check: run cut at 2016-12-30 must reproduce the IS part of the full run exactly.

## Hypotheses (decided in advance; they encode the author's priors, see disclosure)
H1 T1/T2 cut full-sample MDD vs SPY by >= 40%, but OOS excess Sharpe is NOT higher than SPY's (V-shaped recoveries 2018/2020/2025 cause whipsaw).
H2 T3 has higher excess Sharpe than SPY in both IS and OOS.
H3 Sector rotation T5 does not beat SPY OOS on excess Sharpe.
H4 T7 has a high IS Sharpe at low exposure but degrades OOS and is the most cost-sensitive rule.

## Forward-candidate rule (ALL must hold for the selected trial; failing is a valid, reportable outcome; nothing is re-tuned afterwards)
G1 OOS excess Sharpe >= 0.5 AND >= SPY buy-and-hold OOS excess Sharpe.
G2 IS null-variance DSR >= 0.90 over the 7 selection trials.
G3 OOS max drawdown <= 25%.
G4 Regimes: in covid_crash and bear_2022 the strategy's in-window MDD < SPY's; in covid_recovery+bull_2021 combined and in recovery_bull_2023plus
   it captures >= 50% of SPY's total return.
G5 Robustness: OOS excess Sharpe > 0 at 25 bp/side, and >= 0.5 x base OOS excess Sharpe for every phase shift.
A weaker label "risk-overlay candidate" (NOT a pass) is reported if G1 fails only on the SPY comparison while OOS excess Sharpe >= SPY's - 0.15 and
OOS MDD <= 0.6 x SPY's OOS MDD, and G2-G5 hold.
