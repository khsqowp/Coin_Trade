# Pre-registration KR-daily-v1: Korean equities, daily bars, long-only (written BEFORE any strategy backtest or full-history download)
Scope: research backtest only. Reads come from the KIS PAPER quotation API (daily chart path only, tp.kis.fetch_daily). There are no orders and no forward-tracker registration.
Author: investment-expert agent #1 (KR). Date: 2026-11-03 (KST evening, market closed).

## What was seen before this was written (disclosure)
* There was an availability probe (research/kr_daily_v1/probe.py). It returned ETF/stock names and row counts in 2008, 2012 and 2016 windows. It computed no returns, and no prices were inspected.
* The cached 400-day KIS files in data/ohlcv were NOT opened.
* Prior knowledge (cannot be removed): the author knows the broad KOSPI history. That covers the 2008 GFC, the 2011-2016 "Boxpi" range, the 2017 rally, the 2018 sell-off, the 2020 crash and rebound, the 2021-22 decline and the 2025 rally.
  The rules below are textbook rules with textbook parameters, chosen so this knowledge does not steer parameter choices. The knowledge still acts as soft data snooping (see the report).

## Data
* Source: KIS paper daily chart, FID_ORG_ADJ_PRC=0 (split-adjusted price). Price return only: cash dividends and ETF distributions are NOT included.
  For KODEX 200 that understates buy-and-hold by about 1.5-2%/yr. The strategies also lose the dividend while invested, so they are understated too, but less while in cash.
* Fetched with kis.fetch_daily(code, days=4800) into research/kr_daily_v1/data/ (not data/ohlcv). Rate limit: the module's 0.8 s per call plus EGW00201 back-off. The run happens outside KRX hours so the intraday collector is not disturbed.
* Universe (fixed now, NOT chosen by performance):
  - Index: 069500 KODEX 200 (KOSPI 200 tracker, deepest KR ETF). Cash proxy for sensitivity only: 114260 KODEX 3-yr KTB.
  - Sector family: all 8 "TIGER 200 <sector>" ETFs listed together in April 2011: 139220 Construction, 139230 Heavy Industry, 139240 Steel/Materials,
    139250 Energy/Chem, 139260 IT, 139270 Financials, 139280 Defensive (was Consumer Staples), 139290 Consumer Discretionary. This is the whole family as listed, not a cherry-pick.
    Sector ETFs carry no single-name survivorship and are exempt from the KR securities transaction tax.
  - Stock family: KOSPI top-10 by market capitalisation at END-2010, frozen point-in-time. The list comes from a news summary and has not been checked against KRX:
    005930 Samsung Elec, 005490 POSCO (Holdings), 005380 Hyundai Motor, 009540 Hyundai Heavy (now HD Korea Shipbuilding), 012330 Hyundai Mobis,
    051910 LG Chem, 055550 Shinhan, 105560 KB Financial, 032830 Samsung Life, 000270 Kia. None of these was delisted, so the remaining survivorship is limited to that.
    The list was fixed more than a year before the evaluation start, so it is free of the "today's winners" bias that the existing 8-symbol cache has (373220 listed 2022, 207940 listed 2016).
* Common evaluation window: 2012-06-01 to the last available date. The start is the first month-end with 12 months of sector-ETF history plus a buffer.
  IN-SAMPLE (selection) = 2012-06-01..2019-12-31. OUT-OF-SAMPLE = 2020-01-01..end. OOS is used for nothing except the final evaluation of the IS-selected rule and the transparency table.
* Regime calendar: fixed in an addendum BEFORE any strategy is run. It is derived only from the 069500 price path: bear = peak-to-trough decline >= 20%, bull = advance >= 40% from a trough,
  chop = at least 12 months during which the index stays inside a +/-15% band around its mean. The addendum is hashed before the strategy run.

## Execution and cost model (primary)
Signals use the close of day t. Fills happen at the OPEN of t+1 (the KRX opening single-price auction) with per-side slippage. Positions are marked close-to-close. Fractional shares are used in the primary run.
* Commission 0.015% per side (all instruments).
* Sell tax: stocks 0.20% of sell notional. That is conservative versus the house 0.18%; the 2026 statutory rate is uncertain to the author, and the tax was 0.30% before mid-2019. Domestic equity ETFs pay 0%.
* Slippage per side: 069500 0.03%, 114260 0.05%, TIGER 200 sector ETFs 0.20% (thin; LP spreads), stocks 0.10%.
* Cash earns 0% (primary). Sensitivity, selection=0: cash in 114260; slippage x2; stock tax 0.30%; integer shares at 10,000,000 KRW capital.

