# KR-daily-v1: Korean equities, daily bars, long-only (round 1 research report)

**Status:** research only. Nothing was registered for forward tracking and no order code was added.

## Bottom line

**Recommendation: none of the 8 strategies goes to the next review stage as a trading strategy.**

- **The strategy picked on the in-sample (IS) period fails the pre-registered gate.** The pick was T2: hold KODEX 200 (069500) when its 12-month return is positive, otherwise cash.
  - It fails 4 of the 6 gate criteria.
  - Its out-of-sample (OOS) Sharpe is 0.69, against 0.76 for buy-and-hold.
  - Its full-period deflated Sharpe (DSR, which corrects for the number of strategies tried) is 0.72, below the 0.90 bar.
  - Its maximum drawdown (MDD) is 41.9%, above the 35% cap.
- **None of the 8 strategies beats simply holding KODEX 200 by a margin that can be told apart from noise.**
  - The best full-period DSR is 0.80 (T3). Buy-and-hold itself scores 0.78 on the same test.
  - For every strategy, the 90% bootstrap confidence interval (CI) of OOS excess return over buy-and-hold either contains zero or is entirely negative.
- **The IS selection was effectively a coin flip.** T2's IS Sharpe was 0.417, against 0.387 for buy-and-hold and 0.385 for T3. Shifting the rebalance dates by 5 trading days drops T2's IS Sharpe to 0.19 and changes which strategy would have been picked.
- **No strategy is robust across market conditions.** Every one has a negative Sharpe in falling markets and lags buy-and-hold in sideways markets.

## 1. Pre-registration and what was disclosed

The rules are in `PREREG_kr_daily_v1.md` (sha256 `62d35359...73ddb2`, hashed 2026-11-03 14:22 UTC). That was before the full-history download and before any strategy was run.

The date ranges for bull, bear and sideways markets are in `REGIMES.json` (sha256 `5c1b7262...49b82d`, hashed 14:27 UTC). They were also fixed before any strategy run, using the KODEX 200 price path only.

**No rule, parameter, universe, cost or date window was changed after seeing results.**

Things done that the pre-registration did not list:
- A test that shifts all rebalance dates by 5 trading days. It was written into the code before the first run, but not named in the pre-registration.
- Two extra splits added after seeing results, for information only: "OOS without 2026" and "2026 only".
- Synthetic correctness tests for the simulator.

What I had seen before writing the pre-registration:
- An availability check (`probe.py`) that returned only names and row counts. No prices or returns.
- My own general knowledge of KOSPI history. That counts as soft data snooping (see section 6, point 1).

## 2. Exact rules (enough to reimplement)

**Data**
- Source: KIS paper-trading daily chart with `FID_ORG_ADJ_PRC=0`, which is split-adjusted.
- Prices only. Dividends and ETF distributions are not included.
- Trading calendar is that of 069500.
- A missing or zero open is replaced by the previous close. Prices are carried forward through trading halts.

**Execution**
- Signals use the close of day t. Orders fill at the open of day t+1.
- Portfolio value is marked close-to-close.
- Fractional shares in the main run (whole-share version under Sensitivities).
- An instrument is traded only when its target weight changes. Sells execute first, then buys are scaled to the available cash.

**Costs per side**

| instrument | slippage | commission | sell tax |
|---|---|---|---|
| 069500 (KODEX 200) | 0.03% | 0.015% | none |
| 114260 (3-year government bond ETF) | 0.05% | 0.015% | none |
| TIGER 200 sector ETFs | 0.20% | 0.015% | none (ETFs are exempt) |
| individual stocks | 0.10% | 0.015% | 0.20% (more conservative than the house 0.18%) |

Cash earns 0%.

**Definitions**
- "Month-end" is the last trading day of the calendar month.
- "12-1 momentum" is the price 21 trading days ago divided by the price 252 trading days ago, minus 1. This is the 12-month return skipping the most recent month.

**The 8 strategies** (none uses a stop-loss)

| id | universe | rule |
|---|---|---|
| T1 | 069500 | At month-end, hold 100% if the close is above the average of the last 10 month-end closes, otherwise cash |
| T2 | 069500 | At month-end, hold 100% if the 12-month return is above 0, otherwise cash |
| T3 | 069500 | On the last trading day of each week, set the weight to min(1, 0.15 / (20-day volatility x sqrt(252))). Trade only if the new weight differs from the current one by at least 0.10 |
| T4 | 069500 | Daily. Enter when the close is above its 200-day average and the 2-day RSI is below 10. Exit when the close is above its 5-day average |
| T5 | the 8 TIGER 200 sector ETFs (139220-139290) | At month-end, hold the top 3 by 12-1 momentum at 1/3 each. A slot whose momentum is 0 or below stays in cash |
| T6 | same | T5, but everything goes to cash when T1's market filter is off |
| T7 | the 10 largest KOSPI stocks at end-2010, frozen: 005930, 005490, 005380, 009540, 012330, 051910, 055550, 105560, 032830, 000270 | Same logic as T5 |
| T8 | same | T7 plus T1's market filter |

