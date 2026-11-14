# Pre-registration KR-daily-v2: full KOSPI+KOSDAQ universe (incl. delisted), daily bars, long-only, cross-sectional
Written 2026-11-04 ~08:30 KST, BEFORE any v2 price series was opened or any v2 strategy was run (the fetch is running; no file in research/kr_daily_v2/data has been read).
Scope: research backtest only. Reads come from the KIS PAPER daily-chart quotation path. No orders, and nothing is registered for forward tracking.
Predecessor: research/kr_daily_v1 (8 trials, no edge vs KODEX 200). Its data and results HAVE been seen, including the 2026 mania/crash regime. That knowledge is disclosed as contamination.

## What was seen before writing this (disclosure)
* Round 1 (v1): the full 2012-2026 path of KODEX 200, 8 sector ETFs and 10 large caps. All v1 strategy results.
* The local research repo /Users/user/Desktop/CODE/Ochestration/trading (read-only), in particular docs/research/stocks_kr.md.
  That is an earlier port of crypto strategies to KR daily data: 64 present-day survivor stocks, 2018-01..2026-10, about 216 variants. Its findings:
  - 60-120 day momentum with monthly rebalancing beat equal-weight, but depended on about 10 winners.
  - Short-horizon pullback, swing and EMA families lost to costs.
  - The volume-spike hypothesis had an edge only in crypto.
  This is prior search on overlapping KR data and is counted in the multiple-testing sensitivity below.
* The strategy catalog docs/research/strategy_catalog.md (crypto rounds 1-16, about 9-10k evaluated combinations). It was used for archetype ideas only.
* Universe lists only (no prices):
  - KIND 상장법인목록: 2,658 listed (KOSPI 829, KOSDAQ 1,829).
  - KIND 상장폐지현황: 1,072 delisted since 2010-01-01.
  - A 7-call probe showing that KIS serves history for delisted codes (053000, 000830, 005110, 134780, 026180, 181980) and new alphanumeric codes.

## Universe and survivorship handling
* Codes = (all currently listed common-stock issuers) ∪ (all issuers delisted on or after 2011-06-01), from the KIND lists dated 2026-11-04.
  SPACs (name contains 스팩 / 기업인수목적) are excluded. Result: 3,336 codes. The list files and their sha256 are in universe/.
  Delisted names are INCLUDED, so the backtest universe is not survivors-only. Their history includes the 정리매매 (delisting liquidation) sessions where KIS has them.
* Known residual gaps:
  - Issuers delisted before 2011-06 are irrelevant to a 2012-06 start.
  - Preferred shares, ETFs, REITs (only if listed as REIT funds) and KONEX are outside the lists or are filtered out by liquidity.
  - Code reuse or changes after mergers or spin-offs are not reconciled.
* Fetch: research/kr_daily_v2/fetch_v2.py.
  - Same request as kis.fetch_daily, adjusted prices, through kis._get_chart (0.8 s spacing plus EGW00201 back-off), but starting at each delisting date and tolerating halt gaps.
  - Fixed random order (seed 20261104). Pauses on weekdays 08:50-15:40 KST. Fixed END = 2026-11-03.
* DEADLINE RULE: analysis starts when the fetch completes, or at 2026-11-06 15:40 KST at the latest.
  If the fetch is incomplete at that point, the analysis uses the codes fetched so far. Because of the random order, that is an unbiased random subset of the list (listed and delisted alike). Coverage is reported.
* Point-in-time eligibility (evaluated with data up to t only):
  - At least 252 trading days of history.
  - Traded (volume > 0) on t and on at least 55 of the last 60 sessions.
  - 60-session median traded value (acml_tr_pbmn) >= 1 bn KRW.
  - U500 = the top 500 eligible names by that median value. All trials except V3 draw from U500. V3 replicates its original universe rule (median value >= 1 bn KRW and >= 30 bars).
* No market-cap, book-value or fundamental data is available from this source. Only price/volume factors are testable (a limitation, not a choice).

