# Generation 11 A1 — SPY volatility-expansion / momentum transfer

## Decision

**Reject this fixed rule for the stated objective.** On this local snapshot, it lost money in the full sample and both displayed subperiods, while SPY buy-and-hold returned more. This is a result about one preregistered rule, not evidence that profitable automated strategies do not exist.

## Execution and audit

- Run ID: `GEN11A1-20261106-SPY_VOL_BURST_MOM5_H5`; status: `COMPLETED_EXPLORATORY`.
- Independent reviewer approved the corrected A1 specification before execution. A1 only relaxes computed adjusted-OHLC ordering for relative roundoff up to `1e-12`; raw OHLC checks remain strict.
- Freeze hashes matched immediately before execution. The runner records `STARTED` before data loading and `COMPLETED_EXPLORATORY` after calculation.
- Tests: 7/7 passed; `compileall` passed.
- Post-run arithmetic check independently recomputed CAGR, Sharpe, and within-window MDD for both series in all three windows; all six metric triples matched the saved JSON, and all 8,497 curve rows were finite.
- Data: 8,498 SPY rows, 1993-01-29–2026-11-02. SHA-256 is pinned in `FREEZE_A1.json` and the run manifest.
- Fixed signal: `ATR20/close` above the prior 100-session linear 80th percentile and positive 5-session return; next-session adjusted-open entry, five open-to-open intervals, 10bp per side. One position maximum.
- Activity: 939 signals, 251 completed trades, 688 suppressed while a position was active, no terminal-censored signals; invested for 14.77% of curve intervals.

## Net descriptive metrics

| Window | Strategy CAGR | Strategy Sharpe | Strategy MDD | SPY CAGR | SPY Sharpe | SPY MDD |
|---|---:|---:|---:|---:|---:|---:|
| Full, 1993-02-01–2026-11-02 | -0.88% | -0.075 | -48.15% | 10.77% | 0.648 | -55.42% |
| 2001-01-02–2016-12-30 | -1.57% | -0.178 | -30.26% | 5.29% | 0.362 | -55.42% |
| 2017-01-03–2026-11-02 (contaminated) | -2.14% | -0.233 | -30.44% | 14.97% | 0.893 | -32.05% |

Drawdowns are recomputed from a fresh baseline within each displayed window. All strategy and benchmark metrics use the same open-to-open curve intervals and specified costs.

## Limits and interpretation

- The 2017+ segment and full history are not untouched holdouts; both have prior exposure in this research workspace. These values are descriptive, not out-of-sample confirmation.
- This transfers a crypto-screening event signal to SPY and adds a fixed five-interval event holding rule. It is related to volatility-expansion and momentum families; it is not an independent-family discovery.
- The SPY data vendor's corporate-action adjustment and exchange-session completeness are not independently established. No cost stress, random-portfolio null, global DSR/PSR, or multiplicity correction is claimed.
- No parameter retuning or repeat run was performed after seeing the results.

## Artifacts

- Original frozen preregistration: `PREREG.md`; superseding tolerance amendment: `ADDENDUM_A1.md`.
- Executed freeze: `FREEZE_A1.json`; original unexecuted freeze preserved as `FREEZE.json`.
- Runner/tests: `run_gen11.py`, `test_gen11.py`.
- Machine-readable metrics: `results_GEN11A1-20261106-SPY_VOL_BURST_MOM5_H5.json`.
- Attempt ledger: `attempts_GEN11A1-20261106-SPY_VOL_BURST_MOM5_H5.jsonl`.
- Manifest: `manifest_GEN11A1-20261106-SPY_VOL_BURST_MOM5_H5.json`.
- Daily curve: `curve_GEN11A1-20261106-SPY_VOL_BURST_MOM5_H5.csv.gz`.
