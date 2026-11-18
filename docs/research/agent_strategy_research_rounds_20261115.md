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

## Round 4 — low-skewness decile factor (92-symbol revalidation)

Purpose: rerun the archived Gen17 low-skew idea (`docs/archive/salvage_2026-11-15/.../generation_17_low_skew/records/PREREG_low_skew_factor_gen17_20261107.md`) on the full current 92-symbol KR and 92-symbol US caches instead of the original 7-name US / 21-name KR cohorts. This is a reproduction of an existing hypothesis, not a new one. It is an E2 exploratory screen, not SPEC.md E3 sealed validation. It is not independent OOS: every price in both caches through 2026-11-12 has been inspected repeatedly in earlier rounds. It is a survivor cohort: current watchlist names only, with no point-in-time membership and no delisted/merged instruments, which biases results upward for both the factor and the benchmark.

Fixed before the run and not changed afterward: G1 = n/((n-1)(n-2)) · Σ((r−mean)/s)³ on the last 63 close-to-close simple returns (64 consecutive valid closes on the market union calendar, s with ddof=1, s=0 or non-finite → ineligible); rank ascending G1 with ticker tie-break; hold the lowest 10% of the eligible cross-section, K = max(1, floor(0.10 × eligible)), equal weight; decisions every 21 trading-calendar sessions, using the decision-date close, filled at the next session close; shares then fixed until the next execution (weights drift). The decile rule replaces Gen17's fixed K=2/5; nothing else in the signal changed. The run was executed once. There was no retry with a different window or decile.

Reused unchanged from `scripts/research/equity_trend_gate_probe.py`: Close loading (`read_market`, all 92 files per market from a directory scan), calendars (KR union calendar from 2011-01-03; US dates on which all 92 symbols have closes, 2021-07-29 to 2026-11-12), costs (KR 6.5/11.5 bp fee base/stress + 5 bp slippage each side + 20 bp stock sell tax with the listed ETFs exempt; US 8+10 bp base, 36+25 bp stress each side), and `metrics()` (CAGR on 365.2425 days, MDD, daily Sharpe ×√252 with sample std, zero risk-free rate). Turnover is cumulative one-way, the same as the earlier tables. Deviations from the comparators: fills are next-session close, not next open; the account is liquidated with sell costs on the final date. Benchmark: same-cohort equal-weight buy-and-hold, 1/N budget per symbol bought at the factor's first execution close (or a later symbol's first close; budget waits in cash meanwhile), held to the end, liquidated with sell costs. In KR, late-listed names left the B&H at 90.8% average exposure. No symbol had a missing close at any execution date ("frozen" events = 0). Synthetic checks run before the real run: G1 matched `scipy.stats.skew(bias=False)` within 7e-16, the 64-close boundary, hole and constant-series exclusion, and price-scale invariance held, and a zero-cost ledger matched manual chaining of held-name returns.

| Market | Portfolio | Cost | CAGR | MDD | Sharpe | Terminal NAV | Cum. one-way turnover (per year) | Costs (NAV units) |
|---|---|---|---:|---:|---:|---:|---:|---:|
| KR 2011-01-03–2026-11-12 | Low-skew decile | Base | 8.48% | 42.92% | 0.543 | 3.636 | 97.4× (6.14×) | 0.555 |
| KR | Low-skew decile | Stress | 7.82% | 43.66% | 0.509 | 3.298 | 97.3× (6.14×) | 0.667 |
| KR | EW B&H | Base | 11.95% | 44.33% | 0.645 | 5.993 | 0.96× | 0.019 |
| KR | EW B&H | Stress | 11.95% | 44.33% | 0.645 | 5.987 | 0.96× | 0.022 |
| US 2021-07-29–2026-11-12 | Low-skew decile | Base | 20.72% | 26.23% | 1.066 | 2.708 | 30.7× (5.80×) | 0.186 |
| US | Low-skew decile | Stress | 14.84% | 27.66% | 0.808 | 2.079 | 30.6× (5.79×) | 0.539 |
| US | EW B&H | Base | 16.60% | 24.67% | 0.904 | 2.253 | 1.00× | 0.006 |
| US | EW B&H | Stress | 16.41% | 24.67% | 0.895 | 2.234 | 1.00× | 0.020 |

