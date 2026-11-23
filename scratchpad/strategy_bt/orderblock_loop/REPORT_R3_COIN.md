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
