# Crash-filter comparison on the live momentum-rotation config (round `crash_cmp`, 2026-11-14)

Design frozen in `prereg.md` (addendum dated 2026-11-14) before running. Script: `run_crash_cmp.py`; raw numbers: `crash_cmp_numbers.json`; 21 rows appended to `ledger.jsonl` (`round: crash_cmp`). Engine `app/rs_sl_engine.py` unmodified (threshold varied by swapping `sim.crash` with `btc_flags(P, thr, 14)`). Parity check: variant A at -10% reproduces the existing live ledger cells exactly (full CAGR 79.15% / 86.61% / 71.06% at 4x/3x/2x; intraday MDD identical).

Config: lookback 14d, rebal 3d, K=8, deploy 0.95, no stops, funding on, 0.1%/side, kill -35% DD + 14d cooldown (except D), IS 2022-01..2024-06, OOS 2024-07..end, mean of 3 rebalance phases. Calmar = CAGR / intraday MDD. Worst month = worst calendar-month return (first month measured from window start). TiM = share of days with open positions. Kills/yr over full period; Liq = sum over 3 phases (cross-margin engine liquidation).


## 4x (primary)

| variant | win | CAGR | close MDD | intraday MDD | Calmar | Sharpe | end x | worst month | kills/yr | liq | TiM |
|---|---|---:|---:|---:|---:|---:|---:|---:|---:|---:|---:|
| A live (-10%, flatten all) | IS | 55.1% | 60.2% | 65.5% | 0.84 | 0.93 | 3.00 | -27.1% | 1.95 |  | 81% |
|  | OOS | 104.6% | 61.9% | 79.6% | 1.31 | 1.24 | 5.10 | -28.6% | 1.95 |  | 84% |
|  | full | 79.2% | 61.9% | 79.6% | 0.99 | 1.09 | 16.25 | -28.6% | 1.95 | 0 | 82% |
| B crash filter OFF | IS | 89.6% | 57.5% | 61.1% | 1.47 | 1.14 | 5.01 | -23.6% | 2.44 |  | 93% |
|  | OOS | 42.6% | 74.8% | 85.3% | 0.50 | 0.84 | 2.24 | -34.5% | 2.44 |  | 88% |
|  | full | 67.5% | 74.8% | 85.3% | 0.79 | 1.01 | 11.93 | -34.5% | 2.44 | 0 | 91% |
| C longs-only flatten (-10%) | IS | 24.6% | 65.9% | 67.9% | 0.36 | 0.70 | 1.75 | -31.4% | 3.07 |  | 88% |
|  | OOS | 20.7% | 74.4% | 81.8% | 0.25 | 0.71 | 1.54 | -50.2% | 3.07 |  | 88% |
|  | full | 24.2% | 84.3% | 85.4% | 0.28 | 0.72 | 2.86 | -50.2% | 3.07 | 0 | 88% |
| D filter OFF + kill OFF (ref) | IS | 95.6% | 56.7% | 62.8% | 1.57 | 1.16 | 5.51 | -28.0% | 0.00 |  | 100% |
|  | OOS | 103.9% | 67.9% | 78.1% | 1.38 | 1.15 | 5.84 | -39.5% | 0.00 |  | 100% |
|  | full | 97.2% | 68.5% | 78.1% | 1.26 | 1.17 | 28.01 | -39.5% | 0.00 | 0 | 100% |
| A thr -7% | IS | 126.9% | 49.6% | 56.9% | 2.23 | 1.37 | 7.76 | -24.7% | 1.88 |  | 77% |
|  | OOS | 40.9% | 66.3% | 79.6% | 0.51 | 0.82 | 2.18 | -30.2% | 1.88 |  | 76% |
|  | full | 83.0% | 66.3% | 79.6% | 1.04 | 1.13 | 17.97 | -30.2% | 1.88 | 0 | 77% |
| A thr -15% | IS | 14.9% | 68.2% | 70.9% | 0.22 | 0.58 | 1.43 | -30.1% | 2.51 |  | 85% |
|  | OOS | 36.5% | 71.2% | 74.0% | 0.49 | 0.80 | 2.03 | -33.5% | 2.51 |  | 87% |
|  | full | 26.1% | 72.1% | 74.6% | 0.35 | 0.70 | 3.08 | -33.5% | 2.51 | 0 | 86% |
| A thr -20% | IS | 60.0% | 59.8% | 63.2% | 0.95 | 0.96 | 3.27 | -23.6% | 2.65 |  | 88% |
|  | OOS | 46.7% | 73.1% | 84.3% | 0.55 | 0.87 | 2.39 | -34.5% | 2.65 |  | 88% |
|  | full | 55.4% | 73.1% | 84.3% | 0.66 | 0.93 | 8.32 | -34.5% | 2.65 | 0 | 88% |