## Strategy trials (all parameters fixed here; 8 SELECTION trials, nothing else will be added to the selection set)
"Month-end" = the last trading day of the calendar month in the data. 12-1 momentum = close(t-21)/close(t-252)-1, measured in trading days.
* T1 IDX_SMA10M: at each month-end, if the 069500 close > mean of the last 10 month-end closes, hold 100% 069500; otherwise hold cash (Faber 2007).
* T2 IDX_TSMOM12: at each month-end, if the 069500 12-month return (close_t/close_{t-252}-1) > 0, hold 100% 069500; otherwise cash (Moskowitz-Ooi-Pedersen 2012 / Antonacci absolute momentum).
* T3 IDX_VOLTGT15: weight in 069500 = min(1, 0.15 / (20-day realised daily-return stdev * sqrt(252))). It is recomputed on the last trading day of each week and traded only if |new-old| >= 0.10.
* T4 IDX_RSI2: daily. Enter 100% 069500 when close > SMA200(close) AND RSI(2, Wilder) < 10. Exit when close > SMA5(close). Signals at the close, fills at the next open (Connors).
* T5 SEC_MOM3: at each month-end, rank the 8 sector ETFs by 12-1 momentum and take the top 3, each at 1/3 weight. A slot whose ETF has 12-1 momentum <= 0 is held in cash instead.
  No other ranking is used (Moskowitz-Grinblatt 1999 industry momentum).
* T6 SEC_MOM3_MF: T5, but everything is in cash whenever the T1 market filter (069500 below its 10-month mean) is off.
* T7 STK_MOM3: T5 logic applied to the frozen 10-stock list (top 3 by 12-1 momentum, 1/3 weight each, absolute filter > 0).
* T8 STK_MOM3_MF: T7 with the T1 market filter.
Each rebalance trades only the instruments whose target weight changed (sell first, then buy), and pays the costs above on the traded notional.

## Benchmarks (selection = 0)
B1: 069500 buy and hold. B2: equal-weight 8 sector ETFs, rebalanced monthly, costs applied. B3: equal-weight frozen 10 stocks, rebalanced monthly, costs applied.

## Evaluation
Daily NAV returns. Reported metrics: Sharpe (sqrt 252, no risk-free deduction, house convention), CAGR, total return, max drawdown, time in market, round-trip trade count, net win rate per round trip, and cost drag.
These are computed on IS, OOS, full, and each regime window.
PSR and deflated Sharpe come from tp.research.dsr_ann (null variance 1/years; N = 8 selection trials). They are logged in a SEPARATE registry, research/kr_daily_v1/trials.sqlite,
so the crypto study registry is neither diluted nor polluted. The empirical-variance DSR is reported as well.
SELECTION RULE: the trial with the highest IS Sharpe is the pick. Its OOS result is the headline. The OOS results of all 8 trials are shown for transparency only and are labelled hindsight.

## Hypotheses (decided in advance)
H1 T1/T2 cut max drawdown versus B1 by >= one third in both IS and OOS, at the cost of lagging B1 in bull regimes.
H2 In the chop regime(s), T1/T2 have Sharpe below B1 (whipsaw). This is an expected failure mode, not a surprise.
H3 T5 beats B2 on OOS Sharpe. Literature support is mixed for KR.
H4 T7/T8 (3 of 10 stocks) are high-variance. No significant edge is expected (DSR < 0.9).
H5 T4 has positive IS and OOS Sharpe with low exposure (< 30% time in market).

## Next-stage gate (ALL must hold for the IS-selected trial; failure is a valid outcome and nothing will be re-tuned)
(a) OOS Sharpe >= 0.5.
(b) OOS Sharpe >= B1 OOS Sharpe, OR (OOS Sharpe >= 0.8 x B1 OOS Sharpe AND OOS MDD <= 0.6 x B1 OOS MDD).
(c) Full-period null-variance DSR (N = 8) >= 0.90.
(d) Full-period MDD <= 35%.
(e) In every bear window, return > B1 return. Sharpe > 0 in at least 2 of the 3 regime types.
(f) With slippage x2, OOS Sharpe >= 0.4.
If the IS pick fails, the report says so. A different trial that looks good OOS will NOT be promoted (that would be OOS selection). At most it is flagged as a hypothesis for a NEW pre-registration on new data.
