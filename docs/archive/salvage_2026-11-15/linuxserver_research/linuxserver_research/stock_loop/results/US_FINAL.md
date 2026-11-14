# US_FINAL - US-18-T100 "momentum-leader dip" (US session, 2026-11-13)

## Strategy (frozen)
Universe: point-in-time top-100 by 20-day traded value out of 503 CURRENT S&P 500 names (harness cache, adjusted prices). Signal at close t: stock is in the top quartile of 126-day return within that day's universe AND RSI(2)<5. Buy at close t; exit at the first close above SMA5 within 5 bars, else close t+5. Costs: USCost (round trip 0.403%). Equal-weight slots (N=10).

## Process / trial count
Stage 1: 30 trials (12 preregs + variants/breadth), 0 survivors. Round 2: 8 new preregs (15 trials), US-18 survived (T30 t=3.07, T100 t=3.66). Stage 2: 27-cell grid x 2 universes (54 trials), cumulative 99, BH q(default) 0.006 (T30) / 0.001 (T100). Plateau in both (ok-frac 1.00 / 0.93; all neighbours positive). Walk-forward 2014-24: T30 +0.35% t=1.62 (FAIL, so T30 not a candidate), T100 +0.51% t=3.91. Candidate chosen by pre-registered neighbour-smoothed mean: RSI<5, 126d, top 0.25.

## Stage 3 (holdout 2024-11-12..2026-11-11, one look, spec/US-18/stage3_prereg.md)
410 trades, net +1.984%/trade, t=3.31 (block-clustered 2.70), hit 70%, worst trade -20.2%. N=10 portfolio Sharpe 2.01 (N=5: 1.83), max drawdown -12.8% (N=5: -14.4%), max concurrent 10, 332 accepted trades. Random-entry percentile 100 (2000 draws; random mean +0.55%). 2x cost mean +1.58% (t=2.64). Dev years positive 93%. All six criteria PASS.
Dev reference: n=3323, net +0.52%, t=4.62, N=10 Sharpe 0.96, 2x-cost +0.12%, 3x-cost -0.28%.

## Why this must be discounted
1. Holdout is ~4x dev. P&L is concentrated in recent high-momentum names (BE, WDC, HOOD, CRWD, RDDT: 35% of total P&L; 2026 median trade +3.2%); mean excluding top-10% trades +0.58%; mean excluding 2025-03-25..05-15 +1.66%.
2. Survivorship/selection: the universe is today's S&P 500, which includes names that entered the index because they rose. Frozen universes with unchanged parameters: top-100 frozen 2024-11-11 -> holdout +0.99%, t=2.06, Sharpe 1.11, 2x +0.58% (dev +0.63%, 2x +0.23%, Sharpe 1.20); frozen 2014-12-31 -> holdout +0.45%, t=1.56, Sharpe 0.81, 2x +0.05% (FAILS the Sharpe>=1 bar); dev +0.41%, 2x +0.01%. Realistic edge: ~0.4-1.0% net per trade, i.e. 0.0-0.6% after 2x costs.
3. Breadth: T50 dev +0.55% (t 4.35), T100 +0.52%, T30 +0.45% (dev 2x +0.05%), T200 +0.46% (hold +1.10%), T400 +0.29% (dev 2x -0.12%, Sharpe 0.24). Edge lives in liquid, high-attention names.
4. Cost sensitivity: dev edge turns negative at 3x cost; thin vs. real slippage. Next-open entry (feasible for KST) costs ~0.14% dev / 0.44% holdout vs close entry but stays positive: dev +0.38% (2x -0.02%), holdout +1.55%.
5. Year-by-year (T100, full sample): negative only 2022 (-0.37%); others positive, 2026 +3.07%.
6. Tax (22% above 2.5M KRW/yr) not modelled; bear markets like 2022 are the main risk (2022 mean -0.37%, 353 trades).

## Recommendation
Do not trade live capital on this. At most paper-trade US-18-T100 (next-open entry, N<=10) for a few months; require point-in-time constituents to rebuild the test. Tests: us/tests/test_us.py (5 unit tests) pass.

## Files
spec/US-ADDENDUM-data.md, spec/US-01..20/prereg.md, spec/US-18/stage2_prereg.md, stage3_prereg.md; us/ (code); results/US_stage1.json, US_round2.json, results/US-18/{stage2,stage3,robustness,survivorship}.json, holdout_trades_US-18-T100.parquet, results/US-xx/trades_*.parquet.


