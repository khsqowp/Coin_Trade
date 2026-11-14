# Forward paper candidates (pre-registered)
Registered by `./run.sh research forward-eval` (first call creates `runs/forward_registry.json`; entries are never rewritten). Evaluation = the same
deterministic code run on bars that OPEN after the registration timestamp, starting flat, 1x notional, primary futures cost model
(taker 0.05%/side + 0.02% slippage, no BNB), real funding, isolated margin, mmr 0.5%. Paper simulation only: no order function exists anywhere in this code.
RiskConfig limits are NOT changed by any candidate; a forward SUCCESS does not enable trading, it only lets the owner ask for a gate review.

## Success / failure criteria (fixed now; code: `tp.forward.CRITERIA` / `judge`, tested in `tests/test_round2_ops.py`)
| status | rule |
|---|---|
| RUNNING | fewer than 28 days of forward bars OR fewer than 20 trades |
| FAIL (mdd) | max drawdown > 20% at any time after day 7 |
| SUCCESS | >= 28 days, >= 20 trades, net return > 0, annualised Sharpe >= 0.5, max drawdown <= 15% |
| FAIL (sharpe<0) | >= 28 days and Sharpe < 0 |
| INCONCLUSIVE | everything else after 28 days: keep running, re-judge every week; no re-registration, no parameter change |
Benchmarks (C0) are never judged. A candidate must also beat the matching benchmark's Sharpe before the owner is asked anything; this comparison is made by a human, not automatically.
Even a SUCCESS on 28 days is weak evidence (Sharpe standard error over 28 days is far larger than 0.5): treat it as "not rejected", not "validated".

## Candidates
| id | what | why listed | research basis (round 2) | data needed |
|---|---|---|---|---|
| C0_buyhold_BTC / ETH | perp long 1x | benchmark | S1 | klines (auto-updated every 30 min by tp-news) |
| C1_trend_mtf_long_ETH_1h | coin_trend_mtf long ETH 1h | best 1h variant in S1 (Sharpe 1.05, DSR 0.13: NOT significant) | S1 | klines |
| C2_btc_alt_long_ETH_4h | coin_btc_regime_alt long ETH 4h | best variant overall in S1 (Sharpe 1.16, DSR 0.28: NOT significant); long-biased, funding drag ~5%/yr | S1 | klines, BTC klines |
| C3_trend_mtf_ls_BTC_1h | trend_mtf long/short BTC 1h | base for overlays; baseline OOS Sharpe was negative (-0.67) | S4 | klines |
| C3v_voltarget | C3 x clip(median_rv/rv, .25, 2) | only overlay that passed the H4 rule (3 of 4 bases improved, mean +0.135 Sharpe) | S4 (d) | klines |
| C3f_fomc | C3 flat +-6h around FOMC statements | negative control: H4 failed (2 of 4, placebo p 0.18-0.84) | S4 (a) | fomc_dates.json (36 dates to 2026-09; refresh with `fomc-fetch` after 2026-09 — dates after the last entry are NOT filtered) |
| C3r_retire | C3 x [30d shadow Sharpe > 0] | negative control: H4 failed (2 of 4, -0.16 mean) | S4 (e) | klines |
| C4_A1_rule_BTC | rule table by deterministic 4h regime (trend_up -> trend_mtf long 1h; trend_down -> short; range -> mean_reversion 15m w0.7; high_vol -> breakout_squeeze 15m w0.5), 15m clock | H2 passed at the 5m clock only (significant vs walk-forward best fixed, not vs buy&hold); failed at the 15m clock | S3 | klines BTC 4h/1h/15m |
| C6_llm_rm_on_C3 | C3 x risk_multiplier (<=1) recorded by the LLM regime agent (carried or fresh) | the only way to evaluate the LLM judgement: forward only. Compare with C3v (deterministic vol target) and plain C3 | none (cannot be backtested) | runs/regime_log.sqlite crypto rows (hourly, tp-sched) |

## Assumptions and limits
* Sample is tiny: 28 days gives ~20-80 trades per candidate; one regime. A pass is not evidence of skill. DSR-corrected research found NO configuration significant.
* Maker fills, VIP tier, BNB discount, true maintenance-margin brackets and slippage are assumptions (see RESULTS_round2.md cost-model section).
* C6 has a feedback-free design (the multiplier only scales C3; nothing flows to orders). Its carried rows repeat the last LLM judgement, so the effective number of independent LLM judgements is smaller than the number of hourly rows.
* The daily summary (23:00 UTC) prints the status line; `./run.sh research forward-eval` prints the full table.