## 3x (secondary)

| variant | win | CAGR | close MDD | intraday MDD | Calmar | Sharpe | end x | worst month | kills/yr | liq | TiM |
|---|---|---:|---:|---:|---:|---:|---:|---:|---:|---:|---:|
| A live (-10%, flatten all) | IS | 77.3% | 51.4% | 56.6% | 1.36 | 1.16 | 4.25 | -23.4% | 0.98 |  | 86% |
|  | OOS | 95.1% | 59.4% | 63.1% | 1.56 | 1.25 | 4.72 | -30.3% | 0.98 |  | 85% |
|  | full | 86.6% | 61.5% | 64.0% | 1.37 | 1.22 | 20.92 | -30.3% | 0.98 | 0 | 85% |
| B crash filter OFF | IS | 91.3% | 43.4% | 46.5% | 1.96 | 1.26 | 5.14 | -20.3% | 1.68 |  | 97% |
|  | OOS | 41.5% | 69.0% | 71.7% | 0.58 | 0.83 | 2.20 | -32.3% | 1.68 |  | 90% |
|  | full | 67.0% | 69.0% | 71.7% | 0.93 | 1.05 | 11.84 | -32.3% | 1.68 | 0 | 93% |
| C longs-only flatten (-10%) | IS | 57.4% | 52.2% | 55.3% | 1.04 | 0.96 | 3.13 | -25.1% | 1.68 |  | 95% |
|  | OOS | 59.2% | 66.6% | 69.5% | 0.85 | 0.98 | 2.88 | -42.7% | 1.68 |  | 92% |
|  | full | 59.7% | 66.6% | 69.5% | 0.86 | 0.98 | 9.43 | -42.7% | 1.68 | 0 | 93% |
| D filter OFF + kill OFF (ref) | IS | 74.6% | 46.4% | 51.8% | 1.49 | 1.12 | 4.08 | -21.2% | 0.00 |  | 100% |
|  | OOS | 93.1% | 56.3% | 66.2% | 1.46 | 1.18 | 4.85 | -30.6% | 0.00 |  | 100% |
|  | full | 82.5% | 57.1% | 66.2% | 1.27 | 1.16 | 18.71 | -30.6% | 0.00 | 0 | 100% |
| A thr -7% | IS | 96.3% | 42.7% | 50.2% | 1.92 | 1.33 | 5.44 | -24.6% | 1.05 |  | 78% |
|  | OOS | 44.1% | 62.1% | 65.5% | 0.67 | 0.86 | 2.30 | -34.7% | 1.05 |  | 79% |
|  | full | 70.9% | 62.1% | 65.5% | 1.08 | 1.11 | 13.06 | -34.7% | 1.05 | 0 | 79% |
| A thr -15% | IS | 74.5% | 47.5% | 50.4% | 1.53 | 1.13 | 4.10 | -20.2% | 1.61 |  | 91% |
|  | OOS | 63.9% | 71.7% | 73.2% | 0.87 | 1.02 | 3.08 | -32.3% | 1.61 |  | 87% |
|  | full | 70.8% | 71.7% | 73.2% | 0.97 | 1.08 | 13.20 | -32.3% | 1.61 | 0 | 89% |
| A thr -20% | IS | 94.0% | 43.4% | 46.5% | 2.02 | 1.28 | 5.31 | -20.3% | 1.68 |  | 94% |
|  | OOS | 44.8% | 69.0% | 71.7% | 0.62 | 0.86 | 2.32 | -32.3% | 1.68 |  | 89% |
|  | full | 70.2% | 69.0% | 71.7% | 0.98 | 1.08 | 12.90 | -32.3% | 1.68 | 0 | 91% |