## Calendar, split, regimes
Master calendar = KODEX 200 (069500) trading days. Evaluation window = 2012-06-01..2026-11-03.
IS = 2012-06-01..2019-12-31. OOS = 2020-01-01..2026-11-03.
Regime windows = research/kr_daily_v1/REGIMES.json (already hashed 2026-11-03 14:27 UTC), unchanged.
Contamination: the OOS window's index path was seen in v1, so v2 OOS is out-of-sample only for the cross-sectional rules, not for the market path.

## Execution and costs (primary)
Signal at the close of t, fill at the open of t+1.
* An order is DEFERRED while the instrument cannot trade:
  - no row or volume = 0 (halt), or
  - a locked limit day: high == low and abs(open/prev close - 1) >= 0.25.
  A deferred buy is cancelled after 5 sessions; a deferred sell keeps retrying.
* A held position whose data ends before END (delisting) is closed at its last available close, less sell costs.
* Commission 0.015% per side. Sell tax 0.20% (flat; the actual tax was 0.30% before 2019-06, and 2026 is uncertain).
* Slippage per side, by the instrument's 60-session median traded value at the decision:
  - >= 50 bn: 0.05%
  - 10-50 bn: 0.10%
  - 1-10 bn: 0.25%
  - < 1 bn: 0.50%
* Fractional shares. Cash earns 0%. Instruments whose target weight is unchanged are not re-traded (drift kept). Sells execute first, then buys are scaled to available cash.
* Sensitivities (selection = 0): slippage x2; tax 0.30%; rebalance phase +5 sessions (monthly rules); capacity participation at 10M, 100M and 1bn KRW.

## Strategy trials (9 SELECTION trials, parameters fixed here, all long-only)
Archetypes are taken from the crypto library and the prior KR port, re-specified for KR daily bars. "Month-end" = the last session of a calendar month. Portfolios are equal-weight.
* V1 XS_MOM12_1: at month-end, the top 20 of U500 by 12-1 momentum (C[t-21]/C[t-252]-1). (Jegadeesh-Titman; the crypto "momentum rotation" family.)
* V2 XS_MOM12_1_MF: V1, all cash when KODEX 200 is below the mean of its last 10 month-end closes (v1 T1 filter).
* V3 XS_MOM60_REPL: exact replication of the prior KR port's best-documented rule (stocks_kr.md "60/5/21 + filter both").
  - Universe: median value >= 1 bn KRW and >= 30 bars.
  - Rank by 60-session return; hold the top 5.
  - Rebalance every 21 sessions, counted from the first evaluation session.
  - Cash on any day when (a) the equal-weight eligible-universe index has a 14-session return <= -10% (released when the 14-session return >= 0), or (b) that index is below its 200-session SMA.
  2012-06..2017-12 was NEVER seen by that study (its data started 2018-01), so this is a genuine out-of-sample test of an inherited rule.
* V4 XS_52WH: at month-end, the top 20 of U500 by C[t]/max(C[t-251..t]). (George-Hwang 52-week high.)
* V5 XS_LOWVOL: at month-end, the 20 names in U500 with the lowest 252-session stdev of daily returns. (The low-volatility anomaly.)
* V6 XS_MOM_LOWVOL: at month-end, the top 20 of U500 by the mean of the percentile rank of 12-1 momentum (high = good) and the percentile rank of 252-session volatility (low = good).
* V7 TS_DONCHIAN_70_25: daily. A name in the latest month-end U500 enters when C[t] > max(C[t-70..t-1]). A held name exits when C[t] < min(C[t-25..t-1]), whether or not it is still in U500.
  At most 20 positions at 5% of NAV each. If there are more entries than free slots, the highest 60-session median value goes first. (The crypto R14 "Donchian70/25" archetype.)
