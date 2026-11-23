# R3 Coin Order-Block Search Design

## Decision

R3-coin is registered and implemented as a 48-configuration, TRAIN-only search. The re-registration keeps earlier trial rows intact and adds 48 attempts to cumulative `N_train`; each new attempt receives a fresh unique ID. No real-data run was performed and no real TEST data was read.

## Why this round exists

The supplied R2 summary reports 72 configurations, all `unscorable`, because five symbols had unresolved funding mark prices and three symbols had no TRAIN bars. Four of 72 had positive expectancy. The strongest reported cell was 4h long displacement, R=2.0, 48-bar deadline: +28 bp expectancy, PF 1.10, 169 trades. These figures motivate the hypothesis only; they are not independently re-created or used as a pass threshold.

## Registered search

The fixed grid is 3 OB definitions × 4 prior-complete-day trend filters × 4 UTC signal sessions = 48 attempts. Definitions are displacement, BOS-origin, and volume-confirmed displacement. Trend filters are none, prior completed UTC daily close above SMA20, above SMA50, and SMA20 above SMA50. Session filters are none, Asia (00:00–07:59 UTC), Europe (08:00–15:59 UTC), and US (16:00–23:59 UTC), classified by the signal 4h bar open. All configurations are 4h long, R=2.0, retest deadline 48 bars.

Funding events are compared with each trade's actual holding interval. The 2026-11-23 censoring addendum in `PREREG.md` is the primary rule: a completed trade overlapping an unresolved mark or coverage sentinel is removed from performance statistics and counted in `censored_funding_trades` and `censored_fraction`. A trial is scorable only when the censored fraction is at most 0.35, at least 20 completed trades remain, and at least 25 symbols remain. Failures name the failed floor and its observed/required values. All trade and setup ID lists use `trial_ledger_compaction.compact_id_list` count/hash summaries. The scorer enforces internally that unscorable and censored IDs belong to the generated trade set.

Each setting also records a sensitivity run that removes every symbol with any unresolved funding mark or coverage gap. Its kept-symbol count, scored trade count, expectancy, profit factor, win rate, and drawdown are separate fields. This sensitivity run does not decide primary scorable status. Censoring depends only on funding-data availability and trade timing; changing trade P&L cannot change which IDs are censored. This is a fixed, non-adaptive rule.

## Exact future run command

Exact command (from any directory):

```sh
cd /Users/user/CODE/Coin_Trade/scratchpad/strategy_bt/orderblock_loop && /Users/user/CODE/trading_data/cache/orderblock/venv/bin/python search_crypto_r3.py --shard 0/1
```

This command was documented for the future TRAIN rerun; it was not run during this debugging task. When run, it uses the TRAIN-only loader and appends 48 `R3-coin` rows with new unique IDs to `TRAIN_TRIALS.csv`; earlier rows remain counted. Run only when the registered resource and single-heavy-task gates are satisfied. Current process status could not be checked because the sandbox denied `ps`.

## Verification performed for this design

The specified venv passed the full loop unittest suite: 163 tests, 0 failures. Regression coverage confirms that a symbol with a missing mark is retained when there is no overlapping held trade, becomes overlap-flagged when a generated trade intersects the missing mark, and that unscorable IDs are a subset of generated trade IDs even when their count exceeds the scored-trade count. Other R3 synthetic coverage includes the 48 unique configurations, the 25-symbol floor, prior completed UTC days, UTC session classification, and unique trial IDs.

## Funding-censor rule implementation (2026-11-23)

Before implementation, `PREREG.md` fixed the censoring cap, remaining-trade floor, symbol floor, P&L-independence rule, and the five-symbol exclusion sensitivity comparison. The code writes compact count/hash summaries for all trade/setup ID collections. Regression tests cover the unscorable-ID subset invariant, identical censor IDs under positive and negative synthetic P&L, and the exact 0.35, 20-trade, and 25-symbol thresholds. The full unittest suite passed with the designated venv: 201 tests, 0 failures. No real-data full run was performed and no TEST data was read.

Exact rerun command (documented, not executed):

```sh
cd /Users/user/CODE/Coin_Trade/scratchpad/strategy_bt/orderblock_loop && /Users/user/CODE/trading_data/cache/orderblock/venv/bin/python search_crypto_r3.py --shard 0/1
```

No full search or real-data rerun, TEST access, candidate freeze, or commit was performed. During cause tracing, one command's output included ledger metric JSON; the metrics were not analyzed or used to set this correction. The amendment was written before code changes. `ps` was denied, so the active-process state is unverified.

## Third R3-coin rerun funding diagnosis (2026-11-23)

Before reading the requested diagnostics, `PREREG.md` v2.2 fixed the rule: a finite positive price supplied by the already registered preceding-1m-close fallback is scorable; only an unresolved mark/close or coverage-gap sentinel overlapping exposure is a missing-price unscorable event. Existing entry/exit ordering uncertainty remains unscorable.

The last 48 `R3-coin` rows were read from `TRAIN_TRIALS.csv` using `csv.field_size_limit(sys.maxsize)`. All 48 have metric `status=unscorable`; `funding_close_fallbacks=354` on every row. The detail field says funding trades are unscorable and five symbols retain missing funding prices after close fallback. The unscorable counts range from 65 to 1,811. Every row's `unscorable_funding_trade_ids` is a subset of its `trade_ids`.

