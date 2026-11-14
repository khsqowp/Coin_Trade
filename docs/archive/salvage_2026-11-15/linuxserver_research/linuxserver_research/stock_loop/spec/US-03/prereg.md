# US-03 — Overnight vs intraday return decomposition (diagnostic) (US, Stage 1 prereg)
Written 2026-11-13 by the US-side session BEFORE any run. Owner of the market: US session.

## Idea
Most of the index drift accrues overnight; an overnight-only holding could capture it.

## Signal (fixed defaults)
No signal: decompose open/close returns for SPY, QQQ and the 30-name universe; test buy close_t / sell open_{t+1} every day, and only on days when close_t < SMA5 (pullback state).

## Execution
Buy close t, sell open t+1 (hold overnight). Expect daily round-trip costs to dominate; reported mainly to settle the question and to feed the state-conditioned variant.

## Defaults
Unconditional daily and 'close < SMA5' conditional variants.

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
