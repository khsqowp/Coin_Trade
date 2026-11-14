# Research US daily v1: rule-based US equity ETF exposure (backtest only, no orders)
Protocol: `research/us_daily_v1/PREREG_us_daily_v1.md`, sha256 `ddfdc666...f153`, hashed 2026-11-03 14:21:27 UTC (`PREREG_us_daily_v1.timestamp`), written BEFORE any strategy return was computed.
Code: `src/tp/usdata.py` (data), `research/us_daily_v1/usbt.py` (study), `research/us_daily_v1/test_usbt.py` (10 synthetic tests, all pass).
Raw outputs: `is_selection.json`, `oos_results.json`, `sensitivity.json`, `lookahead_check.json`, `data_quality.json`, `dsr_n49.json`, `equity_curves.csv` (this directory); trial registry `runs/research/us_daily_v1/trials.sqlite` (7 selection + 42 sensitivity rows, study `US1`, kept apart from the crypto registry).
Reproduce (host, isolated venv, no keys):
`cd ~/trading/pipeline && export TP_ROOT=$PWD PYTHONPATH=src && .venv_us/bin/python research/us_daily_v1/usbt.py lookahead|is|oos|sens`

## Bottom line
**The selected strategy fails the pre-registered forward-candidate rule. Recommendation: do NOT take it to the next stage as an alpha strategy.**
* Selected by in-sample Sharpe: `spy_sma200_m` (Faber 10-month/200-day SMA timing on SPY, monthly). OOS 2017-01 .. 2026-11: excess Sharpe 0.51 vs SPY buy-and-hold 0.72,
  CAGR 8.5% vs 14.9%, MDD 24.4% vs 33.7%. Bootstrap P(strategy daily mean <= SPY's) = 0.97.
* It failed G1 (OOS Sharpe below SPY's) and G2 (in-sample deflated Sharpe 0.847 < 0.90, already known before OOS was opened). It also missed the weaker "risk-overlay" label: that needs OOS Sharpe >= SPY - 0.15 = 0.57, and it got 0.51.
* No rule beat SPY buy-and-hold on OOS excess Sharpe, including rules checked in hindsight. The closest was the vol-target rule (0.71 vs 0.72), with lower drawdown (21.5% vs 33.7%) but a lower return.
* What the data does support: the trend filter worked as **insurance against slow bear markets**. Full-period MDD was 24% vs 55%, driven by 2000-02 and 2008. In 2017-2026 the bear markets were mostly V-shaped (2018 Q4, 2020, 2025), so that insurance cost about 6 percentage points of CAGR. That is a portfolio-policy question for the owner, not an edge.

## 1. Pre-registration (honest timeline)
1. Explored codebase, found `tp.news.fetch_us_daily` (Yahoo, `range=5y`, 18 symbols -> `data/ohlcv/yahoo_*`). **Correction to the task brief:** US daily data infrastructure was not zero, but it held only 5 years, which is too short for this study. It was left untouched.
2. Stooq tested first: now behind a JavaScript proof-of-work page, unusable headless. Yahoo chart API with `period1/period2` works and returns full history (yfinance not needed).
3. Built `tp.usdata`, fetched 17 series, ran data-quality checks, and looked at **benchmark-only** facts (SPY drawdown episodes, SPY calendar-year returns) to fix the regime windows.
4. Wrote and hashed the pre-registration (7 selection trials, canonical published parameters, gates G1-G5, hypotheses H1-H4).
5. Wrote the simulator and tests. Two simulator bugs were found and fixed **before any strategy run**: tiny negative cash after costs caused spurious daily micro-rebalances, and round-trip counting tracked drifting weights instead of units.
6. Ran the look-ahead check, then the IS stage only, which locked the selection. Then two cosmetic code fixes (a pandas FutureWarning, and reporting the T-bill benchmark's excess Sharpe as 0 instead of float noise). IS was re-run and verified identical. Then OOS and sensitivity were run once.
* **Nothing in the rules was changed after seeing results.** Two deviations and ambiguities are disclosed:
  * (a) Pre-registered G4 says the "covid_recovery+bull_2021 combined" capture without defining it. As a product of the two windows the capture is 45.7% (fail). As the continuous window 2020-03-24..2022-01-03 it is 51.2% (pass). Both are shown, and the verdict does not depend on this.
  * (b) The in-sample DSR on full-period data (0.93) is NOT used as a pass, because selection happened on that data.

## 2. Exact rules (reimplementable)
Common to every rule:
* **Data:** total-return-adjusted prices (Yahoo `adjclose/close` factor applied to OHLC).
* **Execution:** decision at the close of day t, fill at the open of t+1 (market-on-open). Overnight t->t+1 is earned with the old weights, and t+1 open->close with the new weights.
* **Simulation:** unit-based, so holdings drift between rebalances. Weights are set on post-cost equity.
* **Cash:** earns ^IRX/100/252 per trading day, using the prior day's yield.
* **Exposure:** long-only, maximum gross 1.0, no stops.
* **Calendar:** month-end = last trading day of the month in the SPY calendar. Week-end = last trading day of the ISO week.

| id | rule |
|---|---|
| T1 `spy_sma200_m` **(selected)** | At month-end: SPY weight 1 if close > SMA200(close), else 0 (cash). |
| T2 `spy_absmom12_m` | At month-end: SPY weight 1 if the 252-day SPY return exceeds the compounded T-bill return over the same 252 days, else 0. |
| T3 `spy_voltgt_w` | At week-end: sigma = std(20 daily returns) x sqrt(252). Weight = min(1, 0.15/sigma). Trade only if \|target - current\| >= 0.05. |
| T4 `spy_sma200_voltgt_w` | At week-end: T3 weight if the latest month-end T1 state is ON, else 0. Same 0.05 band. |
| T5 `sector_dm3_m` | At month-end: score = close[t-21]/close[t-252] - 1 for the 9 original SPDR sectors. Top 3 get 1/3 each; a slot goes to cash if its score <= the T-bill return over the same window. Ties broken alphabetically. |
| T6 `sector_dm3_trend_m` | T5, but everything goes to cash when the T1 state is OFF at the decision. |
| T7 `spy_rsi2_mr` | Daily. Wilder RSI(2): if flat and close > SMA200 and RSI2 < 10, weight 1. If long and close > SMA5, weight 0. |

Costs: 5 bp per side on traded notional.
* 1 bp for commission and regulatory fees (IBKR-style $0.0035/share, SEC Section 31 fee and FINRA TAF).
* 4 bp for slippage and half-spread versus the official open. SPY's half-spread is < 0.2 bp and the sector SPDRs are roughly 0.5-3 bp, so this is deliberately conservative.
* No borrow cost, since there is no shorting or leverage.

Selection rule: highest IS (2000-01-03..2016-12-30) annualised Sharpe of daily excess returns over T-bills, net of costs.

## 3. In-sample vs out-of-sample (net of 5 bp/side; Sharpe = excess over T-bills, ppy 252)
IS 2000-01-03 .. 2016-12-30 (17.0 y). OOS 2017-01-03 .. 2026-11-02 (9.8 y). 7 selection trials (disclosed and logged); 42 further sensitivity runs (selection = 0).

| rule | IS Sharpe | IS CAGR | IS MDD | OOS Sharpe | OOS CAGR | OOS MDD | OOS exposure | OOS fills | OOS round trips / win rate | OOS cost drag/yr |
|---|---|---|---|---|---|---|---|---|---|---|
| **T1 spy_sma200_m (selected)** | **0.587** | 8.3% | 17.3% | **0.514** | 8.5% | 24.4% | 0.83 | 20 | 9 / 56% | 0.10% |
| T2 spy_absmom12_m | 0.444 | 6.7% | 18.7% | 0.590 | 11.2% | 33.7% | 0.86 | 6 | 2 / 50% | 0.03% |
| T3 spy_voltgt_w | 0.262 | 4.4% | 44.5% | 0.709 | 11.6% | 21.5% | 0.90 | 115 | n/a (never flat) | 0.07% |
| T4 spy_sma200_voltgt_w | 0.556 | 7.3% | 16.3% | 0.447 | 7.3% | 21.2% | 0.79 | 90 | 10 / 60% | 0.13% |
| T5 sector_dm3_m | 0.400 | 7.0% | 30.4% | 0.657 | 13.6% | 30.3% | 0.98 | 424 | 72 / 61% | 0.27% |
| T6 sector_dm3_trend_m | 0.557 | 8.1% | 19.1% | 0.452 | 8.0% | 23.0% | 0.82 | 382 | 85 / 57% | 0.31% |
| T7 spy_rsi2_mr | 0.420 | 4.1% | 15.0% | 0.394 | 4.9% | 9.7% | 0.11 | 173 | 86 / 69% | 0.88% |
| B1 SPY buy-and-hold | 0.234 | 4.4% | 55.2% | **0.724** | 14.9% | 33.7% | 1.00 | 0 | - | - |
| B2 QQQ buy-and-hold | 0.152 | 1.9% | 83.0% | 0.818 | 20.3% | 35.1% | 1.00 | 0 | - | - |
| B3 equal-weight 9 sectors, monthly | 0.344 | 6.5% | 53.5% | 0.676 | 13.3% | 36.7% | 1.00 | 1071 | - | 0.02% |
| B4 T-bills | 0 | 1.6% | 0 | 0 | 2.5% | 0 | 0 | 0 | - | - |

Multiple-testing correction for the selected rule. The replicated `tp.research.dsr_ann` logic was applied; the module itself was not imported because `tp.research` pulls crypto-only dependencies.

| quantity | value | note |
|---|---|---|
| IS DSR (null variance 1/years, n = 7) | **0.847** | SR0 = 0.337 annualised, below the 0.90 gate |
| IS DSR (robust empirical variance, n = 7) | 0.928 | |
| IS DSR (n = 49, counting every logged run) | 0.559 | SR0 = 0.551 |
| OOS PSR(0) | 0.944 | |
| OOS DSR (null, n = 7) | 0.587 | |
| OOS DSR (n = 49) | 0.258 | |
| OOS paired block bootstrap vs SPY, mean daily difference | annualised 95% CI [-13.7%, +0.35%] | P(<= 0) = 0.97 |

The four best IS Sharpes were 0.587, 0.557, 0.556 and 0.444. The "selection" among the top three is statistically a coin flip.

### Pre-registered gates for the selected rule

| gate | result | verdict |
|---|---|---|
| G1: OOS Sharpe >= 0.5 and >= SPY's | 0.514 vs 0.724 | **FAIL** |
| G2: IS null DSR >= 0.90 | 0.847 | **FAIL** |
| G3: OOS MDD <= 25% | 24.4% | pass (barely) |
| G4: in-window MDD below SPY's in covid_crash and bear_2022 | 12.1% vs 33.4%; 17.3% vs 24.5% | pass |
| G4: bull capture >= 50% in covid_recovery + bull_2021 | 45.7% as a product of windows / 51.2% as one continuous window | ambiguous |
| G4: bull capture >= 50% in recovery_bull_2023plus | 48.2% vs 122.2% = 39% | **FAIL** |
| G5: OOS Sharpe > 0 at 25 bp/side | 0.481 | pass |
| G5: OOS Sharpe >= 0.5 x base under phase shifts | 0.571 at -5 days, 0.713 at -10 days | pass |

**Overall: FAIL.**

### Hypotheses

| hypothesis | result | verdict |
|---|---|---|
| H1: T1/T2 cut full-period MDD by >= 40% but don't beat SPY's OOS Sharpe | T1 MDD -56%, T2 -39%; neither beats SPY OOS | supported for T1, T2 just short |
| H2: vol targeting beats SPY's Sharpe both IS and OOS | IS 0.262 vs 0.234 (marginal); OOS 0.709 vs 0.724; full-period MDD 44.5% (no protection in slow bears) | not supported OOS |
| H3: sector rotation does not beat SPY OOS | 0.657 vs 0.724; also below equal-weight sectors at 0.676 | supported |
| H4: RSI(2) mean reversion degrades OOS and is the most cost-sensitive rule | IS 0.42 was never "high"; it degraded only a little OOS (0.39); it is the most cost-sensitive rule, with Sharpe below 0 at 25 bp/side | partly supported |

## 4. Per-regime breakdown (total return / max drawdown inside the window; dates verified from SPY closes in the data)
SPY drawdown episodes >= 10% found in the data: 2000-03-24 -> 2002-10-09 (-47.5%), 2007-10-09 -> 2009-03-09 (-55.2%), 2015-07-20 -> 2016-02-11 (-13.0%), 2018-09-20 -> 2018-12-24 (-19.3%), 2020-02-19 -> 2020-03-23 (-33.7%, new high 2020-08-10), 2022-01-03 -> 2022-10-12 (-24.5%, new high 2023-12-13), 2025-02-19 -> 2025-04-08 (-18.8%).

| window | dates | T1 selected | T2 absmom | T3 voltgt | T5 sector | T7 rsi2 | SPY | QQQ |
|---|---|---|---|---|---|---|---|---|
| dotcom_bust (IS) | 2000-03-24..2002-10-09 | -4.9% / 11.4% | -11.7% / 14.7% | -42.0% / 43.7% | -24.8% / 30.4% | +12.1% / 7.8% | -47.2% / 47.5% | -82.7% / 83.0% |
| bull_03_07 (IS) | 2002-10-10..2007-10-09 | +85.6% / 9.1% | +71.8% / 9.1% | +95.5% / 10.0% | +111.8% / 12.8% | +19.7% / 5.8% | +119.0% / 14.2% | +171.0% / 17.3% |
| gfc (IS) | 2007-10-10..2009-03-09 | -4.6% / 9.8% | -10.4% / 15.9% | -35.9% / 35.9% | -17.0% / 24.4% | +3.9% / 0.2% | -55.2% / 55.2% | -51.6% / 53.4% |
| bull_09_15 (IS) | 2009-03-10..2015-07-20 | +127.0% / 17.3% | +129.4% / 18.6% | +161.8% / 16.3% | +132.4% / 20.2% | +32.2% / 15.0% | +256.8% / 18.6% | +373.9% / 16.1% |
| chop_15_16 (IS) | 2015-07-21..2016-12-30 | -2.4% / 13.4% | -6.3% / 18.3% | +6.6% / 11.3% | +0.5% / 13.6% | +1.6% / 2.9% | +8.6% / 12.8% | +5.7% / 16.1% |
| q4_2018 | 2018-09-21..2018-12-24 | -21.8% / 21.7% | -19.4% / 19.3% | -15.5% / 15.4% | -19.3% / 20.0% | -2.8% / 6.1% | -19.4% / 19.3% | -22.0% / 22.7% |
| covid_crash | 2020-02-20..2020-03-23 | -11.9% / 12.1% | -33.7% / 33.4% | -21.5% / 21.2% | -30.3% / 30.1% | -4.5% / 8.6% | -33.7% / 33.4% | -27.9% / 27.9% |
| covid_recovery | 2020-03-24..2020-08-10 | +11.0% / 7.0% | +31.3% / 7.0% | +16.7% / 4.8% | +42.7% / 6.7% | +1.8% / 1.4% | +51.2% / 7.0% | +58.9% / 5.1% |
| bull_2021 | 2021-01-04..2022-01-03 | +29.5% / 5.1% | +29.5% / 5.1% | +27.2% / 5.1% | +26.0% / 7.6% | +9.5% / 4.1% | +29.5% / 5.1% | +28.7% / 10.9% |
| bear_2022 | 2022-01-04..2022-10-12 | -16.5% / 17.3% | -12.7% / 13.5% | -19.8% / 19.8% | -4.3% / 13.8% | -2.1% / 5.9% | -24.5% / 24.5% | -34.3% / 33.4% |
| recovery_bull_2023plus | 2022-10-13..2026-11-02 | +48.2% / 10.0% | +82.5% / 18.8% | +89.5% / 16.6% | +90.3% / 17.0% | +35.9% / 5.0% | +122.2% / 18.8% | +165.5% / 22.8% |
| tariff_2025 (inside the above) | 2025-02-20..2025-04-08 | -8.8% / 9.7% | -18.8% / 18.4% | -16.6% / 16.2% | -15.3% / 14.6% | -0.6% / 2.9% | -18.8% / 18.4% | -22.8% / 22.4% |

Reading for the selected rule:
* It protects well in **slow** bears (dot-com, GFC, and most of 2022).
* In 2018 Q4 it was hurt more than SPY (-21.8% vs -19.4%): a monthly whipsaw sold on 2018-11-01, bought back 2018-12-03 just before the December leg down, then sold again 2019-01-02 near the low.
* On a calendar-2022 basis it lost **more** than SPY (-20.7% vs -18.2%), because of re-entries on 2022-04-01 and 2022-12-01.
* In OOS it was out of the market in Mar-May 2020, Jan 2023, Nov 2023, Apr-May 2025 and Apr 2026, and missed most of each rebound.

OOS calendar years (T1 / SPY):

| year | T1 | SPY |
|---|---|---|
| 2017 | +21.7% | +21.7% |
| 2018 | -7.4% | -4.6% |
| 2019 | +6.7% | +31.2% |
| 2020 | +15.5% | +18.3% |
| 2021 | +28.7% | +28.7% |
| 2022 | -20.7% | -18.2% |
| 2023 | +10.7% | +26.2% |
| 2024 | +24.9% | +24.9% |
| 2025 | +12.3% | +17.7% |
| 2026 YTD | +1.0% | +11.2% |

## 5. Benchmarks
See the tables above (same windows, same cost model). SPY buy-and-hold had the best OOS Sharpe of any SPY-based rule. QQQ (0.82) beat everything in OOS, but QQQ had a 0.15 IS Sharpe and an 83% drawdown, so choosing it now would be pure hindsight. The full-period ordering (2000-2026) is the reverse of the OOS ordering:

| | T1 | SPY |
|---|---|---|
| Full-period Sharpe | 0.56 | 0.40 |
| Full-period MDD | 24% | 55% |
| Full-period CAGR | 8.35% | 8.13% |

So the answer depends almost entirely on whether the evaluation window contains a slow bear market.

## 6. Why this might still be overfit or fragile
* **Multiple testing / selection noise.**
  * 7 pre-registered selection trials, plus 42 logged sensitivity runs. With all 49 counted, IS DSR is 0.56.
  * The top three IS Sharpes are within 0.03 of each other.
  * Rebalance phase: shifting T1's decision day by 5 or 10 trading days moves its IS Sharpe from 0.587 to 0.44 / 0.36. Under a different phase convention, a different rule would have been "selected". The house crypto round 3 found the same phase lottery.
* **Literature / knowledge snooping.** All rule families and parameters are published (Faber 2007, Antonacci, Moskowitz-Ooi-Pedersen 2012, Moreira-Muir 2017, Connors 2008). Those authors fit them on data overlapping this IS period. I also know the broad market history to 2025. The IS period is therefore not clean; the OOS (2017+) is post-publication for every rule. This bias favours the strategies, and they still lost OOS.
* **Regime dependency.**
  * The trend filters' entire advantage comes from 2000-02 and 2008. The OOS sample has one slow bear (2022) and three V-shaped shocks, which is the worst case for monthly trend rules.
  * A ~10-year OOS with only 9 round trips cannot distinguish "the edge decayed" from "this decade had no slow bear". Neither the positive nor the negative result is strong evidence either way.
* **Cost-model risk.**
  * Low turnover makes T1-T4 insensitive to costs (T1's OOS Sharpe is 0.48 even at 25 bp/side).
  * T7 is cost-fragile: Sharpe 0.54 at 0 bp, 0.25 at 10 bp, below 0 at 25 bp.
  * Not modelled: opening-auction price impact for large size, minimum commissions on small accounts (IBKR $0.35 is about 3.5 bp on a $1,000 order), fractional-share availability, **taxes** (a Korea-resident investor pays 22% on annual overseas gains above KRW 2.5M; frequent trend exits realise gains and lower after-tax CAGR further), and **KRW/USD FX** (both the return and the hedging decision are omitted).
  * Cash is assumed to earn the 13-week T-bill yield with no friction.
* **Data-source quality** (Yahoo, unofficial, key-less, can change or break without notice).
  * Checked:
    * zero NaN, duplicate or non-positive rows in all 14 ETFs;
    * zero OHLC inconsistencies;
    * zero sessions missing against the SPY calendar;
    * no adjustment-factor jumps > 5%;
    * every flagged > 15% daily move matched a known real event (QQQ/XLK on 2001-01-03; XLE/XLF in 2008-09 and on 2020-03-09);
    * SPY adjusted total return trails ^SP500TR by a mean of 0.10%/yr, which matches SPY's 0.0945% expense ratio;
    * calendar-year SPY returns match published SPY total returns;
    * the SPY/^GSPC price ratio stays between 0.0978 and 0.1014.
  * Caveats:
    * Daily SPY vs ^SP500TR correlation is only 0.988 (99th-percentile absolute daily difference 0.77%), lower than expected. Likely a timestamp/stale-print issue in the index series; not investigated further.
    * XLI has one zero-volume day.
    * ^IRX has 31 NaN days (forward-filled) and tiny negative prints.
    * Dividends are reinvested at the ex-date close (Yahoo's convention), not on the pay date.
    * There is no second independent vendor: Stooq is blocked. **A red-team check against a second source (e.g. Tiingo or Nasdaq Data Link with a free key) is recommended.**
* **Survivorship.**
  * The 9 original sector SPDRs are a complete partition of the S&P 500 at launch, and all still trade, so there is no symbol survivorship among them. SPY and QQQ are indices that rebalance away their own losers, which is the instrument working as designed rather than a bias.
  * Residual biases: XLRE (2015) and XLC (2018) are excluded, and the 2018 GICS change moved GOOGL/META out of XLK/XLY. Choosing US equities at all (the best-performing major market in this sample) is itself a market-level selection.
* **Implementation details that could flip small differences.** Market-on-open fills at the official open, signals at the close then a fill at the next open (verified with a look-ahead test: an IS run cut at 2016-12-30 reproduces the full run bit-for-bit for all 11 series), fractional shares, and month-end defined on the SPY calendar.

## 7. Recommendation
* **Not worth taking forward as a return-enhancing strategy.** The pre-registered selection failed G1 and G2, and no rule in the family beat buy-and-hold SPY on OOS risk-adjusted return. I am not proposing a re-tuned variant. That would be the overfitting the protocol exists to prevent, and the honest conclusion is "no evidence of edge over SPY in this family on 2017-2026".
* What could legitimately go to review, explicitly as a **risk-policy option and not alpha**: whether the owner wants drawdown insurance (T1: full-period MDD 24% vs 55%) at a cost of roughly 6 pp/yr of CAGR in V-shaped decades. That is a preference decision for the owner.
* If a round 2 happens, it should be pre-registered fresh, for example on:
  * (a) a multi-asset version (trend on SPY/EFA/TLT/GLD, where trend-following's documented edge is diversification across assets rather than timing one index);
  * (b) longer daily history (^SP500TR from 1988, or Ken French data back to 1926) so that more than three slow bears are in the test.
  These are ideas only; nothing was run on them.

## 8. `tp.usdata` (new module, `src/tp/usdata.py`)
* **What it fetches:** full daily history for an explicit symbol list from `https://query1.finance.yahoo.com/v8/finance/chart/<SYM>` (`period1/period2`, `interval=1d`, `events=div,split`). It stores the raw vendor fields (split-adjusted OHLC, `adjclose`, volume) and the dividend/split events, so adjustments can be audited. `adjusted()` derives total-return OHLC.
* **Cache and provenance:** written to `data/us_daily/<SYM>.parquet`, with `<SYM>.meta.json` (url, fetched_at UTC, sha256 of the response body, rows, first/last date) and `<SYM>.events.json`. A cache younger than 20 h is served without network. `load()` is cache-only.
* **Rate-limit discipline:** one request per symbol, at least 2 s between requests, a maximum of 4 tries with backoff on 429/5xx (honours Retry-After, capped at 300 s), no retry on other 4xx, and one failing symbol does not stop the rest.
* **Completeness:** the bar of the current session is dropped until 16:30 America/New_York (the same rule as `tp.news`). Dates are NY session dates, not UTC dates.
* **Safety:** there is **no order code, no broker, and no key or secret handling**. A path allow-list (`/v8/finance/chart/` only) raises on anything else; a test asserts this, plus the absence of order/post/key strings.
* **Integration:** not wired into `tp.news`, the scheduler, the forward tracker or the export.
* **Not a point-in-time database:** it serves today's view of history and has no delisted tickers.
* **Environment:**
  * Isolated venv `~/trading/pipeline/.venv_us`: pandas 2.2.3, numpy 2.0.2, scipy 1.13.1, pyarrow 21, requests, pytest.
  * The venv holds its own `.gitignore` (`*`), so no repository file was modified.
  * The Docker image and the system Python were not touched. Note: `pyarrow` is not in the container image, so running this module inside the `tp` containers would need an image change. Out of scope here.

Files added in this round (none committed): `src/tp/usdata.py`, `research/us_daily_v1/*`, `data/us_daily/*` (gitignored), `runs/research/us_daily_v1/*` (gitignored), `.venv_us/` (self-ignored).
Untouched: `~/trading/freqtrade/`, all Docker containers, `.env` and secrets, the crypto trial registry, the forward tracker and the export.
