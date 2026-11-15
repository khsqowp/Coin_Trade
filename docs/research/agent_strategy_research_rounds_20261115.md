# Agent strategy research rounds — 2026-11-15

Status: in progress. Exploratory results only; no strategy has passed validation or been promoted.

## Research boundaries

- Local Mac research only. No Oracle/remote builds, deployment, orders, or broker paper trading.
- KR/US scope is cash stocks and ETFs. Crypto scope is USDT perpetual market-data analysis for user-directed manual long/short decisions; this work does not place orders.
- KR/US annual return near 20% is an exploratory target, not a forecast or guarantee. Maximum drawdown is still undefined, so no automated-trading readiness decision is possible.
- Crypto 80% is a target, not an achieved result. The tested decision metric is net-profitable exit under a fixed target/stop/expiry outcome, and is not interchangeable with simple close-direction accuracy.
- Experiments are development-only. No sealed period was opened or tuned. Do not convert the best cell among many trials into a success claim.

## Round 1 — cash equities exploratory screens

Data: current local 92-symbol KR and 92-symbol US daily CSV caches. Both are survivor/current cohorts and not point-in-time universes. Historical membership, delisted/merged names, complete corporate-action provenance, and survivorship-free prices are not established.

### Korea

The initial monthly top-10 60-day momentum probe reported CAGR 16.28%, MDD 50.99%, Sharpe 0.679. A code review found stock sell fees/tax were double counted by 6.5 bp. An in-memory corrected-cost rerun, without changing source files, reported CAGR 16.71%, MDD 50.88%, Sharpe 0.692. Breakout-20 remained negative (corrected CAGR about -4.17%, MDD 60.20%); 5-day reversal corrected CAGR about 8.17%, MDD 50.68%.

The corrected paired annual active-return interval versus 069500 was approximately +0.29 to +23.10 percentage points over 15 annual observations; versus the 92-name survivor equal-weight cohort it was approximately -0.84 to +20.23 points. These small-sample intervals do not correct trial selection or survivor bias. All are exploratory results, not a validated edge.

### United States

An independent full-funded NAV rerun of 92 current cached symbols over the common 2021-07-29 through 2026-11-12 window found daily top-10 126-day momentum CAGR 22.42%, MDD 34.17%, Sharpe 0.871 at base assumed costs. A 20-day circular block bootstrap gave a 95% CAGR interval of -5.10% to +64.04%. At stress assumptions, CAGR fell to 2.99% and MDD widened to 47.98%. The 2022 annual return was -29.13%; 2023 +63.57%; 2024 +45.38%; 2025 +8.76%; 2026 YTD +41.50%. This is not validation: sample is short, the universe is survivor-biased, the interval is wide, and results are cost-sensitive.

An intraday volatility-breakout probe was catastrophic: base CAGR around -59.8%, MDD 99.2%, NAV ending near 0.008; stress was near total loss. A prior fixed-notional stress report that implied NAV below zero was invalid; it is superseded by the fully funded NAV accounting above.

## Round 1 — crypto signal and boundary diagnostics

The available local candle database contains about 120 days and OHLCV-like fields, but no funding or open-interest history. Earlier 28-cell structure probes on BTC used 1/3/5/10/15/30/60-minute intervals, two setups, and 10/20-bar expiries. Under next-bar-open entry, first-touch target/stop, stop-first ties, and 0.10% round-trip cost, 1-minute target-first outcomes were 31.1–47.6% across the reported setups/horizons; mean net returns were negative. Prefix checks covered only selected 1m/5m cases, not the entire grid.

An independent six-symbol 15-minute-boundary event probe found 10/20-minute target-first rates near 47–49% and mean net return about -0.10% after the assumed 0.10% round-trip cost. This did not reproduce the claimed candle-boundary edge in the tested development window. It used only six symbols and OHLCV-derived signals.

## Round 2 — crypto setup grid

### Ten-symbol fixed-rule grid

One agent tested a fixed breakout-confluence setup, a squeeze-expansion setup, and a momentum baseline over 12 bar intervals (1m through 1D), 10x/20x expiries, and 0.10%/0.20% round-trip cost cases: 72 rule/timeframe/horizon configurations, 144 cost cells. Development window was 2026-07-17 through 2026-10-09 exclusive, on the first ten symbols from the then-current universe snapshot. No rule was fitted.

Among candidate cells with at least 200 trades, net-profitable exit rates ranged 24.6–36.2%; target-first ranged 17.1–30.1%; direction-at-expiry ranged 22.8–47.3%. Example 1m/10x breakout net-profitable rate was 26.6% (n=4,204, 3.48% coverage), with mean net return -0.102%. The baseline also failed and candidates did not establish consistent net-profit advantage. At 0.20% cost, examples declined to 15.1–25.3%. Twelve-hour and daily candidates were not evaluable due insufficient completed higher-timeframe warmup. No funding, market impact, spread, or live slippage was modeled. This is a rejection of these fixed candidates as evidence of an edge, not proof that every possible strategy fails.

### BTC/ETH independent price-action grid

