# Candle data quality and test provenance

This document defines the local data gates and points to the audited snapshots. The exchange source databases are ignored runtime data and are not silently rewritten by audits or repairs.

## Audited snapshots (2026-11-15)

|Dataset|Rows|Symbols|Range / defects|Disposition|
|---|---:|---:|---|---|
|`candles.sqlite`|17,142,161|100|Observed spans are continuous per symbol; 0 off-grid timestamps, invalid OHLCV rows, null rows, or duplicate keys.|Complete across its observed spans. It supports the July–October 2026 P5–P9 development window; do not extend collection without a preregistered need.|
|`vision_dev.sqlite`|19,776,458|6|2020-01 through 2026-06. It has 14,400 missing minutes: SOLUSDT and XRPUSDT each lack 4,320 minutes in 2022-02-26–2022-03-01 and 2,880 minutes in 2022-04-01–2022-04-03.|Source preserved. The missing rows were retrieved from Binance USDⓈ-M public klines and stored separately.|
|`vision_dev_repaired.sqlite`|19,790,858|6|Same observed spans, with all 14,400 missing minutes restored; 0 missing minutes, invalid rows, off-grid timestamps, null rows, or duplicate keys.|Use this explicitly for future historical research. Earlier results still refer to the original DB.|

Detailed per-symbol findings are in [data_quality_20261115.json](data_quality_20261115.json), [vision_data_quality_20261115.json](vision_data_quality_20261115.json), [vision_repaired_quality_20261115.json](vision_repaired_quality_20261115.json), and their Markdown reports. The 453 archive manifest entries sum to the original `vision_dev.sqlite` row count; this confirms row accounting, not the continued availability or revalidation of each original compressed archive. The two 2026 collector logs match current per-symbol row counts for 97/100 symbols; the exact reconciliation and three exceptions are in [collect_log_reconciliation_20261115.md](collect_log_reconciliation_20261115.md). Repair ranges, timestamps, payload hashes, and integrity results are recorded in [data_repair_20261115.json](data_repair_20261115.json) and [data_repair_20261115.md](data_repair_20261115.md).

The logs `collect.log` and `collect120.log` are progress records, not complete lineage manifests. Their per-symbol insert counts match the DB exactly for 97 symbols. BTCUSDT, ETHUSDT, and HUSDT differ; the latter two show failed 90-day requests, and BTC shows only 20 rows in the 30-day log. These counts strongly associate the logs with the DB, but cannot prove exact key lineage because prior rows and partially committed failed requests are possible. The log format needs request bounds, page hashes, and resume state going forward.

## Repeatable checks

- `python -m chart_predictor.data_quality <db> --json <path> --markdown <path>` runs a read-only audit. It checks schema, per-symbol spans, minute-grid alignment, missing opens inside each observed span, duplicate `(symbol, open time)` keys, nulls, and invalid OHLCV relationships.
- `python -m chart_predictor.repair_vision_gaps` idempotently obtains only the listed gaps and writes them to `chart_predictor/data/vision_gap_repair.sqlite`. It retains each raw response page and SHA-256. It never edits `vision_dev.sqlite`.
- `python -m chart_predictor.merge_vision_repair` creates `chart_predictor/data/vision_dev_repaired.sqlite` as a separate snapshot, preserves repair-page provenance, checks zero source/patch overlap, and fails if any observed-span minute is still missing. It refuses to overwrite an existing snapshot.
- New collector runs record request windows, status, inserted counts, page response counts, and SHA-256 of canonicalized JSON pages in `collection_runs` and `collection_pages` inside the candle database. Empty pages and failed/incomplete runs are recorded; errors still propagate to the caller. Existing `collect.log` files predate this manifest and cannot be upgraded retroactively.
- `chart_predictor.store.record_trial` reuses a trial ID when model, prompt version, code SHA, split, hypothesis, sample count, and non-null data fingerprint all match. A changed fingerprint remains a new trial. Legacy rows remain intact.
- Setup backtests already fingerprint raw inputs and report results, and record stage trials in ignored `data/trials.sqlite`. The JSON reports and this audit note are the durable, reviewable research records; keep generated data databases and source archives out of Git.

## Data acquisition gate

Acquire more data only for a named hypothesis, instrument universe, and half-open time window. Check source schema and publication availability first, fetch public market data without credentials, verify exact timestamp coverage and OHLCV invariants, retain raw response/archive hashes, and write repairs as a separate immutable input. A larger database alone is not a quality improvement. Preserve development, validation, and sealed/forward boundaries from [SPEC.md](SPEC.md); never use a repair to silently change a prior test's input.

## Test gate

Before a research run, record its hypothesis, exact code/data fingerprints, universe, time bounds, costs, split, and frozen decision threshold. After the run, retain the report and decision, including null results and failures. Exact deterministic reruns reuse the same trial identity; any changed input or rule is a new trial. Current P5–P9 negative results remain valid for their original inputs and must not be overwritten by the repair.