**Benchmarks**
- B1: KODEX 200 buy-and-hold.
- B2: the 8 sector ETFs equal-weighted, rebalanced monthly, with costs.
- B3: the 10 stocks equal-weighted, rebalanced monthly, with costs.

**Why this universe**
- The sector ETFs are a complete family (all 8 listed together in April 2011), not a hand-picked subset. A sector ETF carries no single-company survivorship bias.
- The stock list is point-in-time and fixed 1.5 years before the backtest window starts. It includes companies that later lagged badly, such as POSCO, Hyundai Heavy, Samsung Life and LG Chem.
- The already-cached symbols were deliberately not used. 373220 listed in 2022 and 207940 in 2016, so choosing them is hindsight.

**Window**
- Full window: 2012-06-01 to 2026-11-03 (3,553 trading days).
- IS: 2012-06 to 2019-12. OOS: 2020-01 to 2026-11.
- Selection trials: 8, logged in a separate `trials.sqlite`, so the crypto registry is untouched.

## 3. IS vs OOS (main cost assumptions)

Sharpe is annualised with sqrt(252) and no risk-free rate, the house convention. DSR uses the house null-variance method with 8 trials. The Sharpe a strategy must clear to count as skill is 0.54 for IS, 0.57 for OOS and 0.39 for the full period.

| | IS Sharpe | IS ret | IS MDD | OOS Sharpe | OOS ret | OOS MDD | Full Sharpe | Full CAGR | Full MDD | Full DSR | round trips | win rate | yearly cost |
|---|---|---|---|---|---|---|---|---|---|---|---|---|---|
| T1 | -0.07 | -7% | 25.5% | 0.86 | +273% | 41.9% | 0.54 | 9.2% | 41.9% | 0.72 | 17 | 29% | 0.11% |
| **T2 (IS pick)** | **0.42** | +28% | 12.9% | **0.69** | +178% | 41.9% | 0.55 | 9.4% | 41.9% | **0.72** | 12 | 42% | 0.09% |
| T3 | 0.39 | +34% | 22.4% | 0.81 | +126% | 31.5% | 0.61 | 8.2% | 31.5% | 0.80 | 1 | n/a | 0.10% |
| T4 | -0.02 | -1% | 8.5% | 0.24 | +19% | 23.0% | 0.16 | 1.2% | 23.0% | 0.18 | 90 | 61% | 0.61% |
| T5 | 0.31 | +25% | 27.5% | 0.75 | +201% | 37.7% | 0.56 | 9.9% | 37.7% | 0.74 | 82 | 48% | 1.22% |
| T6 | 0.17 | +8% | 17.8% | 0.69 | +160% | 39.1% | 0.49 | 7.7% | 39.1% | 0.64 | 83 | 48% | 1.04% |
| T7 | -0.20 | -32% | 39.2% | 0.62 | +186% | 49.6% | 0.31 | 4.9% | 62.4% | 0.38 | 102 | 42% | 0.84% |
| T8 | -0.34 | -33% | 40.3% | 0.69 | +212% | 49.5% | 0.34 | 5.3% | 49.5% | 0.42 | 89 | 42% | 0.82% |
| B1 | 0.39 | +36% | 23.1% | 0.76 | +244% | 41.9% | 0.59 | 11.6% | 41.9% | 0.78 | - | - | ~0 |
| B2 | 0.09 | +2% | 27.5% | 0.68 | +157% | 42.1% | 0.44 | 7.1% | 53.6% | 0.58 | - | - | 0.16% |
| B3 | 0.08 | 0% | 32.7% | 0.67 | +172% | 44.5% | 0.43 | 7.4% | 52.2% | 0.56 | - | - | 0.22% |

**Two points for the reviewer**
- **The house's alternative "empirical-variance" DSR is not stricter here.** With only 8 closely related trials it comes out higher, and even buy-and-hold scores 0.94 on it. The null-variance DSR above is the one that matters.
- **The win rates for T1 and T2 mean nothing statistically.** They rest on 12-17 round trips over 14 years.

**OOS excess return over buy-and-hold** (annualised, 90% block-bootstrap CI)

