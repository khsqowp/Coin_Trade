# US_STATE (2026-11-13, after round 6 = FINAL)
Rounds: 1 (US-01..12, 30 trials), 2 (US-13..20, 15), Stage 2 on US-18 (54 grid cells), 3 (Stage 3 of US-18-T100), 4 (US-21..27, 13), 5 (US-28..32, 17), 6 (US-33..34, 11). Cumulative BH list = 140 trials.
Survivors: Stage 1 survivors exist only on the dynamic (survivorship-laden) T100 universe: US-18, US-32-DYN-h5/h10/h20, US-33a-DYN, US-33c-DYN. None is positive+t>=2+2x>0 on both frozen universes F14/F18. US-18-T100 (RSI2<5, 126d top quartile, dynamic PIT top-100) is the only Stage 3 pass (holdout +1.98%/trade, Sh 2.01) but is survivorship-dependent (see US_FINAL.md).
Holdout looks (results/holdout_unlock.log): 3, all for the same frozen US-18-T100 candidate - (1) Stage 3 look, (2) breadth/outlier robustness, (3) frozen-universe survivorship diagnostic. No new candidate has been looked at on the holdout. BH over holdout looks: one candidate test, p~0.001 (t=3.31) -> q=0.001 (n=1); diagnostics are not additional independent tests.
Not done / ideas: point-in-time S&P constituents (the real fix); US-34 shows the best frozen-universe signal is plain momentum drift (hold 20d, +0.8..1.4%, t~1.9) - test it only with PIT membership; paper-trade US-18 with next-open entry.

## Round 7 (extra, survivorship repair) - done
9 trials, cumulative 149. MEM universe (Wikipedia Date added) keeps Stage 1 passes (US-18c t=3.86; h5/h10/h20, US-24, US-25 specs t 3.4-5.1) but nothing clears the strict gate on F14+F18 (2x>0 and t>=2). No holdout look. Verdict: not meaningful for <=5-day US strategies. Residual survivor bias (no removed names) remains, so even MEM numbers are upper bounds.

## Round 8 (longer holds 10-40d) - done
47 trials, cumulative 196. 0 groups pass the strict gate: 40d leaders/trend earn +1.8..3.3%/trade (2x, 3x positive) but equal market drift (beta ~1, Sharpe <= EW buy-and-hold on MEM/F14, alpha t<=0.1 there). No Stage 2/3; holdout looks still 3. Verdict US 10-40d: not meaningful (beta, not alpha).

## Round 9 (ETF/VIX/cross-asset; beyond cap, owner-authorised) - done
11 trials, cumulative 207, 0 survivors. Pooled ETF dips are net negative/zero after 0.40% cost; VIX-spike timing is noise; best US-51 (equity-vs-bond divergence) t_week 2.68 with 93 episodes, US-52 (VIX>=30 falling) +1.35% with 56 episodes - both below the bar and too few independent episodes. Holdout untouched (3 looks, all US-18-T100).