Root cause: 354 counts fallback-priced input settlements across the entire loaded barsets, not fallback events overlapping trades and not an error count. `data_access` stores a successful close proxy as a finite positive `FundingEvent.mark_price` and sets `used_candle_close_fallback=True`; `crypto.simulate_trade` charges that price in the registered funding formula. `search_crypto._sentinel_reason` excludes such priced events from missing-mark sentinels. The five remaining unresolved-price symbols, not the 354 successful proxies, explain the unscorable rows when those missing-price sentinels overlap trades. Thus 32 kept symbols do not cure missing prices on overlapping trades. The third rerun rows are diagnostic only and remain unchanged.

Code makes the usable-price predicate explicit for sentinel and symbol diagnostics. Regression tests cover fallback-priced funding scoring and daily-PnL reconciliation, fallback exclusion from missing-mark sentinel classification, and the existing generated-trade ID subset invariant. The specified full loop suite passed: 167 tests, 0 failures.

Exact registered rerun command (not executed in this debugging task):

```sh
cd /Users/user/CODE/Coin_Trade/scratchpad/strategy_bt/orderblock_loop && /Users/user/CODE/trading_data/cache/orderblock/venv/bin/python search_crypto_r3.py --shard 0/1
```

No real-data full run, TEST read, process termination, Ochestration access, or commit was performed. Process state could not be independently checked because sandbox `ps` access was denied.

## Fourth R3-coin funding status diagnosis (2026-11-23)

Scope: static tracing of `PREREG.md`, `search_crypto.py`, `search_crypto_r3.py`, `crypto.py`, and `data_access.py`; one synthetic regression test added. No TRAIN/TEST data or `TRAIN_TRIALS.csv` was read or changed. No real-data command was run.

The reported `593` is not explained by missing-mark/coverage censoring. The scorer only puts a completed trade into `censored_funding_trades` when `_overlapping_sentinel_timestamps()` finds an unresolved-price or coverage-gap event during the actual holding interval. It puts a trade in `unscorable_funding_trades` when `simulate_trade()` returns a trade with `net_return is None` and that unresolved-sentinel overlap list is empty, or when daily P&L validation fails without such an overlap. `funding_sentinels` only audits unresolved mark/coverage events, so valid-price events with unknowable within-candle ordering do not appear there.

The registered rules support this separation. The R3-coin censor addendum applies to unresolved mark/coverage sentinels. PREREG v2.2 explicitly keeps price-independent settlement ordering uncertainty (including entry/exit candle ambiguity) fail-closed and unscorable. The existing simulator uses `fail_closed` by default; for time exits, an event exactly at the exit timestamp has unknown ordering, and for stop/target exits events in the exit candle are also unknown. Consequently a valid mark can yield an unscorable trade while `censored_funding_trades=0`, `censored_fraction=0.0`, and all missing-price sentinel overlap counts are zero. This is consistent with the registered rules; changing those trades to censored or adverse-only would change the rule and is not authorized by the addendum.

The `593` count itself cannot be decomposed into exact event timestamps from static code and the user-provided summary alone. The scorer has a second unscorable path for failed daily-P&L reconciliation, so exact attribution of every row would require per-trade TRAIN diagnostics. No such data was read here. A synthetic regression now locks the specific valid-mark/unknown-order case: it must remain unscorable, must not count as sentinel-censored, and must have no missing-price sentinel audit row.

Full unittest command (to verify the code-only change; no search runner is invoked):

```sh
cd /Users/user/CODE/Coin_Trade/scratchpad/strategy_bt/orderblock_loop && /Users/user/CODE/trading_data/cache/orderblock/venv/bin/python -m unittest discover -s tests
```

Observed verification: `Ran 212 tests in 1.850s`, `OK` (exit code 0). The exact future R3-coin rerun command remains the one documented above and was not run. Existing trial rows remain untouched.

## R3-coin adverse-only funding-order rerun addendum (2026-11-23)

The preceding diagnostic identified unknown settlement ordering as the cause of a large share of the R3-coin unscorable trades. This code-only amendment registers the same `funding_order_policy=adverse_only` already preregistered for R4-coin. With valid mark and rate, ambiguous funding is charged only when adverse to the position; favorable ambiguous cashflow is zero. This is a conservative convention for consistent cost treatment across the two coin rounds, selected from the supplied diagnostic and the existing R4 preregistration, without viewing R3 performance results.

The earlier R3 rows remain diagnostic and unchanged. The new 48-configuration R3 rerun is a separate set of trials with fresh IDs and adds 48 to cumulative `N_train`. Missing mark and coverage-gap overlap censoring remains unchanged; no missing event is imputed or scored as zero. No R4 behavior, thresholds, grid, or G criteria are changed.

Exact rerun command (documented only; not executed):

```sh
cd /Users/user/CODE/Coin_Trade/scratchpad/strategy_bt/orderblock_loop && /Users/user/CODE/trading_data/cache/orderblock/venv/bin/python search_crypto_r3.py --shard 0/1
```

Verification scope: synthetic regression tests and the full unittest suite only. No real-data run, TEST read, `TRAIN_TRIALS.csv` access, process inspection/termination, or commit was performed.

Post-change verification result: the focused R3 suite passed (`Ran 11 tests`, `OK`) and the crypto simulator suite passed (`Ran 35 tests`, `OK`). Full `unittest discover -s tests` ran 219 tests and failed with 1 failure and 2 errors, all reported in `test_search_crypto_r6.py`: `test_atr_bin_uses_only_preceding_history_and_median_ties_are_low` failed, while `test_minimum_symbol_floor_is_30` and `test_symbol_floor_passes_at_30_without_signals` errored with `KeyError: 'S0'`. These failures are outside the R3/R4 files changed for this amendment. The full-suite requirement therefore remains unmet; no unrelated R6 code or tests were changed.