KR: 186 rebalances, average 81.5 eligible names, average 7.8 held. 36.3% of picks were ETFs. The most-held names were 132030 (gold futures ETF), 114260 (government bond ETF), 001270, 133690, and 069500, so the low-skew rank in KR largely selects low-volatility ETFs and bond/gold proxies. 114800 (inverse) was also picked at times. Annual returns were −18.9% in 2011, −17.1% in 2012, and −17.6% in 2022. The factor trails B&H on CAGR (−3.47 pp base, −4.13 pp stress) and Sharpe at both cost levels. It improves MDD by only about 1.4/0.7 pp. KR is a clear failure. It is also weaker than the Round 1 KR 60-session momentum (16.71% / 50.88% / 0.692 base), except for MDD.

US: 58 rebalances, 9 names held each time. 17.2% of picks were ETFs. The most-held names were IBM, CSCO, ADBE, DIS, and INTC. At base cost, this is the only cell that meets the project's numerical bar (CAGR ≥20%, MDD ≤30%, Sharpe ≥1.0). It beats B&H on CAGR (+4.12 pp) and Sharpe (+0.16), but its MDD is 1.56 pp worse than B&H. At stress cost, it fails the bar and trails B&H on CAGR (−1.57 pp) and Sharpe (−0.09). It is cost-sensitive: stress costs absorb 0.54 NAV units at about 5.8× one-way turnover per year. Compared with Round 1–3 US 126-session momentum on the same window (daily 22.42% / 34.17% / 0.871; monthly 25.50% / 41.11%), CAGR is lower but drawdown and base Sharpe are better. Much of the relative edge comes from 2022 (+1.8% vs B&H −16.2%) and 2023. In 2025, the factor returned +6.1% vs B&H +27.3%. The Gen17 preregistered screen requires both base and stress CAGR and Sharpe to strictly beat B&H, with MDD no worse in both cost cases. US fails it on MDD (both costs) and on stress CAGR/Sharpe. KR fails it on CAGR and Sharpe in both costs.

Comparison with the original Gen17 (N=7/21): Gen17 reported US low-G1 K=2 at 68.01% CAGR / 26.41% MDD / Sharpe 1.872 base, vs B&H 50.74%. That is a +17.3 pp CAGR edge, and +6.6 pp at stress. KR K=5 was 28.83% / 31.90% / 1.003, vs B&H 49.09% (fail). Gen17 used OOS from 2023-01, 8/36 bp US one-way costs, and population-std Sharpe. The period and costs therefore differ from this run, and the numbers are not like-for-like. Even so, the direction is unambiguous. With 92 names and a decile portfolio, the US edge over same-cohort B&H shrinks to +4.1 pp at base. It turns negative (−1.6 pp) at stress, and drawdown is no longer better than B&H. KR stays below B&H as before. The large Gen17 US number was mostly a concentration effect of picking 2 of 7 mega-cap survivors in a strong 2023–2026 tape. It did not survive the larger cross-section. What remains in the US is a modest, cost-fragile, low-volatility-like tilt on a 5.3-year survivor sample, with no uncertainty interval computed. It overlaps known low-risk and lottery-demand effects and is not a new family.

Verdict: **REJECTED** under the preregistered Gen17 screen. KR fails CAGR and Sharpe in both cost cases. US passes the 20% / 30% / 1.0 bar only at base cost and fails at stress and against B&H on MDD. Not promoted; no parameter retry. Reproduce with `PYTHONDONTWRITEBYTECODE=1 /opt/anaconda3/bin/python3 scripts/research/low_skew_decile_probe.py` (prints the full JSON, including per-rebalance picks).

