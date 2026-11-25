# RANKED TOP 20 - EXPLORATORY SCREEN ONLY

> EXPLORATORY SCREEN ONLY - not part of the 13-round preregistered G-gate track, not added to TRAIN_TRIALS.csv, no promotion without separate formal preregistration + synthetic tests + resource-gated TRAIN run.

Method: 31 crypto perps (of the 35-symbol universe; ENA, POL, TON have no TRAIN bars and TIA has 142), 1h TRAIN bars (data_access.iter_train_bars), shared exit (stop 1.5 ATR14, target 3.0 ATR14, 24-bar max hold, 12bp RT cost, one position per symbol). Ranking = composite_score = t_stat(net bps) x (0.5 + 0.5 x fraction of symbols with positive mean). Eligibility for the composite: >= 100 pooled trades and >= 10 symbols traded.

Scored 166 of 166 ideas with at least one trade; 160 met eligibility; no-trade ideas: 0.

| rank | idea_id | name | composite | n_trades | exp net bps | win % | PF | t | pos-sym % | rough Sharpe | prior rank |
|---|---|---|---|---|---|---|---|---|---|---|---|
| 1 | C154 | funding_contrarian_f0.0005 | 1.64 | 6438 | 13.8 | 40.8 | 1.07 | 1.95 | 69 | 1.18 | 46 |
| 2 | C153 | funding_contrarian_f0.0003 | 0.82 | 9964 | 5.8 | 39.9 | 1.03 | 1.10 | 48 | 0.67 | 45 |
| 3 | C067 | vol_compr_break_q0.6_N24 | 0.43 | 1151 | 5.8 | 32.9 | 1.05 | 0.56 | 52 | 0.34 | 38 |
| 4 | C066 | vol_compr_break_q0.6_N12 | 0.36 | 2187 | 3.1 | 32.9 | 1.03 | 0.49 | 47 | 0.29 | 37 |
| 5 | C069 | vol_compr_break_q0.7_N24 | 0.32 | 3437 | 2.5 | 34.2 | 1.02 | 0.44 | 45 | 0.27 | 40 |
| 6 | C044 | dip_buy_D15_W168 | 0.29 | 12688 | 1.9 | 39.3 | 1.01 | 0.38 | 55 | 0.23 | 27 |
| 7 | C004 | tsmom_cross_N48 | 0.27 | 20773 | 0.8 | 39.4 | 1.01 | 0.35 | 52 | 0.21 | 8 |
| 8 | C162 | xs_reversal_N336 | 0.06 | 9555 | 0.3 | 39.3 | 1.00 | 0.08 | 39 | 0.05 | 160 |
| 9 | C152 | funding_contrarian_f0.0002 | 0.01 | 12884 | 0.1 | 39.4 | 1.00 | 0.01 | 48 | 0.01 | 44 |
| 10 | C109 | volume_regime_mom_regimelo_N24 | 0.01 | 10983 | 0.0 | 36.8 | 1.00 | 0.01 | 35 | 0.00 | 114 |
| 11 | C068 | vol_compr_break_q0.7_N12 | -0.27 | 6211 | -1.4 | 34.3 | 0.99 | -0.37 | 45 | -0.23 | 39 |
| 12 | C091 | vr_trend_W336_v1.25_N24 | -0.40 | 295 | -10.8 | 37.3 | 0.92 | -0.55 | 47 | -0.33 | 69 |
| 13 | C090 | vr_trend_W336_v1.25_N12 | -0.44 | 418 | -12.3 | 37.6 | 0.92 | -0.63 | 40 | -0.38 | 68 |
| 14 | C077 | vol_spike_fade_fast24_x2.5 | -0.53 | 924 | -24.7 | 43.9 | 0.94 | -0.73 | 44 | -0.44 | 110 |
| 15 | C139 | donchian_close_break_N336 | -0.62 | 9169 | -4.1 | 38.1 | 0.98 | -0.80 | 55 | -0.49 | 92 |
| 16 | C057 | exhaust_fade_N8_m2 | -0.66 | 1158 | -10.9 | 37.3 | 0.93 | -0.94 | 41 | -0.57 | 61 |
| 17 | C099 | vr_revert_W336_v1.25_N24 | -0.76 | 4035 | -5.7 | 39.9 | 0.96 | -1.06 | 43 | -0.65 | 77 |
| 18 | C144 | consec_closes_K7 | -0.76 | 2891 | -7.8 | 37.1 | 0.95 | -1.04 | 47 | -0.63 | 131 |
| 19 | C071 | vol_compr_break_q0.8_N24 | -0.77 | 7180 | -4.2 | 34.6 | 0.97 | -1.08 | 42 | -0.66 | 42 |
| 20 | C002 | tsmom_cross_N12 | -0.90 | 36830 | -2.4 | 38.7 | 0.98 | -1.21 | 48 | -0.73 | 6 |

