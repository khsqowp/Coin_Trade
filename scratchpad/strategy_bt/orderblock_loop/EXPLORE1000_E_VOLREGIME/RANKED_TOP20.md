# RANKED TOP 20 - EXPLORATORY SCREEN ONLY (lane E: volatility regime)

> EXPLORATORY SCREEN ONLY - not part of the 13-round preregistered G-gate track, not added to TRAIN_TRIALS.csv, no promotion without separate formal preregistration + synthetic tests + resource-gated TRAIN run.

Method: 31 crypto perps with TRAIN 1h bars (4 symbols with too few bars dropped), data_access.iter_train_bars. Shared engine with lane C: next-open entry, 12bp RT cost, one position per symbol, stop checked before target. Two exit profiles: std (1.5/3.0 ATR, 24 bars) and wide (2.5 ATR stop, no target, 72 bars). RANKING METRIC = hedged_composite: each trade's net bps minus d x (equal-weight 31-coin basket return over the same holding window), so common crypto drift in this bull-leaning sample is removed. hedged_composite = t(hedged net bps) x (0.5 + 0.5 x fraction of symbols with positive hedged mean). Raw (unhedged) composite_score is kept in RESULTS.csv for reference only. Eligibility: >= 100 pooled trades and >= 10 symbols.

Proposed 252 ideas; scored 252 with at least one trade; 250 met eligibility; no-trade ideas: 0. All ideas use OHLCV only, so none were data-blocked.

| rank | idea_id | name | hedged composite | n_trades | hedged exp net bps | hedged win % | hedged t | hedged pos-sym % | raw exp net bps | prior rank |
|---|---|---|---|---|---|---|---|---|---|---|
| 1 | E242 | rv_squeeze_channel_break_q0.6_N48_modecont_exitwide | 2.15 | 4961 | 21.2 | 41.5 | 2.61 | 65 | 36.6 | 146 |
| 2 | E238 | rv_squeeze_channel_break_q0.6_N24_modecont_exitwide | 2.12 | 6676 | 16.4 | 41.7 | 2.47 | 71 | 27.1 | 142 |
| 3 | E118 | bb_width_squeeze_release_p0.2_L500_modecont_exitwide | 2.06 | 8770 | 13.4 | 41.9 | 2.50 | 65 | 27.7 | 46 |
| 4 | E234 | rv_squeeze_channel_break_q0.5_N48_modecont_exitwide | 1.79 | 2788 | 24.6 | 41.4 | 2.15 | 67 | 49.4 | 138 |
| 5 | E020 | vol_gated_breakout_gatelo_0.2_N24_sigdch_exitwide | 1.58 | 5208 | 11.2 | 42.7 | 2.00 | 58 | 41.1 | 4 |
| 6 | E032 | vol_gated_breakout_gatelo_0.35_N96_sigdch_exitwide | 1.51 | 4557 | 14.2 | 41.6 | 1.84 | 65 | 52.6 | 16 |
| 7 | E028 | vol_gated_breakout_gatelo_0.35_N24_sigdch_exitwide | 1.49 | 7322 | 11.0 | 42.4 | 1.93 | 55 | 39.0 | 12 |
| 8 | E230 | rv_squeeze_channel_break_q0.5_N24_modecont_exitwide | 1.44 | 3934 | 16.0 | 41.7 | 1.83 | 57 | 17.8 | 134 |
| 9 | E102 | range_expansion_bar_k2.5_q0.85_modecont_exitwide | 1.38 | 4913 | 17.6 | 39.6 | 1.68 | 65 | 53.6 | 102 |
| 10 | E022 | vol_gated_breakout_gatelo_0.2_N96_sigtsm_exitwide | 1.26 | 2710 | 12.3 | 42.9 | 1.56 | 61 | 39.0 | 6 |
| 11 | E024 | vol_gated_breakout_gatelo_0.2_N96_sigdch_exitwide | 1.20 | 3192 | 10.8 | 41.7 | 1.46 | 65 | 59.8 | 8 |
| 12 | E030 | vol_gated_breakout_gatelo_0.35_N96_sigtsm_exitwide | 1.03 | 3791 | 9.1 | 42.4 | 1.28 | 61 | 41.1 | 14 |
| 13 | E080 | vol_of_vol_spike_W720_zt3.0_D24_modefade | 0.99 | 725 | 18.2 | 43.7 | 1.21 | 64 | -13.3 | 164 |
| 14 | E034 | vol_gated_breakout_gatehi_0.65_N24_sigtsm_exitwide | 0.87 | 4322 | 11.8 | 41.9 | 1.16 | 50 | -33.8 | 18 |
| 15 | E098 | range_expansion_bar_k2.5_q0.75_modecont_exitwide | 0.86 | 7191 | 8.8 | 40.0 | 1.07 | 61 | 38.3 | 98 |
| 16 | E077 | vol_of_vol_spike_W720_zt3.0_D6_modecont | 0.80 | 986 | 14.7 | 47.1 | 1.07 | 50 | 17.9 | 161 |
| 17 | E110 | bb_width_squeeze_release_p0.1_L500_modecont_exitwide | 0.69 | 6411 | 5.3 | 41.2 | 0.89 | 55 | 25.2 | 38 |
| 18 | E228 | vol_expansion_breakout_X2.0_N48_exitwide | 0.63 | 1294 | 32.4 | 39.3 | 0.81 | 55 | -18.3 | 132 |
| 19 | E166 | vol_spike_decay_cont_X3.0_d1.0_D24_exitwide | 0.61 | 152 | 31.5 | 42.8 | 0.76 | 60 | -133.4 | 210 |
| 20 | E224 | vol_expansion_breakout_X2.0_N12_exitwide | 0.60 | 1510 | 26.8 | 40.1 | 0.77 | 57 | -59.6 | 128 |