## Round 5 — low-realized-volatility decile factor (92-symbol)

Purpose: test the low-volatility anomaly once on the same 92-symbol KR/US harness as Round 4. Volatility here means the sample standard deviation of returns, not skewness. These are different statistics, and the Round 4 rejection was not assumed to carry over. This is an E2 exploratory screen. The survivor-cohort and already-inspected-period caveats from Round 4 apply unchanged. It is not independent OOS.

Fixed before the run and not changed afterward: signal = sample std (ddof=1) of the same last 63 close-to-close simple returns (64 consecutive valid closes on the union calendar); s=0 or non-finite → ineligible that date (same exclusion as the G1 version); rank ascending std with ticker tie-break; lowest 10%, K = max(1, floor(0.10 × eligible)), equal weight; decisions every 21 sessions on the decision-date close, filled at the next session close, weights drift until the next execution; final-date liquidation with sell costs. The run was executed once. There was no retry with another window, decile, weighting, or universe filter.

Script: `scripts/research/low_vol_decile_probe.py` is a copy of `low_skew_decile_probe.py`. Changes: (1) `g1_matrix` was replaced by `vol_matrix` (std ddof=1, same validity mask); the variable name `g1` was kept in `market_inputs`/`main`. (2) The output label is now `lowvol`. (3) `market_inputs` also returns the union frame. (4) An overlap diagnostic `overlap_with_lowskew` was added. It imports `g1_matrix`/`run_factor` from the Round 4 script and does not affect the strategy. The following are reused unchanged: `read_market`, the calendars, `COSTS` and the KR tax/ETF exemption (from `equity_trend_gate_probe.py`), `metrics()`, `_rebalance`, `run_factor`, and `run_buy_hold`. Pre-run synthetic checks: matched pandas `rolling(63).std(ddof=1)` within 2e-17, valid from the 64th close, hole and constant-series exclusion, and price-scale invariance. The B&H benchmark was recomputed with the same function. It reproduces the Round 4 numbers exactly (KR 11.95%/44.33%/0.645, US 16.60%/24.67%/0.904 base).

| Market | Portfolio | Cost | CAGR | MDD | Sharpe | Terminal NAV | Cum. one-way turnover (per year) | Costs (NAV units) |
|---|---|---|---:|---:|---:|---:|---:|---:|
| KR 2011-01-03–2026-11-12 | Low-vol decile | Base | 5.45% | 12.99% | 0.862 | 2.321 | 28.6× (1.80×) | 0.118 |
| KR | Low-vol decile | Stress | 5.26% | 13.19% | 0.834 | 2.255 | 28.6× (1.80×) | 0.153 |
| KR | EW B&H | Base | 11.95% | 44.33% | 0.645 | 5.993 | 0.96× | 0.019 |
| KR | EW B&H | Stress | 11.95% | 44.33% | 0.645 | 5.987 | 0.96× | 0.022 |
| US 2021-07-29–2026-11-12 | Low-vol decile | Base | 3.00% | 7.92% | 0.647 | 1.169 | 8.5× (1.61×) | 0.033 |
| US | Low-vol decile | Stress | 1.58% | 8.78% | 0.352 | 1.087 | 8.5× (1.61×) | 0.106 |
| US | EW B&H | Base | 16.60% | 24.67% | 0.904 | 2.253 | 1.00× | 0.006 |
| US | EW B&H | Stress | 16.41% | 24.67% | 0.895 | 2.234 | 1.00× | 0.020 |

KR: 186 rebalances, average 81.5 eligible names, average 7.8 held, 0 frozen events. 79.0% of picks were ETFs. The most-held names were 114260 (186/186 rebalances), 148070 (173), 153130 (169), 102110, 132030, 261240, and 069500. All of these are in `KR_ETFS`, and the top three are bond/short-rate ETFs. The portfolio is mostly a bond, gold, FX, and index-ETF basket, so it is not a low-volatility stock portfolio. Its worst year was 2022 at −8.9% (B&H −19.4%), and it returned +34.0% in 2025 (B&H +69.8%). Versus B&H, CAGR is −6.50 pp base and −6.68 pp stress. Sharpe is better (+0.22 / +0.19), and MDD is about 31 pp better. It misses the 20% CAGR bar by a wide margin.

