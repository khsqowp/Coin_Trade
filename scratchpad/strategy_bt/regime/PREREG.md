# PREREG: regime-switching / regime-filter study (written BEFORE any result)

Date: 2026-11-20. Nothing here is tuned. All thresholds are round numbers fixed now.
Python: `../bb_stoch_stc/.venv/bin/python`. Do not modify `common/ plugins/ results/ verify*/`.

## Data and cost model
- Long history: `data_long/{BTC,ETH,BNB,XRP}USDT_{1d,1h}.parquet` (2017+; BNB from 2017-11, XRP from 2018-05).
- 4h strategies: 4h bars are resampled from long 1h (UTC-anchored, only complete 4-bar groups). DEVIATION (no 4h long file).
- 15m candidates (btc-max10-nyse-close and any other 15m row): SKIPPED (15m long history exists only for BTC/ETH, not BNB/XRP).
- Simulator: `common.engine.simulate` unchanged (fee 0.04%/side, slippage 0.02%/fill, next-bar-open fills, fixed 10,000 capital / 1,000 notional, pct = net/capital, returns are percent-SUMS, not compounded).
- Plugins: `plugins/slice_*/`, FROZEN params = the `params` JSON in `results/slice_*/summary.csv` (no re-tuning, no grid).
- Each candidate is run ONCE per symbol on the full long history (V0 trade list). Trade identity: (candidate, symbol, entry time, exit time, side, pct).

