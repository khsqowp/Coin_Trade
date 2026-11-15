# R009 plan — L2 pilot body and deterministic replay audit

Status: `body_complete_finalize_failed`; data-integrity audit only, not a strategy trial.

## Scope

Audit the one-hour BTCUSDT/ETHUSDT public depth+aggregate-trade pilot started in run directory `chart_predictor/data/crypto_l2_pilots/20261115T222507Z-d6ad3567/`. Preserve its original `.partial` filename and bytes because the capture process exited with a generic `RuntimeError` and did not write its expected completion/incomplete manifest.

## Checks performed

- Parsed every JSONL line and checked newline termination.
- Calculated the raw SHA-256 and measured first-to-last receive-time span.
- Replayed the untouched partial body through the offline compact reducer and UTC 10-second window aggregator twice into temporary output paths.
- Compared SHA-256 of both compact outputs and both window outputs.
- Did not construct candidates, labels, fills, performance metrics, or strategy scores.

## Acceptance boundary

This run is not accepted as a completed recorder pilot because the run-level manifest is missing. Successful parsing and deterministic replay establish integrity of the body and replay implementation only; they do not prove exchange-side completeness, continuous connection coverage, multi-day recovery, strategy validity, or predictive value.
