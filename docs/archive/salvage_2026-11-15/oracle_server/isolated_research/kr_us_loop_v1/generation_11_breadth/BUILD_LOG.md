# Generation 11 breadth — build and test log

- Candidate scope: one fixed 9-sector-ETF breadth gate; no parameter grid.
- Prior-overlap audit: Gen02 `BREADTH_60_40_BASKET`, US v2 X2/X9, and Gen01 SMA200 regime switch are related. The frozen rule is not an independent family. See `PREREG.md`.
- Data availability: all nine frozen sector ETF parquet paths and SPY path exist in the local ignored mirror. No parquet value, date range, metric, or performance result has been read in this build stage.
- Integrity fingerprints: ten raw file SHA-256 hashes are recorded in `FREEZE.json`; this pins identity, not data correctness or atomicity.
- TDD RED: initial test import failed because `run_gen11.py` did not yet exist (`ModuleNotFoundError: run_gen11`), the expected missing-implementation state.
- Independent-review change request: before any market-value read, create and fsync a unique-run `STARTED` JSONL event; preserve/update a manifest on failure; append durable `FAILED`/`FINISHED`; separate evaluated/risk-on/entry/exit/terminal counts from turnover; use sample daily standard deviation for Sharpe. No signal, price, cost, benchmark, or window definition changed. See `ADDENDUM_A1.md`.
- Independent review follow-up: require a real pandas `DatetimeIndex` during input loading, before any signal or metric calculation; added a synthetic malformed-index test. No market values were opened.
- Independent review follow-up: removed deprecated/removed `DataFrame.applymap` use for pandas 3 compatibility; use `to_numpy(dtype=float)` plus scalar finite/positive checks and test with a DataFrame-like object that has no `applymap` method.
- TDD GREEN after A1: synthetic unit tests cover inclusive SMA200, strict comparison, 5-of-9 threshold, fail-closed panel checks, next-open lag, transaction-cost boundaries, terminal liquidation, independent activity counts, sample Sharpe, durable STARTED→FAILED / duplicate-run protection, date-index type rejection, and pandas-3-compatible frame validation.
- Syntax: `compile(source, filename, "exec")` passed for runner and tests without writing `.pyc` files. `py_compile` was attempted but macOS Python tried writing its cache under a protected global cache path; it is not treated as a code failure.
- Environment limitation: default Python 3.9 has no pandas, so real-Parquet integrity validation and performance execution have not been run. The root reviewer must first approve the frozen candidate; then use a suitable already-installed local environment for the single run. Do not install dependencies or access remote data as part of this candidate.
- Gate: `FREEZE.json` remains `PENDING_INDEPENDENT_GO`; runner enforces this state and will refuse to read market data until the root reviewer records GO.
