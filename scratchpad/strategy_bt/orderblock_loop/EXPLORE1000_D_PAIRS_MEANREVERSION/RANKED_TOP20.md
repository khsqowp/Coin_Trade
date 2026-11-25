# RANKED TOP 20 - EXPLORATORY SCREEN ONLY

> EXPLORATORY SCREEN ONLY -- not part of the 13-round preregistered G-gate track, not added to TRAIN_TRIALS.csv, no promotion without separate formal preregistration + synthetic tests + resource-gated TRAIN run.

Lane D (statistical pairs / spread / relative-value mean reversion), 1h TRAIN bars via data_access.iter_train_bars. Cost 12bp round-trip per unit traded (pair trades: 12bp x (1+|beta|)). Entries at next open, exits at bar closes, greedy one open trade per unit.

Proposed 260 ideas; screened 250; data-blocked (not run) 10; eligible 244.
Composite = t_day x (0.5 + 0.5 x positive-unit fraction). t_day clusters trades by day. Eligibility: >=100 trades, >=20 trading days, >=10 units (basket: >=8 quarters).

| rank | idea_id | name | composite | n_trades | units | exp net bps | trim1% exp | worst-year exp | max abs trade bps | win % | PF | t_day | pos-unit % | corr w/ FUND | corr w/ C154 proxy |
|---|---|---|---|---|---|---|---|---|---|---|---|---|---|---|---|
| 1 | D018 | PAIR_Z_BTC_refBTCUSDT_hedgeols_W240_K2.5_H120 | 2.01 | 1622 | 30 | 69.7 | 64.7 | -32.5 | 6913 | 49.6 | 1.27 | 2.30 | 75 | 0.04 | -0.06 |
| 2 | D012 | PAIR_Z_BTC_refBTCUSDT_hedgeols_W240_K1.5_H120 | 1.63 | 3261 | 30 | 48.5 | 46.5 | 1.7 | 14609 | 50.6 | 1.16 | 1.96 | 67 | -0.06 | -0.04 |
| 3 | D015 | PAIR_Z_BTC_refBTCUSDT_hedgeols_W240_K2.0_H120 | 1.62 | 2398 | 30 | 53.6 | 45.5 | -19.0 | 14112 | 50.0 | 1.19 | 1.99 | 63 | 0.01 | -0.06 |
| 4 | D104 | PAIR_CORRBREAK_BTC_refBTCUSDT_hedgeols_W168_K2.0_H72 | 1.45 | 452 | 28 | 118.5 | 107.0 | -7.0 | 6988 | 50.9 | 1.30 | 1.76 | 65 | 0.07 | -0.05 |
| 5 | D045 | PAIR_Z_ETH_refETHUSDT_hedgeols_W96_K2.5_H120 | 1.10 | 4129 | 30 | 19.0 | 9.9 | -10.7 | 17024 | 47.6 | 1.11 | 1.34 | 63 | 0.02 | -0.02 |
| 6 | D240 | SINGLE_LEADLAG_refBTCUSDT_K3.0_H3_dirnfade | 0.99 | 11504 | 30 | 12.6 | 9.7 | -16.8 | 4390 | 51.8 | 1.13 | 1.06 | 87 | 0.03 | -0.02 |
| 7 | D048 | PAIR_Z_ETH_refETHUSDT_hedgeols_W240_K1.5_H120 | 0.97 | 3271 | 30 | 22.9 | 14.8 | -5.7 | 9372 | 49.6 | 1.08 | 1.19 | 63 | 0.06 | 0.00 |
| 8 | D042 | PAIR_Z_ETH_refETHUSDT_hedgeols_W96_K2.0_H120 | 0.96 | 6017 | 30 | 12.7 | 4.1 | -8.9 | 17176 | 47.2 | 1.07 | 1.13 | 70 | 0.06 | -0.03 |
| 9 | D063 | PAIR_Z_ETH_refETHUSDT_hedgeols_W480_K2.5_H120 | 0.93 | 815 | 29 | 48.4 | 34.5 | -38.1 | 7144 | 47.7 | 1.17 | 1.14 | 63 | -0.02 | -0.02 |
| 10 | D027 | PAIR_Z_BTC_refBTCUSDT_hedgeols_W480_K2.5_H120 | 0.92 | 783 | 29 | 48.2 | 44.8 | -35.2 | 6437 | 46.1 | 1.16 | 1.05 | 76 | -0.01 | -0.05 |
| 11 | D102 | PAIR_CORRBREAK_BTC_refBTCUSDT_hedgeols_W168_K1.5_H72 | 0.75 | 593 | 28 | 55.8 | 36.2 | -18.3 | 11708 | 51.4 | 1.14 | 0.98 | 54 | 0.08 | -0.02 |
| 12 | D008 | PAIR_Z_BTC_refBTCUSDT_hedgeols_W96_K2.5_H48 | 0.69 | 4205 | 30 | 12.2 | 3.8 | -17.0 | 5902 | 46.5 | 1.07 | 0.88 | 57 | 0.08 | 0.07 |
| 13 | D051 | PAIR_Z_ETH_refETHUSDT_hedgeols_W240_K2.0_H120 | 0.63 | 2468 | 30 | 16.8 | 12.5 | -29.7 | 7812 | 49.2 | 1.06 | 0.78 | 62 | 0.06 | -0.04 |
| 14 | D009 | PAIR_Z_BTC_refBTCUSDT_hedgeols_W96_K2.5_H120 | 0.62 | 4141 | 30 | 11.7 | 5.6 | -19.5 | 5688 | 46.5 | 1.06 | 0.81 | 53 | 0.07 | 0.08 |
| 15 | D101 | PAIR_CORRBREAK_BTC_refBTCUSDT_hedgeols_W168_K1.5_H24 | 0.53 | 615 | 28 | 21.1 | 19.1 | -42.7 | 4440 | 50.2 | 1.09 | 0.69 | 54 | 0.03 | 0.08 |
| 16 | D006 | PAIR_Z_BTC_refBTCUSDT_hedgeols_W96_K2.0_H120 | 0.52 | 5962 | 30 | 8.6 | 3.4 | -12.3 | 13027 | 46.8 | 1.04 | 0.67 | 57 | 0.06 | 0.05 |
| 17 | D110 | PAIR_CORRBREAK_BTC_refBTCUSDT_hedgeols_W336_K1.5_H72 | 0.47 | 273 | 27 | 56.8 | 67.3 | -203.1 | 9257 | 52.7 | 1.12 | 0.53 | 75 | -0.11 | -0.06 |
| 18 | D103 | PAIR_CORRBREAK_BTC_refBTCUSDT_hedgeols_W168_K2.0_H24 | 0.44 | 462 | 28 | 21.7 | 14.9 | -20.3 | 3923 | 51.1 | 1.09 | 0.58 | 50 | 0.05 | -0.00 |
| 19 | D066 | PAIR_Z_ETH_refETHUSDT_hedgeols_W960_K1.5_H120 | 0.42 | 820 | 27 | 21.7 | 1.3 | -146.6 | 7358 | 48.3 | 1.06 | 0.56 | 50 | 0.10 | -0.08 |
| 20 | D024 | PAIR_Z_BTC_refBTCUSDT_hedgeols_W480_K2.0_H120 | 0.42 | 1206 | 29 | 19.9 | 17.4 | -45.2 | 6761 | 47.4 | 1.06 | 0.55 | 52 | 0.01 | -0.01 |

