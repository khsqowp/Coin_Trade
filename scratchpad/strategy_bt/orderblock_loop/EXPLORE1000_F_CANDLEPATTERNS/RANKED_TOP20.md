# RANKED TOP 20 - EXPLORATORY SCREEN ONLY (lane F: candlestick / price-action)

> EXPLORATORY SCREEN ONLY - not part of the 13-round preregistered G-gate track, not added to TRAIN_TRIALS.csv, no promotion without separate formal preregistration + synthetic tests + resource-gated TRAIN run.

Method: 31 crypto perps, 1h TRAIN bars via data_access.iter_train_bars; shared exit (stop 1.5 ATR14, target 3.0 ATR14, 24-bar max hold, 12bp RT cost, one position per symbol, next-bar-open entry, onset-filtered signals). Ranking = composite = t(net bps) x (0.5 + 0.5 x fraction of symbols with positive mean). Eligibility: >= 100 trades and >= 10 symbols.

Scored 246 of 249 ideas with at least one trade; 229 met eligibility.

| rank | id | name | composite | trades | net bps/trade | win % | PF | t | pos-sym % | EV 1st half | EV 2nd half | both halves > 0 |
|---|---|---|---|---|---|---|---|---|---|---|---|---|
| 1 | F222 | bollinger_reject_k2.5_modecont_conf0 | 1.06 | 6500 | 6.1 | 39.4 | 1.04 | 1.29 | 65 | -6.7 | 13.7 | no |
| 2 | F117 | inside_chain_K1_T0_modefade_V0 | 1.00 | 26868 | 3.1 | 39.2 | 1.02 | 1.30 | 55 | 9.4 | -1.2 | no |
| 3 | F223 | bollinger_reject_k2.5_modecont_conf1 | 0.92 | 6133 | 5.7 | 39.1 | 1.04 | 1.17 | 58 | -6.5 | 13.2 | no |
| 4 | F057 | outside_moderev_N0 | 0.80 | 25289 | 2.3 | 39.5 | 1.02 | 0.99 | 61 | 2.7 | 2.0 | yes |
| 5 | F012 | engulf_modecont_T168_V1.5 | 0.65 | 9068 | 3.4 | 38.6 | 1.02 | 0.90 | 45 | 6.4 | 1.7 | yes |
| 6 | F021 | doji_ext_N24_b0.1_pf0.1_moderev | 0.52 | 4612 | 3.9 | 38.1 | 1.02 | 0.65 | 58 | -14.1 | 16.5 | no |
| 7 | F121 | inside_chain_K1_T48_modefade_V0 | 0.49 | 20084 | 1.8 | 38.9 | 1.01 | 0.65 | 52 | 8.6 | -3.0 | no |
| 8 | F010 | engulf_modecont_T72_V1.5 | 0.49 | 9898 | 2.4 | 38.2 | 1.02 | 0.66 | 48 | 6.7 | 0.0 | yes |
| 9 | F125 | inside_chain_K2_T0_modefade_V0 | 0.47 | 2896 | 4.5 | 39.4 | 1.03 | 0.60 | 58 | 1.2 | 6.9 | yes |
| 10 | F063 | flag_K6_M6_Y0.5_X2.5 | 0.33 | 819 | 7.3 | 37.0 | 1.04 | 0.45 | 46 | 11.4 | 4.6 | yes |
| 11 | F126 | inside_chain_K2_T0_modefade_V1.5 | 0.30 | 826 | 5.1 | 38.5 | 1.03 | 0.36 | 68 | 7.8 | 3.2 | yes |
| 12 | F161 | bigbar_run_K3_b1.0_modecont_T0 | 0.27 | 587 | 6.0 | 39.7 | 1.04 | 0.35 | 57 | 0.6 | 9.1 | yes |
| 13 | F162 | bigbar_run_K3_b1.0_modecont_T48 | 0.18 | 584 | 4.0 | 39.6 | 1.02 | 0.23 | 57 | -2.3 | 7.7 | no |
| 14 | F066 | flag_K6_M6_Y0.8_X4.0 | 0.11 | 139 | 5.9 | 40.3 | 1.03 | 0.16 | 38 | 20.6 | -3.2 | no |
| 15 | F025 | doji_ext_N24_b0.2_pf0.1_moderev | 0.08 | 8368 | 0.5 | 38.0 | 1.00 | 0.11 | 45 | -14.3 | 11.3 | no |
| 16 | F130 | inside_chain_K2_T48_modefade_V1.5 | 0.03 | 681 | 0.7 | 38.0 | 1.00 | 0.04 | 57 | 1.4 | 0.2 | yes |
| 17 | F129 | inside_chain_K2_T48_modefade_V0 | -0.04 | 1938 | -0.5 | 38.9 | 1.00 | -0.05 | 55 | -0.9 | -0.2 | no |
| 18 | F083 | pennant_K24_M12_X2.0 | -0.07 | 219 | -2.5 | 35.2 | 0.98 | -0.10 | 33 | -20.1 | 15.3 | no |
| 19 | F111 | failed_break_N72_confirm0_X0 | -0.08 | 7075 | -0.6 | 39.6 | 1.00 | -0.11 | 48 | 5.3 | -5.5 | no |
| 20 | F113 | failed_break_N72_confirm1_X0 | -0.09 | 7074 | -0.6 | 39.6 | 1.00 | -0.12 | 48 | 5.3 | -5.5 | no |

