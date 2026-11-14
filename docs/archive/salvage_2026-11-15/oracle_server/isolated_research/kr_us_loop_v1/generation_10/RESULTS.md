# Generation 10 result — NR7 close-confirmed breakout on SPY

## Decision

**Reject this fixed rule for the stated objective.** The run is a completed exploratory test, not a finding that profitable systematic strategies do not exist. This rule materially lagged SPY buy-and-hold in all three reported windows.

## Frozen method and verification

- Preregistration: [`PREREG.md`](PREREG.md), frozen in [`FREEZE.md`](FREEZE.md); SHA-256 `0e0869c8093797cc611aee0597a90818742f2d5da0239d977ed76c0ab9ca6047`.
- Independent read-only review: GO before data execution; no blocking simulation issue identified.
- Tests: 9/9 passed before execution; compileall passed.
- Source rule: `trading/app/new_strategy_screening.py:181-184`.
- Execution: close-confirmed signal, next observed open entry, exit after ten full open-to-open intervals, one position max, 10 bp per side.
- Data: local SPY parquet, 8,498 rows, 1993-01-29–2026-11-02. Raw OHLC integrity and adjusted-OHLC integrity gates passed. PnL uses adjusted-open; trigger uses raw vendor OHLC. Vendor adjustment and exchange-calendar provenance are not independently validated.
- Attempt ID: `GEN10-20261106T122721-77015-US-SPY_NR7_CLOSE_BREAK_H10`.
- Run artifacts: `manifest_GEN10-20261106T122721-77015.json`, `attempts_GEN10-20261106T122721-77015.jsonl`, and `equity_curves_GEN10-20261106T122721-77015.csv.gz`.

## Results (net, descriptive)

| Window | NR7 CAGR | NR7 Sharpe | NR7 within-window MDD | SPY buy-and-hold CAGR | SPY Sharpe | SPY within-window MDD |
|---|---:|---:|---:|---:|---:|---:|
| Full, 1993-02-01–2026-11-02 | -1.76% | -0.108 | -70.62% | 10.77% | 0.648 | -55.42% |
| 2001-01-02–2016-12-30 | -5.28% | -0.401 | -64.19% | 5.29% | 0.362 | -55.42% |
| 2017-01-03–2026-11-02 (previously inspected) | 0.71% | 0.122 | -27.96% | 14.97% | 0.893 | -32.05% |

The 2017+ drawdown was smaller, but return and risk-adjusted return were far worse; that does not rescue the rule. Each MDD is recalculated from a fresh baseline within the displayed window. Window metrics are slices of continuous portfolio return streams, not separate portfolios restarted at each boundary.

## Activity and limitations

- 527 signals; 350 trades; 177 overlap-suppressed; 0 terminal-censored.
- The source family offered 5/10/20-session exits; only the preselected 10-session variant was run. This is a research degree of freedom, and the rule is correlated with prior breakout experiments.
- No DSR/BH significance claim: cumulative global trial inventory is unresolved, no untouched OOS period exists in this historical snapshot, and this candidate overlaps prior work.
- No tuning or second attempt was made after seeing results.
