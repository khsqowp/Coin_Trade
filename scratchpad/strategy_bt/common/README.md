# Shared strategy backtest harness

`common` is a strategy-independent research harness for archived strategy plugins. Run commands from `trading/scratchpad/strategy_bt` with the repository's `.venv/bin/python`; the runner never downloads data and reads only existing `{SYMBOL}_{tf}.parquet` files.

## Plugin contract

A plugin is a Python module found recursively under `--plugins-dir`. It must expose `SPEC_ID`, `PARAMS` (default parameter mapping), `PARAM_GRID`, `TIMEFRAMES`, and `signals(df, **params)`. `SIDES` is optional and defaults to `"both"`; valid values are `long`, `short`, and `both`. `signals` returns a DataFrame aligned to `df` with boolean `long_entry`, `short_entry`, `long_exit`, and `short_exit`. A signal is known after that bar's close; entries execute at the next bar's open. Optional per-bar management fields are `stop_pct` (fraction, e.g. `.05`), `atr_stop` (absolute price distance, used when `stop_pct` is absent), `tp_pct` (fraction), and `max_hold` (bars). Optional plugin `PARAMS` may include ladder fields `n_adds`, `add_spacing_pct`, and `add_size_mult` (spacing is in percent).

`DEVIATIONS` must be a non-empty list when the implementation changes or assumes anything. `IMPLEMENTED_FIELDS` may list spec keys from `entry_long`, `entry_short`, `exit`, `stop_loss`, `take_profit`, `filters`, `position_sizing`, and `timeframes`. The compliance audit reports present and unimplemented fields and warns on incomplete mechanical specs with no deviations. The audit is bookkeeping, not proof that a plugin faithfully implements a natural-language rule.

`PARAM_GRID` is a mapping with at most three axes and at most four values per axis. The harness rejects larger grids. It computes the Cartesian product on top of `PARAMS` defaults. Param selection maximizes pooled TRAIN percent-sum return across available symbols. A strategy with fewer than 30 pooled TRAIN trades is `INELIGIBLE`.

## Execution and protocol

The simulator charges 0.04% fees and 0.02% slippage on each fill, enters at next-bar open, holds at most one position per symbol (unless plugin ladder parameters explicitly add), checks the stop before target on each OHLC bar, fills gaps through a stop at that bar's open, and fills exit signals on the next open through the signal contract. Remaining positions are marked at the final close. Trade `pct` is net P&L divided by fixed 10,000 capital, and total return is the sum of per-trade percentages; it is not compounded.

Each series is split chronologically 60/40. The selected parameter set is frozen for TEST. Reported pooled figures are percent-sum return, profit factor, win rate, maximum drawdown, and trade count. The seeded 200-repetition random-entry benchmark matches the observed TEST trade count and long/short mix as far as non-overlapping candidate entries permit, then applies identical fee, slippage, stop, target, and time-limit rules. It reports the fraction of null returns at or below observed TEST return. When finite series length prevents the requested count, the null can produce fewer trades; this limitation is intentionally not filled with synthetic outcomes.

Plateau status is `NA` for a one-point grid. Otherwise, immediate grid neighbors are those differing in exactly one axis. `ROBUST` requires at least one neighbor and at least 70% of observed neighbors to have positive TRAIN return and at least 50% of the winner's return; otherwise it is `FRAGILE`. This is a compact local stability test, not a confidence interval.

The mechanical raw verdict is PASS only with TEST null percentile >=95, `ROBUST` plateau, >=30 TEST trades, positive TEST return, and at least 3 of 5 major symbols positive. Other outcomes are FAIL with reason codes. The adjusted gate uses the requested threshold `100*(1-(0.05/N))`, the Bonferroni per-test alpha `0.05/N` expressed as a null percentile; exact Sidak uses `100*(1-(1-0.05)**(1/N))` as the required percentile. The ledger records family candidate counts across strategy × timeframe × parameter points, slice strategy count, thresholds, and timestamp under an advisory POSIX file lock. Since repeated trades are dependent and multiple strategies/timeframes may also be dependent, neither null percentile nor Sidak/Bonferroni resolves all selection bias.

## CLI

```sh
cd trading/scratchpad/strategy_bt
../bb_stoch_stc/.venv/bin/python -m common.run \
  --slice-file slice_0.txt --plugins-dir plugins --out results/run_0 \
  --workers 1 --timeout 300 --data-dir ../bb_stoch_stc/data \
  --ledger results/ledger.csv
```

`--tf-limit 4h 1d` restricts timeframes. Missing plugins produce `NO_PLUGIN`; exceptions produce `ERROR` with traceback tail; a hard subprocess timeout produces `TIMEOUT`. Completed strategy IDs in `summary.csv` are skipped on restart; `--force` reruns them. `--workers` limits concurrent strategy subprocesses; each strategy still has its own hard timeout. Outputs are `summary.csv`, `REPORT.md`, and append-only `progress.log`. Secondary symbols ADA, DOGE, LINK, LTC use frozen chosen params and are reported separately when cache exists.

## Writing plugins and caveats

Copy `examples/sma_cross.py` as a starting point, then set the exact archived `SPEC_ID`, explain assumptions in `DEVIATIONS`, list implemented fields, keep every signal causal, and return aligned boolean columns. `check_no_lookahead(plugin, df)` compares full-series outputs with recomputation on representative prefixes; the runner invokes this check on available primary symbol data before evaluation. It catches many accidental future dependencies but cannot prove causality for every possible input or transform.

Bars are assumed complete and ordered. No resampling, missing-bar repair, funding, borrow costs, liquidation, partial fills, exchange filters, portfolio capital sharing, or correlated-position constraints are modeled. Ladder behavior is intentionally simple and fixed-notional. Random-entry null outcomes are a diagnostic benchmark, not a formal hypothesis test. The default primary universe is five liquid majors; missing cached parquet files are silently omitted and the actual symbol count is reported, so fewer than five cannot satisfy the three-of-five interpretation reliably. Archived strategy semantics may be underspecified; verdicts should be treated as comparable screening evidence, not proof of a tradable edge.