---
# UPDATE after rounds 4-6 (coordinator request: survivorship-robust search)
Result: NO further candidate passes. 140 cumulative trials (30 + 15 + 54 Stage-2 cells + 13 + 17 + 11). Stage 1 survivors after round 3 (US-32 DYN h5/h10/h20, US-33a-DYN, US-33c-DYN) exist only on the dynamic top-100 universe; the same specifications on universes frozen at 2014-12-31 (F14) and 2018-12-31 (F18) are noise (t 1.0-2.8, 2x-cost mean mostly negative), so they were not carried to Stage 2 under the stricter gate fixed in spec/US-33/prereg.md before Stage 2 was ever run. No new Stage 3, no new holdout look.
Key findings (dev only):
- US-18 default cell on frozen universes: +0.09% (t 0.94, F14), +0.13% (t 1.07, F18) vs +0.29% (t 3.66) dynamic. Different leader definitions (12-1, 52w-high) and dip triggers (IBS, 3d drop, SMA10) on frozen universes: best US-25-F14 (126d leader, close<=0.96*SMA10) +0.50% t=2.35, 2x +0.10%, top-5 share 0.38; below t=3.
- Fixed holds 5/10/20 raise gross with horizon (0.6 -> 1.1 -> 1.7%) and US-34 (no dip at all) gives the same 20d result (+0.8% / +1.4%, t ~1.9): the "edge" is momentum drift of names that are in the index today, not a dip effect.
- Regime filters (SPY>SMA200, near 252d high) lift the DYN t-stat but not frozen results; low-vol filter hurts. 2022 loss not repaired in frozen universes.
- KR-24 analogue (post-crash dry-up) does not transfer: -0.75% (t -2.3, F14), -0.87% (F18). ETF leader dip +0.07% (t 0.68). US open/close drift is not distorted like KR (SPY o->c +0.022%/day, c->o +0.036%/day dev).
- Concentration, 3x cost and next-open numbers are in each round's JSON (top5_share, mean_3x, mean_nextopen) and ledger rows.
Holdout looks (all the same frozen US-18-T100 candidate): 3 unlocks logged 16:22:43 (Stage 3), 16:23:20 (robustness), 16:24:07 (survivorship diagnostic). BH across holdout looks: single candidate, q=0.001; the other two looks were diagnostics.
Conclusion: US-18-T100 stays "technical Stage 3 pass, survivorship-dependent: paper-trade only". Nothing else survives.