## Why-notes (top 20)

1. **funding_contrarian_f0.0005**: Crowded perp positioning shows up in funding; extreme funding tends to mean-revert as the crowded side pays. Mirror-adjacent to R13 (overheat), so overlap risk noted.
2. **funding_contrarian_f0.0003**: Crowded perp positioning shows up in funding; extreme funding tends to mean-revert as the crowded side pays. Mirror-adjacent to R13 (overheat), so overlap risk noted.
3. **vol_compr_break_q0.6_N24**: Volatility compression precedes expansion; breakouts from low-vol ranges in crypto tend to run.
4. **vol_compr_break_q0.6_N12**: Volatility compression precedes expansion; breakouts from low-vol ranges in crypto tend to run.
5. **vol_compr_break_q0.7_N24**: Volatility compression precedes expansion; breakouts from low-vol ranges in crypto tend to run.
6. **dip_buy_D15_W168**: Buy-the-dip in crypto drawdowns with a green confirmation bar; drawdowns tend to partially recover in bull regimes.
7. **tsmom_cross_N48**: Trend persistence in crypto perps: leveraged flow and slow narrative diffusion keep multi-day moves going.
8. **xs_reversal_N336**: Relative losers over short windows bounce as liquidity providers rotate back into lagging coins.
9. **funding_contrarian_f0.0002**: Crowded perp positioning shows up in funding; extreme funding tends to mean-revert as the crowded side pays. Mirror-adjacent to R13 (overheat), so overlap risk noted.
10. **volume_regime_mom_regimelo_N24**: Trend moves on abnormal participation (high turnover) tend to persist, while thin-volume moves revert.
11. **vol_compr_break_q0.7_N12**: Volatility compression precedes expansion; breakouts from low-vol ranges in crypto tend to run.
12. **vr_trend_W336_v1.25_N24**: Hurst/variance-ratio trendiness gate: momentum signals are only traded where returns are positively autocorrelated.
13. **vr_trend_W336_v1.25_N12**: Hurst/variance-ratio trendiness gate: momentum signals are only traded where returns are positively autocorrelated.
14. **vol_spike_fade_fast24_x2.5**: Vol spikes in crypto are liquidation-driven; the vol risk premium implies over-reaction is faded.
15. **donchian_close_break_N336**: Close-based channel breakout is a simple trend-following premium test.
16. **exhaust_fade_N8_m2**: Parabolic runs of same-direction bars in perps exhaust as stop-hunting completes and momentum traders take profit.
17. **vr_revert_W336_v1.25_N24**: Variance-ratio mean-reversion gate: contrarian signals only where returns are negatively autocorrelated.
18. **consec_closes_K7**: Runs of same-direction closes in perps mark short-term exhaustion before the reversion.
19. **vol_compr_break_q0.8_N24**: Volatility compression precedes expansion; breakouts from low-vol ranges in crypto tend to run.
20. **tsmom_cross_N12**: Trend persistence in crypto perps: leveraged flow and slow narrative diffusion keep multi-day moves going.

## Caveats

- EXPLORATORY SCREEN ONLY. Not G-eligible, not added to TRAIN_TRIALS.csv or any ledger, not counted toward the 13-round cap.
- No look-ahead-bias audit beyond the construction rules; no walk-forward, no out-of-sample split inside TRAIN.
- No multiple-testing correction across 166 ideas; top t-stats are optimistic and selection-biased.
- Single shared exit for every idea (1.5/3.0 ATR, 24 bars). Families whose edge lives on a different horizon (e.g., 4-bar seasonal, funding-settlement entries) are judged on this exit only, so a low rank is not evidence the underlying idea is dead.
- 1h timeframe only, equal-weight symbols, gaps in bar history not repaired; rough Sharpe scales per-trade stats by pooled trades per year and assumes independence.
- Spearman rank correlation between the pre-run prior ranking and empirical composite ranking (eligible ideas): 0.14.
- Promotion to any candidate requires separate formal preregistration, synthetic tests, and a resource-gated TRAIN run.