## 2x (secondary)

| variant | win | CAGR | close MDD | intraday MDD | Calmar | Sharpe | end x | worst month | kills/yr | liq | TiM |
|---|---|---:|---:|---:|---:|---:|---:|---:|---:|---:|---:|
| A live (-10%, flatten all) | IS | 62.8% | 30.0% | 34.0% | 1.87 | 1.26 | 3.38 | -13.0% | 0.07 |  | 88% |
|  | OOS | 78.7% | 35.4% | 43.2% | 1.84 | 1.36 | 3.80 | -21.2% | 0.07 |  | 90% |
|  | full | 71.1% | 36.0% | 43.2% | 1.65 | 1.32 | 13.25 | -21.2% | 0.07 | 0 | 89% |
| B crash filter OFF | IS | 51.0% | 33.9% | 38.1% | 1.39 | 1.08 | 2.81 | -14.3% | 0.42 |  | 99% |
|  | OOS | 73.7% | 42.5% | 53.5% | 1.44 | 1.24 | 3.60 | -19.3% | 0.42 |  | 97% |
|  | full | 61.9% | 42.5% | 53.5% | 1.18 | 1.17 | 10.19 | -19.3% | 0.42 | 0 | 98% |
| C longs-only flatten (-10%) | IS | 32.7% | 44.5% | 47.3% | 0.69 | 0.78 | 2.03 | -22.4% | 0.84 |  | 97% |
|  | OOS | 58.0% | 47.1% | 49.9% | 1.16 | 1.06 | 2.83 | -23.4% | 0.84 |  | 97% |
|  | full | 45.0% | 47.4% | 49.9% | 0.90 | 0.93 | 5.92 | -23.6% | 0.84 | 0 | 97% |
| D filter OFF + kill OFF (ref) | IS | 50.9% | 34.0% | 38.1% | 1.38 | 1.08 | 2.81 | -14.3% | 0.00 |  | 100% |
|  | OOS | 71.2% | 42.4% | 50.8% | 1.45 | 1.20 | 3.53 | -21.1% | 0.00 |  | 100% |
|  | full | 60.4% | 43.0% | 50.8% | 1.21 | 1.15 | 9.80 | -21.1% | 0.00 | 0 | 100% |
| A thr -7% | IS | 72.3% | 29.4% | 34.1% | 2.13 | 1.40 | 3.89 | -15.0% | 0.07 |  | 80% |
|  | OOS | 74.3% | 36.0% | 47.8% | 1.63 | 1.34 | 3.61 | -21.4% | 0.07 |  | 84% |
|  | full | 74.1% | 36.8% | 47.8% | 1.60 | 1.38 | 14.55 | -21.2% | 0.07 | 0 | 82% |
| A thr -15% | IS | 45.1% | 33.8% | 37.7% | 1.24 | 1.01 | 2.54 | -13.7% | 0.49 |  | 93% |
|  | OOS | 52.8% | 46.2% | 56.2% | 0.94 | 1.03 | 2.65 | -21.0% | 0.49 |  | 93% |
|  | full | 49.4% | 46.2% | 56.2% | 0.88 | 1.03 | 6.86 | -21.0% | 0.49 | 0 | 93% |
| A thr -20% | IS | 56.1% | 33.9% | 38.1% | 1.52 | 1.15 | 3.05 | -14.3% | 0.42 |  | 96% |
|  | OOS | 65.4% | 46.5% | 54.4% | 1.35 | 1.13 | 3.32 | -18.8% | 0.42 |  | 96% |
|  | full | 60.6% | 46.5% | 54.4% | 1.20 | 1.15 | 10.34 | -18.8% | 0.42 | 0 | 96% |