US: 58 rebalances, 9 names held, 0 frozen events. 95.6% of picks were ETFs. BIL, TIP, IEF, UUP, and SHY were held at every rebalance, followed by USMV (51), XLP (39), and XLV (25). The decile is essentially a T-bill, Treasury, and dollar portfolio. Versus B&H, CAGR is −13.60 pp base and −14.83 pp stress, and Sharpe is −0.26 / −0.54. MDD is better (7.9% vs 24.7%), but only because the portfolio is cash-like. Annual returns ranged from −3.4% to +5.8%.

Overlap with Round 4 low-skew picks: we compared same-date executions at base cost (186 KR / 58 US matched). On average, 20.3% of low-vol picks were also low-skew picks in KR (median 22.2%, Jaccard 12.0%) and 4.8% in US (median 0%, Jaccard 2.6%). The two factors pick largely different names. Round 5 is not Round 4 under another name.

Interpretation: the 92-symbol cohort mixes stocks with bond, cash, gold, FX, and inverse ETFs. In a mixed-asset universe like this, a pure low-volatility rank collapses into the lowest-risk asset classes. The result is a test of "own the cash/bond sleeve", not of the equity low-volatility anomaly, which is normally a within-equity effect. This is a property of the preregistered universe, not a bug. Rerunning on an equity-only subset would be a new, separately preregistered hypothesis and was not run here. Note: 360750 is held in KR but is not in `KR_ETFS`, so the harness charges it the stock sell tax. This is unchanged harness behavior, and the effect on the result is negligible.

Verdict: **REJECTED** under the same Gen17 screen (strictly beat B&H on CAGR and Sharpe, with MDD no worse, at both cost levels). KR fails CAGR at both costs (it passes Sharpe and MDD). US fails CAGR and Sharpe at both costs. Neither market approaches the 20% CAGR bar. Not promoted; no parameter retry. Reproduce with `PYTHONDONTWRITEBYTECODE=1 /opt/anaconda3/bin/python3 scripts/research/low_vol_decile_probe.py`.

Summary: Rejected. KR has better Sharpe and MDD but CAGR 5.3–5.5% vs B&H 11.9%. US has CAGR 1.6–3.0% vs 16.4–16.6% and also trails on Sharpe. In this mixed universe the decile collapses into bond/T-bill ETFs. Overlap with the low-skew picks is 20% in KR and 5% in US.

## Round 6 — volatility-targeted overlay on US 126-day momentum

Purpose: keep the existing top US candidate unchanged (126-session momentum, top-10 equal weight, daily rebalance at the next open, ungated; Round 3 base-cost 22.42% / 34.17% MDD / Sharpe 0.871). Add only a volatility-targeting exposure overlay, and check whether it cuts MDD enough to clear the bar. This is not a new selection signal. It is an E2 exploratory screen, not SPEC.md E3 sealed validation, and it is not independent OOS. The 2021-07-29 to 2026-11-12 US window has already been inspected repeatedly in Rounds 1–5 with this same strategy. The 92-symbol cache is a current survivor cohort with no point-in-time membership and no delisted/merged names, so absolute returns are biased upward.