## Regime definition (causal)
BTC daily bars. For daily bar d (index = bar open date), with c = close:
- SMA200 = mean(c[d-199..d]); dist = c/SMA200 - 1; slope = SMA200[d]/SMA200[d-20] - 1.
- Trend score S = dist/0.10 + slope/0.05.
- ADX14 = Wilder ADX (period 14) on daily OHLC.
- Label L[d] is computed from bar d and is known at the close of d. A timestamp t (e.g. a trade's entry fill time) uses label L[floor_day(t) - 1 day], i.e. only data up to the prior daily close. Warm-up (first ~220 days) = no label (trades there are excluded from filtered variants, and from V0 comparisons all variants use the same TEST window so V0 is also evaluated only where labels exist).
- Ordered buckets (label 0 = most bearish). S edges:
  - K=2: edges [0] -> {down, up}. Up set = {1}.
  - K=3: edges [-1, +1] -> {down, side, up}. Up = {2}, Down = {0}.
  - K=5: edges [-3,-1,+1,+3] -> {strong down, down, side, up, strong up}. Up = {3,4}, Down = {0,1}.
  - K=7: K=5 buckets, with "down" and "up" each split by ADX14 >= 25 (strong trend) vs < 25: order = strong down, down(ADX>=25), down(ADX<25), side, up(ADX<25), up(ADX>=25), strong up. Up = {4,5,6}, Down = {0,1,2}.
  - Bucket rule: label = number of edges <= S (S exactly on an edge goes to the higher bucket).
- Ambiguous flag (fixed): ambiguous if min over the K scheme's edges of |S - edge| < 0.25 (S-units), OR ADX14 < 15. (K=7 additionally uses the ADX=25 split boundary: ambiguous if bucket is a split bucket and |ADX-25| < 2.)
- Applied market-wide: the BTC label is used for all four symbols.

## Candidates
- Finalists: jesse_simple_bollinger (1h), btc-macd-15-41-12 (1d), turtle-system-2 (1d), btc-bollinger-37-16 (1d), btc-roc-36-9pct (1d). btc-max10-nyse-close skipped (15m).
- Plus the top 20 implemented rows (status DONE, plugin exists) by TRAIN return (`train_return` in results/slice_*/summary.csv, descending), union with finalists, 15m rows dropped. Rows are (strategy_id, timeframe). The resulting list is written to `results/candidates.csv`.

## TEST window and walk-forward
- Evaluation window (TEST) for ALL variants incl. V0 = trades whose entry fill is >= 2018-07-01 and where a label exists, through the end of data. The first walk-forward training span is therefore only ~10 months (2018-03 labels onward), so early V1 periods are mostly cash by the min-trades rule; this is a known limitation, accepted.
- "2018 window" = entries 2018-07-01..2018-12-31 (H2 2018, not full-year, because of regime warm-up). "2022 window" = entries in calendar 2022.
- Max drawdown: peak-to-trough of cumulative pct (points of capital) of the pooled trades ordered by exit time (realized, closed-trade basis).
- Metrics pooled over the 4 symbols per (variant, K, candidate).

## Variants
- V0: unfiltered candidate, trades in TEST window.
- V1 switch (per K; pool = ALL candidates and pool = FINALISTS, two separate trials per K). Walk-forward, expanding window, retrain every 6 months at 2018-07-01, 2019-01-01, ... For each retrain date T and each regime r: using ONLY trades with exit < T and entry regime r (pooled over symbols), choose the candidate with the highest summed pct provided it has >= 15 such trades AND summed pct > 0; else cash for regime r. For trades entering in [T, T+6mo) with entry regime r, keep a trade iff its candidate is the one chosen for r. (Trade-tag evaluation: V0 trade lists are filtered, not re-simulated.) V1 baseline "V0" for the pool = mean over pool candidates of their unfiltered TEST return (same window); the best single candidate V0 is also reported for information.
- V2 ambiguous-cash (per candidate, per K): keep a V0 trade iff its entry-time label is non-ambiguous AND (side long and label in Up set) or (side short and label in Down set). (Trade-tag evaluation; gating entries by tagging, not by re-simulating position slots - DEVIATION from literal "cash otherwise", chosen so observed and null use identical machinery.)
- V3 symbol exclusion (per candidate, per K): per symbol, compute its own daily S and ADX (same definitions on that symbol's daily bars), trailing 180-day mean of S and of ADX (up to prior daily close); symbol is ambiguous on day t if min over K edges |meanS - edge| < 0.25 or mean ADX < 15. Drop trades of that symbol with entry on an ambiguous day. Used regimes: none (episode condition N/A for V3 -> treated as satisfied).
- K in {2,3,5,7} for all variants.

## Trials
N_trials = every (variant in {V1,V2,V3}, K, candidate) evaluated; V1 counts one trial per (K, pool). V0 is not a trial.

## Null (label shuffle preserving run lengths)
- Circular shift of the valid daily label series (labels and ambiguous flags shifted jointly; for V3 each symbol's ambiguity series shifted by an independent random offset), shift drawn uniformly from [30, n-30]. 1000 draws, seed fixed (1729). The variant's TEST return is recomputed under shifted labels (for V1 the entire walk-forward including selection is redone). Null percentile = fraction of null returns <= observed return, times 100. Empirical p = (1 + #null >= obs)/(1 + draws).
- Candidates passing every other gate may be re-drawn using ALL possible distinct shifts (exhaustive) to reach the finest attainable p-resolution.
- Bonferroni threshold: p <= 0.05/N_trials. If the finest attainable empirical p (1/(#distinct shifts+1)) is larger than that threshold, the adjusted gate is UNREACHABLE and counted as FAIL (a normal-approximation z-based p is reported informationally only).

## Episodes
For each K and regime, number of contiguous runs of that label in the daily label series (full sample and in TEST window). Regimes with < 3 episodes (TEST window) are flagged unevaluable.

## PASS RULE (all must hold, per variant/K/candidate)
1. Variant TEST return > V0 TEST return on the same data (V1: > pool-mean V0).
2. Null percentile >= 95.
3. Bonferroni-adjusted pass: empirical p <= 0.05/N_trials.
4. Loss reduced in both windows: for each of 2018H2 and 2022: if V0 window return >= 0 then variant window return >= 0, else variant window return > V0 window return.
5. >= 3 episodes (in TEST window) for every regime used (V2: the Up regimes, plus Down regimes if the candidate has shorts; V1: every regime in which a candidate was ever chosen; V3: N/A).
Anything not passing all five is FAIL. No post-hoc changes to thresholds, K schemes, or candidate lists; deviations are listed in REPORT.md.