Window-level end multiples are per window (IS and OOS each start at 1.0); only `full` is the compounded path.

## 42 BTC crash episodes (-10% flag, contiguous runs since 2022-01-01)

Per episode: equity change from the close before the first flagged day to the close of the last flagged day, phase-averaged, A (flatten, live) vs B (hold). Paths diverge over time (kill switch timing), so this is a window-wise comparison on each variant's own path, not a clean counterfactual.

| lev | mean chg A | mean chg B | #positive A | #positive B | sum log(1+chg) A | sum log(1+chg) B | B>A (episodes) |
|---|---:|---:|---:|---:|---:|---:|---:|
| 4x | -0.28% | 0.39% | 16/42 | 19/42 | -0.138 | +0.082 | 21/42 |
| 3x | 0.01% | 0.57% | 24/42 | 23/42 | -0.006 | +0.168 | 22/42 |
| 2x | 0.11% | 0.39% | 24/42 | 25/42 | +0.041 | +0.125 | 21/42 |

Worst 5 episodes under B at 4x:

| episode | dates | days flagged | B | A (same window) |
|---:|---|---:|---:|---:|
| 41 | 2026-06-02 .. 2026-06-14 | 13 | -20.5% | -1.1% |
| 11 | 2022-08-19 .. 2022-08-19 | 1 | -8.0% | -8.0% |
| 20 | 2023-08-18 .. 2023-08-19 | 2 | -7.9% | -5.1% |
| 23 | 2024-06-24 .. 2024-06-24 | 1 | -7.0% | -7.0% |
| 17 | 2022-09-24 .. 2022-09-26 | 3 | -6.7% | -0.9% |

Best 5 episodes under B at 4x:

| episode | dates | B | A |
|---:|---|---:|---:|
| 8 | 2022-05-07 .. 2022-05-22 | 13.1% | 5.0% |
| 28 | 2024-08-09 .. 2024-08-12 | 12.0% | -0.4% |
| 27 | 2024-08-04 .. 2024-08-07 | 11.1% | -0.3% |
| 18 | 2022-11-09 .. 2022-11-22 | 8.7% | -4.3% |
| 25 | 2024-07-04 .. 2024-07-05 | 7.6% | 3.1% |

## Liquidation check, 4x cross-margin (per phase 0/1/2)

Engine test: liquidated if hourly worst-case equity <= maintenance margin. Also min(intraday-worst equity / prior close equity) and its date, worst close-to-close day, peak gross exposure / equity.

| variant | phase | liquidated | min worst/prev close | date | worst close day | peak gross/equity | kills |
|---|---:|---|---:|---|---:|---:|---:|
| B crash filter OFF | 0 | False | 0.376 | 2025-10-10 | -24.2% | 5.53x | 12 |
| B crash filter OFF | 1 | False | 0.376 | 2025-10-10 | -24.2% | 5.53x | 11 |
| B crash filter OFF | 2 | False | 0.376 | 2025-10-10 | -24.2% | 5.53x | 12 |
| A live (-10%, flatten all) | 0 | False | 0.331 | 2025-10-10 | -24.3% | 5.62x | 10 |
| A live (-10%, flatten all) | 1 | False | 0.331 | 2025-10-10 | -24.3% | 5.62x | 9 |
| A live (-10%, flatten all) | 2 | False | 0.331 | 2025-10-10 | -24.3% | 5.62x | 9 |
| D filter OFF + kill OFF (ref) | 0 | False | 0.376 | 2025-10-10 | -25.7% | 5.53x | 0 |
| D filter OFF + kill OFF (ref) | 1 | False | 0.331 | 2025-10-10 | -27.9% | 8.64x | 0 |
| D filter OFF + kill OFF (ref) | 2 | False | 0.378 | 2024-12-09 | -24.3% | 5.76x | 0 |

## Reading the results (descriptive, no recommendation)