Fixed before the run and not changed afterward: realized_vol_t = sample std (ddof=1) of the last 20 daily close-to-close returns of the *pre-overlay* momentum portfolio, annualized by √252, using closes through t. Exposure at the day-t open is scale_t = min(1.0, 0.15 / realized_vol_{t−1}). There is no leverage: the cap is 1.0, per SPEC.md's cash equities/ETF scope. scale_t = 1.0 when realized_vol_{t−1} is missing (the 20-return warmup), zero, or non-finite. The account holds scale_t × NAV in the top-10 equal weights and the remainder in zero-interest cash. Scale changes alter per-name share counts. They therefore enter the same per-name |Δshares × open| turnover that is charged fee + slippage, together with the normal daily rebalance trades. The pre-overlay series is the same-cost-scenario baseline NAV, so base uses the base-cost baseline and stress uses the stress-cost baseline. Costs are unchanged: 8+10 bp base and 36+25 bp stress per side. The run was executed once. target_vol (15%), lookback (20), the cap (1.0), and the cost treatment were not retried.

Implementation: `scripts/research/us_mom126_voltarget_probe.py` imports `read_market`, `metrics`, `K`, and `us_run` from `equity_trend_gate_probe.py`. `us_ledger` is a line-for-line copy of `us_run`'s daily ungated ledger with one change: the target is multiplied by scale_t. With scale = 1 it asserts equality to `us_run` on CAGR, MDD, Sharpe, and turnover (difference below 1e-9) for both cost scenarios. A future-mutation check confirmed that changing pre-overlay NAV from date t onward leaves every scale up to and including t unchanged. The baseline reproduced exactly: base 22.42% / 34.17% / 0.871, stress 2.99% / 47.98%.

| US daily top-10 126-session momentum | Cost | CAGR | MDD | Sharpe | Mean exposure | Cum. one-way turnover (per year) | Passes 20/30/1.0 |
|---|---|---:|---:|---:|---:|---:|:---:|
| Baseline (no overlay) | Base | 22.42% | 34.17% | 0.871 | 99.9% | 106.2× (20.08×) | No (MDD, Sharpe) |
| Vol-target 15% / 20d | Base | 14.36% | 24.19% | 0.964 | 59.5% | 73.3× (13.86×) | No (CAGR, Sharpe) |
| Baseline (no overlay) | Stress | 2.99% | 47.98% | 0.261 | 99.9% | 106.2× (20.07×) | No (all three) |
| Vol-target 15% / 20d | Stress | 1.57% | 36.32% | 0.186 | 59.6% | 73.3× (13.86×) | No (all three) |

Turnover is the cumulative one-way figure from `metrics()`, divided by 5.29 years for the per-year number. The Round 3 table's 90.97× was the *gated* variant. The ungated baseline is 106.2×.

Exposure diagnostics (base; stress differs by under 0.1 pp): mean scale_t 0.596, median 0.568, minimum 0.187. scale_t was below 1.0 on 91.3% of trading days. The pre-overlay portfolio's 20-day realized vol averaged 29.1% (median 26.6%, 90th percentile 45.4%), about twice the 15% target. The overlay therefore acts mostly as a permanent ~40% cash sleeve rather than a crisis-only de-risking switch. Mean scale fell every year: 0.80 (2021), 0.73 (2022), 0.64 (2023), 0.59 (2024), 0.47 (2025), 0.38 (2026 YTD).

| Year | Baseline base | Vol-target base | Baseline stress | Vol-target stress |
|---|---:|---:|---:|---:|
| 2021 (from 07-29) | +12.4% | +9.0% | +4.7% | +2.1% |
| 2022 | −29.1% | −18.0% | −43.6% | −31.4% |
| 2023 | +63.6% | +33.6% | +36.7% | +17.4% |
| 2024 | +45.4% | +28.8% | +20.3% | +13.1% |
| 2025 | +8.8% | +12.4% | −2.5% | +5.9% |
| 2026 (to 11-12) | +41.5% | +17.5% | +23.4% | +10.3% |

