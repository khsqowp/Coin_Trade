# USD-M 1h setup M2 fixed re-evaluation

Run date: 2026-11-20. This is one fixed historical re-evaluation of the 38
already-implemented chart setups from `chart_predictor.setups.SETUPS`; it is not
a search over every possible crypto strategy and is not a live-trading result.

## Frozen design and data

- Preregistration: [`PREREG_USDM_1H_SETUP_M2_20261120.md`](PREREG_USDM_1H_SETUP_M2_20261120.md)
- Run artifacts: [`runs/usdm_1h_setup_m2_20261120/`](runs/usdm_1h_setup_m2_20261120/)
- 36 symbols, 27,969 hourly bars per symbol, period 2023-03-23 15:00 UTC to
  2026-06-01 exclusive.
- 38 fixed setups × H=10 and H=20 hourly bars = 76 cells. Entry is the next
  hourly open; setup stop is 1R; target is 2R; same-bar ambiguity is stop-first;
  timeout is M2 failure. Invalid post-gap stops remain issued-signal failures.
- Development, validation, and sealed intervals were frozen before the run.
  The development segment chose only one long/short control direction per
  horizon; candidate rules and parameters were not selected or changed.
- Base/stress fees are legacy 10/30 bp round trip; timestamp-audited funding is
  applied. Spread and slippage are not measured, so net values are not execution
  forecasts.
- Selected archive hashes matched the supplied audit, and all 1,404 symbol-months
  passed hourly/funding alignment. This does not resolve universe survivorship,
  source truth, archive gaps outside the cohort, or trading fill realism.

## Result and disposition

| Measure | Observed result |
|---|---:|
| Setup × horizon cells | 76 |
| Completed event-ledger rows | 3,200,180 |
| Best sealed target-first M2 | 38.46% (10/26) |
| Cells at the 80% M2 target | 0 / 76 |
| Cells with ≥200 per-symbol non-overlap OOS signals | 66 / 76 |
| Cells with ≥10% signal coverage | 14 / 76 |
| Cells with positive mean net outcome in both fee scenarios | 7 / 76 |

The top sealed M2 cell was `engulfing_rsi_extreme_strict`, H=20: 10/26 target
first (38.46%), 23 symbol-nonoverlap events, 1.43% coverage, and mean net
outcome +0.733% base / +0.533% stress per issued event after funding. Its 95%
Wilson interval is approximately 22.43%–57.20%; the sample is far below the
required non-overlap N=200 and does not meet the 80% target. The corresponding
H=10 cell was 10/27 (37.04%), 24 non-overlap events, and 1.48% coverage.

The highest-coverage positive-stress cells were `volume_climax_exhaustion`,
H=20 (1,659 signals, 22.30% M2, 90.93% coverage, +0.235% base / +0.035% stress)
and its H=10 counterpart (1,662 signals, 16.31% M2, 90.92% coverage, +0.168%
base / -0.032% stress). These do not approach the M2 threshold; the H=10 stress
mean is negative.

**Verdict: REJECT this fixed 38-setup × 2-horizon family for the preregistered
M2 ≥80% objective. No strategy passes.** The strongest M2 cell has insufficient
sample and coverage and misses the target by more than 41 percentage points.
Positive average net outcome in a few cells is not a pass and is not evidence
of stable profitability.

The study-wide aggregate across all cells is descriptive only because signals
are reused across cells and are dependent across symbols/time. Do not interpret
the registry run-envelope aggregate as candidate performance. No Phase 7
robustness tests are warranted for promotion because no cell clears the primary
sealed gates; the full ledger remains available for audit. Future strategy
families need a new preregistration and cannot reuse this sealed interval for
selection without marking it as exposed.

## Verification

- Run envelope: `python3 scripts/research/run_contract.py docs/research/inventory/runs/usdm_1h_setup_m2_20261120/run.json`
  returned `STRUCTURALLY VALID`; this validates record shape only.
- `gzip -t` passed on `trade_ledger.csv.gz`.
- Independent CSV streaming counted 3,200,180 rows.
- Summary contains 76 candidate/horizon cells and 36 cohort symbols.
- The run directory contains `run.json`, `summary.json`, `report.md`, and the
  complete compressed event ledger. Exact code, input, and preregistration
  fingerprints are recorded in `run.json`.