## Full Stage 1 table (86 strategy rows; Stage 2/3 rows for US-18 in LEDGER.md)
| id | n | net mean % | t | Sh(N=5) | BE round-trip cost % | halves % | 2x-cost mean % | BH q (cum 140) | S1 verdict |
|---|---|---|---|---|---|---|---|---|---|
| US-01 | 1819 | -0.294 | -2.40 | -0.87 | 0.108 | -0.34/-0.28 | -0.697 | 0.032 | noise |
| US-02 | 124 | +0.809 | 1.78 | 0.47 | 1.211 | +0.48/+1.00 | +0.406 | 0.110 | noise |
| US-01-T100 | 5000 | -0.221 | -2.24 | -1.40 | 0.182 | -0.18/-0.24 | -0.624 | 0.045 | noise |
| US-02-T100 | 396 | -0.384 | -1.21 | -0.31 | 0.019 | +0.07/-0.69 | -0.786 | 0.284 | noise |
| US-03-SPY | 3740 | -0.367 | -32.63 | -8.47 | 0.036 | -0.38/-0.36 | -0.770 | 0.000 | hurts |
| US-03-SPY-SMA5 | 1472 | -0.346 | -15.12 | -3.76 | 0.057 | -0.34/-0.35 | -0.748 | 0.000 | hurts |
| US-03-QQQ | 3740 | -0.353 | -27.50 | -7.14 | 0.050 | -0.36/-0.35 | -0.755 | 0.000 | hurts |
| US-03-QQQ-SMA5 | 1492 | -0.331 | -12.81 | -3.22 | 0.072 | -0.31/-0.35 | -0.734 | 0.000 | hurts |
| US-03-T30 | 111630 | -0.344 | -24.84 | -5.82 | 0.059 | -0.35/-0.34 | -0.746 | 0.000 | hurts |
| US-03-T30-SMA5 | 51212 | -0.349 | -16.48 | -5.57 | 0.054 | -0.33/-0.37 | -0.751 | 0.000 | hurts |
| US-03-T100 | 372100 | -0.354 | -28.26 | -6.24 | 0.049 | -0.36/-0.35 | -0.757 | 0.000 | hurts |
| US-03-T100-SMA5 | 170436 | -0.349 | -18.60 | -6.05 | 0.054 | -0.34/-0.36 | -0.751 | 0.000 | hurts |
| US-04 | 13976 | -0.113 | -2.53 | -0.47 | 0.289 | -0.12/-0.11 | -0.516 | 0.023 | noise |
| US-05 | 6610 | +0.111 | 1.53 | -0.18 | 0.514 | +0.13/+0.10 | -0.292 | 0.170 | noise |
| US-06 | 5900 | +0.054 | 0.70 | 0.11 | 0.457 | +0.03/+0.08 | -0.348 | 0.520 | noise |
| US-07 | 597 | -0.396 | -2.10 | -0.60 | 0.007 | -0.30/-0.46 | -0.799 | 0.061 | noise |
| US-04-T100 | 45284 | -0.136 | -3.94 | -0.68 | 0.267 | -0.12/-0.15 | -0.538 | 0.001 | hurts |
| US-05-T100 | 20896 | +0.045 | 0.79 | -0.31 | 0.447 | +0.10/-0.01 | -0.358 | 0.468 | noise |
| US-06-T100 | 18396 | +0.023 | 0.39 | -0.39 | 0.426 | -0.03/+0.07 | -0.380 | 0.727 | noise |
| US-07-T100 | 1912 | -0.336 | -2.27 | -0.84 | 0.067 | -0.21/-0.43 | -0.739 | 0.043 | noise |
| US-08-SPY | 178 | -0.157 | -1.06 | -0.27 | 0.246 | -0.14/-0.18 | -0.560 | 0.346 | noise |
| US-08-QQQ | 178 | -0.047 | -0.26 | -0.07 | 0.356 | -0.03/-0.07 | -0.449 | 0.805 | noise |
| US-09-SPY | 92 | -0.430 | -2.21 | -0.56 | -0.028 | -0.25/-0.59 | -0.833 | 0.047 | noise |
| US-09-T30 | 1681 | -0.674 | -3.23 | -0.98 | -0.272 | -0.89/-0.56 | -1.077 | 0.005 | hurts |
| US-09-T100 | 4992 | -0.693 | -3.65 | -1.03 | -0.290 | -0.87/-0.57 | -1.095 | 0.001 | hurts |
| US-10 | 4868 | -0.184 | -4.62 | -0.63 | 0.219 | -0.18/-0.19 | -0.586 | 0.000 | hurts |
| US-11 | 2253 | -0.208 | -0.72 | -0.16 | 0.195 | +0.51/-0.78 | -0.610 | 0.511 | noise |
| US-12 | 460 | -0.245 | -0.86 | -0.28 | 0.158 | -0.46/-0.16 | -0.648 | 0.438 | noise |
| US-11-T100 | 7492 | -0.277 | -1.18 | -0.43 | 0.125 | +0.23/-0.72 | -0.680 | 0.299 | noise |
| US-12-T100 | 1673 | -0.245 | -1.46 | -0.50 | 0.157 | -0.14/-0.29 | -0.648 | 0.191 | noise |
| US-13-SPY | 81 | +0.619 | 1.96 | 0.52 | 1.021 | +0.22/+0.85 | +0.216 | 0.080 | noise |
| US-13-QQQ | 173 | +0.499 | 2.10 | 0.56 | 0.902 | +0.33/+0.60 | +0.097 | 0.060 | noise |
| US-14 | 6060 | +0.292 | 1.63 | 0.28 | 0.694 | +0.34/+0.21 | -0.111 | 0.145 | noise |
| US-15 | 442 | +0.525 | 1.61 | 0.26 | 0.928 | +0.24/+0.67 | +0.122 | 0.150 | noise |
| US-16 | 210 | +0.196 | 0.38 | 0.10 | 0.599 | +0.03/+0.30 | -0.207 | 0.730 | noise |
| US-17 | 640 | -0.439 | -1.36 | -0.39 | -0.036 | -0.21/-0.52 | -0.842 | 0.229 | noise |
| US-18 | 3168 | +0.324 | 3.07 | 0.25 | 0.727 | +0.39/+0.26 | -0.079 | 0.007 | advance |
| US-19 | 2565 | +0.219 | 1.61 | 0.07 | 0.621 | +0.21/+0.22 | -0.184 | 0.149 | noise |
| US-14-T100 | 20200 | +0.257 | 1.59 | 0.23 | 0.660 | +0.37/+0.09 | -0.146 | 0.153 | noise |
| US-15-T100 | 1195 | +0.455 | 2.21 | 0.38 | 0.858 | +0.21/+0.58 | +0.052 | 0.047 | noise |
| US-16-T100 | 651 | -0.181 | -0.55 | -0.14 | 0.222 | +0.16/-0.49 | -0.584 | 0.615 | noise |
| US-17-T100 | 1736 | -0.243 | -0.97 | -0.24 | 0.160 | -0.04/-0.33 | -0.646 | 0.379 | noise |
| US-18-T100 | 10135 | +0.290 | 3.66 | 0.31 | 0.693 | +0.43/+0.16 | -0.113 | 0.001 | advance |
| US-19-T100 | 8066 | +0.112 | 0.98 | -0.04 | 0.514 | +0.16/+0.07 | -0.291 | 0.376 | noise |
| US-20-IWM | 147 | +0.281 | 0.88 | 0.23 | 0.684 | +0.80/+0.09 | -0.122 | 0.427 | noise |
| US-21-F14 | 3494 | +0.225 | 1.93 | -0.06 | 0.628 | +0.22/+0.23 | -0.177 | 0.083 | noise |
| US-21-F18 | 1960 | +0.270 | 2.04 | 0.37 | 0.673 | +0.57/+0.05 | -0.133 | 0.067 | noise |
| US-22-F14 | 1217 | +0.250 | 1.28 | -0.12 | 0.653 | +0.67/-0.14 | -0.152 | 0.258 | noise |
| US-22-F18 | 657 | -0.065 | -0.30 | -0.68 | 0.338 | +0.79/-0.45 | -0.468 | 0.782 | noise |
| US-23-F14 | 5986 | +0.025 | 0.30 | -0.70 | 0.428 | +0.01/+0.04 | -0.378 | 0.782 | noise |
| US-23-F18 | 3580 | +0.134 | 1.26 | 0.02 | 0.536 | +0.42/-0.14 | -0.269 | 0.268 | noise |
| US-24-F14 | 2308 | +0.496 | 1.92 | 0.35 | 0.898 | +0.84/+0.34 | +0.093 | 0.084 | noise |
| US-24-F18 | 1577 | +0.362 | 1.11 | 1.09 | 0.765 | +0.43/+0.29 | -0.041 | 0.326 | noise |
| US-25-F14 | 2966 | +0.502 | 2.35 | 0.23 | 0.905 | +0.93/+0.27 | +0.099 | 0.035 | noise |
| US-25-F18 | 1962 | +0.406 | 1.54 | 0.58 | 0.809 | +0.66/+0.15 | +0.003 | 0.168 | noise |
| US-26-F14 | 6993 | +0.093 | 0.94 | -0.31 | 0.496 | +0.18/+0.01 | -0.309 | 0.398 | noise |
| US-26-F18 | 4160 | +0.130 | 1.07 | -0.23 | 0.533 | +0.20/+0.07 | -0.273 | 0.343 | noise |
| US-27-ETF | 1312 | +0.068 | 0.68 | 0.16 | 0.471 | +0.17/-0.02 | -0.335 | 0.527 | noise |
| US-28-F14 | 272 | -0.748 | -2.26 | -0.71 | -0.345 | -0.45/-1.11 | -1.151 | 0.044 | noise |
| US-28-F18 | 173 | -0.865 | -2.02 | -0.83 | -0.462 | -0.92/-0.82 | -1.268 | 0.070 | noise |
| US-29-F14 | 2 | +0.010 | 0.01 | 0.02 | 0.413 | +nan/+0.01 | -0.392 | 0.995 | noise |
| US-29-F18 | 3 | +0.977 | 0.74 | 1.46 | 1.379 | +0.98/+nan | +0.574 | 0.501 | noise |
| US-30-F14 | 206 | +0.850 | 1.24 | 0.07 | 1.253 | +0.70/+0.95 | +0.447 | 0.274 | noise |
| US-30-F18 | 148 | -0.500 | -0.85 | -0.59 | -0.097 | -1.68/+0.28 | -0.903 | 0.438 | noise |
| US-31-F14 | 1494 | +0.351 | 0.99 | -0.16 | 0.753 | +0.70/-0.07 | -0.052 | 0.376 | noise |
| US-31-F18 | 820 | -0.061 | -0.20 | 0.01 | 0.342 | -0.30/+0.01 | -0.464 | 0.850 | noise |
| US-32-DYN-h5 | 3325 | +0.641 | 4.26 | 0.62 | 1.044 | +0.82/+0.49 | +0.238 | 0.000 | advance |
| US-32-DYN-h10 | 3319 | +0.974 | 4.48 | 0.68 | 1.377 | +0.99/+0.96 | +0.571 | 0.000 | advance |
| US-32-DYN-h20 | 3313 | +1.933 | 6.31 | 1.36 | 2.336 | +1.93/+1.93 | +1.530 | 0.000 | advance |
| US-32-F14-h5 | 2299 | +0.241 | 1.36 | 0.06 | 0.643 | +0.52/-0.00 | -0.162 | 0.229 | noise |
| US-32-F14-h10 | 2292 | +0.288 | 1.00 | 0.14 | 0.691 | +0.89/-0.25 | -0.115 | 0.375 | noise |
| US-32-F14-h20 | 2278 | +0.728 | 1.66 | 0.89 | 1.131 | +1.44/+0.09 | +0.325 | 0.139 | noise |
| US-32-F18-h5 | 1373 | +0.208 | 1.04 | 0.16 | 0.611 | +0.54/-0.08 | -0.195 | 0.355 | noise |
| US-32-F18-h10 | 1363 | +0.405 | 1.09 | 0.14 | 0.808 | +0.22/+0.57 | +0.003 | 0.336 | noise |
| US-32-F18-h20 | 1350 | +1.272 | 2.20 | 0.90 | 1.675 | +0.88/+1.62 | +0.870 | 0.047 | noise |
| US-33a-DYN | 2464 | +0.414 | 3.88 | 0.44 | 0.817 | +0.53/+0.31 | +0.011 | 0.001 | advance |
| US-33a-F14 | 1628 | +0.289 | 2.40 | -0.10 | 0.692 | +0.32/+0.26 | -0.114 | 0.032 | noise |
| US-33a-F18 | 1005 | +0.285 | 1.80 | 0.25 | 0.688 | +0.40/+0.14 | -0.117 | 0.107 | noise |
| US-33b-DYN | 1613 | +0.311 | 2.49 | 0.11 | 0.714 | +0.46/+0.18 | -0.092 | 0.026 | noise |
| US-33b-F14 | 1128 | +0.128 | 0.83 | -0.50 | 0.531 | +0.03/+0.20 | -0.275 | 0.445 | noise |
| US-33b-F18 | 744 | +0.201 | 1.14 | -0.08 | 0.604 | +0.16/+0.24 | -0.201 | 0.316 | noise |
| US-33c-DYN | 2653 | +0.389 | 3.65 | 0.37 | 0.791 | +0.43/+0.35 | -0.014 | 0.001 | advance |
| US-33c-F14 | 1782 | +0.317 | 2.78 | -0.07 | 0.720 | +0.33/+0.31 | -0.086 | 0.014 | noise |
| US-33c-F18 | 1023 | +0.275 | 1.74 | 0.30 | 0.678 | +0.40/+0.10 | -0.128 | 0.120 | noise |
| US-34-F14 | 3100 | +0.812 | 1.83 | 0.45 | 1.215 | +0.27/+1.36 | +0.409 | 0.102 | noise |
| US-34-F18 | 1825 | +1.362 | 1.92 | 1.08 | 1.765 | +2.03/+0.68 | +0.959 | 0.084 | noise |