## Why-notes (top 20)

1. **rv_squeeze_channel_break_q0.6_N48_modecont_exitwide** (E242): Realized-vol squeeze (close-to-close) released by a channel break; cont vs fade tests whether low-vol breakouts are real.
2. **rv_squeeze_channel_break_q0.6_N24_modecont_exitwide** (E238): Realized-vol squeeze (close-to-close) released by a channel break; cont vs fade tests whether low-vol breakouts are real.
3. **bb_width_squeeze_release_p0.2_L500_modecont_exitwide** (E118): Bandwidth-percentile squeeze release, with longer percentile windows than the classic 100-bar squeeze.
4. **rv_squeeze_channel_break_q0.5_N48_modecont_exitwide** (E234): Realized-vol squeeze (close-to-close) released by a channel break; cont vs fade tests whether low-vol breakouts are real.
5. **vol_gated_breakout_gatelo_0.2_N24_sigdch_exitwide** (E020): Vol-regime-gated trend following: trend signals are traded only in low-vol (orderly trends) or high-vol (liquidation-driven runs) regimes.
6. **vol_gated_breakout_gatelo_0.35_N96_sigdch_exitwide** (E032): Vol-regime-gated trend following: trend signals are traded only in low-vol (orderly trends) or high-vol (liquidation-driven runs) regimes.
7. **vol_gated_breakout_gatelo_0.35_N24_sigdch_exitwide** (E028): Vol-regime-gated trend following: trend signals are traded only in low-vol (orderly trends) or high-vol (liquidation-driven runs) regimes.
8. **rv_squeeze_channel_break_q0.5_N24_modecont_exitwide** (E230): Realized-vol squeeze (close-to-close) released by a channel break; cont vs fade tests whether low-vol breakouts are real.
9. **range_expansion_bar_k2.5_q0.85_modecont_exitwide** (E102): Range-expansion days with decisive closes: follow-through versus fade is an empirical question about whether volatility shocks carry information.
10. **vol_gated_breakout_gatelo_0.2_N96_sigtsm_exitwide** (E022): Vol-regime-gated trend following: trend signals are traded only in low-vol (orderly trends) or high-vol (liquidation-driven runs) regimes.
11. **vol_gated_breakout_gatelo_0.2_N96_sigdch_exitwide** (E024): Vol-regime-gated trend following: trend signals are traded only in low-vol (orderly trends) or high-vol (liquidation-driven runs) regimes.
12. **vol_gated_breakout_gatelo_0.35_N96_sigtsm_exitwide** (E030): Vol-regime-gated trend following: trend signals are traded only in low-vol (orderly trends) or high-vol (liquidation-driven runs) regimes.
13. **vol_of_vol_spike_W720_zt3.0_D24_modefade** (E080): Vol-of-vol spikes mark regime instability; whether the subsequent move continues or reverts is tested directly, with no price-structure condition.
14. **vol_gated_breakout_gatehi_0.65_N24_sigtsm_exitwide** (E034): Vol-regime-gated trend following: trend signals are traded only in low-vol (orderly trends) or high-vol (liquidation-driven runs) regimes.
15. **range_expansion_bar_k2.5_q0.75_modecont_exitwide** (E098): Range-expansion days with decisive closes: follow-through versus fade is an empirical question about whether volatility shocks carry information.
16. **vol_of_vol_spike_W720_zt3.0_D6_modecont** (E077): Vol-of-vol spikes mark regime instability; whether the subsequent move continues or reverts is tested directly, with no price-structure condition.
17. **bb_width_squeeze_release_p0.1_L500_modecont_exitwide** (E110): Bandwidth-percentile squeeze release, with longer percentile windows than the classic 100-bar squeeze.
18. **vol_expansion_breakout_X2.0_N48_exitwide** (E228): Volatility expansion plus price breakout: the breakout is only taken as volatility regime shifts up.
19. **vol_spike_decay_cont_X3.0_d1.0_D24_exitwide** (E166): Post-spike decay: once volatility normalizes, the direction set during the spike may continue as trend-following capital returns.
20. **vol_expansion_breakout_X2.0_N12_exitwide** (E224): Volatility expansion plus price breakout: the breakout is only taken as volatility regime shifts up.

