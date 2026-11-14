# Generation 11 A1 — execution outcome

## Outcome

**Execution failed; this is not a strategy rejection and there is no performance verdict.** The single authorized attempt started only after the independent GO, freeze/review binding, single-run guard, and all frozen artifact hashes passed. The runner loaded the four frozen ETF parquet inputs, then emitted NumPy overflow / invalid-division warnings while calculating metrics. It failed at JSON serialization with `Out of range float values are not JSON compliant: inf`.

No strategy metric, signal ranking, window-specific score, or finite equity-curve artifact is reported here. The traceback does not establish which window or metric first became non-finite, nor whether the cause is an input anomaly, accounting behavior, or numerical handling. It would be misleading to label this candidate profitable, unprofitable, or rejected. The permitted one-run allowance is consumed; no rerun, patch-and-rerun, or post-result parameter change is authorized for this candidate.

## Attempt record

- Attempt ID: `GEN11A1-DUALMOM-US_INDEX_ETF_12_1_CASH`.
- State: `STARTED` then `FAILED` at 2026-11-06 13:09 UTC.
- Failure: `ValueError: Out of range float values are not JSON compliant: inf` while serializing metric output.
- Runtime warning: `numpy` cumulative overflow; invalid value during maximum-drawdown division. Preserve as warning only; root cause not confirmed.
- Inputs: the frozen SPY/QQQ/IWM/DIA parquet and metadata SHA-256 values are recorded in the attempt ledger and `FREEZE_A1.json`.
- Persisted: failure manifest and full STARTED/FAILED traceback in `manifest_GEN11A1-DUALMOM-US_INDEX_ETF_12_1_CASH.json` and `attempts_GEN11A1-DUALMOM-US_INDEX_ETF_12_1_CASH.jsonl`.
- Not persisted: results JSON and equity curve were never written because the run failed before those writes. No independent metric recomputation or full-curve finite-value check is possible from this attempt.
- Trading / remote server / order placement: none.

## Future harness hardening (not applied to this frozen candidate)

Before considering a different, separately preregistered candidate, its runner should validate every interval return and cumulative equity value for finiteness, detect overflow before metric aggregation, record a machine-readable failure with the affected stage/window, and persist a diagnostic curve only when every row passes the finite-value gate. Any such change belongs to a future candidate version and requires tests, new hashes, and independent review. It must not be used to reopen or rerun this consumed attempt.
