# Coin_Trade data-cleanup diff audit (read-only)

Audit target: primary checkout `/Users/user/CODE/Coin_Trade`, HEAD `beb947f361668e4a0d4cd7620ba740c9eaaec3e4`; the data-cleanup modifications listed below were uncommitted during this audit. No source or test files in that checkout were edited.

## Confirmed defect

`chart_predictor/collector.py:101-107` records an empty API response using the current `page_number` and exits `_fetch_range` without incrementing it. `collect_symbol` then continues to later missing intervals with that unchanged number (`:140-143`). The `collection_pages` primary key is `(collection_id,page_number)` (`:25-27`).

### Reproduction

Using a temporary SQLite DB with two missing one-minute intervals, a mocked session returned an empty list for the first interval and the exact missing candle for the second. Result:

```text
IntegrityError UNIQUE constraint failed: collection_pages.collection_id, collection_pages.page_number
run ('failed', 'IntegrityError', 0)
pages [(1, 0, 0)]
```

The second candle row was present in the temporary DB after the exception even though the run was marked failed with `inserted_rows=0`; it had no corresponding page-provenance record. Cause: `_store(..., commit=False)` inserts the row before the duplicate page-record insert fails, and the exception handler commits the failed-run update (`collector.py:151-155`). This is reproducible and should be fixed before treating collection-run provenance as reliable. A regression test should cover at least two missing ranges, empty first response, nonempty second response, and assert either correctly numbered page records or an atomic, non-partial failure.

The existing new empty-response test covers only one missing range, so it passes without exercising this collision.

## Other reviewed changes

- `data_quality.py` opens SQLite read-only and reports gaps, off-grid timestamps, invalid OHLCV, nulls, and schema. Its fingerprint deliberately covers schema/coverage metadata, not full candle contents; it must not be presented as a content checksum.
- `repair_vision_gaps.py` keeps the source DB untouched, retains raw response pages and hashes, and checks exact timestamp continuity and OHLCV constraints before returning fetched rows. Its resume shortcut treats an exact existing row count as complete without revalidating every row against retained payload hashes; this is a latent integrity risk if the patch DB is externally altered, not evidence that current rows are altered.
- `merge_vision_repair.py` refuses source/patch overwrite, verifies overlapping keys, row totals, and gaps across each symbol's observed span, and retains repair pages. It does not itself prove all values match raw page payloads or that coverage outside observed first/last rows is complete; the separately stored audit reports and source preservation remain necessary.
- `store.py` makes prediction rows append-only and identifies repeated trials by code/split/hypothesis/sample/data fingerprint. Its lookup-then-insert deduplication has no unique constraint, so concurrent identical registrations could race; no concurrent writer was observed or tested here.
- `setup_backtest.py` now includes data and selected-code fingerprints in report identity and records trial entries. The new 14 focused tests pass, but the full setup backtest was not run as part of this audit.

## Verification performed

- `PYTHONDONTWRITEBYTECODE=1 /opt/anaconda3/bin/python3 -B -m pytest -q -p no:cacheprovider chart_predictor/tests/test_collector_gaps.py chart_predictor/tests/test_data_quality.py` — **14 passed**.
- A separate temporary-DB/mock-session reproduction confirmed the multi-gap empty-page defect above.
- Git status was inspected. User-owned modifications remain unstaged/uncommitted in the primary checkout; no unrelated files were touched.

## Decision

Data-quality and immutable-repair direction is sound, but collection provenance is not robust to an empty page followed by another missing range. Keep the affected user changes intact; request/await an explicit implementation task before modifying them. Treat any run encountering this path as failed and re-audit the affected time ranges because a row can be inserted without its page record.
