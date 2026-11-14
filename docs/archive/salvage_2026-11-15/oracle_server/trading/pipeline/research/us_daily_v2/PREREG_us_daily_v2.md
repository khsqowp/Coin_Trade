# Pre-registration, US daily v2: cross-sectional rules on the point-in-time S&P 500 (written BEFORE any v2 strategy backtest)
Scope: backtest research only. No orders, no keys. Nothing goes to the forward tracker / export. Author: investment-expert agent #2 (US). 2026-11-04 UTC.

## Disclosure of what was seen before writing this
* Round 1 (research/us_daily_v1): SPY / QQQ / 9 sector ETFs, 2000-2026, including the OOS window 2017-2026 that is reused here. I have therefore
  already SEEN how SPY, QQQ, sector rotation, 200-day timing, vol targeting and RSI(2) on SPY behaved in this OOS window (soft snooping; the
  v2 OOS is not virgin data for market-level behaviour, only for single-stock cross-sectional rules).
* Prior knowledge: the academic literature behind every rule below (published 1990-2011, i.e. fitted mostly on pre-2010 data), and broad
  market history to 2025 (e.g. that mega-cap growth / momentum names led 2023-2024, the 2020 momentum-crash-free V shape, the Nov-2020 value rebound,
  the 2022 low-vol outperformance). I cannot un-know these; the families were nevertheless chosen from the literature and the owner's strategy
  repo, not from looking at v2 data.
* Strategy-idea source: owner's crypto repo /Users/user/Desktop/CODE/Ochestration/trading/app (read for archetypes only, no code ported).
  Archetype -> daily-equity analogue used here: momentum rotation / ROC -> X1-X3; BTC-regime filter -> X2's market filter; Donchian / breakout ->
  X4 (52-week-high); RSI / MA-pullback / mach7 pullback / CCI / range reversion -> X6 (weekly reversal) and X7 (RSI(2) pullback);
  volume-spike / FRVP+volume -> X8 (high-volume return drift); golden cross / EMA cross / Supertrend / ichimoku trend states -> X9 (trend breadth);
  adaptive position sizing -> X3 risk-adjusted momentum; nothing in the repo maps to low volatility (X5, added from the literature as the
  defensive factor). Methodology adopted from the repo's rounds 4/16: random-entry null, Bonferroni + Benjamini-Hochberg, top-contributor
  concentration check, fixed grids that are not changed after results.
* Archetypes REJECTED for daily US equities (not tested, not counted): Fibonacci retracement, FVG / order block, liquidity sweep, Elliott wave,
  Heikin-Ashi, VWAP, FRVP (intraday/microstructure constructs without a daily-equity rationale or with discretionary definitions);
  pairs trading and all short/long-short/leverage/funding/liquidation strategies (long-only cash account assumed; shorting single stocks adds
  borrow-cost and recall risk that free data cannot model).
* Data seen before writing: the fja05680 membership file headers/row count only, and the fetch progress counters. No v2 price-based statistic.

## Universe and data
* Membership: fja05680/sp500 `sp500_ticker_start_end.csv` (GitHub, last commit 2026-09-07): ticker spells of S&P 500 membership since 1996.
  A stock is ELIGIBLE at decision date t if (a) t is inside one of its membership spells, (b) Yahoo daily data exists for it on t, (c) it has
  >= 260 trading days of price history up to t, (d) vendor instrumentType is EQUITY. Membership after 2026-09-07 is carried forward (list frozen).
* Prices: Yahoo chart v8 via tp.usdata (total-return adjusted OHLC, volume). Ticker '.' -> '-' (BRK.B -> BRK-B).
* KNOWN BIASES (measured, not removable): delisted / bankrupt / acquired members are often NOT served by Yahoo -> missing from the eligible set
  (survivorship, optimistic). Renamed tickers (e.g. FB->META) lose their pre-rename spell when the old ticker is not served (coverage loss, sign
  unclear). Re-used tickers can attach a DIFFERENT company's prices to an old spell (audited by vendor longName for spells that ended before 2015).
  Measures: (1) PIT coverage = eligible-with-data member-days / member-days, per year; (2) our equal-weight universe vs RSP (real equal-weight S&P 500
  ETF, from 2003-05) over the same dates = an estimate of the total universe bias; (3) every strategy is judged against a RANDOM-PORTFOLIO NULL drawn
  from the same biased eligible set, which cancels the universe bias to first order.
* Held stock whose data ends (delisting / acquisition / vendor gap): valued at the last close, sold at that price at the next decision (optimistic
  for bankruptcies, which are mostly absent anyway).

## Periods (fixed by rule, decided now)
* OOS: 2017-01-03 .. last complete bar (same as round 1).
* IS start: the first calendar-year start >= 2000-01-03 at which yearly PIT coverage (above) is >= 85% for that year and every later IS year.
  IS end 2016-12-30. If no year qualifies before 2008, IS starts 2008-01-02 and the report says so. Warm-up data before IS start is used for signals.
* Regime windows: as round 1 (SPY dates, verified): covid_crash 2020-02-20..2020-03-23, covid_recovery 2020-03-24..2020-08-10, bull_2021 2021-01-04..2022-01-03,
  bear_2022 2022-01-04..2022-10-12, recovery_bull_2023plus 2022-10-13..end, plus q4_2018 2018-09-21..2018-12-24 and tariff_2025 2025-02-20..2025-04-08.
  The drawdown episodes of the equal-weight universe will also be computed and any disagreement with these windows reported (windows are not moved).

