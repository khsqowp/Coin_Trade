# Binance USD-M `bookDepth` archive feasibility — 2026-11-19

## Decision

`MAIN_STRUCTURE_FAIL`. The 80 preregistered 2025 symbol-days cannot be certified as a complete, regular 30-second snapshot panel. All 80 publisher checksums and HTTP status pairs passed, and the 10-band schema was stable, but no file met the preregistered requirement that all 2,879 timestamp intervals equal exactly 30 seconds. Forty files also contain fewer than 2,880 distinct timestamps. This source is not admitted to 1-minute-anchor strategy testing under this audit.

The audit is historical-source validation only. It did not calculate signals, target labels, M2, TP/SL, directional accuracy, or returns. The frozen sample and decision rules are in [the preregistration](binance-bookdepth-archive-feasibility-prereg-2026-11-19.md); all per-file details and hashes are in [the machine-readable result](binance-bookdepth-archive-feasibility-2026-11-19.json).

## Scope and result

| Sample | Files | HTTP 200 + checksum pass | Rows / distinct timestamps | Cadence result |
|---|---:|---:|---|---|
| Main: 20 symbols × 4 fixed 2025 dates | 80 | 80/80 | Jan 1: 28,800 / 2,880 each; Apr 1: 28,800 / 2,880 each; Jul 1: 28,590 / 2,859 each; Oct 1: 27,560 / 2,756 each | 0/80 exact 30-second sequences; maximum observed gap by date: 47s, 45s, 202s, 205s |
| Known-issue diagnostic: 4 symbols × 5 dates in 2026 | 20 | 20/20 | Diagnostic-only; reported defect changes the band matrix | Not part of main-sample eligibility |

The first fixed file froze 10 percentage bands: `[-5, -4, -3, -2, -1, +1, +2, +3, +4, +5]`. That exact set held for all 80 main-sample files. There were no detected null, non-finite, zero, or negative `depth`/`notional` values, and no duplicate `(timestamp, percentage)` keys. The numerical cumulative-depth monotonicity check had zero violations in the 80 main files when signed percentage values were treated as the two sides and ordered by absolute distance. This is only an internal numeric diagnostic; it does not establish timestamp event-time semantics, executable quotes, or raw L2 equivalence.

The exact issue-reproduction comparison matched 43/44 frozen counts. The only mismatch was `SOLUSDT`, `2026-09-06`, `-1.0%`: expected 2,877 distinct rounded `notional/depth` values, observed 2,879. All four cross-symbol `+0.2%` counts matched (SOL 4, BTC 3, ETH 2, AVAX 1). Per preregistration, the report is **not exactly reproduced** because all 44 cells must match; no tolerance or partial-match rule was used. The source issue is a user report, not a Binance confirmation. [Upstream issue #496](https://github.com/binance/binance-public-data/issues/496)

## Interpretation and limits

- Checksum validity proves that downloaded bytes match the publisher sidecar; it does not prove complete or correctly timed market observations.
- Main-sample row counts and timestamps fail the frozen regular-cadence gate. Do not treat these archives as a reliable, contiguous 30-second panel or silently fill/resample missing snapshots.
- The 2026 diagnostic is separate from the 2025 main sample. Its 43/44 near-reproduction neither repairs nor disqualifies the main sample.
- Binance describes `bookDepth` as cumulative depth at percentage distances from mid; this is aggregated depth telemetry, not per-order L2. It cannot substantiate order-level replenishment, queue position, best bid/ask, spread, or executable fills. [Binance Futures book-depth FAQ](https://www.binance.com/en/support/faq/detail/afd1ccded7ca41108b281c927fefa3a0)
- No result here supports a predictive-accuracy claim or the ≥80% target-first criterion. A different feed or a new preregistered hypothesis would be needed before outcome testing.

## Reproduction

From the repository root, stage only the 100 fixed historical archives with `bash scripts/research/download_binance_bookdepth_allowlist.sh`. The script keeps ZIPs, checksum sidecars, and HTTP-status TSV outside Git under `/private/tmp/binance-bookdepth-audit-20261119/`, verifies each archive SHA-256 before accepting it, and prints progress. Then run `python3 -B scripts/research/audit_binance_bookdepth.py --output docs/research/binance-bookdepth-archive-feasibility-2026-11-19.json`. The audit script is offline and reads only the staged files and status manifest.

Binance Vision terms allow only the approved personal, non-production historical research use in this work; no live signal, execution, commercial use, or external signal distribution is in scope. [Binance Vision terms](https://github.com/binance/binance-public-data/blob/master/TERMS_AND_CONDITIONS.md)