Interpretation: the overlay did what vol targeting mechanically does. At base cost, MDD fell 10.0 pp to 24.19%, below the 30% limit, and Sharpe rose 0.09 to 0.964. CAGR fell 8.06 pp to 14.36%, well below 20%, and Sharpe still did not reach 1.0. The 2022 loss shrank (−29.1% → −18.0%), and 2025 improved. In the strong 2023, 2024, and 2026 tapes, it gave up roughly a third to a half of the return because exposure was held near 40–60%. At stress cost, both versions are near zero CAGR. The overlay cuts turnover by about 31%, but the daily equal-weight re-targeting cost still dominates, and the overlay lowers CAGR and Sharpe further while reducing MDD by 11.7 pp. A 15% target is far below this concentrated 10-name portfolio's natural ~27–29% vol, so the result reads mostly as "hold ~60% of the baseline". This is close to scaling a Sharpe-0.87 stream down, plus a small vol-timing gain (+0.09 Sharpe at base). It is not evidence of a robust drawdown-control edge. No bootstrap or uncertainty interval was computed. A Sharpe change of 0.09 on 5.3 years of daily data is well within sampling noise.

Verdict: **FAILS the bar.** The 20% CAGR + ≤30% MDD + ≥1.0 Sharpe requirement is not met in either cost case. Base fails CAGR (14.36%) and Sharpe (0.964) while passing MDD (24.19%). Stress fails all three (1.57% / 36.32% / 0.186). The fixed hypothesis is recorded as tested once and not promoted. Per preregistration, no retry with another target_vol, lookback, or cap. Reproduce with `PYTHONDONTWRITEBYTECODE=1 /opt/anaconda3/bin/python3 scripts/research/us_mom126_voltarget_probe.py` (prints full JSON, including the per-year mean scale).

Summary: The 15%/20-day vol target on US mom126 cut MDD from 34.2% to 24.2% at base, but CAGR fell from 22.4% to 14.4% and Sharpe reached only 0.96. Mean exposure was 60%. Stress CAGR was 1.6%. Fails the bar; no retry.

## Round 7 — volatility-targeted overlay refinement (target_vol 22%)

Purpose: Round 6 found that the 15% target was far below the pre-overlay portfolio's natural ~29% realized vol, so the overlay worked as a permanent ~40% cash sleeve. The user approved one preregistered calibration before this run: change only target_vol to 22% annualized and rerun the identical Round 6 script and logic. The lookback (20 returns), cap (1.0, no leverage), scale_t = 1 fallback, next-open execution, zero-interest cash, same-scenario pre-overlay baseline, and costs (8+10 bp base, 36+25 bp stress per side) are unchanged. This is the last change allowed in this calibration round. If 22% also fails the bar, the overlay is rejected with no further target_vol, lookback, or cap retries. The status is the same as Round 6: E2 exploratory screen, not SPEC.md E3 sealed validation, and not independent OOS. The 2021-07-29 to 2026-11-12 US window has already been inspected in Rounds 1–6. The 92-symbol cache is a current survivor cohort with no point-in-time membership and no delisted/merged names, so absolute returns are biased upward. Choosing 22% after seeing Round 6's realized-vol distribution is itself a use of in-sample information.

Implementation: `scripts/research/us_mom126_voltarget_probe.py` now accepts `--target-vol`. The default stays 0.15, and rerunning without the argument reproduces Round 6 exactly: base 14.36% / 24.19% / 0.964 and stress 1.57% / 36.32% / 0.186. The value is passed into `vol_target_scales` and `causality_check`, and nothing else changed. The same assertions passed: the scale = 1 ledger matched `us_run` to within 1e-9, and the future-mutation causality check passed. The run was executed once with `--target-vol 0.22`.