* V8 EV_VOLSPIKE20: daily (the owner's hypothesis, crypto §12 definition). A name in U500 signals when volume[t] >= 3 x mean(volume[t-20..t-1]) AND C[t]/C[t-1]-1 < +3%.
  Buy at the next open; sell at the open 20 sessions after entry. At most 20 slots at 5%. Ties go to the highest volume ratio.
* V9 XS_STREV_W: on the last session of each ISO week, the bottom 20 of U500 by 5-session return (C[t]/C[t-5]-1); hold one week. (The short-term reversal / pullback family.)

Archetypes deliberately NOT tested, with reasons:
* Fibonacci, FVG, order block, liquidity sweep, Elliott, ICT, Heikin-Ashi, FRVP, VWAP: these need intraday structure or have no economic rationale on daily KR bars. Heikin-Ashi/EMA-cross trend is covered by V7. The prior KR port found EMA/TRX below equal-weight.
* The 10,000-won rule: intraday.
* mach7, squeeze, swing6, pullback-with-TP/SL: the prior KR port lost or concentrated. A pullback is covered by V9.
* Funding arbitrage and liquidation proximity: no KR analogue.
* Pairs and long/short: retail KR short selling is impractical.
* Dual Thrust: an intraday breakout; its daily analogue is V7.
* Leverage: out of scope.

## Benchmarks (selection = 0)
* B1: KODEX 200 buy-and-hold (primary bar).
* B4: equal-weight U500, rebalanced monthly, costs applied.
* B5: equal-weight of all eligible names (median value >= 1 bn), rebalanced monthly, costs applied.

## Evaluation
Same metrics as v1: Sharpe (sqrt 252), CAGR, MDD, round trips, net win rate, time in market, turnover, cost drag. Computed on IS, OOS, FULL and each regime window.
Also reported: the top-10 contributor share of P&L, and results with the 10 largest single-name P&L contributors removed (the winner-dependence check from the prior KR port).
* Multiple testing:
  - PRIMARY N = 17 (8 v1 trials + 9 v2 trials by this researcher on KR daily data), using tp.research.dsr_ann null variance.
  - SENSITIVITY N = 233 (+ about 216 variants from the prior KR port, same market, overlapping years) and N = 1000.
  - All are reported. The v2 trials are logged in research/kr_daily_v2/trials.sqlite.
* SELECTION RULE: the V-trial with the highest IS Sharpe is the pick. Its OOS result is the headline. The OOS results of all trials are shown for transparency and labelled hindsight.

## Hypotheses (decided in advance)
* H1: V1 does not beat B4 on OOS Sharpe. KR price momentum is historically weak.
* H2: V5 has a lower MDD than B4 in both IS and OOS, and a Sharpe >= B4 in both.
* H3: V8 (volume spike) has no edge after costs: OOS Sharpe <= B4.
* H4: V9 (weekly reversal) is negative net of the 0.20% tax and weekly turnover, in both IS and OOS.
* H5: V7 (Donchian) has Sharpe < B4 in the chop regime type.
* H6: V3 Sharpe over 2012-06..2017-12 (unseen by the prior study) is below its 2018-01..2026-11 Sharpe (selection-bias decay).
* H7: no trial passes the gate.

## Gate (ALL must hold for the IS pick; failure is a valid outcome; nothing will be re-tuned)
* (a) OOS Sharpe >= 0.5.
* (b) OOS Sharpe >= B1 OOS Sharpe AND OOS Sharpe >= B4 OOS Sharpe.
* (c) FULL null-variance DSR at N = 17 >= 0.90. The N = 233 value is reported and must be >= 0.80.
* (d) FULL MDD <= 35%.
* (e) Sharpe > 0 in at least 2 of the 3 regime types, AND bear-type return > B1 bear-type return.
* (f) Slippage x2 OOS Sharpe >= 0.4, AND with the top-10 contributors removed, FULL Sharpe still >= B4 FULL Sharpe.
* (g) Capacity: at 100M KRW, 95th-percentile order participation <= 5% of the 60-session median traded value.
If the IS pick fails, no other trial is promoted. At most it becomes a hypothesis for a NEW pre-registration evaluated on forward paper data.
