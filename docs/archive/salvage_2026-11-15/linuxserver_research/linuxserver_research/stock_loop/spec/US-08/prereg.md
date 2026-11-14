# US-08 — Turn-of-month index drift (US, Stage 1 prereg)
Written 2026-11-13 by the US-side session BEFORE any run. Owner of the market: US session.

## Idea
Index ETFs earn most of their return around the month turn.

## Signal (fixed defaults)
Calendar: the second-to-last trading day of the month close to the third trading day of the next month close, on SPY and QQQ (separately).

## Execution
Buy at close of trading day -2, sell at close of trading day +3. Costs are tiny relative to a 5-day hold.

## Defaults
-2 .. +3 trading-day window.

## Outputs required
Event study (n trades, mean net return, t-stat clustered by day, hit rate, avg hold), same-sign check in both dev halves, 2x-cost result, simple portfolio curve (max concurrent positions per PLAN), worst trade. Holdout is NOT touched.

## Verdict rule
advance / noise / hurts exactly per PLAN.md Stage 1.

## Common (all US hypotheses; copied from PLAN.md, nothing here overrides it)
- Data: KIS daily OHLCV (adjusted, MODP=1) from linuxserver `.kis-cache` (US stocks 2010-12..2026-11-11 for most, short history for DELL/BKNG/HOOD etc.; US ETFs 2010-12..). READ-ONLY copy; never write into the repo dir. No intraday data in Stage 1.
- Universe default: point-in-time liquid names = rank by 60-day median dollar volume, top 30 each day (as in aw_data.py), plus the ETFs where stated. Survivorship (today's large caps, no delisted names) is a stated, unfixable bias; every result is discounted for it.
- Dev data: start .. 2024-11-11. Final holdout (untouched until Stage 3): 2024-11-12 .. 2026-11-11. Dev halves split at the dev-sample midpoint by date.
- Costs per side (default scenario): commission 0.10% + slippage 0.05% + FX 0.05% (round trip 0.10% FX with preferential rate) + SEC fee on sells 0.00278%. 2x-cost sensitivity always reported. Entry/exit fills: stated per hypothesis (open or close of the bar); signals use only information available at that moment.
- Stage 1 pass rule: net mean trade return > 0 with |t| >= 3 on dev data, same sign in both dev halves; trades counted per signal-day (clustered by day for t-stats, since same-day signals are correlated).
- No parameter search in Stage 1: the defaults below are fixed before any run. Any change is a new hypothesis with a new id and increments the trial count.