## Rationale (top 20)

1. **PAIR_Z_BTC_refBTCUSDT_hedgeols_W240_K2.5_H120** (D018): Correlated-coin spreads (log X vs beta*log BTC) tend to revert after dislocations; cointegration-style screen, no external data. Net 69.7 bps/trade over 1622 trades, t_day 2.30.
2. **PAIR_Z_BTC_refBTCUSDT_hedgeols_W240_K1.5_H120** (D012): Correlated-coin spreads (log X vs beta*log BTC) tend to revert after dislocations; cointegration-style screen, no external data. Net 48.5 bps/trade over 3261 trades, t_day 1.96.
3. **PAIR_Z_BTC_refBTCUSDT_hedgeols_W240_K2.0_H120** (D015): Correlated-coin spreads (log X vs beta*log BTC) tend to revert after dislocations; cointegration-style screen, no external data. Net 53.6 bps/trade over 2398 trades, t_day 1.99.
4. **PAIR_CORRBREAK_BTC_refBTCUSDT_hedgeols_W168_K2.0_H72** (D104): Enter spread reversion only when trailing correlation with BTC has broken down (<thr); tests whether decorrelated dislocations revert. Net 118.5 bps/trade over 452 trades, t_day 1.76.
5. **PAIR_Z_ETH_refETHUSDT_hedgeols_W96_K2.5_H120** (D045): Same spread-reversion logic against ETH, the second liquid anchor; partially overlaps BTC family by construction. Net 19.0 bps/trade over 4129 trades, t_day 1.34.
6. **SINGLE_LEADLAG_refBTCUSDT_K3.0_H3_dirnfade** (D240): Extreme 1h move in BTC/ETH (z-scored) followed by a time-exit trade in other coins, following or fading the reference. Net 12.6 bps/trade over 11504 trades, t_day 1.06.
7. **PAIR_Z_ETH_refETHUSDT_hedgeols_W240_K1.5_H120** (D048): Same spread-reversion logic against ETH, the second liquid anchor; partially overlaps BTC family by construction. Net 22.9 bps/trade over 3271 trades, t_day 1.19.
8. **PAIR_Z_ETH_refETHUSDT_hedgeols_W96_K2.0_H120** (D042): Same spread-reversion logic against ETH, the second liquid anchor; partially overlaps BTC family by construction. Net 12.7 bps/trade over 6017 trades, t_day 1.13.
9. **PAIR_Z_ETH_refETHUSDT_hedgeols_W480_K2.5_H120** (D063): Same spread-reversion logic against ETH, the second liquid anchor; partially overlaps BTC family by construction. Net 48.4 bps/trade over 815 trades, t_day 1.14.
10. **PAIR_Z_BTC_refBTCUSDT_hedgeols_W480_K2.5_H120** (D027): Correlated-coin spreads (log X vs beta*log BTC) tend to revert after dislocations; cointegration-style screen, no external data. Net 48.2 bps/trade over 783 trades, t_day 1.05.
11. **PAIR_CORRBREAK_BTC_refBTCUSDT_hedgeols_W168_K1.5_H72** (D102): Enter spread reversion only when trailing correlation with BTC has broken down (<thr); tests whether decorrelated dislocations revert. Net 55.8 bps/trade over 593 trades, t_day 0.98.
12. **PAIR_Z_BTC_refBTCUSDT_hedgeols_W96_K2.5_H48** (D008): Correlated-coin spreads (log X vs beta*log BTC) tend to revert after dislocations; cointegration-style screen, no external data. Net 12.2 bps/trade over 4205 trades, t_day 0.88.
13. **PAIR_Z_ETH_refETHUSDT_hedgeols_W240_K2.0_H120** (D051): Same spread-reversion logic against ETH, the second liquid anchor; partially overlaps BTC family by construction. Net 16.8 bps/trade over 2468 trades, t_day 0.78.
14. **PAIR_Z_BTC_refBTCUSDT_hedgeols_W96_K2.5_H120** (D009): Correlated-coin spreads (log X vs beta*log BTC) tend to revert after dislocations; cointegration-style screen, no external data. Net 11.7 bps/trade over 4141 trades, t_day 0.81.
15. **PAIR_CORRBREAK_BTC_refBTCUSDT_hedgeols_W168_K1.5_H24** (D101): Enter spread reversion only when trailing correlation with BTC has broken down (<thr); tests whether decorrelated dislocations revert. Net 21.1 bps/trade over 615 trades, t_day 0.69.
16. **PAIR_Z_BTC_refBTCUSDT_hedgeols_W96_K2.0_H120** (D006): Correlated-coin spreads (log X vs beta*log BTC) tend to revert after dislocations; cointegration-style screen, no external data. Net 8.6 bps/trade over 5962 trades, t_day 0.67.
17. **PAIR_CORRBREAK_BTC_refBTCUSDT_hedgeols_W336_K1.5_H72** (D110): Enter spread reversion only when trailing correlation with BTC has broken down (<thr); tests whether decorrelated dislocations revert. Net 56.8 bps/trade over 273 trades, t_day 0.53.
18. **PAIR_CORRBREAK_BTC_refBTCUSDT_hedgeols_W168_K2.0_H24** (D103): Enter spread reversion only when trailing correlation with BTC has broken down (<thr); tests whether decorrelated dislocations revert. Net 21.7 bps/trade over 462 trades, t_day 0.58.
19. **PAIR_Z_ETH_refETHUSDT_hedgeols_W960_K1.5_H120** (D066): Same spread-reversion logic against ETH, the second liquid anchor; partially overlaps BTC family by construction. Net 21.7 bps/trade over 820 trades, t_day 0.56.
20. **PAIR_Z_BTC_refBTCUSDT_hedgeols_W480_K2.0_H120** (D024): Correlated-coin spreads (log X vs beta*log BTC) tend to revert after dislocations; cointegration-style screen, no external data. Net 19.9 bps/trade over 1206 trades, t_day 0.55.