A separate agent tested pivot-to-current AVWAP pullback, BB/KC squeeze plus Donchian/volume, and ATR expansion with completed 4x-timeframe trend alignment across 12 timeframes, 10x/20x expiries, 1R/2R targets, and base/stress costs. It used only BTC and ETH over the same 84-day development window. There were 72 symbol/setup/timeframe rule configurations and 576 planned outcome cells; 248 cells had fewer than 30 non-overlapping signals and were labeled NOT EVALUABLE.

Across pooled base-cost 1R rows, direction-at-expiry was 46.36%, target-first 39.72%, net-profitable exits 29.40%, and mean net return -0.1003%. The strongest cell with at least 30 non-overlapping signals was BTC 30m squeeze, 10-bar expiry, n=54: net-profitable exits 58.9% (date-cluster 95% CI 47.7–69.2%), target-first 52.1%, mean net -0.0420%, coverage 1.34%. No adequately sampled cell reached 80%. The script did not run prefix/future-mutation checks in this round; risk-invalid exclusions were not tallied separately. Funding was absent and excluded. These outcomes are not eligible for promotion.

## Source and method notes

- TradingView Pine examples must be checked for historical/realtime differences. The [official Pine Script repainting guide](https://www.tradingview.com/pine-script-docs/concepts/repainting/) documents repainting from unconfirmed chart bars and higher-timeframe `request.security()` values; confirmed, offset HTF data is necessary for comparable historical/realtime signals.
- External results do not transfer automatically. A [2026 peer-reviewed microstructure study](https://www.frontiersin.org/journals/blockchain/articles/10.3389/fbloc.2026.1811716/full) used six cryptocurrencies and over three million minute-level Binance spot/perpetual observations, with leakage controls and fees, and reported that modeled strategies did not survive realistic fees. That is context, not evidence about these local experiments.
- A [2026 preprint on quarter-hour effects](https://arxiv.org/abs/2607.09426) uses trade-level order-flow/imbalance data, unlike the local OHLCV cache. Its reported longer-horizon predictability cannot be reconstructed from current local fields alone.

## Round 2 — equity robustness follow-up

### Korea

The unchanged 60-day monthly top-10 momentum rule was rerun through the already explored 2026-11-12 cutoff with corrected sell-fee/tax accounting. Base costs produced 16.71% CAGR / 50.88% MDD; stress costs produced 16.05% / 51.05%. One-way turnover was 5.76× annually. Across 2011–2025 annual returns, 95% intervals were 1.93–41.91% at base costs and 1.36–41.11% at stress costs. This does not remove survivor bias or constitute independent OOS. The cache lacks point-in-time/delisted membership, dependable ETF tax classifications, ETF tax-basis/distribution data, and verifiable corporate-action adjustment provenance.

### United States

The requested chronological/stress rerun did not execute. The agent correctly noted that the full 2021–2026 sample had already been inspected, so splitting a later segment from it would not create independent OOS evidence. Existing full-period bootstrap intervals were -5.10% to +64.04% at base assumptions and -21.39% to +36.31% at stress assumptions. No annual-fold or turnover results were produced in this follow-up; do not claim them.

## Round 3 — preregistered broad-market trend gate

One fixed risk-gate hypothesis will be tested on the same already-inspected local caches: keep the unchanged KR 60-day monthly top-10 momentum and US 126-day daily top-10 momentum rules, but hold 100% cash whenever the corresponding broad ETF proxy (KR 069500; US SPY) closes at or below its own trailing 200-session SMA. The benchmark and SMA use only the last completed close; re-entry is at the next scheduled rebalance. No other parameters change. Use the prior base and stress costs, compare both original and filtered NAV, and report exposure, turnover, yearly returns, CAGR/MDD, Sharpe, and uncertainty.

This is one new trial per market, not validation. All underlying prices through 2026-11-12 have already been inspected, and the current-cohort membership/corporate-action limits remain. Do not call any post-split period independent OOS or open a sealed set. The two delegated agents could not access the repo because their runtime mounted the nonexistent `/Users/user/Desktop/CODE/trading_bot` rather than `/Users/user/CODE/Coin_Trade`; neither executed. The same fixed hypothesis was therefore rerun locally using the existing caches and the reproducible script `scripts/research/equity_trend_gate_probe.py`.

| Market / fixed strategy | Cost | Base CAGR / MDD | SMA200 gate CAGR / MDD | Gate exposure | Gate cumulative one-way turnover |
|---|---:|---:|---:|---:|---:|
| KR monthly top-10 60-session momentum | Base | 16.71% / 50.88% | 16.70% / 47.05% | 59.89% | 61.9× |
| KR monthly top-10 60-session momentum | Stress | 16.05% / 51.05% | 16.24% / 47.21% | 59.89% | 61.9× |
| US daily top-10 126-session momentum | Base | 22.42% / 34.17% | 17.42% / 33.68% | 77.24% | 90.97× |
| US daily top-10 126-session momentum | Stress | 2.99% / 47.98% | 1.27% / 41.52% | 77.24% | 90.97× |

KR costs: 6.5 bp fee plus 5 bp slippage each side, plus 20 bp sell tax for stocks; manually listed ETFs are assumed exempt. US costs: 8 bp fee plus 10 bp slippage each side at base; 36 bp fee plus 25 bp slippage each side at stress. The gate helped KR drawdown by about 3.8 percentage points without changing base CAGR, but left substantial losses in 2012 and 2016. In the US, it reduced drawdown only 0.5 point at base while CAGR fell 5.0 points; under stress it reduced drawdown 6.5 points but CAGR fell 1.7 points. The gate is not a clear improvement across regimes and cost scenarios. These results are still exploratory: the KR turnover differs slightly from the earlier agent implementation, and both samples are the same already-inspected, survivor-biased caches. No independent future test or formal uncertainty interval was generated for this gate.

### Fixed US monthly-rebalance follow-up (corrected implementation)

To test whether daily turnover was needlessly eroding the US 126-session top-10 momentum result, the same already-inspected 92-symbol survivor cache, signal, costs, and SMA200 gate were rerun with trades only at the next session open after each month's final session. Between scheduled rebalances, share counts remain fixed; the market drift changes weights naturally. An initial implementation mistakenly reset shares to target weights every day despite updating monthly signals. That run was discarded, the trade block was restricted to scheduled rebalance dates, and all figures below are from the corrected rerun through 2026-11-12. The script is `scripts/research/equity_trend_gate_probe.py`.

| US 126-session top-10 | Cost | Daily CAGR / MDD | Monthly CAGR / MDD | Monthly one-way turnover |
|---|---:|---:|---:|---:|
| Ungated | Base | 22.42% / 34.17% | 25.50% / 41.11% | 22.46× |
| Ungated | Stress | 2.99% / 47.98% | 20.99% / 42.21% | 22.43× |
| SPY SMA200 gate | Base | 17.42% / 33.68% | 12.78% / 41.11% | 20.91× |
| SPY SMA200 gate | Stress | 1.27% / 41.52% | 9.01% / 42.21% | 20.87× |

The ungated monthly variant cut modeled turnover materially and improved the stress-cost CAGR versus daily rebalancing, but it had a materially deeper base-cost drawdown than daily ungated. The SMA gate reduced return and did not improve the monthly strategy's measured maximum drawdown. This is one exploratory comparison, not independent validation: the US cache starts 2021-07-29, the current-survivor universe has survivorship bias, the full period has already been inspected, and no point-in-time membership, corporate-action audit, uncertainty interval, or sealed evaluation is available. It does not establish that monthly momentum is robust or suitable for autonomous trading.

An independent KR/US audit confirmed the main data limitation: the 92-symbol cache is a current/survivor cohort and does not establish point-in-time membership or delisted/merged instruments. The independent cost-only sensitivity check on monthly US momentum found CAGR 25.50% at the existing base cost, 20.99% at existing stress cost, 12.15% at 1.50% one-way cost, and 2.95% at 2.50% one-way cost; turnover stayed near 22.48× cumulative. The extra costs are hypothetical stress tests, not measured fills. This supports only that result is cost-sensitive, not that the strategy has an edge. A separate alternative-strategy agent did not complete its backtest and inadvertently read some post-2024-11-12 timestamp/close values while checking the dataset endpoint; that attempt is invalid for any strict sealed-data claim and produced no strategy performance numbers. No sealed result is reported here.

### Independent static audit of the 12-timeframe taker study

An independent reviewer inspected the script and report but did not query the database or rerun the study because the script writes report artifacts into the repository. This is a code audit, not a result reproduction. It identified interpretation and coverage limits that must accompany the earlier tables: (1) exit PnL is stop/target/expiry-based, while the `direction` and simple momentum/up/down baselines use the expiry close, so those are not exit-direction accuracy; (2) 10×/20× is only a stop-distance eligibility filter and does not multiply PnL or model margin, liquidation, funding, spread, or slippage; (3) non-overlap selection is performed separately for long and short, allowing same-symbol/time opposing signals to appear in both sets; (4) explicit minute continuity/alignment validation is not comprehensive; (5) causal checks are representative synthetic/prefix tests, not full-path checks for every timeframe/symbol; and (6) the many timeframe/horizon/side/cost/leverage comparisons have no explicit multiple-testing correction. Existing numeric results therefore remain exploratory and are not independently reproduced. Detailed audit and required fixes: `/private/tmp/crypto_multitf_repro.md` (local ephemeral file; not a repository artifact).

### Corrected 12-timeframe rerun after audit

The research runner now accepts `--outdir`, rejects misaligned/incomplete minute aggregates and trade paths with missing 1m bars, and selects mutually exclusive events across long and short per symbol before computing statistics. Its 10×/20× columns are explicitly only stop-distance eligibility labels; PnL is unlevered. The full development-window rerun generated 6,934,104 raw outcome rows, 48 symbol/timeframe aggregates, and 192 summary cells for BNB/BTC/DOGE/ETH through 2026-10-09 exclusive. Representative BTC 1m/30m/4h causal checks passed 15/15 prefix checks and 15/15 future-mutation checks; all three deliberate future-peek controls were detected. The test suite for the research runner passed after the changes.

Among the 48 base-cost cells with at least 200 mutually non-overlapping observations, the highest net-positive-exit rate was 38.89% (30m long, 10-hour horizon, n=324; day-cluster 95% interval 33.43–43.98%; raw signal incidence 0.082%). Its target-first rate was 33.95% (95% interval 28.25–39.51%), mean net return -0.0411% (day-cluster interval -0.1648% to +0.0686%), and expiry-direction accuracy 47.84%. No base-cost cell with n≥200 had positive mean net return; every stress-cost cell with n≥200 had negative mean net return. Highest base mean net among those cells was still -0.0411%; at stress it was -0.2411% (same 30m long setup, interval -0.3600% to -0.1127%). No result approaches the requested 80% target. Maximum signal incidence over all timeframe/side cells remains below 2.6%; no probability calibration/M4 coverage selection was performed. The revised outputs are `docs/research/long_history_taker_multitf_corrected_20261115.{json,md}`. Reproduce with `PYTHONDONTWRITEBYTECODE=1 /opt/anaconda3/bin/python3 scripts/research/long_history_taker_multitf_probe.py --outdir docs/research`.

### New compression-breakout plus BTC regime hypothesis

One independent agent preregistered a single 15m setup on the 100-symbol local USDT-perpetual cache: ATR/close in the prior-30-day 20th percentile, 20-bar close breakout, completed BTC 4h EMA50 regime agreement, next-15m-open entry, 1.5 ATR stop, 2R target, and 12-bar time exit. It computed trades only from 2026-07-17 inclusive through the 2026-10-09 exclusive development cutoff, resolving with 1m OHLC and stop-first same-minute ties. It reported 2,050 trades across 99 symbols and 54 signal days; target/stop/stop-gap/timeout counts were 545/1,122/12/371. Mean trade result was +0.0390R gross, -0.4301R after base costs, and -0.9662R after stress costs; net-profitable trade rates were 38.7%, 36.2%, and 32.4%, respectively. Date-cluster 95% CI for mean net R was [-0.5911,-0.2933] base and [-1.2354,-0.7292] stress. The hypothesis is rejected, not an 80% signal. The reported date bootstrap does not remove cross-symbol same-day correlation, and the 84-day window is short. However, the agent then computed a SHA-256 by reading the entire SQLite file at byte level, including pages outside the development query range. It did not display post-cutoff prices, but strict sealed-data non-access cannot be claimed for this run; treat the strategy performance as exploratory only and do not treat the sealed range as untouched. Reproduction files are ephemeral at `/private/tmp/crypto_new_hypothesis.md` and `/private/tmp/crypto_hypothesis_probe.py`.

The next two crypto agents were tasked with an RSI(2)/Bollinger mean-reversion test and an EMA pullback test. The mean-reversion agent could not start a local process and produced no metrics; the EMA task later completed and is summarized below. In the parallel US ETF volatility-targeting task, the agent reported SPY data unavailable, but the current checkout has `.kis-cache-local/US_SPY.csv` and the local equity runner requires and successfully used `SPY`; therefore its claimed data-availability blocker is contradicted by current local evidence, and no test result is accepted. The KR agent also failed to start its execution process. These failed agent outputs do not constitute strategy results.

### EMA trend pullback across 13 timeframes

The second crypto agent's EMA20/50/200 pullback setup has now completed and was rerun after correcting stop gaps to fill at the adverse 1m open. The fixed rule uses EMA20/50/200 alignment and EMA200 slope, a pullback within 1 ATR of EMA20, a confirming candle, next-bar entry, 1 ATR stop, 2R target, and 10/20-bar timeout. It covered 13 timeframes from 1m to 1d on BNB/BTC/DOGE/ETH, cutoff 2026-10-09 exclusive, with continuous 1m paths and stop-first ambiguous candles. Base/stress round-trip costs were 0.10%/0.30%; no slippage, funding, or leverage PnL was modeled. The report contains 78 cells (13 TF × 2 horizons × long/short/both), 2,274,162 raw outcome records and 1,153,471 mutually exclusive selected records.

For the concrete 1m/10-bar combined-direction cell, target-first was 28.5% (day-cluster 95% CI 28.3–28.7%), net-positive trades were 26.3%, and mean base net return was -0.098%; mean stress net was -0.298%. The highest target-first rate among cells with N≥200 was 33.5% (1m short, 20 bars, N=130,574). The highest base net-positive rate and mean net return among cells with N≥200 were both 43.0% and +0.513% (12h long, 10 bars, N=291), but the mean-return day-cluster 95% interval was [-0.293%, +1.268%] base and [-0.430%, +1.077%] stress, so positive expectancy is not established. No cell approached 80%. Raw directional signals were 4.2–5.3% of complete bars, with no M4 confidence calibration or selected high-confidence subset. Full report and runnable script are `docs/research/ema_pullback_long_history_20261115.md` and `scripts/research/ema_pullback_probe.py`; reproduce locally with `/opt/anaconda3/bin/python3 -B scripts/research/ema_pullback_probe.py`. Treat all results as exploratory development data, not sealed validation.

## Round 3 — crypto candidate tests

### Volume climax plus failed breakout

An agent tested strict 20-bar highs/lows with volume at least 3× trailing 20-bar median, followed by a failure close and opposite-side entry at the next bar open. Stops were beyond the climax/failure range by 0.25 ATR; target was 1.5R; expiry was 10×/20× timeframe bars. All 12 requested intervals (1m through 1D) completed for 10 symbols. The grid recorded 120 rule/timeframe runs, 48 planned pooled output cells, and 394,784 event rows. Costs were 0.10% base round trip and 0.30% total stress round trip; funding was unavailable and excluded.

At base cost, the strongest cell by net-profitable-exit rate among cells with at least 200 independent signals was 30m timeframe, 10-bar expiry (300 minutes): n=1,066 independent signals, 4.18% raw signal coverage (2.65% non-overlapping coverage), target-first 24.7%, net-profitable exits 45.7% (date-cluster 95% interval 41.5–49.7%), and mean net return -0.0667%. At 1m/10-bar expiry, n=36,280 independent events pooled across symbols gave 25.0% net-profitable exits and -0.0997% mean net. Across all cells, pooled base-cost target-first was 29.25%, net-profitable exits 31.24%, and mean net return -0.1016%; stress-cost net-positive exits fell to 14.06% and mean return to -0.3016%. No tested cell approached 80%.

Prefix and future-mutation checks passed on BTC at 1m, 30m, 4h, and 1D (5 checks each); the deliberate future-peek negative control was detected. This is representative causal testing, not exhaustive verification of every cell.

### Heikin-Ashi continuation

A separate agent tested a fixed rule: three consecutive same-color Heikin-Ashi bars, close outside prior 20-bar Donchian range, and completed 4× timeframe EMA50 slope agreement. Stops were 1.5 ATR, targets 2R, and expiry 10×/20× timeframe bars. The trial used 10 symbols, 12 intervals, 24 timeframe/horizon cells, 48 base/stress cost cells, and one fixed rule trial. Data cutoff remained 2026-10-09 exclusive. Prefix/future-mutation checks covered BTC and ETH at 1m, 15m, 1h, and 1D; the deliberate future-peek control was detected.

The highest base-cost net-profitable-exit rate with at least 30 signals was 50.6% at 30m/10-bar expiry (5 hours), n=164, coverage 4.53%, target-first 29.9%, mean net +0.503% per trade, with a date-cluster interval of 42.0–60.6%. The best cell by this rate with at least 200 signals was 10m/20-bar expiry (200 minutes), n=286: 35.0% net-positive exits (95% interval 27.9–42.1%), 27.6% target-first, 45.8% direction-at-expiry, mean net -0.149%. It is not eligible for promotion: coverage is below the 10% gate and 80% was not demonstrated. At 0.20% stress cost, the 30m/10-bar cell had 50.0% positive exits and mean net +0.403%, but its interval crossed zero for mean net; the rule was not retuned or evaluated on sealed data. Higher-timeframe and many other cells were too sparse.

The volume-climax universe symbols could not be independently checked against a contemporaneous exchangeInfo `underlyingType == COIN` snapshot. Its censor counter had a bookkeeping issue: the report listed 196, but this included a two-count increment for each of 17 no-entry cases; event reconciliation indicates 162 censored signal-horizon pairs. The final corrected scripts compiled and exited 0. For the Heikin-Ashi run, an earlier counter-aggregation defect was fixed before the final script compiled and exited 0.

Both results remain development-only. The apparent HA 30m mean is a hypothesis for future data, not a winning strategy. The existing rule and validation gates do not permit opening the sealed period for a cell that fails minimum sample and coverage requirements.

### Long-history 30m Heikin-Ashi follow-up

The fixed HA rule above was rerun on the long-history cache for BTC, ETH, BNB, and DOGE, ending 2026-06-30 and strictly before the 2026-10-09 exclusive development cutoff. SOL and XRP were excluded wholesale because known missing-minute gaps can corrupt rolling indicators, completed-HTF state, or trade horizons; no interpolation was used. The 4h EMA50 filter uses only fully completed 4h bars, labels `[00:00,04:00)` at 04:00, and signals enter at the next 30m open. Stop is 1.5×30m ATR14, target 2R, expiry 10 or 20 30m bars, same-bar stop/target ambiguity resolves stop-first, and modeled round-trip fee is 0.10%. A conservative leverage eligibility screen rejects stop distance at or beyond 9.5% for 10× and 4.5% for 20×; this is only a rough maintenance buffer, not exchange liquidation simulation. Funding and slippage are absent.

| Direction | Expiry | Leverage | Eligible trades | Target-first | Net-positive exits | Mean net per trade |
|---|---:|---:|---:|---:|---:|---:|
| Long | 10 bars (5h) | 10× | 8,813 | 21.59% | 38.67% | -0.067% |
| Short | 10 bars (5h) | 10× | 7,202 | 21.30% | 35.14% | -0.222% |
| Long | 20 bars (10h) | 10× | 8,813 | 28.62% | 36.96% | -0.056% |
| Short | 20 bars (10h) | 10× | 7,202 | 27.51% | 34.32% | -0.200% |
| Long | 10 bars (5h) | 20× | 8,715 | 21.51% | 38.68% | -0.069% |
| Short | 10 bars (5h) | 20× | 7,097 | 21.47% | 35.37% | -0.181% |
| Long | 20 bars (10h) | 20× | 8,715 | 28.57% | 36.95% | -0.059% |
| Short | 20 bars (10h) | 20× | 7,097 | 27.69% | 34.47% | -0.166% |

No tested pooled cell is near 80%; every mean net return is negative before funding and slippage. These rates are descriptive and have no date-cluster confidence intervals in this probe, so overlapping trades make naive binomial uncertainty inappropriate. The result rejects this fixed HA setup as a current candidate; it does not establish that all HA variants fail. The full implementation is `scripts/research/long_history_ha_probe.py`.

### Long-history 30m volume-climax failure follow-up

The round-3 volume-climax rule was also replayed on BTC, ETH, BNB, and DOGE over the same pre-cutoff long-history cache. SOL/XRP remain excluded for continuity uncertainty. At bar *i*, the trigger is a strict new 20-bar high/low and volume at least 3× the median of the previous 20 bars; the next completed bar must close back inside the extreme. Entry is at the following 30m open. Stop is beyond the climax/failure range plus 0.25×ATR14, target 1.5R, horizon 10/20 bars, and ambiguous same-bar stop/target resolves stop-first. Round-trip costs are 0.10% base and 0.30% stress. A rough leverage eligibility screen uses 9.5%/4.5% max stop distance for 10×/20×; it is not an exchange liquidation model. No funding, spread, or separate slippage series is included.

| Horizon | Leverage | Cost | Eligible events | Direction correct at expiry | Net-positive exits | Mean net/trade |
|---|---:|---|---:|---:|---:|---:|
| 10 bars (5h) | 10× | Base | 20,374 | 52.48% | 41.78% | -0.139% |
| 10 bars (5h) | 10× | Stress | 20,374 | 52.48% | 36.52% | -0.339% |
| 10 bars (5h) | 20× | Base | 19,839 | 52.48% | 41.57% | -0.141% |
| 10 bars (5h) | 20× | Stress | 19,839 | 52.48% | 36.28% | -0.341% |
| 20 bars (10h) | 10× | Base | 20,370 | 51.77% | 40.34% | -0.155% |
| 20 bars (10h) | 10× | Stress | 20,370 | 51.77% | 37.41% | -0.355% |
| 20 bars (10h) | 20× | Base | 19,835 | 51.73% | 40.11% | -0.157% |
| 20 bars (10h) | 20× | Stress | 19,835 | 51.73% | 37.15% | -0.357% |

The highest per-symbol base net-positive rate was 45.34% (DOGE, 10 bars, 10×); mean net still -0.077%. The fixed rule does not provide a useful directional edge or approach 80%. These are descriptive pooled counts without date-cluster intervals and are not promotion evidence. Reproducible code: `scripts/research/long_history_volume_climax_probe.py`.

### Long-history 30m taker-imbalance breakout follow-up

The newly stored taker-buy quote field was tested with one fixed rule on BTC, ETH, BNB, and DOGE only: long after a close above the prior 20-bar high with taker-buy imbalance `2*taker_buy_quote/quote_volume - 1 >= 0.30` and volume at least 1.5× the prior 20-bar median; short is symmetric below the prior 20-bar low with imbalance <= -0.30. Entry is next 30m open, stop 1.5×ATR14, target 2R, expiry 10/20 bars, stop-first tie handling, and 0.10%/0.30% round-trip base/stress costs. The 10×/20× eligibility screen is the same rough 9.5%/4.5% maximum stop-distance check. SOL/XRP were omitted due gaps; funding, spread, and exchange liquidation rules were not modeled.

| Direction | Horizon | Leverage | Cost | Events | Direction correct at expiry | Net-positive exits | Mean net/trade |
|---|---:|---:|---|---:|---:|---:|---:|
| Long | 10 bars (5h) | 10× | Base | 366 | 46.72% | 37.43% | -0.105% |
| Short | 10 bars (5h) | 10× | Base | 480 | 41.46% | 35.21% | -0.136% |
| Long | 20 bars (10h) | 10× | Base | 366 | 48.36% | 38.25% | -0.063% |
| Short | 20 bars (10h) | 10× | Base | 480 | 44.79% | 36.04% | -0.099% |
| Long | 10 bars (5h) | 10× | Stress | 366 | 46.72% | 31.42% | -0.305% |
| Short | 10 bars (5h) | 10× | Stress | 480 | 41.46% | 30.63% | -0.336% |
| Long | 20 bars (10h) | 10× | Stress | 366 | 48.36% | 36.61% | -0.263% |
| Short | 20 bars (10h) | 10× | Stress | 480 | 44.79% | 35.00% | -0.299% |

The 20× eligible event counts differ by only two short events from the 10× results; pooled rates and conclusions are materially unchanged. BTC and ETH long 20-bar cells had positive mean net under base costs individually, but only n=81 and n=74 respectively, and both turned negative under stress. The pooled rule is negative, the direction rate is near chance, and no result approaches 80%. This is not a promising standalone rule. No date-cluster confidence interval was computed. Reproducible code: `scripts/research/long_history_taker_imbalance_probe.py`.

### Long-history taker-imbalance multi-timeframe grid

The same fixed rule was expanded across 1m, 3m, 5m, 10m, 15m, 30m, 1h, 2h, 4h, 6h, 12h, and 1D bars, with 10×/20× eligibility screens, 10/20-bar horizons, long/short, and 0.10%/0.30% round-trip cost cases: 24 fixed timeframe/horizon configurations and 192 outcome cells. The four gap-free symbols and development cutoff remain unchanged. Stops/targets are resolved against original 1m OHLC with stop-first ties, even when the forecast timeframe is higher. Signals are greedily made non-overlapping per symbol and side without using outcomes; uncertainty uses 1,000 UTC-day cluster bootstrap draws. Prefix and future-mutation checks passed 5/5 each at BTC 1m, 30m, and 4h; a deliberate future-peek negative control was detected at all three.

At base cost, 48 cells had at least 200 non-overlapping trades. No cell met 80% net-positive exits or 75% target-first, and none had positive mean net. The strongest net-positive cell was 30m long / 20-bar horizon (10h), 20×: n=336, net-positive rate 38.69% (day-cluster 95% interval 33.95–43.53%), target-first 33.93% (28.75–39.02%), expiry direction accuracy 48.21% (42.52–53.96%), and mean net -0.045% (interval -0.154% to +0.058%). Its prior-bar momentum baseline was 53.27%; always-up was 48.21% and always-down 51.49%. At stress costs, all 48 cells with n≥200 had negative mean net; the best was -0.245% (95% day-cluster interval -0.351% to -0.127%). Maximum raw signal incidence was 2.57% of valid timeframe bars at 1m-short, below the proposed 10% coverage gate; this is signal incidence, not calibrated M4 coverage. No probability calibration was run.

An initial generated table used the signal candle itself for its prior-momentum baseline, making that comparator tautologically aligned with breakouts. That table was rejected and regenerated with the fully completed candle before the signal candle; only the corrected JSON/Markdown artifacts are valid. The full 192-cell result is [JSON](long_history_taker_multitf_20261115.json) and [Markdown](long_history_taker_multitf_20261115.md), reproduced by `scripts/research/long_history_taker_multitf_probe.py`.

## Additional data acquisition track — historical cache populated; long-history signal tests pending

The local database's short history and missing funding/open-interest fields limit futures strategy conclusions. Binance's official [Public Data repository](https://github.com/binance/binance-public-data) documents monthly USD-M klines with quote volume, trade count, and taker-buy base/quote volume, plus SHA-256 checksum sidecars. One 2025-01 BTCUSDT 1m zip was measured at 1,917,878 bytes; a one-month aggTrades archive was 542,757,450 bytes, so the initial extension uses klines only and does not download aggTrades.

The current [Binance Vision dataset terms](https://github.com/binance/binance-public-data/blob/master/TERMS_AND_CONDITIONS.md) allow personal non-production historical backtesting, subject to CC BY-NC-SA 4.0 attribution/share-alike terms, and prohibit commercial utilization and compensated third-party signal distribution without a separate license. This work remains local, personal, and non-production; no raw dataset will be committed or pushed.

A separate script, `scripts/research/binance_vision_klines.py`, writes only to ignored `chart_predictor/data/vision_dev.sqlite`, never the live collector DB. It rate-spaces requests, checks each downloaded zip against the SHA-256 sidecar, and stores checksums and taker-buy fields. The 2025-01 smoke run covered BTC, ETH, SOL, XRP, BNB, and DOGE. The historical backfill then completed for 2020-01 through 2026-06 (exclusive 2026-07): 453 monthly archives, 19,776,458 one-minute rows, and 15 missing symbol-month archives, mostly before those symbols existed. Per-symbol rows: BNB 3,359,039; BTC 3,417,120; DOGE 3,141,540; ETH 3,417,120; SOL 3,039,420; XRP 3,402,219. The database passes SQLite integrity checking and is git-ignored; no raw archive or database is to be committed.

Continuity QC found no internal missing minutes for BNB, BTC, DOGE, or ETH. SOL and XRP each have two internal gaps totaling 7,200 missing minutes: 2022-02-26 00:00 through 2022-02-28 23:59 UTC and 2022-04-01 00:00 through 2022-04-02 23:59 UTC. Binance's [public-data issue #297](https://github.com/binance/binance-public-data/issues/297) independently documents the Apr 2022 SOL/XRP missing archives, but the Feb interval is established here from timestamps and has not been matched to an authoritative explanation. Do not interpolate. Any event whose feature warmup, entry, or outcome horizon intersects either gap must be censored; report excluded counts by symbol and timeframe.

The collector's unit tests pass 6/6 after aligning its declared SQLite column names with the downloaded database's existing schema. Its `PRIMARY KEY` previously referenced an obsolete column after the field-name edit; this was caught and fixed before proceeding. A write attempt against the 2.4-GiB local DB returned SQLite `attempt to write a readonly database`; no DB contents were changed. The database is therefore kept as-is, and the collector schema now matches it. Available disk after backfill was about 47 GiB. No credentials, orders, remote server, or existing live candle database were used.

Historical ingestion and four fixed-rule long-history tracks are complete: 30m Heikin-Ashi continuation, 30m volume-climax failure, 30m taker-imbalance breakout, and the taker-imbalance rule across 12 timeframes. These are exploratory and failed profitability/80% gates. Existing 84-day results above remain unchanged and cannot be retroactively described as long-history validation. Next local-only loops should test distinct fixed signal families across multiple timeframes and include event-level chronological verification; SOL/XRP features crossing known gaps must be censored. Repeatedly tuning rules on this already viewed development data cannot establish an edge; a candidate must be frozen before any future/paper forward test. Do not use the sealed interval to search parameters.

## Round 4 continuation — 2026-11-15: US downside-beta ETF screen and agent audit

### US ETF downside-beta candidate

The existing fixed-rule script `scripts/research/equity_us_downside_beta_probe.py` was replayed once against the local read-only KIS cache, strictly before the exclusive `2024-11-12` cutoff. The candidate equal-weights the three lowest SPY downside-beta ETFs among SPY, QQQ, IEF, GLD, DBC, and SHY, estimating beta from the preceding 60 complete sessions in which SPY fell. Rebalance is monthly. Base/stress round-trip friction is the script's assumed 0.36% / 1.22%. The 84 monthly return observations span 2017-10-31 through 2024-10-31. BIL and SPY buy-and-hold and a matched 60-session top-three momentum portfolio are comparators.

At base cost, downside beta returned 3.21% CAGR / −14.32% MDD (12-month circular-block bootstrap 95% CAGR interval −1.07% to +8.21%); momentum returned 10.39% / −17.84%; SPY 13.88% / −33.72%; BIL 2.09% / −0.21%. At stress cost, downside beta returned 2.20% / −15.37% (interval −2.21% to +7.44%); momentum 7.35% / −19.71%; SPY 13.74% / −33.72%; BIL 1.97% / −0.62%. The lower drawdown is real in this replay but comes with low return; both candidate CAGR intervals include zero. No paired relative-return interval was calculated, so relative differences are descriptive only. This does not meet the approximate 20% return objective and is not a validated result.

An independent verifier confirmed the 7 pre-cutoff CSV return series, turnover-cost identity, and all 8 bootstrap CAGR intervals exactly. It checked but did not independently reconstruct the daily NAV path, so MDD values are not independently recomputed.

Input file pre-cutoff SHA-256 values, exact reproduction command, limitations, and full table are in [`equity_us_downside_beta_results_20261115.md`](equity_us_downside_beta_results_20261115.md). The code file's Git blob SHA-1 is `0bf4156a6e59dea3232eeac2f720cd3797a3a17a`. The cache is a selected current ETF cohort; point-in-time membership, delistings, total-return/distribution treatment, and measured transaction costs are not established. This historical period has already been inspected; no OOS or sealed claim is valid.

### Agent status and non-results

- Korea's agent proposed an as-filed operating-profit acceleration event study, but did not run it because the cache contains no publication-time disclosures, restatement history, or survivorship-free issuer/security mapping. This is a data-feasibility lead, not a strategy result.
- One US audit agent failed before starting a process (`Failed to create unified exec process: No such file or directory`). A separately spawned independent verifier later confirmed the return series, cost turnover identity, and bootstrap intervals; it did not rebuild the full daily NAV, so MDD still lacks an independent numeric reconstruction.
- Both crypto agents correctly withheld performance claims: one could not access the exact candidate-audit file in its own checkout; the other noted that the six-symbol long-history panel cannot meet the frozen M4 universe gate of 20 symbols and that no confidence-calibration rule is registered. A new crypto simulation was therefore not run in this continuation. These are not strategy failures; they are unexecuted experiments. The 100-symbol minute database is already-exposed development data and cannot be called sealed.

No strategy is promoted in this continuation. Next useful evidence is not another parameter sweep on the same historical caches: it is (a) a permitted, point-in-time and total-return equity dataset, (b) an independent reconstruction of the US ETF daily NAV/MDD path, and (c) prospectively frozen crypto predictions collected against a documented append-only data/access boundary. The local 100-symbol recent crypto database may be used only for explicitly exploratory screens, with all previously tested setup families excluded in advance.

### Pine indicator / macro-to-micro design review — 2026-11-15

The user-provided Pine source was reviewed by three independent agents and the parent researcher. Consensus: do not backtest its defaults. The script does not compute an actual completed higher-timeframe regime; it derives a rolling range length from lower-timeframe bars. Its sequential `if` blocks can test MSS on the same bar as the sweep, and can score the entry bar's full range after the state changes. Wick-price fills are not established by OHLC ordering, ambiguous same-bar TP/SL is resolved TP-first, armed setups and trades have no expiry, and persistent entry alert flags can repeat. The default fixed bracket is TP 0.3% vs SL 0.4% (0.75R), requiring 57.14% gross break-even before costs; under the existing 0.10% round-trip fee assumption the simplified break-even rises to 71.43%.

The only candidate retained for further consideration is a top-down event rule: a completed 4h BTC market-structure regime (confirmed swing HH+HL / LH+LL; otherwise neutral) gates a 5m per-coin sweep of the previous 12 completed bars, followed only on later completed bars by an MSS close-break; next 5m open entry, sweep-extreme stop, 2R target, and a fixed 10-bar outcome window. The draft definitions, causal constraints, data prerequisites and M4 gates are documented in [`crypto_pine_macro_to_micro_audit_20261115.md`](crypto_pine_macro_to_micro_audit_20261115.md). This candidate is not a frozen preregistration and has **not** been tested. Existing data is already exposed, so only a new prospective/append-only evaluation could support a validation claim; do not run more historical parameter searches.

No new result was claimed for the Pine strategy. The three agents independently recommended deferring performance tests until HTF regime, MSS confirmation, sequence expiry, exact fill/cost assumptions, confidence calibration and a genuinely unexamined evaluation period are fixed.
