# Generation 11 result — one-month sector-ETF reversal

## Decision

**Reject this fixed candidate for the stated objective.** After costs, it underperformed SPY buy-and-hold on both CAGR and Sharpe in every preregistered descriptive window, and had deeper maximum drawdowns. This result is a failure of this one candidate to pass its gate. It is not evidence that profitable systematic strategies do not exist, and it does not prove the broader one-month reversal literature or other strategy rules are invalid.

## Frozen run and checks

- Run: `GEN11-20261106T124600-034`; attempt ID: `GEN11-20261106T124600-034-US_SECTOR_BOTTOM3_PREV_MONTH`.
- One market-performance run, no parameter variants or retest. Status: `COMPLETED_EXPLORATORY`.
- Freeze: [`FREEZE.md`](FREEZE.md), timestamp 2026-11-06T12:40:22Z.
- Frozen preregistration, runner, and test hashes matched before the run and after it. Independent root review approved the final code/rule. The pre-performance raw-data integrity gate passed.
- Unit tests: 8/8 passed after execution; compileall passed.
- Data: nine sector ETFs plus SPY; common range 1998-12-22–2026-11-02, 7,008 common open dates (7,007 open-to-open intervals); local non-atomic Yahoo-derived mirror only. The full data hashes are in the run manifest.
- The earlier failed preflight due solely to an unregistered derived adjusted-OHLC float-order test is preserved in [`attempts_preflight.jsonl`](attempts_preflight.jsonl). No signals or performance metrics were computed in that failed preflight.

## Net performance (descriptive; not untouched OOS)

| Window | Bottom-3 sector reversal CAGR | Sharpe | Maximum drawdown | SPY buy-and-hold CAGR | Sharpe | Maximum drawdown |
|---|---:|---:|---:|---:|---:|---:|
| Full, 1998-12-22–2026-11-02 | 5.64% | 0.361 | -61.67% | 8.70% | 0.537 | -55.42% |
| 2001–2016 | 4.33% | 0.299 | -61.67% | 5.29% | 0.362 | -55.42% |
| 2017–2026-11-02 (previously inspected) | 8.51% | 0.514 | -43.95% | 14.97% | 0.893 | -32.05% |

The simulated portfolio made 333 monthly target rebalances, recorded 450.018 total risky-weight absolute turnover units, and was terminally liquidated with 100% turnover. One target for the incomplete terminal holding month was censored. Cash earned zero. The above values are after the preregistered 10 bp per traded notional charges. These are continuous portfolio paths sliced into descriptive windows; the portfolios were not reset at window boundaries.

## Interpretation and limitations

The bottom-three prior-month sector return strategy lagged SPY by 3.06 percentage points CAGR and 0.176 Sharpe over the full sample. In the 2017+ already-inspected slice, it lagged by 6.46 percentage points CAGR and 0.379 Sharpe. Its drawdown was worse in all reported windows. It fails the preregistered gate; no tuning or alternate holding count/frequency was run.

This is an ETF-level heuristic inspired by one-month stock return-reversal research, not a faithful replication: Jegadeesh (1990) studies securities, not aggregate sector ETFs ([primary paper DOI](https://doi.org/10.1111/j.1540-6261.1990.tb05110.x)). It is correlated with previously tested weekly individual-stock reversal and sector rotation, not independent alpha evidence. The mirror is not a licensed point-in-time sector total-return database; fund data/provenance and corporate-action adjustments are not independently validated; the historical market has been inspected; the global trial count is incomplete. No p-value, DSR/PSR, multiple-testing significance, untouched-OOS, or deployability claim is made.

## Durable artifacts

- Rule: [`PREREG.md`](PREREG.md)
- Freeze: [`FREEZE.md`](FREEZE.md)
- Runner and tests: [`run_gen11.py`](run_gen11.py), [`test_gen11.py`](test_gen11.py)
- Completed attempt ledger: [`attempts_GEN11-20261106T124600-034.jsonl`](attempts_GEN11-20261106T124600-034.jsonl)
- Run manifest and full input fingerprints: [`manifest_GEN11-20261106T124600-034.json`](manifest_GEN11-20261106T124600-034.json)
- Daily net return curves: [`equity_curves_GEN11-20261106T124600-034.csv.gz`](equity_curves_GEN11-20261106T124600-034.csv.gz)
- Earlier preflight failure ledger: [`attempts_preflight.jsonl`](attempts_preflight.jsonl)