| strategy | 90% CI |
|---|---|
| T1 | [-7.5%, +8.0%] |
| T2 | [-12.8%, +3.8%] |
| T3 | [-19.3%, -0.9%] |
| T4 | [-36.4%, -3.4%] |
| T5 | [-13.6%, +7.6%] |
| T6 | [-16.8%, +5.6%] |
| T7 | [-14.0%, +12.5%] |
| T8 | [-14.5%, +12.5%] |

**Gate result for T2**

| criterion | value | result |
|---|---|---|
| (a) OOS Sharpe at least 0.5 | 0.69 | pass |
| (b) OOS Sharpe at least B1's (0.76), or at least 80% of it with MDD at most 25.2% | 0.69, with MDD 41.9% | **fail** |
| (c) full-period DSR at least 0.90 | 0.72 | **fail** |
| (d) full-period MDD at most 35% | 41.9% | **fail** |
| (e) beats B1 in every bear window, and positive Sharpe in at least 2 of 3 market types | ties B1 in all three 2026 bear windows because it stayed fully invested | **fail** |
| (f) OOS Sharpe at least 0.4 with doubled slippage | 0.69 | pass |

As pre-registered, no other strategy is promoted in its place.

**Hypotheses**

| hypothesis | outcome | detail |
|---|---|---|
| H1: T1/T2 cut MDD by at least a third vs B1, both IS and OOS | **rejected** | IS: T2 yes (12.9% vs 23.1%), T1 no (25.5% vs 23.1%). OOS: both 41.9%, same as B1. The monthly signal stayed fully long through the 38-day, -40.8% crash in mid-2026. |
| H2: T1/T2 lag B1 in sideways markets | **supported** | T1 lost 20% in 2012-16 while B1 gained 10% |
| H3: T5 beats B2 on OOS Sharpe | **weakly supported** | 0.75 vs 0.68, and 0.31 vs 0.09 IS. But it never beat B1. |
| H4: T7/T8 show no real edge | **supported** | |
| H5: T4 is positive both IS and OOS | **rejected** | IS Sharpe -0.02. In 2008-12 it had Sharpe 0.59 with 71% winners, so the effect appears to have faded. |

## 4. Results by market condition

**How the date ranges were set** (from the KODEX 200 path only)
- A bear market is a fall of at least 20% from peak to trough.
- A bull market is a rise of at least 40% from a trough.
- A sideways market is a 12-month stretch that stays within +-15% of its average.

Two judgment calls are flagged in `REGIMES.json`:
- The 2016-18 bull is about +37% on month-end closes, just under the 40% rule. It is the only bull in IS.
- 2023-24 is labelled sideways, although it sits inside a slow +47% rise.

**Total return by window**

| window | dates | B1 | T1 | T2 | T3 | T5 |
|---|---|---|---|---|---|---|
| sideways IS ("Boxpi") | 2012-06 -> 2016-10 | +9.6% | -19.9% | -2.3% | +7.0% | +15.8% |
| bull IS | 2016-11 -> 2018-01 | +36.3% | +36.3% | +36.3% | +36.3% | +33.6% |
| bear IS | 2018-01 -> 2019-08 | -23.1% | -22.0% | -10.8% | -22.4% | -27.5% |
| bear (COVID) | 2020-01 -> 2020-03 | -34.6% | -11.8% | -11.8% | -23.4% | -19.9% |
| bull | 2020-03 -> 2021-07 | +125.5% | +67.2% | +67.2% | +70.9% | +60.8% |
| bear | 2021-07 -> 2022-09 | -34.3% | -9.1% | -15.8% | -31.5% | -13.6% |
| sideways OOS | 2023-01 -> 2024-06 | +35.0% | +12.3% | +15.9% | +28.4% | +20.0% |
| bear | 2024-07 -> 2025-04 | -21.6% | -14.3% | -17.5% | -18.2% | +0.7% |
| bull | 2025-04 -> 2026-02 | +212.6% | +182.2% | +128.4% | +123.0% | +155.0% |
| bear | 2026-02 -> 2026-03 | -20.6% | -20.6% | -20.6% | -7.8% | -16.7% |
| bull | 2026-04 -> 2026-06 | +97.6% | +97.6% | +97.6% | +21.8% | +59.6% |
| bear | 2026-06 -> 2026-07 | -40.8% | -40.8% | -40.8% | -8.9% | -37.5% |
| bear (still running) | 2026-09 -> 2026-10 | -24.0% | -24.0% | -24.0% | -10.5% | -17.4% |

**Sharpe by market type** (strategy / B1)

