# R3 Coin Order-Block Search Design

## Decision

R3-coin is registered and implemented as a 48-configuration, TRAIN-only search. The re-registration keeps earlier trial rows intact and adds 48 attempts to cumulative `N_train`; each new attempt receives a fresh unique ID. No real-data run was performed and no real TEST data was read.

## Why this round exists

The supplied R2 summary reports 72 configurations, all `unscorable`, because five symbols had unresolved funding mark prices and three symbols had no TRAIN bars. Four of 72 had positive expectancy. The strongest reported cell was 4h long displacement, R=2.0, 48-bar deadline: +28 bp expectancy, PF 1.10, 169 trades. These figures motivate the hypothesis only; they are not independently re-created or used as a pass threshold.

## Registered search

The fixed grid is 3 OB definitions × 4 prior-complete-day trend filters × 4 UTC signal sessions = 48 attempts. Definitions are displacement, BOS-origin, and volume-confirmed displacement. Trend filters are none, prior completed UTC daily close above SMA20, above SMA50, and SMA20 above SMA50. Session filters are none, Asia (00:00–07:59 UTC), Europe (08:00–15:59 UTC), and US (16:00–23:59 UTC), classified by the signal 4h bar open. All configurations are 4h long, R=2.0, retest deadline 48 bars.

The rule drops a symbol from every R3 configuration when it has no complete TRAIN bars, any absent, non-finite, or non-positive funding mark, or a funding coverage gap. Exclusion reason and symbols are stored in each trial metric. At least 25 kept symbols are required; otherwise the trial is `unscorable`. The full pre-exclusion TRAIN input is fingerprinted. The re-registration and trial-ID rule are fixed in `PREREG.md`, sections “R3-coin addendum” and “R3-coin 재등록 보충 규칙”.

## Exact future run command

Exact command (from any directory):

```sh
cd /Users/user/CODE/Coin_Trade/scratchpad/strategy_bt/orderblock_loop && /Users/user/CODE/trading_data/cache/orderblock/venv/bin/python search_crypto_r3.py --shard 0/1
```

The command acquires the existing shared heavy-task lock and appends 48 `R3-coin` rows with new unique IDs to `TRAIN_TRIALS.csv`; earlier rows remain counted. Run only when the registered resource and single-heavy-task gates are satisfied. This report does not assert that those gates are currently satisfied.

## Verification performed for this design

The specified venv passed the complete loop suite: 153 tests, 0 failures. The separate red-team suite passed 24 tests, 0 failures. Synthetic R3 tests cover the 48 unique configurations, missing mark/coverage/no-bar exclusions, the 25-symbol floor, use of prior completed UTC days for trend filters, UTC session classification, and fresh trial IDs with ledger metadata.

No real-data search, TEST access, candidate freeze, or commit was performed.
