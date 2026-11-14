# Addendum A1 — accounting and data-integrity correction

Frozen 2026-11-06 12:58 UTC, before any performance output was generated or viewed. The original `FREEZE.json` is preserved unchanged; its attempt ledger contains only `PREPARED_AWAITING_INDEPENDENT_REVIEW`. It was never eligible for execution because the independent review found defects. The original candidate ID will not be run. Only the replacement attempt `GEN11A1-DUALMOM-US_INDEX_ETF_12_1_CASH` may be considered, and it remains blocked pending a new independent GO bound to `FREEZE_A1.json`.

## Corrections

1. **Rebalance-cost accounting:** the previous draft took its return denominator after deducting costs, omitting monthly entry, exit, and switching fees from the return series. The corrected runner calculates each interval return against NAV immediately before any open-time rebalance fee, then applies the target holding's open-to-open gross return. A switch from asset A to B costs two sides; asset-to-cash or cash-to-asset costs one side; unchanged target costs zero. If invested at the terminal open, one liquidation side is included in the final interval return.
2. **Fail-closed date handling:** the prior draft sorted each input frame, silently repairing an unsorted source. The corrected runner rejects any duplicate or non-increasing source dates and never sorts or forward-fills.
3. **Frozen metadata verification:** the replacement freeze includes SHA-256 for each parquet and its vendor metadata file. The runner verifies both before decoding any parquet prices; the STARTED record captures both hashes.
4. **Turnover reporting:** the result records target-change count, one-way turnover units including terminal liquidation, and exposure. These counts are descriptive; they are not evidence of live fills.
5. **Single-run enforcement:** the replacement attempt rejects a prior STARTED/COMPLETED/FAILED event or an existing result/curve/manifest output. No reruns or variants are authorized.

The fixed candidate rule, four-symbol universe, schedule, costs, benchmark, and descriptive windows are otherwise unchanged from `PREREG.md`. No performance values, signal rankings, or candidate selection statistics have been calculated or inspected. This addendum itself does not grant performance-run permission. `FREEZE_A1.json` is the replacement manifest that an independent reviewer must bind before any run.