## Execution and costs
* Decision at close t, fill at OPEN t+1, unit-based simulation (as round 1). Cash earns ^IRX. Long-only, gross <= 1, no leverage, fractional shares.
* Cost per side: 10 bp of traded notional (1 bp commission/regulatory + 9 bp half-spread / open-auction impact for S&P 500 names; pre-2001
  decimalisation spreads were wider, which is why the IS start rule usually lands after 2001 anyway). Sensitivity: 5, 20, 40 bp.
* Monthly rules fully re-equalise held names at each decision (turnover counted).

## Strategy rules (9 selection trials; N = 50 names unless stated; ties by ticker)
Month-end = last trading day of the month (SPY calendar). Returns use adjusted closes. Eligible set E_t as above.
* X1 `mom12_1`: monthly, score = C[t-21]/C[t-252] - 1; hold top 50 equal weight. (Jegadeesh-Titman 1993; Carhart 1997)
* X2 `mom12_1_mkt`: X1, but 100% cash when SPY close <= SPY SMA200 at the decision. (Cooper-Gutierrez-Hameed 2004; Daniel-Moskowitz 2016 crash risk)
* X3 `riskadj_mom`: monthly, score = (C[t-21]/C[t-252]-1) / std(daily returns t-251..t); top 50. (Barroso & Santa-Clara 2015 style vol scaling of momentum)
* X4 `high52w`: monthly, score = C[t] / max(C[t-251..t]); top 50 (closest to the 52-week high). (George & Hwang 2004)
* X5 `low_vol`: monthly, score = - std(daily returns t-251..t); top 50 = lowest volatility. (Ang et al. 2006; Baker-Bradley-Wurgler 2011)
* X6 `st_reversal_w`: weekly (last trading day of ISO week), score = - (C[t]/C[t-5] - 1); top 50 = worst week; hold one week. (Jegadeesh 1990; Lehmann 1990)
* X7 `rsi2_pullback`: daily slots, max 20 positions at 5% of equity at entry. Entry candidates: eligible, C > SMA200, Wilder RSI(2) < 5, not held;
  priority lowest RSI(2). Exit (next open) when C > SMA5 or after 10 trading days. (Connors 2008)
* X8 `volume_drift`: daily slots, max 20 x 5%. Event: V[t] > 3 x mean(V[t-50..t-1]) and C[t]/C[t-1]-1 > 4%; priority highest volume ratio; hold exactly
  20 trading days. (Gervais-Kaniel-Mingelgrin 2001 high-volume return premium; PEAD proxy)
* X9 `trend_breadth`: monthly, hold equal weight every eligible stock with C > SMA200 and SMA50 > SMA200, each capped at 2% (so < 50 qualifiers leave cash).
Benchmarks (selection = 0): SPY buy-and-hold; RSP buy-and-hold (from its start; reported where available); EW_UNIV = equal weight of the full eligible
set, monthly rebalanced, same costs; T-bills.

## Selection, nulls and multiple testing
* Primary metric: annualised excess (over T-bill) Sharpe of daily returns, net of 10 bp, ppy 252. Selected = highest IS excess Sharpe among X1-X9.
* Trial count for deflation: cumulative US programme = 7 (round 1) + 9 (round 2) = 16 selection trials. DSR (tp.research.dsr_ann logic: null variance
  1/years and robust empirical variance) reported with n = 16 and n = 9; sensitivity runs logged with selection = 0 and disclosed.
* Random-portfolio null per strategy, same eligibility, same decision dates, same number of names (X9: same count as the strategy that day),
  same costs, same market filter for X2: 200 draws for monthly/weekly rules, 100 for X7/X8 (random candidates replace the signal, same exit rules).
  p-value = (1 + #null >= strategy) / (1 + draws) on OOS excess Sharpe (and on IS for information). Bonferroni and BH (q) across the 9 OOS p-values.
* Paired block bootstrap (21-day blocks) of the daily return difference vs SPY and vs EW_UNIV, OOS.

## Forward-candidate rule for the SELECTED strategy (all must hold; failure is a valid outcome; no re-tuning afterwards)
G1 OOS excess Sharpe >= SPY's and >= EW_UNIV's.
G2 IS null-variance DSR (n = 16) >= 0.90.
G3 OOS random-null p <= 0.05 and BH q <= 0.05.
G4 OOS return in excess of EW_UNIV positive in at least 3 of the 4 named regimes (covid_crash+covid_recovery as one window 2020-02-20..2020-08-10,
   bull_2021, bear_2022, recovery_bull_2023plus).
G5 OOS excess Sharpe at 20 bp/side still >= SPY's; phase shifts (month-end -5 and -10 days; weekly -> Wednesday; daily rules n/a) keep OOS
   excess Sharpe >= 0.5 x base.
G6 Concentration: removing the 10 names with the largest summed OOS P&L contribution, OOS total return still exceeds EW_UNIV's.
Hypotheses (priors, stated so they can be wrong): H1 momentum (X1/X3/X4) beats EW_UNIV IS but not convincingly OOS; H2 low-vol (X5) has the best
IS Sharpe and the lowest MDD but lags in the 2023+ bull; H3 short-term reversal (X6) and RSI(2) (X7) do not survive 20 bp; H4 no strategy
passes G3 after BH.
