# stock_loop — KR/US short-term strategy search (owner: user; started 2026-11-13)

Roles: session "coin-trade" = KR + shared lib (lib/). session "리눅스 투자 세션" = US. Each calls its own Codex agents. Share via this dir only.
Files: PLAN.md (this), LEDGER.md (one row per strategy: id, market, idea, stage, key net metrics, verdict, next), spec/<id>/prereg.md, results/<id>/..., lib/ (shared harness), lib/READY (created when harness done).

## Goal
Find several promising SHORT-TERM (hold ~intraday..5 trading days, "빠르게 먹고 다른 대상") strategies on KR and US stocks, then tune the survivors to the best one(s). Fast loop: hypothesis -> test -> small parameter tweaks -> summary -> go/no-go. Daily bars first (long history). Intraday/minute data is short here (KR tick since ~2026-10, yfinance minute only recent): use it ONLY to generate hypotheses, never as validation.

## Costs (verified 2026-11-13 via web; re-check tax)
- KR: Toss Prime = 5,900 KRW/month; commission INCL. 유관기관 fees refunded as cashback up to 100M KRW cumulative monthly turnover; above cap or without Prime: 0.015% per side (KRX). Sell-side 증권거래세(+농특세) applies always — look up the CURRENT 2026 rate from an official source (KRX/NTS), put it in lib/costs.py, test 0.18% and 0.20% as sensitivity. Model BOTH scenarios: A=Prime (commission 0 up to 1e8 KRW monthly turnover, fixed 5,900/mo cost, then 0.015%/side), B=no Prime (0.015%/side). Slippage: KR 0.05-0.10%/side by liquidity.
- US: Toss 0.1%/side commission (orders <= $10 free), SEC fee on sells ~0.00278% (check), FX spread ~0.1% per round trip with 우대, slippage 0.05%/side. Always run 2x cost sensitivity.
- Account is small (~1.3M KRW scale): capacity is not the constraint, costs are.

## Method (anti-overfit; mandatory)
1. Reserve a FINAL HOLDOUT = last 24 months. Never look at it during Stages 1-2. One look in Stage 3.
2. Stage 1 SCREEN: <=12 hypotheses per market with default params, event-study + simple portfolio; write prereg.md BEFORE running. Keep only: net-of-cost mean trade return > 0 with |t|>=3 on development data, same sign in both halves of dev data.
3. Stage 2 TUNE: small grid around defaults (<=3 params x 3 values); require a PLATEAU (neighbors also positive), not a spike; walk-forward. Count all trials for multiple-testing (BH q<0.10).
4. Stage 3 VALIDATE on the holdout: net Sharpe >= 1.0, beats random-entry baseline (>=1000 draws, >=95th pct), positive in >=70% of years in dev data, survives 2x cost, >=200 trades, max concurrent positions <=10, worst-trade/drawdown reported. Survivorship bias (no delisted names) must be stated and discounted; prefer liquid large caps.
5. Verdicts: advance / noise / hurts. Max 6 rounds per market; after each round post <=15 lines to LEDGER.md and message the other session. User decides go/no-go on summaries.

## Safety (linuxserver runs the LIVE Binance bot + whole site)
Work only in /home/noroot/research/stock_loop/ (NOT inside /home/noroot/CODE/Ochestration: auto_deploy cron pulls it). Never stop/restart containers/services; never read/print .env/alert.env/secrets/bot state volumes; no sudo; no GitHub push. Heavy jobs: `flock /home/noroot/research/stock_loop/.heavy.lock nice -n 19 ionice -c3 <cmd>` (one heavy job at a time across both sessions), memory cap (systemd-run --user --scope -p MemoryMax=3G else ulimit -v), <=2 workers; check uptime/free -m first; abort if load>4 or avail RAM<2 GiB. Public data only (FinanceDataReader/pykrx/yfinance), low rate, cached under lib/cache/.
Reuse /home/noroot/research/gulp_pattern/ (gulp.py, fetch.py) for data loaders, validation and random baseline; the 'gulp' strategy itself was tested = noise (do not retest).