---
# UPDATE after round 7 (membership-date universe, US-35)
Verdict for US short-term (<=5-day) strategies: NOT MEANINGFUL. 
- Membership-date PIT universe (Wikipedia 'Date added', raw saved in results/us35_raw/): Stage 1 stays positive on MEM for the US-18 cell (+0.42%, t=3.86, 2x +0.01%), fixed holds h5/h10/h20, US-24 and US-25 specs, but the dev edge shrinks from 0.52% to 0.42% for US-18 and is front-loaded: 2015+ +0.34% (t=2.49), 2019+ +0.20% (t=1.16, 2x -0.21%); 2022 -0.65%. At 5-day-or-shorter horizons the 2x-cost mean is ~0 on MEM and negative on the frozen universes.
- Strict gate (MEM + F14 + F18 all positive, t>=2, 2x>0): no specification passes (e.g. US-18c F14 +0.23% t=1.49 2x -0.17%, F18 +0.15% t=0.98). Hence no Stage 2, no Stage 3, no new holdout look.
- US-18-T100: its Stage 3 pass (holdout +1.98%) cannot be reproduced on survivorship-adjusted dev data; treat as a survivorship/regime artifact (holdout dominated by recent index-entrant winners). Residual bias from removed/delisted names is unrepaired, so MEM numbers are upper bounds.
- Only longer holds (h20, plus no-dip US-34) show sizeable gross (+1.5% h20 MEM, 2x +1.06%), but that is momentum drift beyond the 5-day scope and still fails on frozen universes (t 1.7-2.2).
- Holdout looks: 3 (all US-18-T100: Stage 3, robustness, survivorship diagnostic); BH over them: one candidate, q about 0.001; no further looks. Cumulative trials: 149.
## Round 7 rows
| US-35-18c-MEM | 3261 | +0.416 | 3.86 | 0.39 | 0.818 | +0.69/+0.17 | +0.013 | 0.001 | advance |
| US-35-h5-MEM | 3261 | +0.520 | 3.64 | 0.37 | 0.922 | +0.83/+0.25 | +0.117 | 0.001 | advance |
| US-35-h10-MEM | 3254 | +0.695 | 3.37 | 0.30 | 1.098 | +0.97/+0.45 | +0.292 | 0.003 | advance |
| US-35-h20-MEM | 3248 | +1.466 | 4.93 | 1.05 | 1.869 | +1.94/+1.05 | +1.063 | 0.000 | advance |
| US-35-24-MEM | 3280 | +0.602 | 3.57 | 0.68 | 1.005 | +0.92/+0.44 | +0.199 | 0.002 | advance |
| US-35-25-MEM | 4285 | +0.689 | 5.06 | 0.53 | 1.092 | +0.89/+0.57 | +0.286 | 0.000 | advance |
| US-35-34-MEM | 4500 | +0.931 | 2.65 | 0.61 | 1.334 | +0.92/+0.94 | +0.528 | 0.018 | noise |
| US-35-18c-F14 | 2299 | +0.230 | 1.49 | 0.03 | 0.633 | +0.52/-0.02 | -0.172 | 0.180 | noise |
| US-35-18c-F18 | 1373 | +0.154 | 0.98 | 0.10 | 0.557 | +0.49/-0.13 | -0.249 | 0.374 | noise |


