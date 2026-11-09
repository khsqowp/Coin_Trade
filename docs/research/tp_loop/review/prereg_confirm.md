# PRE-REGISTRATION (REVIEWER) - single confirmatory test of the short-side TP (A's T09)
Timestamp (UTC): see `date -u` stamp appended at file end (written BEFORE any of the 6 cells below was executed).

## Disclosure of what I already knew when writing this
- I had read A's results.json (T09 IS/OOS/full numbers, DSR, PBO, bootstrap, neighbour fails), and I had run diag_events.py on T09's 83 TP events (3 phases).
  That diagnostic showed the 29 unique (symbol, exit-date) events fall in ~5 market-wide flash days (2022-06-13, 2024-04-12/13, 2025-02-03, 2025-10-10).
  Therefore the "wick-capture on liquidation-cascade days" mechanism is a POST-HOC OBSERVATION and this test is NOT independent of it.
  I had NOT run any T09 variant at other leverage / kill settings before writing this file.

## Question
Does T09 (short-only full TP at -40% underlying, hourly low <= entry*0.6, fill at threshold, 0.1%/side cost, re-entry allowed) beat V0 once the kill-path chaos of the LIVE config is removed or perturbed?

## Engine / data
app/rs_tp_engine.py (A's engine, verified bit-exact vs rs_final_engine with TP off), same 45-symbol hourly panel, 3 rebalance phases (0,1,2), lookback 14, rebal 3, K 8/8, cost 0.001, real funding, crash flat, cool 14, minn 0, eq0 1.
IS = 2022-01-01..2024-06-30, OOS = 2024-07-01..end. Metrics are phase means (window_metrics: CAGR, intraday MDD; Calmar_i = CAGR/intraday MDD; daily Sharpe*sqrt(365)).

## The 6 configs (complete; nothing added after results). T09 and V0 are always run in the SAME cell.
| id | lev | deploy | kill | purpose |
|---|---|---|---|---|
| K33 | 4.0 | 0.95 | 0.33 | LIVE with kill -0.02 |
| K37 | 4.0 | 0.95 | 0.37 | LIVE with kill +0.02 |
| KOFF | 4.0 | 0.95 | 1.00 (disabled) | LIVE without kill (liquidation can occur) |
| L15 | 1.5 | 0.95 | 0.35 | low-leverage, kill-free regime |
| L20 | 2.0 | 0.95 | 0.35 | research-like leverage |
| L30 | 3.0 | 0.95 | 0.35 | intermediate |
(lev 2.5 omitted to respect the 6-config cap.)

## Cell PASS definition (all must hold, phase means)
1. full-window dSharpe(T09 - V0) >= +0.20 (0.20 > B's measured V0 Sharpe noise max 0.178),
2. full-window dCalmar_i > 0,
3. CAGR(T09) >= 0.9 * CAGR(V0) in full window,
4. dCalmar_i > 0 in IS AND dCalmar_i > 0 in OOS.
A cell where either arm liquidates is UNINFORMATIVE (excluded); at least 4 informative cells are needed, else the test is inconclusive.

## Decision rule (fixed in advance)
- SURVIVES: >= 5 of 6 cells PASS (or >= 80% of informative cells, min 4 informative). Result label = "consistent, not refuted". Even then the reviewer verdict cannot exceed NOT PROVEN, because (a) effective independent trigger events ~5 flash days, (b) wick fills are not verifiable from hourly H/L, (c) the live bot has no resting-limit infrastructure.
- REFUTED (chaos artifact): <= 3 of 6 PASS. Short-TP line of research is closed.
- 4 of 6: AMBIGUOUS -> report as such, no upgrade.
Also fixed: the lev-ladder low-chaos cells (L15, L20, L30) must have >= 2 of 3 PASS for any "SURVIVES" label, otherwise label downgraded to AMBIGUOUS.

## Descriptive diagnostics (NOT decision configs, not counted as trials, cannot upgrade a verdict)
D1. Distinct trigger dates and the share of T09 events on days with >= 3 simultaneous triggers (phase 0 baseline LIVE).
D2. T09 re-run with the TP switched off on those cluster days (copy of the engine in review/ folder, bit-exact vs A when mask is all ones), in cells LIVE(4.0,0.95,0.35) and L20; report dCalmar_i/dSharpe vs V0. Interpretation: advantage that vanishes => "4-day bet".
D3. Net exposure drift: mean (long notional - short notional)/equity in V0 vs T09 (TP breaks dollar neutrality).

## Exploratory (item 5, NOT a recommendation): V0-only leverage ladder lev {2,2.5,3,4} x deploy {0.95,1.0} plus lev 3.8 x deploy 1.0; Calmar_i, CAGR, MDD, kills, IS/OOS.
STAMP 2026-10-30T14:09:55Z