## Rationale (one line each)

1. **F222 bollinger_reject_k2.5_modecont_conf0** - Prior close outside BB(20,k); current close back inside (rev) or still outside (cont), optional bar-colour confirmation. Stats: t=1.29, 6500 trades, not stable across halves.
2. **F117 inside_chain_K1_T0_modefade_V0** - K consecutive inside bars, then close beyond the mother-bar extreme. cont = follow the break; fade = trade the false break. Stats: t=1.30, 26868 trades, not stable across halves.
3. **F223 bollinger_reject_k2.5_modecont_conf1** - Prior close outside BB(20,k); current close back inside (rev) or still outside (cont), optional bar-colour confirmation. Stats: t=1.17, 6133 trades, not stable across halves.
4. **F057 outside_moderev_N0** - Outside bar (new high and new low vs prior bar) closing beyond prior range. rev = key-reversal fade; optional N-bar extreme context. Stats: t=0.99, 25289 trades, both halves positive.
5. **F012 engulf_modecont_T168_V1.5** - Bullish/bearish engulfing candle (body engulfs prior body). rev = counter-trend at SMA(T) extreme; cont = with trend. Stats: t=0.90, 9068 trades, both halves positive.
6. **F021 doji_ext_N24_b0.1_pf0.1_moderev** - Indecision doji (body <= b x range) with close in bottom/top pf fraction of N-bar range. rev fades, cont follows. Stats: t=0.65, 4612 trades, not stable across halves.
7. **F121 inside_chain_K1_T48_modefade_V0** - K consecutive inside bars, then close beyond the mother-bar extreme. cont = follow the break; fade = trade the false break. Stats: t=0.65, 20084 trades, not stable across halves.
8. **F010 engulf_modecont_T72_V1.5** - Bullish/bearish engulfing candle (body engulfs prior body). rev = counter-trend at SMA(T) extreme; cont = with trend. Stats: t=0.66, 9898 trades, both halves positive.
9. **F125 inside_chain_K2_T0_modefade_V0** - K consecutive inside bars, then close beyond the mother-bar extreme. cont = follow the break; fade = trade the false break. Stats: t=0.60, 2896 trades, both halves positive.
10. **F063 flag_K6_M6_Y0.5_X2.5** - Flag: impulse of M bars >= X ATR ending K bars ago, tight K-bar consolidation (range <= Y x impulse), close breaks consolidation in impulse direction. Stats: t=0.45, 819 trades, both halves positive.
11. **F126 inside_chain_K2_T0_modefade_V1.5** - K consecutive inside bars, then close beyond the mother-bar extreme. cont = follow the break; fade = trade the false break. Stats: t=0.36, 826 trades, both halves positive.
12. **F161 bigbar_run_K3_b1.0_modecont_T0** - K consecutive large-body bars (body >= b x ATR) in one direction. rev = exhaustion fade; cont = momentum follow. Stats: t=0.35, 587 trades, both halves positive.
13. **F162 bigbar_run_K3_b1.0_modecont_T48** - K consecutive large-body bars (body >= b x ATR) in one direction. rev = exhaustion fade; cont = momentum follow. Stats: t=0.23, 584 trades, not stable across halves.
14. **F066 flag_K6_M6_Y0.8_X4.0** - Flag: impulse of M bars >= X ATR ending K bars ago, tight K-bar consolidation (range <= Y x impulse), close breaks consolidation in impulse direction. Stats: t=0.16, 139 trades, not stable across halves.
15. **F025 doji_ext_N24_b0.2_pf0.1_moderev** - Indecision doji (body <= b x range) with close in bottom/top pf fraction of N-bar range. rev fades, cont follows. Stats: t=0.11, 8368 trades, not stable across halves.
16. **F130 inside_chain_K2_T48_modefade_V1.5** - K consecutive inside bars, then close beyond the mother-bar extreme. cont = follow the break; fade = trade the false break. Stats: t=0.04, 681 trades, both halves positive.
17. **F129 inside_chain_K2_T48_modefade_V0** - K consecutive inside bars, then close beyond the mother-bar extreme. cont = follow the break; fade = trade the false break. Stats: t=-0.05, 1938 trades, not stable across halves.
18. **F083 pennant_K24_M12_X2.0** - Pennant: OLS slope of highs < 0 and lows > 0 over K bars (converging), after impulse of M bars; close breaks the converging range. Stats: t=-0.10, 219 trades, not stable across halves.
19. **F111 failed_break_N72_confirm0_X0** - Previous bar closed beyond the prior N-bar extreme (by X ATR); current bar closes back inside -> fade the breakout. Stats: t=-0.11, 7075 trades, not stable across halves.
20. **F113 failed_break_N72_confirm1_X0** - Previous bar closed beyond the prior N-bar extreme (by X ATR); current bar closes back inside -> fade the breakout. Stats: t=-0.12, 7074 trades, not stable across halves.

