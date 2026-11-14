# Research round 2 results (futures cost model, adaptive allocation, AI-role split)
Generated from `runs/research/*.json` (reproduce: `./run.sh research research-run --study s1|s2|s3_w15|s3_w5|s4`, about 5 minutes total, niced, 2 GB / 1 CPU, no network).
Protocol and hypotheses were written BEFORE the results: `research/PREREG_round2.md`. Data: Binance USDT-M BTC/ETH perpetual klines + real 8h funding.

## 1. Cost model (spot and futures separate; fee, slippage, funding, leverage, mmr are separate parameters)
| item | value used | source |
|---|---|---|
| futures maker / taker (Regular User) | 0.02% / 0.05% per side | https://www.binance.com/en/support/faq/detail/360033544231 |
| futures BNB discount | 10% | same |
| spot fee | 0.1%; with BNB 0.075% | https://www.binance.com/en/support/faq/detail/115000583311 |
| funding | real history, 8h, longs pay when positive | https://www.binance.com/en/support/faq/detail/360033525031 |
| liquidation | mark-price based; model = whole position margin lost, direction locked until the signal resets | https://www.binance.com/en/support/faq/detail/360033525271 |
| maintenance margin | 0.5% (bracket table unreadable: ASSUMPTION; 0.4% / 1.0% tested) | https://www.binance.com/en/support/faq/detail/360033162192 |
| slippage | 0.02% per side (ASSUMPTION; 0.01% / 0.05% tested) | none official |
Caveat: the fee articles call their rates "hypothetical". The owner's real VIP tier may differ. The old 0.15%/side spot assumption was wrong for futures: primary futures cost is 0.07% per side (0.14% round trip) incl. slippage.
Scenario grid: maker mix {taker, 50/50, maker} x BNB {off, on} x slippage {0.01, 0.02, 0.05}% (18 combos, `tp.costs.scenarios`).

## 2. Baselines (S1, 132 rows, primary cost, 2 years for 1h, 3 years for 4h)
| tf | variants | Sharpe > 0 | median Sharpe | buy&hold Sharpe (BTC / ETH) | DSR > 0.95 |
|---|---|---|---|---|---|
| 5m (180d) | 31 | 0 | -5.88 | 0.35 / 0.31 | 0 |
| 15m (365d) | 31 | 2 | -2.05 | -0.56 / -0.58 | 0 |
| 1h (730d) | 31 | 5 | -0.57 | 0.29 / 0.23 | 0 |
| 4h (1095d) | 31 | 16 | 0.07 | 0.67 / 0.37 | 0 |
Best variants: btc_regime_alt long ETH 4h Sharpe 1.16 (return +139%, MDD 39%, DSR 0.28); trend_mtf long ETH 1h Sharpe 1.05 (+63%, MDD 21%, DSR 0.13). Neither survives the multiple-testing correction (124 selection variants).
Reading: at 5m and 15m round-trip cost (0.14%) times trade frequency destroys the edge (5m fees alone 43%/yr for trend_mtf); costs, not signal quality, decide timeframe. From 1h upward some variants are positive, but none is statistically distinguishable from luck.

## 3. Sensitivity (S2)
* Spot vs futures taker, same signals: trend_mtf BTC 1h return -22.2% (spot) / -18.7% (spot BNB) / -10.1% (futures incl. funding). mean_reversion ETH 15m: -0.3% / +0.7% / +1.8%. Futures is cheaper per side, funding is small for short holds.
* Leverage: with full-equity margin, leverage multiplies loss (trend_mtf BTC 1h: 1x -10%, 3x -39%, 5x -66%, 10x -96%). With the Risk-Engine 25% notional cap, leverage is irrelevant. Liquidations did NOT trigger in this grid (adverse moves inside trend trades stayed below 1/lev); ruin came from fee attrition and drawdown. Liquidation mechanics are verified in `tests/test_futbt.py` on synthetic gaps. H5 (liquidations for lev >= 5 at 15m-1h) was NOT confirmed.
* mmr 0.4% / 0.5% / 1.0%: no change in any result (no position came near liquidation).
* Funding drag (buy&hold): BTC 4h 16%/yr, 1h 7%/yr; negligible for <= 15m strategies (H6 confirmed).

