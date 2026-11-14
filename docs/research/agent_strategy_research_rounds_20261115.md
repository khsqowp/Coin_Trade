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

## Additional data acquisition track — historical cache populated; long-history signal tests pending

The local database's short history and missing funding/open-interest fields limit futures strategy conclusions. Binance's official [Public Data repository](https://github.com/binance/binance-public-data) documents monthly USD-M klines with quote volume, trade count, and taker-buy base/quote volume, plus SHA-256 checksum sidecars. One 2025-01 BTCUSDT 1m zip was measured at 1,917,878 bytes; a one-month aggTrades archive was 542,757,450 bytes, so the initial extension uses klines only and does not download aggTrades.

The current [Binance Vision dataset terms](https://github.com/binance/binance-public-data/blob/master/TERMS_AND_CONDITIONS.md) allow personal non-production historical backtesting, subject to CC BY-NC-SA 4.0 attribution/share-alike terms, and prohibit commercial utilization and compensated third-party signal distribution without a separate license. This work remains local, personal, and non-production; no raw dataset will be committed or pushed.

A separate script, `scripts/research/binance_vision_klines.py`, writes only to ignored `chart_predictor/data/vision_dev.sqlite`, never the live collector DB. It rate-spaces requests, checks each downloaded zip against the SHA-256 sidecar, and stores checksums and taker-buy fields. The 2025-01 smoke run covered BTC, ETH, SOL, XRP, BNB, and DOGE. The historical backfill then completed for 2020-01 through 2026-06 (exclusive 2026-07): 453 monthly archives, 19,776,458 one-minute rows, and 15 missing symbol-month archives, mostly before those symbols existed. Per-symbol rows: BNB 3,359,039; BTC 3,417,120; DOGE 3,141,540; ETH 3,417,120; SOL 3,039,420; XRP 3,402,219. The database passes SQLite integrity checking and is git-ignored; no raw archive or database is to be committed.

Continuity QC found no internal missing minutes for BNB, BTC, DOGE, or ETH. SOL and XRP each have two internal gaps totaling 7,200 missing minutes: 2022-02-26 00:00 through 2022-02-28 23:59 UTC and 2022-04-01 00:00 through 2022-04-02 23:59 UTC. Binance's [public-data issue #297](https://github.com/binance/binance-public-data/issues/297) independently documents the Apr 2022 SOL/XRP missing archives, but the Feb interval is established here from timestamps and has not been matched to an authoritative explanation. Do not interpolate. Any event whose feature warmup, entry, or outcome horizon intersects either gap must be censored; report excluded counts by symbol and timeframe.

The collector's unit tests pass 6/6 after aligning its declared SQLite column names with the downloaded database's existing schema. Its `PRIMARY KEY` previously referenced an obsolete column after the field-name edit; this was caught and fixed before proceeding. A write attempt against the 2.4-GiB local DB returned SQLite `attempt to write a readonly database`; no DB contents were changed. The database is therefore kept as-is, and the collector schema now matches it. Available disk after backfill was about 47 GiB. No credentials, orders, remote server, or existing live candle database were used.

Historical ingestion is complete, but no long-history candidate strategy has yet been tested on this database. Existing 84-day results above remain unchanged and cannot be retroactively described as long-history validation. The next local-only research cycle is to rerun fixed HA-continuation and volume-climax rules on the pre-cutoff history, explicitly censoring the SOL/XRP gaps, then compare base/stress costs and report sample size, coverage, clustered uncertainty, and exposure. No parameter search may use the sealed interval.
