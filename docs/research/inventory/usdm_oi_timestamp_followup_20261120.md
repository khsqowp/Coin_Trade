# Binance USD-M OI timestamp follow-up — 2026-11-20

## Decision

**Do not use the metrics archive timestamp as an OI signal-availability timestamp. Do not apply a global +5-minute shift. Historical OI remains ineligible for strategy scoring.** A later, broader archive/REST comparison contradicts the earlier one-day same-label comparison: for 96 valid symbol-days, archive OI at label `T` exactly matches REST OI at `T+5m`; the earlier BTCUSDT 2026-11-19 sample matched REST at `T`. This establishes inconsistent timestamp mapping across the sampled dates, not when the values were first observable.

## Evidence inspected

1. The fixed historical panel sample contains 740 requested symbol/day combinations across 37 symbols and 20 quarterly-spaced dates. There were 720 archive/checksum pairs with HTTP 200 and matching publisher hashes; 20 symbol/day pairs had both objects absent. Among the 720 downloaded archives, 715 had 288 rows, three had 2 rows, and two had 1 row. The five partial files therefore account for 1,432 missing five-minute slots. No duplicate or off-grid timestamps were reported.
2. The timestamp cross-check contains 111 requested symbol-days across 37 symbols and three dates (2026-11-04, 2026-11-08, 2026-11-12). Ninety-six pairs had usable OI on both sides: 32 symbols on each date. All 96 matched the REST record exactly at `T+5m` (maximum relative error 0); none matched exactly at `T`. The other 15 pairs had no OI series on both sides, rather than a valid numeric comparison.
3. The earlier BTCUSDT 2026-11-19 check had 288/288 exact matches at `T` and nonzero differences at `T±5m`. Its archive object was published at 2026-11-20 06:38:52 UTC. That result conflicts with the 96-pair follow-up and cannot justify either global alignment rule.
4. The cross-check compares the current REST history response with archived values. It does not preserve contemporaneous REST snapshots from each historical day, so it cannot establish historical first-availability, API revision behavior, or whether a value was knowable at the archive label.

## Interpretation and risk

- The observed mapping is date/sample dependent: exact `T` for the one BTC day and exact `T+5m` for the 96 valid pairs from three other dates. Do not normalize this into a universal shift; doing so can introduce look-ahead or misalignment.
- Exact agreement with a retrospective REST endpoint is not point-in-time provenance. A current REST response can describe a period timestamp without proving when the observation was published or whether historical values were revised.
- The 2021–2026 stratified archive sample is structurally strong for the sampled files, but it also found five partial daily files and 20 absent symbol/day objects. Missing rows must not be silently filled or forward-filled.
- The quarterly archive-quality sample contains 84 files and reports one missing five-minute slot; all sampled publisher checksums matched. This is a separate sample and does not validate the unsampled archive population.

## Reproduction inputs and limitations

Read-only inputs inspected:

- `/private/tmp/r030-oi-metrics-panel-sample/audit.json`
- `/private/tmp/r031-oi-availability-crosscheck/audit.json`
- `/private/tmp/r031-oi-availability-crosscheck/metrics/`
- `/private/tmp/r031-oi-availability-crosscheck/rest/`
- `/private/tmp/cointrade-oi-rest-alignment-20261120/comparison.json`
- `/private/tmp/cointrade-oi-rest-alignment-20261120/archive.zip`
- `/private/tmp/cointrade-oi-rest-alignment-20261120/rest.json`

Compact verification command for the saved audit summaries:

```sh
python3 -c 'import json,pathlib; d=json.loads(pathlib.Path("/private/tmp/r031-oi-availability-crosscheck/audit.json").read_text()); r=[x for x in d["records"] if x.get("oi_alignment")]; print("valid_pairs",len(r),"exact_T",sum(x["oi_alignment"]["offset_+0m"]["max_relative_error"]==0 for x in r),"exact_T_plus_5m",sum(x["oi_alignment"]["offset_+5m"]["max_relative_error"]==0 for x in r)); p=json.loads(pathlib.Path("/private/tmp/r030-oi-metrics-panel-sample/audit.json").read_text()); print("panel",p["summary"])'
```

The sample-building/cross-check script for `r030`/`r031` was not found beside the saved artifacts or in the named audit directory during this continuation. The JSON retains per-file checksums, REST response hashes, row counts, and alignment summaries, but full independent reproduction of the original 111 REST requests is not claimed here.

## Next gate

1. Preserve these raw files and summaries unchanged.
2. Locate or recreate a small, tested cross-check utility that records exact request parameters, UTC conversions, response bytes/hashes, and alignment sign convention; reproduce several representative pairs including the conflicting 2026-11-19 BTC sample.
3. Do not score any OI strategy until field semantics and historical availability are resolved with evidence independent of the retrospective endpoint. If they cannot be resolved, reject OI as a historical signal input and move to a distinct price/funding-only hypothesis that does not duplicate the rejected families.
4. No OI-based result is approved as a core, and Phase 9 remains blocked.
