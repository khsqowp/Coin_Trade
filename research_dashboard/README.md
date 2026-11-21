# Strategy research dashboard — Stage 1

This is a local, read-only view of archived strategy specifications and recorded historical checks. It has no order paths or exchange connection. The page serves on `127.0.0.1:8765` only.

## Build, run, test

From this directory:

```sh
python3 build_data.py
python3 -m unittest discover -s tests
./serve.sh
```

Open `http://localhost:8765`. `serve.sh` resolves `dist/` relative to itself and does not stop or replace any process. The page refreshes `data.json` once per minute. The builder uses only Python standard-library modules.

Optional paper database copies can be supplied with `python3 build_data.py --forward-db-dir DIR`. The builder opens matching `trading-forward-test*/forward.db` files in SQLite read-only mode (`mode=ro`). Database directory names should include the profile name (`l5_4h`, `l5_12h`, or `jbb_1h`) to map files unambiguously. With no matching database, the profile reads “not loaded”. No DB is copied or modified by the builder.

## Inputs and interpretation

- `strategy_archive/*/strategies/*.json` provides each strategy description, category, source reference, claimed instruments, and mechanical-spec flag.
- `scratchpad/strategy_bt/results/slice_*/summary.csv` provides implementation status, null percentile, plateau, raw/adjusted verdict, parameters, and historical returns.
- `results/ledger.csv` provides the trial-count field. The displayed total is the **maximum** `n_candidates_tested` value, not a sum, because ledger rows can describe overlapping search records.
- `verify2a/a1_results.csv` provides A1; `verify2b/results/group_b.csv` provides B1-B6; `verify/cost_stress.csv` provides doubled-cost results; `regime/results/results.csv` provides the regime gate. Since Group B and cost-stress rows omit timeframe, `verify/reproduce.csv` supplies a candidate-to-timeframe crosswalk; unmatched timeframes remain not run. `verify/REPORT.md`, `verify2a/REPORT.md`, `verify2b/REPORT.md`, and `regime/REPORT.md` were inspected to interpret the CSV names, test rules, and limitations. Report prose is not parsed as a per-strategy test result.
- Size is passed-check count only. Historical train/test returns are secondary details and are never read by the size function.
- Metadata links connect only exact matches on family, timeframe, symbol set, and direction. A sorted chain limits edges and keeps large shared-bet groups connected. The visible label is “approximate (metadata similarity)”. The supplied `verify/correlation.csv` contains the 12-candidate historical return-correlation matrix, so pairs above 0.5 receive a separate purple dashed edge. These edges are historical co-movement descriptions only.

## Verdict and verification rules

The color priority is forward-confirmed, forward-running, adjusted PASS, raw PASS with a non-PASS adjusted verdict, failed raw FAIL, then not tested. The supplied `forward_test.status` considers ongoing paper progress but does not define a “confirmed” threshold; therefore Stage 1 never labels a strategy forward-confirmed. No strategy is a confirmed real winner today. A future stage must define that confirmation gate before assigning the bright-green state.

Depth checks use recorded fields: null percentile >=95; plateau `PASS`/`ROBUST`/`TRUE`/`YES`; exact adjusted verdict PASS; A1 exact PASS; B1-B3 failures from candidate-specific `FINAL` tag labels; B4 positive walk-forward result; B5 failed years no more than half the recorded years; B6 exact PASS; `cost_stress.csv` 2x-cost test return >0; and any regime V1/V2/V3 `PASS=true`. Absent rows are `not_run`, not failed. The `FINAL` tag lets the builder assign the B1, B2, and B3 decisions without mistaking `DONE` (computation completed) for PASS. Non-applicable B6 is marked not run. The forward band reports closed trades, elapsed days, equity snapshot count, historical-rate expected trades, and remaining days/trades to the evidence threshold. `jbb_1h` attaches to the known `jesse_simple_bollinger` strategy node when loaded; L5 database identity is left unassigned. This is tracking information, not proof of profitability.

See [data.schema.md](data.schema.md) for the JSON contract and sources.