## Caveats

- EXPLORATORY ONLY. Nothing here is a validated candidate; no multiple-testing correction, walk-forward, or lookahead audit was run.
- Year stability: only 1 of 244 eligible ideas have a positive mean net in every calendar year (years with >=30 trades). Most top ideas are carried by 2021-2022 alt-season dislocations; this is the main reason none is a lead by itself.
- Tail/path risk: pair and ratio trades reach |net| of several thousand bps (alt-vs-BTC moves of 50-70% in a few days) because exits are bar-close only and there is no dollar stop; the hedged spread is not a bounded-risk position.
- Regime dependence: the TRAIN window is dominated by a strong up-trend for most alts; reversion signals can be mistaken for stable edge when they are really short-side losses in trends.
- Overfitting risk: 250 ideas over shared grids; the top of a ~250-idea grid is expected to contain false positives even under a null.
- Pair/ratio and basket trades are clustered: many pairs share the BTC/ETH leg, so trade counts overstate independent evidence. Day clustering partly corrects this.
- Simplifications: bar-close exits (no intrabar stops), EW index entry approximated by previous close, OLS beta on levels (not a cointegration test), 12bp per leg for pairs (stricter than the single-symbol convention).
- Convergence check: corr_daily_with_best_FUND is the daily-PnL correlation with the best eligible funding-basket idea; high correlation means a lead rhymes with the EXPLORE500 funding-contrarian theme rather than adding a new one.

