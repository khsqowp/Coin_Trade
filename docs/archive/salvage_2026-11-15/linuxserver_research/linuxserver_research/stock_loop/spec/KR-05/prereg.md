# KR-05 - IBS<=0.2 & close>MA200 mean reversion, buy next open, hold 3 (KR, Stage 1 prereg)
Written 2026-11-13T16:13:36 by the KR session BEFORE any run.

## Signal
IBS=(C-L)/(H-L) <= 0.2 at close t AND close_t > SMA200. Buy open t+1, sell close t+3 (3 bars).

## Defaults (fixed)
{'x': 0.2, 'h': 3, 'ma': 200}

## Stage-2 grid
{'x': (0.1, 0.2, 0.3), 'h': (2, 3, 5), 'ma': (0, 100, 200)}

## Common (all KR hypotheses)
- Data: FinanceDataReader/Naver daily OHLCV (price-adjusted) cached under gulp_pattern/cache (read-only reuse, no re-download); calendar = KOSPI index days. Bars with volume 0 or price<=0 are NaN.
- Universe: KOSPI+KOSDAQ names in kr_universe.csv with code ending 0 (excludes preferred), excluding SPAC/ETF/ETN/REIT-like names by name regex. Liquidity: 20-bar mean traded value (close*volume) >= 2e9 KRW, known at signal bar (for open-entry-same-day signals the value is lagged one bar).
- SURVIVORSHIP: the listing is of CURRENTLY listed names only (no delisted). Results are upward-biased, esp. for mean-reversion/oversold ideas; discount accordingly.
- Dev data: start (2014-08) .. 2024-11-11. FINAL HOLDOUT 2024-11-12..2026-11-12 stays locked (lib.splits guard); never unlocked in Stage 1-2. Dev halves split at the dev-sample midpoint (by bar).
- Costs (lib/costs.py): sell tax 0.20% (2026 KOSPI 0.05%+0.15% 농특세 / KOSDAQ 0.20%), commission 0.015%/side, slippage 0.05%/side if 20d value >= 2e10 KRW else 0.10%/side. Scenario A (Toss Prime: commission 0 within 1e8 KRW/month turnover, fixed 5,900 KRW/month) and B (no Prime). Sensitivities: tax 0.18%, 2x all costs. Gating scenario = B (stricter per trade); A shown.
- Stage 1 pass rule (PLAN): net mean trade return > 0, |t|>=3 (SE clustered by entry date), same sign in both dev halves. Defaults fixed here; NO parameter search in Stage 1. Long-only.
- Portfolio: equal weight, max 5 concurrent (capital 1.3M KRW, N=5), first-come by entry time with seeded random tie-break; Sharpe from realised daily P&L (annualised sqrt(252)); implied monthly turnover (buy+sell notional) reported vs Prime cap 1e8 KRW.
- Also reported: break-even round-trip cost (= gross mean trade return).
- Stage 2 (survivors only, max one round): grid of <=3 params x 3 values listed below; plateau rule: >=70% of grid cells have net mean>0 and t>=2 AND all axis-neighbours of the default are net-positive; BH q<0.10 over ALL trials (Stage-1 + Stage-2 cells); random-entry baseline (1000 draws, same entry dates) percentile reported.
- Verdicts: advance / noise / hurts exactly per PLAN.md.