| strategy | bull | bear | sideways |
|---|---|---|---|
| T1 | 3.21 / 3.41 | -1.82 / -2.17 | -0.12 / 0.56 |
| T2 | 2.98 / 3.41 | -1.69 / -2.17 | 0.26 / 0.56 |
| T3 | 3.43 / 3.41 | -2.15 / -2.17 | 0.50 / 0.56 |
| T5 | 2.61 / 3.41 | -1.52 / -2.17 | 0.50 / 0.56 |

The trend rules help only in slow declines such as 2021-22. They cannot react to 1-2 month crashes, and they lose heavily when the market rebounds sharply.

**Before the window (2008-06 -> 2012-05, KODEX 200 only, for information)**

| | B1 | T1 | T2 | T3 | T4 |
|---|---|---|---|---|---|
| Sharpe | 0.22 | 0.38 | 0.11 | 0.17 | 0.59 |
| MDD | 48.7% | 25.7% | 30.4% | 26.2% | 10.0% |

**2026 dominates the OOS period, and it is real, not a data error.**
- KODEX 200 rose +213%, then +98% in 83 days, then fell 40.8% in 38 days.
- On 2026-07-31 KOSPI rose +17.91%, its largest one-day gain ever (newsis 2026-07-31, SBS Biz).
- Samsung's close that day, 262,500, matches the KIS data exactly.
- There were 40 days with moves above 5% in 2026, against 0-3 in a normal year.

**Splits added after seeing results** (Sharpe / MDD, for information only)

| | OOS without 2026 | 2026 only |
|---|---|---|
| B1 | 0.79 / 34.6% | 1.05 / 41.9% |
| T1 | 1.09 / 16.5% | 1.05 / 41.9% |
| T2 | 0.74 / 23.5% | 1.05 / 41.9% |
| T3 | 0.70 / 31.5% | 1.44 / 14.7% |
| T5 | 0.86 / 27.6% | 0.80 / 37.7% |

T1's attractive "OOS without 2026" figure is exactly the hindsight cut that must not drive a selection. Its IS Sharpe was -0.07.

## 5. Sensitivities (not used for selection)

| test | result |
|---|---|
| Slippage x2 | T2 OOS Sharpe 0.69, T3 0.81, T5 0.72 (costs rise to 2.2% a year) |
| Slippage x3 | T5 OOS 0.68 (costs 3.1% a year), T4 0.19 |
| Stock sell tax 0.30% | T7/T8 change by less than 0.01 |
| Cash held in the 3-year bond ETF (114260) instead of 0% | T2 Sharpe: IS 0.58, OOS 0.70, full 0.59, only equal to B1's 0.59. T3 OOS 0.83. |
| Whole shares at 10M KRW | every Sharpe changes by 0.03 or less |
| Rebalance 5 trading days later | T2 IS falls from 0.42 to 0.19. T5 IS rises from 0.31 to 0.37 and would have been the pick. T7 OOS falls from 0.62 to 0.50. |

Cost risk is low for the index rules because ETFs pay no sell tax. It matters for sector rotation, where spreads on the thin sector ETFs dominate. Picking a different strategy after a small date shift is the same instability the crypto round-3 study found.

## 6. Why this might still be overfit or fragile

1. **The real number of trials is higher than 8.**
   - My prior knowledge of KOSPI history (the 2011-16 "Boxpi" range, the 2020 crash, the 2025 rally) shaped which families seemed reasonable.
   - The 8 rules are textbook picks from a large published literature, much of it tested on overlapping KOSPI data.
   - Lookback lengths, rebalance day and timing are researcher choices held at textbook values, but alternatives exist.
   - With an honest count in the dozens, every DSR falls further below 0.9.
2. **The IS selection is noise.** The top three IS Sharpes are within 0.03 of each other, while the standard error over 7.6 years is about 0.36. A 5-day shift changes the pick.
3. **The results depend on one regime.** The OOS ranking is largely decided by about 10 months of an unprecedented semiconductor-led boom and crash in 2025-26. Monthly trend rules cannot react to 33-38-day crashes after a +200% run-up.
4. **Data risks.**
   - **Prices only.** KODEX 200 pays about 1.5-2% a year in distributions. Leaving them out hurts buy-and-hold more than the timing rules, so the true gap to B1 is probably larger than shown.
   - **The KIS paper-trading data is not vendor-grade.** Only the 2026-07-31 day was checked against news.
   - **009540 (Hyundai Heavy)** drops -28.8% on 2017-12-27, possibly an unadjusted rights-issue date. This is unresolved and affects T7, T8 and B3.
   - **The sector ETFs have many zero-volume days** (139240 has 253 since 2012, 139270 has 88), yet the simulator lets T5/T6 trade on them.
   - **Halts:** Samsung (3 days in 2018) and Hyundai Heavy (25 days in 2017) were halted. It was not checked whether any simulated trade fell on a halt day.
   - **The end-2010 top-10 list comes from a news-search summary** and was not checked against KRX.