## Caveats

- EXPLORATORY ONLY. 249 ideas screened with no multiple-testing correction; with this many candidates, several top-20 entries are expected to be false positives.
- Baselines under the same exit and cost (net bps/trade): unconditional long every bar -10.5 (n=71344), unconditional short every bar -17.1 (n=70402), long every 24th bar -15.0 (n=30716). Median net EV across scored ideas is -14.6 bps; 24 of 246 ideas are net positive. A positive number therefore beats a strongly negative unconditional baseline, but this is a bull-skewed window: the baseline long is itself near zero-to-negative after costs, and side-split checks were not run.
- Sample is one 1h TRAIN window (~2.7 years) that is strongly bull-skewed; a rule that works here may only be trend/beta exposure. Trend-context variants are included but not regime-tested. The 'both halves > 0' column is the cheapest stability proxy in this screen; most top-ranked ideas fail it.
- Signals are onset-filtered and traded greedily one position per symbol; trade counts overlap across symbols, so the t-statistic overstates independent evidence.
- Shared exit (1.5/3.0 ATR, 24 bars) is not tuned per family. Pattern families whose edge lives on a different horizon will rank low here without that being evidence they are dead.
- Pattern rules are discretionary-style approximations (e.g. 'doji', 'pin bar', 'flag', 'pennant' via OLS slope sign); parameter grids are small and hand-picked, not optimized.
- Composite is comparable only within this lane; do not compare directly to C/A/B lane composites (different exits and symbol universes).
- Families overlapping the EXPLORE500 C lane (vol-compression/flag breakout, consecutive-run exhaustion) converge with that lane's ranks; treat that as correlation of the same mechanism, not independent confirmation.
- Nothing here is a validated candidate. Any lead requires a separate preregistration, synthetic tests, and a resource-gated TRAIN run.