---
# UPDATE after round 8 (10/20/40-day holds, US-36..US-41)
Verdict for US 10-40 day strategies: NOT MEANINGFUL (no alpha over buy-and-hold). 196 cumulative trials; 0 pass the strict gate; no Stage 2/3; holdout looks unchanged (3, all US-18-T100; BH q ~0.001 for the single candidate).
- 10d: noise. 20d: 2x-positive, t 1.2-2.6 (below 3 on frozen universes). 40d: net +1.8..3.3% per trade, t 2.9..4.6, 2x/3x positive on MEM, F14, F18 - but positions are ~1.0 beta: portfolio Sharpe below equal-weight universe buy-and-hold on MEM and F14, alpha vs SPY not different from zero (MEM -2.9%/yr t -1.0, F14 +0.3% t 0.1). F18 only (the shortest, 2019+ sample) beats it (alpha +12.8% t 2.2, 4.3 years) - not replicated on MEM/F14, so not accepted.
- Sector-ETF momentum and SPY/QQQ/IWM SMA100/200 trend filters (survivorship-free): positive means (+0.5..1.8%) but Sharpe below buy-and-hold in every case (trend filters lower drawdown, give up return).
- US-41-h40 (dip cell, 40d) F18 +7.7% t=4.97 is based on n=98 and fails on MEM (t 1.55).
- Costs are no longer the binding constraint at >=20d (2x/3x stay positive), but the edge over simply holding the universe is absent. Tax: 22% above 2.5M KRW/yr would take ~22% of gains; likely exempt at ~1.3M KRW capital.
## Round 8 table (all strategies; per-round details results/US_round8.json)
| id | n | net % | t(month) | Sh MTM N=10 | BE cost % | halves % | 2x % | 3x % | top5 | Sh EW-BH | Sh SPY | maxDD strat/BH % | alpha %/yr (t) | beta | BH q (cum 196) | S1 |
|---|---|---|---|---|---|---|---|---|---|---|---|---|---|---|---|---|
| US-36-h10-MEM | 4500 | +0.39 | 1.49 | 0.43 | 0.79 | +0.52/+0.26 | -0.01 | -0.42 | 0.41 | 0.87 | 0.88 | -24/-34 | -1.9 (-0.6) | 0.55 | 0.183 | noise |
| US-36-h10-F14 | 3100 | +0.33 | 0.93 | 0.30 | 0.73 | +0.37/+0.29 | -0.07 | -0.48 | 0.50 | 0.74 | 0.79 | -24/-41 | -2.5 (-0.6) | 0.51 | 0.395 | noise |
| US-36-h10-F18 | 1850 | +0.65 | 1.48 | 0.50 | 1.05 | +1.30/-0.01 | +0.24 | -0.16 | 0.39 | 0.95 | 0.89 | -34/-35 | -0.7 (-0.1) | 0.53 | 0.187 | noise |
| US-36-h20-MEM | 4500 | +0.93 | 2.60 | 0.67 | 1.33 | +0.93/+0.93 | +0.53 | +0.13 | 0.30 | 0.88 | 0.90 | -35/-34 | -1.7 (-0.6) | 1.02 | 0.020 | noise |
| US-36-h20-F14 | 3100 | +0.81 | 1.81 | 0.50 | 1.21 | +0.27/+1.36 | +0.41 | +0.01 | 0.36 | 0.75 | 0.80 | -37/-41 | -2.9 (-0.7) | 0.95 | 0.108 | noise |
| US-36-h20-F18 | 1825 | +1.36 | 1.92 | 0.82 | 1.76 | +2.03/+0.68 | +0.96 | +0.56 | 0.40 | 0.96 | 0.91 | -43/-35 | +1.4 (0.3) | 1.01 | 0.087 | noise |
| US-36-h40-MEM | 4475 | +2.23 | 4.39 | 0.62 | 2.64 | +2.20/+2.27 | +1.83 | +1.43 | 0.27 | 0.88 | 0.90 | -36/-34 | -2.9 (-1.0) | 1.07 | 0.000 | advance |
| US-36-h40-F14 | 3075 | +2.12 | 3.52 | 0.66 | 2.52 | +1.30/+2.95 | +1.72 | +1.32 | 0.29 | 0.75 | 0.80 | -36/-41 | +0.3 (0.1) | 0.98 | 0.002 | advance |
| US-36-h40-F18 | 1800 | +3.33 | 3.53 | 1.25 | 3.74 | +4.70/+1.97 | +2.93 | +2.53 | 0.33 | 0.95 | 0.90 | -42/-35 | +12.8 (2.2) | 1.07 | 0.002 | advance |
| US-37-h10-MEM | 4350 | +0.39 | 1.37 | 0.40 | 0.80 | +0.55/+0.23 | -0.01 | -0.41 | 0.39 | 0.82 | 0.84 | -23/-34 | -2.2 (-0.7) | 0.60 | 0.222 | noise |
| US-37-h10-F14 | 3100 | +0.34 | 0.99 | 0.36 | 0.74 | +0.43/+0.25 | -0.07 | -0.47 | 0.50 | 0.74 | 0.79 | -25/-41 | -2.0 (-0.5) | 0.57 | 0.374 | noise |
| US-37-h10-F18 | 1850 | +0.60 | 1.37 | 0.42 | 1.00 | +1.23/-0.03 | +0.20 | -0.20 | 0.43 | 0.95 | 0.89 | -22/-35 | -2.3 (-0.4) | 0.58 | 0.222 | noise |
| US-37-h20-MEM | 4350 | +0.78 | 2.02 | 0.59 | 1.18 | +0.86/+0.70 | +0.38 | -0.03 | 0.36 | 0.83 | 0.85 | -34/-34 | -2.9 (-1.0) | 1.10 | 0.074 | noise |
| US-37-h20-F14 | 3100 | +0.72 | 1.66 | 0.56 | 1.12 | +0.38/+1.06 | +0.32 | -0.08 | 0.40 | 0.75 | 0.80 | -34/-41 | -2.3 (-0.6) | 1.02 | 0.142 | noise |
| US-37-h20-F18 | 1825 | +1.45 | 2.19 | 0.80 | 1.85 | +1.99/+0.89 | +1.05 | +0.64 | 0.34 | 0.96 | 0.91 | -32/-35 | +0.8 (0.2) | 1.04 | 0.053 | noise |
| US-37-h40-MEM | 4325 | +1.92 | 3.68 | 0.53 | 2.33 | +2.03/+1.82 | +1.52 | +1.12 | 0.29 | 0.83 | 0.85 | -35/-34 | -4.2 (-1.5) | 1.11 | 0.001 | advance |
| US-37-h40-F14 | 3075 | +1.75 | 3.01 | 0.51 | 2.15 | +1.22/+2.29 | +1.35 | +0.95 | 0.34 | 0.75 | 0.80 | -33/-41 | -3.0 (-0.7) | 0.99 | 0.008 | advance |
| US-37-h40-F18 | 1800 | +2.95 | 3.28 | 0.93 | 3.35 | +4.09/+1.81 | +2.55 | +2.14 | 0.35 | 0.95 | 0.90 | -31/-35 | +4.6 (0.8) | 1.02 | 0.004 | advance |
| US-38-h10-MEM | 3675 | +0.12 | 0.46 | 0.11 | 0.53 | +0.40/-0.18 | -0.28 | -0.68 | 1.13 | 0.85 | 0.86 | -47/-34 | -3.8 (-1.2) | 0.36 | 0.675 | noise |
| US-38-h10-F14 | 2475 | +0.02 | 0.06 | 0.02 | 0.43 | +0.15/-0.12 | -0.38 | -0.78 | 5.47 | 0.74 | 0.79 | -35/-41 | -4.8 (-1.2) | 0.36 | 0.956 | noise |
| US-38-h10-F18 | 1475 | +0.42 | 0.86 | 0.27 | 0.83 | +0.92/-0.21 | +0.02 | -0.38 | 0.60 | 0.87 | 0.80 | -25/-35 | -0.7 (-0.1) | 0.27 | 0.434 | noise |
| US-38-h20-MEM | 3675 | +0.73 | 1.98 | 0.32 | 1.13 | +0.95/+0.48 | +0.33 | -0.07 | 0.40 | 0.86 | 0.88 | -42/-34 | -4.8 (-1.4) | 0.72 | 0.080 | noise |
| US-38-h20-F14 | 2475 | +0.57 | 1.25 | 0.37 | 0.97 | +0.35/+0.81 | +0.17 | -0.24 | 0.54 | 0.75 | 0.80 | -32/-41 | -3.1 (-0.7) | 0.70 | 0.265 | noise |
| US-38-h20-F18 | 1450 | +0.99 | 1.23 | 0.28 | 1.40 | +1.17/+0.76 | +0.59 | +0.19 | 0.53 | 0.88 | 0.83 | -38/-35 | -4.7 (-0.7) | 0.63 | 0.275 | noise |
| US-38-h40-MEM | 3650 | +1.96 | 3.66 | 0.56 | 2.36 | +2.17/+1.72 | +1.55 | +1.15 | 0.35 | 0.86 | 0.88 | -37/-34 | -1.1 (-0.3) | 0.79 | 0.001 | advance |
| US-38-h40-F14 | 2450 | +1.83 | 2.86 | 0.52 | 2.23 | +1.29/+2.43 | +1.43 | +1.02 | 0.37 | 0.75 | 0.80 | -34/-41 | -0.9 (-0.2) | 0.76 | 0.012 | noise |
| US-38-h40-F18 | 1425 | +2.88 | 2.75 | 0.66 | 3.28 | +3.13/+2.55 | +2.47 | +2.07 | 0.39 | 0.88 | 0.83 | -41/-35 | +0.2 (0.0) | 0.93 | 0.015 | noise |
| US-39-h10-MEM | 4500 | +0.37 | 1.55 | 0.36 | 0.77 | +0.48/+0.27 | -0.03 | -0.43 | 0.39 | 0.87 | 0.88 | -26/-34 | -2.6 (-0.9) | 0.51 | 0.168 | noise |
| US-39-h10-F14 | 3100 | +0.35 | 1.08 | 0.31 | 0.75 | +0.29/+0.41 | -0.05 | -0.46 | 0.41 | 0.74 | 0.79 | -29/-41 | -2.5 (-0.6) | 0.51 | 0.334 | noise |
| US-39-h10-F18 | 1850 | +0.57 | 1.45 | 0.58 | 0.98 | +1.19/-0.04 | +0.17 | -0.23 | 0.35 | 0.95 | 0.89 | -29/-35 | +0.7 (0.1) | 0.50 | 0.195 | noise |
| US-39-h20-MEM | 4500 | +0.84 | 2.64 | 0.57 | 1.25 | +0.90/+0.78 | +0.44 | +0.04 | 0.27 | 0.88 | 0.90 | -34/-34 | -3.5 (-1.4) | 0.94 | 0.019 | noise |
| US-39-h20-F14 | 3100 | +0.82 | 1.97 | 0.63 | 1.22 | +0.33/+1.31 | +0.42 | +0.01 | 0.29 | 0.75 | 0.80 | -41/-41 | -0.6 (-0.2) | 0.94 | 0.080 | noise |
| US-39-h20-F18 | 1825 | +1.21 | 1.86 | 0.85 | 1.61 | +1.97/+0.43 | +0.80 | +0.40 | 0.39 | 0.96 | 0.91 | -35/-35 | +2.0 (0.4) | 0.92 | 0.099 | noise |
| US-39-h40-MEM | 4475 | +2.07 | 4.58 | 0.59 | 2.48 | +2.17/+1.97 | +1.67 | +1.27 | 0.24 | 0.88 | 0.90 | -35/-34 | -3.2 (-1.2) | 0.99 | 0.000 | advance |
| US-39-h40-F14 | 3075 | +1.99 | 3.59 | 0.62 | 2.39 | +1.17/+2.82 | +1.58 | +1.18 | 0.27 | 0.75 | 0.80 | -38/-41 | -0.7 (-0.2) | 0.95 | 0.002 | advance |
| US-39-h40-F18 | 1800 | +2.99 | 3.44 | 1.13 | 3.40 | +4.61/+1.38 | +2.59 | +2.19 | 0.32 | 0.95 | 0.90 | -34/-35 | +8.9 (1.6) | 0.95 | 0.003 | advance |
| US-40-secmom-h20 | 540 | +0.63 | 2.07 | 0.48 | 1.03 | +0.59/+0.67 | +0.23 | -0.18 | 0.75 | 0.86 | 0.91 | -35/-36 | -5.6 (-2.7) | 0.89 | 0.068 | noise |
| US-40-secmom-h40 | 537 | +1.77 | 4.29 | 0.69 | 2.18 | +1.57/+1.98 | +1.37 | +0.97 | 0.71 | 0.86 | 0.91 | -33/-36 | -2.3 (-1.2) | 0.90 | 0.000 | advance |
| US-40-trend-SPY-sma100 | 140 | +0.50 | 1.84 | 0.43 | 0.90 | +0.45/+0.56 | +0.10 | -0.31 | 1.00 | 0.89 | 0.89 | -30/-34 | -2.2 (-0.9) | 0.48 | 0.101 | noise |
| US-40-trend-SPY-sma200 | 147 | +0.64 | 2.18 | 0.50 | 1.04 | +0.76/+0.50 | +0.24 | -0.17 | 1.00 | 0.88 | 0.88 | -34/-34 | -2.6 (-1.1) | 0.63 | 0.053 | noise |
| US-40-trend-QQQ-sma100 | 138 | +0.76 | 1.93 | 0.47 | 1.16 | +0.73/+0.79 | +0.35 | -0.05 | 1.00 | 0.97 | 0.89 | -33/-35 | -2.9 (-1.0) | 0.70 | 0.087 | noise |
| US-40-trend-QQQ-sma200 | 147 | +0.99 | 2.67 | 0.63 | 1.40 | +0.74/+1.29 | +0.59 | +0.19 | 1.00 | 0.95 | 0.88 | -29/-35 | -0.7 (-0.2) | 0.76 | 0.019 | noise |
| US-40-trend-IWM-sma100 | 120 | +0.13 | 0.32 | 0.09 | 0.53 | +0.64/-0.48 | -0.27 | -0.68 | 1.00 | 0.59 | 0.89 | -48/-41 | -5.5 (-1.7) | 0.45 | 0.773 | noise |
| US-40-trend-IWM-sma200 | 128 | +0.28 | 0.67 | 0.18 | 0.68 | +0.59/-0.10 | -0.12 | -0.52 | 1.00 | 0.57 | 0.88 | -44/-41 | -4.3 (-1.2) | 0.46 | 0.534 | noise |
| US-41-h40-MEM | 213 | +2.18 | 1.55 | 0.31 | 2.58 | +1.46/+3.12 | +1.78 | +1.37 | 0.48 | 0.84 | 0.85 | -18/-34 | -1.0 (-0.5) | 0.27 | 0.168 | noise |
| US-41-h40-F14 | 130 | +3.31 | 2.20 | 0.34 | 3.71 | +3.00/+3.65 | +2.91 | +2.50 | 0.41 | 0.72 | 0.77 | -21/-41 | +0.1 (0.0) | 0.22 | 0.051 | noise |
| US-41-h40-F18 | 98 | +7.69 | 4.97 | 1.45 | 8.09 | +8.50/+6.78 | +7.29 | +6.89 | 0.37 | 0.88 | 0.81 | -9/-35 | +9.4 (2.8) | 0.20 | 0.000 | advance |