5. **Cost-model risk.**
   - The 0.20% slippage on sector ETFs is a guess, and real spreads widen under stress.
   - The 2026 securities transaction tax rate is uncertain. The schedule changed in 2019, 2021, 2023, 2024 and 2025.
   - The opening auctions on the 10-25% move days in 2026 were probably worse than modelled.
6. **Liquidity and capacity.**
   - For roughly 10M KRW of capital, KODEX 200 (about 2 trillion KRW traded a day) and the 10 large caps impose no limit.
   - The thinnest sector ETFs (139240, 139290, 139280) trade about 0.07-0.3 billion KRW a day. A 3.3M KRW position is 1-5% of daily value, so fills are uncertain.
7. **Execution.**
   - A live version would have to compute the signal between 15:30 and 08:59 KST.
   - Paper trading proves nothing about fill quality.
8. **Too few trades.** T1 and T2 have only 12-17 round trips, so any trade-level statistic is anecdotal.
9. **Benchmark choice.** Beating the equal-weight benchmarks is easy, because Samsung and SK hynix carried the cap-weighted index in 2025-26. B1 (KODEX 200) is the right benchmark, and nothing beat it.

## 7. Recommendation

**Do not take any KR-daily-v1 strategy to the next stage.** Re-tuning lookbacks, filters or rebalance days on this same data would be exactly the overfitting the protocol exists to prevent, and that has not been done.

Worth a reviewer's time, as a new hypothesis rather than a promotion:
- **T3 volatility targeting on KODEX 200**, as a risk-control overlay rather than a source of extra return.
  - Rationale: volatility comes in clusters, and returns do not rise with volatility (Moreira-Muir 2017).
  - Evidence: full-period Sharpe 0.61 vs 0.59, MDD 31.5% vs 41.9%. In the three 2026 crashes it lost 7.8%, 8.9% and 10.5%, against 20.6%, 40.8% and 24.0% for buy-and-hold.
  - Cost: it gave up return (CAGR 8.2% vs 11.6%, and the CI of excess return is entirely negative).
  - It was not the IS pick, so under the protocol it cannot be promoted.
  - Proposal: a new pre-registration (KR-daily-v2) that freezes T3 exactly as written and judges it only on paper-trading results from the registration date onward. That avoids counting the 2026 data twice.
- **T5 sector momentum** beat equal-weight sectors in both halves, but never beat buy-and-hold and pays 1-3% a year in spreads. Not worth pursuing without better spread data.

Open items for the reviewer:
1. Check the end-2010 top-10 list against KRX.
2. Resolve the 009540 gap on 2017-12-27.
3. Decide whether the simulator should block trades on zero-volume or halt days.
4. Add dividends so the B1 comparison is fair.
5. Confirm the 2026 securities transaction tax rate.

## 8. What was touched

- **Writes:** only `~/trading/pipeline/research/kr_daily_v1/`. Nothing in `data/ohlcv`, `runs/`, `freqtrade/`, the env/secrets files or the forward export was changed, and `store.save` was not used.
- **KIS calls:** about 700 read-only daily-chart calls plus one token issue, through the unchanged `tp.kis` (0.8 s spacing). They ran at about 23:20-23:45 KST, outside the intraday collector's hours. The allow-list was not changed and no order code exists.
- **Containers:** throwaway `docker run --rm` containers from the existing `tp-pipeline:local` image, with the same hardening flags as `run.sh`. The backtests ran with no network. The fetch used `--env-file secrets/kis.env` the same way the `kis` role does; secret values were never read or printed. No running container was touched.
  - Flag: launching throwaway containers this way may count as "touching Docker" under the task's stated scope limits; raised here for the owner/reviewer to judge. It was the only way to call `fetch_daily()` without exposing the KIS credentials on the host.

**Sources**
- 2026 verification: newsis 2026-07-31 (mobile.newsis.com/view/NISX20260731_0003731986), SBS Biz (biz.sbs.co.kr/amp/article/20000325956)
- End-2010 top-10 list (unverified): etoday (www.etoday.co.kr/news/view/819072), sateconomy (www.sateconomy.co.kr/news/view/179591057149327)

---

Reproduce with `bt.py main|sens|ext` in this directory.
