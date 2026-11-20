# Existing experiment registry reconciliation

Snapshot: `research_registry_20261120T021022Z.csv`, generated from the
append-only `docs/research/registry.jsonl` on 2026-11-20 before the new fixed
USD-M run was appended. This is a metadata crosswalk, not a rerun of the 97
experiments present at that snapshot. No historical registry entry was edited.

## Current recorded status

| Market classification | Rows | Recorded status counts | Comparison treatment |
|---|---:|---|---|
| Crypto | 49 | REJECT 42, VALIDATION_REQUIRED 5, BLOCKED 0, NOT_EVALUABLE 1, PASS 1 | M2-eligible only if the original run recorded target-first event paths, cost model, sealed OOS, and required sample metadata. Otherwise retain as historical context and replay under the current crypto scorecard. The one `PASS` is a historical paper/live rotation claim, not an M2 pass. |
| Stocks | 48 | REJECT 28, VALIDATION_REQUIRED 12, BLOCKED 6, NOT_EVALUABLE 2, PASS 0 | KR and US must be split into separate market rows/runs. Current-survivor CSVs and uncertain adjustment provenance prevent promotion, regardless of headline metrics. |
| **Total** | **97** | **REJECT 70, VALIDATION_REQUIRED 17, BLOCKED 6, NOT_EVALUABLE 3, PASS 1** | Historical labels describe the original experiment's contemporaneous bar. They are not current approval labels. |

The current registry snapshot contains 97 rows and the status counts above.
They were recomputed directly from the `verdict` column in that exact CSV using
Python's CSV reader; they are not estimated from prose or file counts.

After the fixed USD-M M2 re-evaluation completed, registry row 98 was appended
with verdict `REJECT`; it does not alter the dated 97-row snapshot above. The
live append-only registry now has 98 rows: coin 50, stock 48; verdict counts are
REJECT 71, VALIDATION_REQUIRED 17, BLOCKED 6, NOT_EVALUABLE 3, PASS 1. The new
run's report and full artifacts are linked in row 98 and
[`usdm_1h_setup_m2_results_20261120.md`](usdm_1h_setup_m2_results_20261120.md).

## Reconciliation rules

- A historical `REJECT` remains rejected for the tested hypothesis/configuration;
  it is not re-opened merely because the common pipeline changes. A genuinely
  changed hypothesis or corrected data source requires a new preregistration
  and registry row.
- `VALIDATION_REQUIRED` means the recorded result is a lead, not a pass. Reasons
  visible in the source records include survivor-universe bias, cherry-picked
  best cells, stress-cost failure, missing full portfolio metrics, funding or
  slippage omissions, weak OOS provenance, or repeated selection on the same
  period.
- `BLOCKED` means the cited run did not produce valid evidence because a data,
  execution, provenance, or run gate stopped it. It is not a strategy failure.
- `NOT_EVALUABLE` means the recorded sample/outputs cannot answer the stated
  acceptance question. Do not infer a numeric result.
- `PASS` is not portable across changed thresholds or metrics. The single
  historical PASS row must be adjudicated against the current market-specific
  gates in a fresh run before any candidate is promoted.
- Rows that combine `kr+us` or `stock_market_unspecified` are not duplicated into
  separate KR and US passes. Split only where source reports provide separate
  data, ledgers, and metrics; otherwise mark the market attribution unresolved.
- Do not equate row counts with independent experiments: one row may summarize
  grids of many configurations, and related rows may reuse the same market data,
  baseline, or selection period. The multiple-testing ledger must count trials
  from the source report/grid, not just registry rows.

## Candidate triage for the first comparable replay

1. **Stocks:** current records already contain broad negative/failed screens and
   several post-hoc leads. Do not re-run rejected grids. First resolve the US
   OHLC anomalies and corporate-action semantics, then create separate KR/US
   eligible symbol/date manifests. Only after a PIT-universe limitation is
   either fixed or formally keeps the work exploratory should `Round9` and the
   strongest recorded cross-sectional candidates be reviewed against the common
   costs and independent round-trip gate. Round9's prior forward correction is
   explicitly invalid as untouched OOS evidence; it cannot be promoted by its
   headline event-study interval.
2. **Crypto:** do not rank CAGR/Sharpe strategy rows against chart-predictor
   target-first rows. The existing P5-P11 chart setups have M2-style results and
   are already mostly rejected; retain their failures as baselines. For any
   candidate not evaluated with target-first paths, first build a common aligned
   kline/mark/funding coverage manifest, then re-score only a small preregistered
   set with the current M2 scorecard. Do not re-open broad grids or use the
   sealed set for selection.
3. **Operational/risk overlays:** cadence, leverage, drawdown guards, and live
   rotation diagnostics are not equivalent independent alpha hypotheses. Keep
   them outside the strategy leaderboard; evaluate them only as account-level
   policy overlays against an unchanged base strategy and common portfolio
   ledger.

## Unresolved mapping work

Fresh read-only path check: all 97 rows have a `doc_ref`, and all 97 references
resolve in the current checkout. Eleven references point to directories rather
than directly to a document file (the archived equity generations and equity
transfer bundle); the remaining 86 point to files. Sixteen rows contain at least one
`artifacts` entry; every listed path resolves after treating trailing text as
an inline command/variant annotation. Eighty-one rows have no artifact path in
the registry, so a direct link from the row to the exact code/data output is
missing even though the long-form document exists.

This crosswalk does not attach per-run data/code fingerprints, independently
verify every reported figure, or establish trial counts from every source
grid. Those require a subsequent source-by-source reconciliation. The metadata
manifest locates files; source contents and large SQLite candle databases have
not been exhaustively audited here. No missing metric or provenance field is
filled by inference.