## Null calibration (random entries, same cost and std exit)

20 seeds, random long and short at 1.0% of bars each. Pooled trades ~12218 median. Raw (unhedged) null expectancy (net bps): mean -11.8, range -19.7 to -4.9. Hedged null expectancy (net bps): mean -12.0, range -17.1 to -8.9. Hedged null composite: mean -3.03, max -2.38. Raw null composite max -0.97 (shows drift contamination of the raw metric). Wide-exit hedged null composite: mean -0.67, max 0.21. Ideas whose hedged composite is not clearly above the hedged null band are indistinguishable from noise at this sample size.

## Caveats

- EXPLORATORY SCREEN ONLY. Not G-eligible, not added to TRAIN_TRIALS.csv or any ledger, not counted toward the 13-round cap.
- No look-ahead audit beyond construction rules; no walk-forward and no out-of-sample split inside TRAIN.
- No multiple-testing correction across the full grid; top t-stats are optimistic and selection-biased.
- Regime dependence: the TRAIN span is dominated by a bull-leaning sample, and vol-regime percentiles are relative to the trailing 1440 bars, so a regime shift can flip conditional results.
- Vol-regime gates are expressed as trailing percentiles, not fitted thresholds, but the thresholds themselves are a grid choice.
- 'Wide' exit shares a single 72-bar hold across ideas; families whose edge lives on a different horizon are judged only on these two exits.
- VRP-style ideas use OHLCV realized vol only. They are NOT options-based volatility risk premium estimates.
- Spearman rank correlation between the pre-run prior ranking and empirical composite ranking (eligible ideas): -0.05.
- Exit confound: most of the top 20 use the 'wide' exit (no target, 72-bar hold). Compare within exit: see the std-exit list below.
- Hedge caveat: hedging against one equal-weight basket assumes beta ~1 to the basket. Where a signal is mostly short in a bull sample, the hedge can flip the sign (e.g., E166 raw -133 bps, hedged +31 bps on 152 trades). Treat sign flips with suspicion.
- Sample size: most top-20 ideas have 2,700 to 9,000 trades, but these are overlapping, serially correlated trades across 31 coins in one bull-leaning ~2.7-year span, so effective sample size is far smaller than the trade count.
- Promotion to any candidate requires separate formal preregistration, synthetic tests, and a resource-gated TRAIN run.

## Best standard-exit ideas (exit = std: 1.5/3.0 ATR, 24 bars), hedged ranking

| rank | idea_id | name | hedged composite | n_trades | hedged exp net bps | hedged t |
|---|---|---|---|---|---|---|
| 1 | E080 | vol_of_vol_spike_W720_zt3.0_D24_modefade | 0.99 | 725 | 18.2 | 1.21 |
| 2 | E077 | vol_of_vol_spike_W720_zt3.0_D6_modecont | 0.80 | 986 | 14.7 | 1.07 |
| 3 | E227 | vol_expansion_breakout_X2.0_N48_exitstd | 0.60 | 1573 | 9.0 | 0.75 |
| 4 | E165 | vol_spike_decay_cont_X3.0_d1.0_D24_exitstd | 0.55 | 168 | 13.5 | 0.70 |
| 5 | E223 | vol_expansion_breakout_X2.0_N12_exitstd | 0.29 | 1879 | 4.6 | 0.42 |
