# Addendum A2 — common-calendar integrity correction

Date: 2026-11-06 (Asia/Seoul)

## A1 attempt disposition

The single A1 attempt remains preserved in `attempts_gen11-breadth-20261106-a1.jsonl` and `manifest_gen11-breadth-20261106-a1.json`. It failed at the input calendar-integrity gate because A1 incorrectly required SPY and all nine sector ETFs to have identical raw date indexes. The coordinator's read-only index-only audit found that SPY has a longer history while all nine sector files share the same shorter calendar. A1 therefore produced no curve and no performance metrics. This is an input-calendar/runner mismatch, not a strategy result or evidence for/against the hypothesis.

## Frozen A2 calendar rule

This addendum changes only date-calendar validation and alignment. It does not change the candidate's signal, SMA window, threshold, exposure, execution timing, adjusted-price method, cost, benchmark, reporting windows, or decision rule in `PREREG.md` and `ADDENDUM_A1.md`.

1. Load the ten frozen instruments only: XLB, XLE, XLF, XLI, XLK, XLP, XLU, XLV, XLY, and SPY.
2. Before signal or return computation, require every source index to be a pandas `DatetimeIndex`, unique, and strictly ascending. Reject malformed calendars; do not sort, deduplicate, repair, or forward-fill source rows.
3. Define the sole analysis calendar as the exact intersection of all ten source date indexes, sorted ascending. The common calendar is not inferred from SPY and no alternate calendar is allowed.
4. Select each frame with exact `.loc[common_calendar]` date membership. Require every aligned frame's index to equal the common calendar exactly. Do not reindex with fill, forward-fill, interpolate, or drop any further rows after the intersection.
5. Calculate sector SMA/breadth, next-open targets, SPY strategy returns, and matched SPY benchmark only on the aligned common calendar. Require at least 200 common closes and one subsequent open-to-open interval.
6. Keep the input content hashes frozen. The A2 runner and tests have independent hashes, and the A2 freeze also pins the unchanged A1 helpers that it imports. The proposed A2 run ID is `gen11-breadth-20261106-a2`; it is reserved for one execution only after a new independent root GO.

## Test and execution gate

The new synthetic test file exercises ten-way intersection, SPY's longer history, a missing sector date, exact aligned-index equality, no forward-fill, invalid index type, duplicate/descending dates, empty intersections, and the exact fixed instrument set. These tests use constructed in-memory frames only; they do not read the parquet files or compute market results.

The A2 candidate is pending independent review. Do not run the real-data loader, calculate performance, modify this addendum/rule after review, rerun A1, overwrite A1 records, or create the A2 attempt ledger before independent GO. Once approved, execute the reserved A2 run ID once. If any integrity or runtime failure occurs, preserve a FAILED record and do not rerun or tune this candidate.
