# Regime switching / filter study - REPORT

Spec: `PREREG.md` (written before any result; thresholds never changed). Code: `run_regime.py`; tests: `tests/test_regime.py` (9 pass: causality of labels and of the timestamp lookup, V3 trailing-mean causality, run-shift invariants, bucket edges, K=2 sets, walk-forward == brute force and never trains on trades with exit >= retrain date, 4h resample). Full run: 87 s, 21 candidates x 4 symbols (BTC ETH BNB XRP), 1000 draws, N_trials = 176 (V1: 8, V2: 84, V3: 84). Data: `results/*.csv` (`results.csv` has every row; `v0_trades.csv` the cached trades).

## Verdict
**0 of 176 trials pass the prereg rule. No K, no variant.** Regime filtering/switching did not produce a defensible improvement over the unfiltered strategies.

Gate funnel over 176 trials: beats V0 on return 19; null pctl >= 95 21 (expected by chance at N=176: about 9); both 4; also loss reduced in 2018H2 and 2022 and episodes OK: 2 (V1 K=3 FINALISTS, V2 K=7 c5-raschke-anti-stochastic 4h). Both fail Bonferroni: empirical p (exhaustive shifts) 0.032 and 0.050 vs threshold 0.05/176 = 0.00028.

**The Bonferroni gate is unreachable by construction** for this null: a circular shift of ~2,900 valid label days gives at most ~2,900 distinct draws, so the smallest possible empirical p is ~0.00034 > 0.00028. Treat the adjusted gate as "cannot pass" rather than as evidence either way; the raw evidence is weak anyway (z-approx p 0.009 and 0.045 unadjusted, 2 survivors out of 176 looks like noise).

## Per variant / K (mean over candidates; ret = percent-sum of pooled 4-symbol trades, TEST = entries 2018-07-01 on)
| Variant | K | n | beat V0 | pctl>=95 | loss red. 2018H2 | loss red. 2022 | mean dRet vs V0 | mean dTrades | mean dMaxDD (pts, + = shallower) | PASS |
|---|---|---|---|---|---|---|---|---|---|---|
| V1 | 2 | 2 | 1 | 1 | 2 | 1 | +67.5 | +153 | +2.0 | 0 |
| V1 | 3 | 2 | 2 | 1 | 2 | 1 | +96.7 | +154 | -0.5 | 0 |
| V1 | 5 | 2 | 1 | 0 | 2 | 1 | +9.0 | +125 | -5.5 | 0 |
| V1 | 7 | 2 | 1 | 0 | 0 | 1 | -38.6 | +107 | -11.9 | 0 |
| V2 | 2 | 21 | 2 | 2 | 20 | 21 | -77.3 | -280 | +11.1 | 0 |
| V2 | 3 | 21 | 1 | 4 | 20 | 20 | -88.7 | -334 | +14.4 | 0 |
| V2 | 5 | 21 | 1 | 4 | 19 | 20 | -93.4 | -347 | +14.5 | 0 |
| V2 | 7 | 21 | 1 | 5 | 19 | 19 | -117.1 | -366 | +13.9 | 0 |
| V3 | 2 | 21 | 4 | 1 | 15 | 12 | -5.7 | -29 | +1.9 | 0 |
| V3 | 3 | 21 | 2 | 0 | 17 | 10 | -28.0 | -68 | +1.1 | 0 |
| V3 | 5 | 21 | 3 | 2 | 17 | 18 | -52.5 | -119 | +5.0 | 0 |
| V3 | 7 | 21 | 0 | 1 | 17 | 15 | -78.2 | -165 | +3.3 | 0 |

V0 pooled baselines: see `results/v0.csv` (e.g. TEST return 83 to 591 per candidate; pool-mean 278 ALL / 243 FINALISTS).

## Which K degrade
- Finer K is monotonically worse. V2 (ambiguous-cash/direction gating) loses 77 -> 89 -> 93 -> 117 return points going K=2 -> 7, V3 loses 6 -> 28 -> 52 -> 78, V1 goes +67 / +97 / +9 / -39. K=7 is the worst in every variant (V1 K=7 loses to V0 and has the worst 2018 and drawdown outcome; 0/21 V3 K=7 rows beat V0).
- V2 buys a shallower drawdown (+11 to +14 pts) and almost always "reduces loss" in 2018H2 and 2022, but only by trading ~80% fewer trades and giving up most of the return (it beats V0 in 1-2 of 21 rows per K). Cash-in-ambiguity is mainly an exposure cut, not timing skill; the 2018/2022 gates are easy to pass for any filter that mostly sits in cash.
- V1 "beats V0" only against the pool-mean baseline. Against the best single candidate (V0 best = 591 for ALL, 308 for FINALISTS) V1 loses in all 8 rows.
- Episodes: every regime has >= 14 episodes in TEST for all K (`episodes.csv`), so nothing was "unevaluable"; the failure is not for lack of regime episodes. Caveat: counts are of contiguous label runs, and the daily label flickers around edges for K=3/5/7 (e.g. K=5 regime 2: 54 episodes in 544 days), so episodes overstate independent evidence.

## Caveats (honest)
- **In-sample strategy params.** Frozen params come from the harness TRAIN split (first 60% of the same 2017-2026 history, i.e. through 2023-03). The 2018-2023 part of the TEST window is therefore in-sample for the strategies (V0 included). Candidates were also chosen by TRAIN rank. This inflates V0 and, to a lesser degree, V1's selection pool; a true OOS check is only 2023-03 onward.
- Walk-forward start 2018-07-01 means the first retrains have <1 year of training and are mostly cash (min 15 trades/regime). The "2018 window" is H2 2018 only (SMA200 warm-up). The 2022 and 2018 windows are 2 bear episodes; with so few independent bear regimes "loss reduced" evidence is thin.
- Trade-tag evaluation: filters drop V0 trades rather than re-simulating position slots, and V1 can overlap positions from different strategies at regime boundaries. Real gating could differ. Entries are tagged by entry-fill-time label (prior daily close); no forced exit on regime change.
- The null (circular shift of labels) tests label alignment only; it shares the trend structure of the labels. Reductions of exposure (V2/V3) are not penalised by it. Null draws are heavily overlapping (max ~2,900 distinct shifts), so p-values are coarse.
- Returns are percent-sum (not compounded) on fixed 1,000 notional per trade; max drawdown is realized closed-trade drawdown. Candidate list is partly overlapping (several trend-following variants are highly correlated), so effective independent trials < 176 and effective candidates < 21.
- tv_dca_rsi_martingale (ladder, DCA) dominates raw returns and shows null pctl 98-100 under V2 yet loses to V0, i.e. the shifted labels are even worse for it; this is not an improvement.

## Deviations / skipped
- 15m rows dropped (3 incl. btc-max10-nyse-close): no 15m long history for BNB/XRP. 4h candidates use 4h resampled from long 1h (no 4h long files).
- Candidates: 21 (top-20 TRAIN rows excluding 15m, union 5 finalists minus max10); list in `results/candidates.csv`. Count of trials: V1 per (K, pool) only (ALL, FINALISTS), not per candidate.
- Trade-tag instead of re-simulation (above). K=7 ambiguity adds an ADX 25 +/- 2 band (stated in PREREG).
- V3 exhaustive refinement uses 5,000 random per-symbol shift draws (not enumeration); refinement ran only for rows passing every other gate (2 rows).
- Nothing was committed. `common/ plugins/ results/ verify*/` untouched.
