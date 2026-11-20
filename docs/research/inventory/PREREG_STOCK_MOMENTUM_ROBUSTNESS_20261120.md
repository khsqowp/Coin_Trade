# Preregistration: robustness diagnostics for stock momentum v2

Frozen 2026-11-20 before executing any robustness calculations. This is a
post-exposure diagnostic of the already inspected 91-symbol current-survivor
cache. It cannot create an untouched OOS or promote a strategy.

## Scope

- Inputs: exactly the 91-symbol-per-market cache and expected common panels in
  `PREREG_STOCK_COMMON_MOMENTUM_EXPLORATORY_20261120_v2.md`; exclude only KR
  `114800` and US `SH`.
- Baselines under examination: KR monthly 60-session top-10 (with/without
  SMA200); US daily and monthly 126-session top-10 (with/without SMA200), each
  under the already frozen base and stress costs.
- Primary gates are unchanged: net CAGR >=20%, MDD <=30%, Sharpe >=1.0, and
  >=200 independent completed OOS round trips under both cost scenarios.
- The v2 run already misses the MDD gate in every momentum cell. This work is
  diagnostic and not a winner-selection exercise.

## Fixed diagnostics

1. **Parameter neighborhood:** rerun all fixed market/cadence/gate variants at
   lookbacks nearest `0.8x`, `1.0x`, and `1.2x` of the v2 lookback: KR
   `{48,60,72}`; US `{101,126,151}`. Run base and stress costs. No other
   parameters, ticker exclusions, or variants may be added after seeing output.
2. **Walk-forward selection:** use a rolling 504-session training window and
   the next six calendar months as test; align each test start to the first
   observed session of a calendar month. Advance subsequent test starts by six
   calendar months so test windows do not overlap. At each fold, choose the candidate
   with the highest training Sharpe among the fixed lookback neighborhood and
   SMA200 on/off, separately for each market and cadence. Tie-break by higher
   training CAGR, then smaller lookback, then SMA200 off. Evaluate the selected
   fixed rule on the next test window from fresh cash, using both cost cases.
   Do not carry holdings between folds. Report every fold, including negative
   and incomplete folds. These are pseudo-OOS slices only: the source history
   and strategy family have already been inspected.
3. **Path uncertainty:** for every v2 momentum portfolio/cost cell, perform
   1,000 random permutations of its daily portfolio return sequence and 1,000
   block-bootstrap paths with fixed 20-session contiguous blocks. Use seed
   `20261120`; each path has the original observation count. Report median and
   95th-percentile MDD, terminal return, and terminal CAGR. This is daily NAV
   path resampling, not independent trade reordering: the strategy's positions
   overlap and the ledger does not encode a separable portfolio allocation
   for each closed trade. Do not describe the permutation as a trade-level
   Monte Carlo.

## Acceptance and stopping

- No result can pass validation from this exposed cache. Diagnostics only
  answer parameter fragility, time-slice instability, and order/clustering
  sensitivity.
- Publish all fixed cells, folds, random seeds, code/prereg/input hashes, and
  the exact command. Do not tune after output.
- If a panel fingerprint, date boundary, accounting identity, or reproducible
  output check fails, stop and record the failure rather than repairing the
  frozen run in place.
- This diagnostic does not authorize a Phase 9 strategy mix: portfolio
  combination still requires individually validated core candidates, of
  which the current set has none.