- 4x full period: A (live) CAGR 79.2%, intraday MDD 79.6%, Calmar 0.99, 16.3x; B (off) 67.5%, 85.3%, 0.79, 11.9x, worst month -34% vs -29%, 2.44 vs 1.95 kills/yr, 0 liquidations in all variants. Removing the filter looks worse on the full path, but the sign flips by window: IS B beats A (89.6% vs 55.1% CAGR, Calmar 1.47 vs 0.84), OOS A beats B (104.6% vs 42.6%, Calmar 1.31 vs 0.50). No window-robust ordering exists. The same flip occurs at 3x; at 2x A leads in both windows (full 71.1% vs 61.9%, Calmar 1.65 vs 1.18).
- D (filter off and kill off) is the best row at 4x full (97.2%, 28.0x, Calmar 1.26, intraday MDD 78.1%, no liquidation), i.e. the kill switch, not the crash filter, is the larger drag in this sample at 4x (see v3 report). Reference only; its MDD is still 78% and its path includes the 2025-10-10 day below.
- Threshold sweep at 4x (full CAGR / Calmar): -7% 83.0%/1.04, -10% 79.2%/0.99, -15% 26.1%/0.35, -20% 55.4%/0.66, off 67.5%/0.79. The curve is non-monotonic and IS/OOS rank orders disagree (-7% IS 127% vs OOS 41%; -10% opposite). Differences are dominated by when kills happen to fire (kill timing is path-chaotic), not by a clean threshold effect. -7% is not evidence that a tighter trigger helps.
- C (longs-only flatten) is clearly worst at 4x (full 24.2%, 2.9x) and weak at 2x/3x; leaving shorts on while flattening longs reduces hedge balance without removing the exposure.
- Episodes (42, mean per-episode equity change, 4x): A -0.28% (16/42 positive), B +0.39% (19/42 positive); sum of log changes A -0.138 vs B +0.082, i.e. holding through episodes is worth about +0.22 log units (~+25%) cumulatively out of total log growth ln(16.3)=2.79 (A) over 4.8 years. B beats A in 21/42 episodes, so it is a coin flip per episode with fat tails: the episode edge is smaller than the full-path gap, meaning most of the A/B CAGR gap arises outside the flagged windows (re-entry timing after release and kill-switch path divergence), not inside them. At 3x: A +0.01% vs B +0.57%; 2x: +0.11% vs +0.39%.
- Worst 5 episodes under B at 4x: 2026-06-02..06-14 (-20.5%, A -1.1%), 2022-08-19 (-8.0%), 2023-08-18..19 (-7.9%, A -5.1%), 2024-06-24 (-7.0%), 2022-09-24..26 (-6.7%, A -0.9%). A single episode (June 2026) accounts for most of B's tail cost.
- Liquidation check, 4x B: no cross-margin liquidation in any phase (A and D also none). Closest call is 2025-10-10, when intraday-worst equity fell to 37.6% of the prior close (B) and 33.1% (A, D phase 1), with peak gross exposure 5.5x equity (8.6x for D phase 1) and worst close-to-close day -24%. Liquidation occurs only when equity-at-worst hits maintenance margin, so the margin of safety was real but thin: a slightly larger one-day gap would liquidate, and this uses hourly H/L only (no sub-hour wicks, no exchange auto-deleveraging, no per-symbol isolated limits).

## Caveats

- Survivorship bias: the panel universe is symbols that exist and have full history; delisted or failed perps are absent, which inflates both long and short books and likely flatters leverage (collapsed coins that would have hit shorts or longs are missing).
- Single historical path, ~4.8 years, 42 crash episodes heavily clustered in 2022 and 2026; the kill switch makes outcomes path-chaotic (a small difference in timing changes whether and when a kill fires), so differences of tens of CAGR points between neighbouring thresholds are within noise, and the IS-versus-OOS sign flips confirm it.
- 21 cells added to the study's trial count (cumulative 888). Not selected or tuned; nothing here is a recommendation to change the bot.
- Episode metric is window-wise on each variant's own path (not a matched counterfactual); episodes under A start flat only after the first flagged day closes, mirroring the engine's day-close flag.
