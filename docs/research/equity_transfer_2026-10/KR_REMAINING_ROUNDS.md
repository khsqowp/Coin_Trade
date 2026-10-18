# KR adaptation status: crypto Rounds 7, 8, 9, 15

Status: partial; this document is scoped to KR equity only. Panel: local KIS daily data, 64 symbols, 2,154 sessions, 2018-01-02 through 2026-10-15. KR cost assumptions and next-open fills are taken from `app/rs_kr_data.py` and `app/rs_kr_engine.py` (commission 0.015% each side, sell tax 0.18%, per-symbol one-way slippage 0.05%/0.10%).

## Round 7

`app/rs_equity_round7_kr.py` adapts the fixed crypto volume-spike champion only as a labeled proxy: volume at least 3x its trailing 20-session mean and absolute daily close return below 5%, with eight event slots and a 20-session scheduled exit. It runs 500 incidence-matched random controls, symbol/year leave-outs, two future-price mutation checks, and two truncated-prefix signal/NAV replays through the KR next-open event engine. These are not the exact crypto champion rules or ledger. Prefix NAV checks retain the panel's precomputed slippage vector, so they do not test point-in-time slippage reclassification.

The requested 20-trade block bootstrap x1,000 is not computed: the shared KR event engine returns only aggregate trade metrics and does not expose per-trade returns or a trace ledger. No bootstrap CI or vote is fabricated. The exact omissions and raw results are recorded in `full_runs/round7_kr.json`.

## Round 8

The exact ten source-selected representatives and every output of the original `variants()` generator are inventoried in `full_runs/round8_9_15_kr.json`. The variant function is extracted from source AST so that the environment's `pandas_ta`/Numba cache import failure does not alter the declared grid. No variant is counted as evaluated: family signals, BTC breaker/resume rules, portfolio controls, and engine semantics are not one-to-one KR equivalents. Consequently no three-axis dominator is asserted and no conditional robustness run is represented as complete.

## Round 9

The original fixed TOP_K12 configuration, all eight source period cells, and stated thresholds are preserved in the inventory. KR executions are not claimed. In particular, crypto BTC resume logic and crypto-period benchmark comparison cannot be silently replaced by a different KR state rule while calling it reproduction.

## Round 15

The inventory preserves source multiplicity counts: R12 127, R13 81, R14 31, 239 unique hypotheses; the five stated Bonferroni/rank-1 BH checks and 21 three-axis candidates are recorded. Aggregate files contain no raw 300-control series or per-hypothesis matched null inputs. Therefore no KR inferential p-value can be recalculated from these inputs. Crypto p=1/301 is not reported as KR evidence; full BH step-up is not claimed.

## Verification and exact scope

The Round7 runner's random controls and leave-outs are actual KR engine runs; Round8/9/15 are source inventories with zero KR strategy evaluations. This is not exhaustive coverage of any crypto search beyond the explicitly inventoried representatives/configurations and source-count fields. Raw artifacts are the two `round*_kr.json` files in `full_runs/`. Files remain uncommitted; parent integration is required.