---
# UPDATE after round 9 (ETF-only, VIX timing, cross-asset; survivorship-free families)
Verdict for ETF/VIX short-term (1-10 day) families: NOT MEANINGFUL (no Stage 1 survivor). 207 cumulative trials; holdout looks unchanged (3, all US-18-T100).
- Pooled ETF dip-buy/reversal rules (31 ETFs, 2-6.9k events, 300-700 weekly episodes) have gross 0.17-0.6% per trade vs 0.40% cost; RSI2<5, 4 down days and IBS<0.1 are net negative (US-45 t_week -3.5).
- VIX-based timing of SPY/QQQ/IWM (spike, Bollinger, 1d jump, VIX/realised) is noise; halves flip sign in 3 of 4.
- Only sparse, high-conviction rules are positive: US-51 (+0.69%, 93 episodes, t_week 2.68, positive after 2x) and US-52 (+1.35%, 56 episodes, t_week 1.75). Effective independent samples are too small to clear t>=3; they are recorded as hypotheses for a future out-of-sample test, not candidates.
- Together with rounds 1-8: no US short-term (<=5d) or long-hold strategy shows alpha net of costs and survivorship/beta in dev data. The one holdout pass (US-18-T100) is a survivorship/regime artifact.
## Round 9 table
| id | events | episodes (weeks) | net % | t(week) | t(date) | Sh | BE cost % | halves % | 2x % | 3x % | yrs+ | BH q (cum 207) | S1 |
|---|---|---|---|---|---|---|---|---|---|---|---|---|---|
| US-42 | 2719 | 436 | -0.168 | -1.37 | -1.92 | -0.92 | 0.235 | -0.20/-0.13 | -0.571 | -0.974 | 0.40 | 0.227 | noise |
| US-43 | 2487 | 470 | +0.213 | 1.12 | 1.55 | -0.15 | 0.615 | +0.07/+0.30 | -0.190 | -0.593 | 0.53 | 0.324 | noise |
| US-44 | 2173 | 452 | -0.229 | -2.42 | -3.07 | -1.50 | 0.174 | -0.12/-0.33 | -0.631 | -1.034 | 0.27 | 0.033 | noise |
| US-45 | 6905 | 702 | -0.161 | -3.51 | -4.09 | -1.95 | 0.242 | -0.20/-0.12 | -0.564 | -0.966 | 0.27 | 0.002 | hurts |
| US-46 | 1144 | 318 | -0.085 | -0.40 | -0.54 | -0.39 | 0.318 | +0.12/-0.21 | -0.488 | -0.891 | 0.60 | 0.725 | noise |
| US-47 | 747 | 112 | -0.378 | -0.56 | -1.13 | -0.10 | 0.025 | +0.55/-1.19 | -0.781 | -1.184 | 0.80 | 0.616 | noise |
| US-48 | 804 | 151 | -0.025 | -0.10 | -0.14 | -0.10 | 0.377 | +0.43/-0.44 | -0.428 | -0.831 | 0.60 | 0.928 | noise |
| US-49 | 465 | 133 | -0.355 | -1.67 | -1.65 | -0.49 | 0.048 | +0.08/-0.69 | -0.758 | -1.160 | 0.33 | 0.143 | noise |
| US-50 | 2793 | 284 | -0.079 | -0.81 | -1.28 | -0.05 | 0.324 | -0.01/-0.15 | -0.482 | -0.885 | 0.33 | 0.460 | noise |
| US-51 | 152 | 93 | +0.685 | 2.68 | 3.21 | 0.39 | 1.088 | +0.41/+1.03 | +0.282 | -0.120 | 0.86 | 0.019 | noise |
| US-52 | 360 | 56 | +1.352 | 1.75 | 2.54 | 0.22 | 1.755 | +0.52/+1.95 | +0.950 | +0.547 | 0.86 | 0.123 | noise |