| US daily top-10 126-session momentum | Cost | CAGR | MDD | Sharpe | Mean exposure | Cum. one-way turnover (per year) | Passes 20/30/1.0 |
|---|---|---:|---:|---:|---:|---:|:---:|
| Baseline (no overlay) | Base | 22.42% | 34.17% | 0.871 | 99.9% | 106.2× (20.08×) | No (MDD, Sharpe) |
| Vol-target 15% / 20d (Round 6) | Base | 14.36% | 24.19% | 0.964 | 59.5% | 73.3× (13.86×) | No (CAGR, Sharpe) |
| Vol-target 22% / 20d (Round 7) | Base | 18.30% | 30.94% | 0.934 | 79.2% | 93.1× (17.61×) | No (all three) |
| Baseline (no overlay) | Stress | 2.99% | 47.98% | 0.261 | 99.9% | 106.2× (20.07×) | No (all three) |
| Vol-target 15% / 20d (Round 6) | Stress | 1.57% | 36.32% | 0.186 | 59.6% | 73.3× (13.86×) | No (all three) |
| Vol-target 22% / 20d (Round 7) | Stress | 1.73% | 44.14% | 0.197 | 79.3% | 93.2× (17.62×) | No (all three) |

Exposure diagnostics at 22% (base; stress differs by under 0.1 pp): mean scale_t 0.793, median 0.833, minimum 0.274. scale_t was below 1.0 on 70.0% of trading days, compared with 91.3% at 15%. The pre-overlay realized vol was the same as in Round 6: mean 29.1%, median 26.6%, 90th percentile 45.4%. Mean scale by year was 0.93 (2021), 0.91 (2022), 0.88 (2023), 0.81 (2024), 0.63 (2025), and 0.56 (2026 YTD).

| Year | Baseline base | VT15 base | VT22 base | Baseline stress | VT15 stress | VT22 stress |
|---|---:|---:|---:|---:|---:|---:|
| 2021 (from 07-29) | +12.4% | +9.0% | +12.3% | +4.7% | +2.1% | +4.8% |
| 2022 | −29.1% | −18.0% | −25.3% | −43.6% | −31.4% | −39.7% |
| 2023 | +63.6% | +33.6% | +51.5% | +36.7% | +17.4% | +27.6% |
| 2024 | +45.4% | +28.8% | +37.5% | +20.3% | +13.1% | +15.6% |
| 2025 | +8.8% | +12.4% | +10.7% | −2.5% | +5.9% | +2.4% |
| 2026 (to 11-12) | +41.5% | +17.5% | +25.8% | +23.4% | +10.3% | +14.7% |

Interpretation: raising the target to 22% moved the result along the expected exposure trade-off without finding a feasible point. At base cost, CAGR recovered 3.9 pp to 18.30%, still 1.7 pp short of 20%. MDD rose to 30.94%, so it now also misses the 30% limit. Sharpe was 0.934, below both the 15% run (0.964) and 1.0. The overlay still cut the 2022 drawdown less than the 15% version did, because during the 2022 decline scale stayed near 0.9. It mostly de-risked in the high-vol 2025–2026 period, when the baseline was strongly positive. That is why the vol-timing Sharpe gain shrank to +0.06 over the baseline. At stress cost, the overlay lowered turnover by about 12%, but CAGR stayed near zero (1.73%) and MDD was 44.14%. Across the two preregistered targets, no target_vol between 15% and 22% appears able to clear all three criteria at once. Near 15%, CAGR is the binding constraint. Near 22%, MDD binds while CAGR is still below 20%. Sharpe stays below 1.0 throughout. No bootstrap was computed, and Sharpe differences of 0.03–0.09 on 5.3 years of daily data are within sampling noise.

Verdict: **FAILS the bar — overlay rejected.** At base cost, 22% fails all three criteria: CAGR 18.30% < 20%, MDD 30.94% > 30%, Sharpe 0.934 < 1.0. Stress also fails all three (1.73% / 44.14% / 0.197). This was the single approved calibration, so the vol-target overlay on US mom126 is closed with no further target_vol, lookback, or cap retries. Reproduce with `PYTHONDONTWRITEBYTECODE=1 /opt/anaconda3/bin/python3 scripts/research/us_mom126_voltarget_probe.py --target-vol 0.22`.

Summary: Vol-target 22% on US mom126 (base) gives CAGR 18.3%, MDD 30.9%, Sharpe 0.93, all three below the bar. Stress CAGR is 1.7%. This was the only approved calibration, so the overlay is rejected.