## 4. LLM-free adaptive allocation (S3; regime = deterministic price classifier on BTC 4h; walk-forward, configs chosen on train only)
Pooled out-of-sample, both symbols, primary cost. "WF best fixed" = best fixed config chosen on each train window. "Oracle" is hindsight (reference only, not a baseline).
| clock | window | buy&hold Sharpe | fixed avg | WF best fixed | A1 rule table | A2 learned table | oracle best fixed |
|---|---|---|---|---|---|---|---|
| 15m | 16 folds, 365d | 0.80 | -4.13 | -1.43 | -1.14 | -1.00 | 4.20 |
| 5m | 10 folds, 180d | 3.89 | -11.25 | -4.42 | 1.54 | -0.91 | 4.94 |
A1 minus WF-best-fixed, annualised return difference with block-bootstrap 90% CI: 15m +13.4% (CI crosses 0, not significant); 5m +105.5% (CI excludes 0, significant). A1 minus buy&hold: negative in both (15m -51%, 5m -149%, 5m CI entirely below 0). A2 (learned) adds nothing reliable.
DSR of A1: 0.00 (15m), 0.06 (5m) against 150 selection trials: NOT significant. Conclusion: adaptive switching reduces the damage of fixed strategies and cut drawdown at 5m (MDD 5.6% vs 41.6% for WF-best-fixed), but it does not beat buy&hold, and it is not a proven edge. Regime shares are dominated by "range" (~79-82%), so A1 is mostly the 15m mean-reversion leg whose turnover is high.
Not testable here: LLM / news regime judgements (the model knows the future of any past date). They are evaluated forward only (C6).

## 5. AI-role candidates vs deterministic substitutes (S4, OOS from 2025-06 for 1h bases and 2026-02 for 15m bases; 4 base configs)
| role | deterministic substitute | improved bases | mean Sharpe delta | H4 verdict |
|---|---|---|---|---|
| (a) event-risk filter (FOMC +-6h flat) | calendar window from federalreserve.gov (36 dates) | 2 / 4 (the two 15m bases: zero change) | +0.03 | FAIL; placebo p 0.18 / 0.21 on the 1h bases (500 random window sets) |
| (c) meta-labeling (purged walk-forward logistic) | none needed | 0 / 4 | -0.12 | FAIL; keeps only 8-16% of trades, threshold 0.5 too aggressive |
| (d) volatility-target sizing | clip(median rv / rv, 0.25, 2) | 3 / 4 | +0.14 | PASS (weak) |
| (e) retirement on 30d shadow-Sharpe decay | rolling shadow Sharpe | 2 / 4 | -0.16 | FAIL; helps trend_mtf BTC (+0.83) and hurts mean reversion (-0.6 / -0.9) |
(b) regime-switch detection and strategy replacement = section 4 (price-only version works only marginally).

## 6. Where an LLM is needed and where it is not
Needs no LLM (deterministic substitute exists and is at least as good in tests): scheduled-event filter (calendar), volatility targeting, regime labelling from prices, retirement on performance decay, meta-labeling (not shown to help at all).
LLM is plausibly needed only for what a rule cannot see: unscheduled and textual events (hacks, delistings, regulation, geopolitical shocks, surprise statements), summarising conflicting news into an event_risk flag. This cannot be backtested honestly, so the value is decided by the forward comparison C6 vs C3v vs C3 (>= 28 days, many more for confidence). Until then the LLM output is advisory and can only reduce risk (risk_multiplier <= 1).
Cost: scheduler spends about $0.05-0.16/day with the carry gate (cap $0.30/day). If C6 shows no advantage over C3v after the forward period, the scheduler can be stopped (`./svc.sh stop sched`) with no loss of the deterministic stack.

## 7. Multiple-testing accounting
All variants are logged in `runs/research/trials.sqlite` (re-runs replace, never duplicate): S1 132 rows (124 selection), S2 108 (sensitivity, not selection), S4 20, W15 3, W5 3 = 150 selection trials (a first version of this document counted 170: 20 S4 rows had been logged twice by a re-run before the uniqueness index existed; de-duplicated in round 3, backup backups/r2-tz/trials.sqlite.pre-r3). Primary DSR uses the null-hypothesis variance (1/years); the stricter robust empirical variant is also reported (`dsr_emp`). Nothing passes DSR > 0.95 except hindsight "oracle" rows, which are labelled as such.

## 8. Failures to report (RiskConfig gate unchanged)
* No configuration reaches DSR > 0.95; no candidate qualifies for live consideration.
* 15m/5m fixed strategies lose money after correct futures costs.
* Adaptive A1 does not beat buy&hold; its 5m significance is relative to a losing baseline.
* Meta-labeling and FOMC filter fail their pre-registered success tests; retirement is mixed.
* Short history (5m: 180 days, one regime) limits every 5m conclusion.
