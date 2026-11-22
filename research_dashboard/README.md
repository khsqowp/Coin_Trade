# Strategy research dashboard — Stage 1

This is a local, read-only view of archived strategy specifications and recorded historical checks. It has no order paths or exchange connection. The page serves on `127.0.0.1:8765` only.

## Build, run, test

From this directory:

```sh
python3 build_data.py
npm test
node --check dist/app.js && node --check dist/force3d.js && node --check dist/size.js && node --check dist/i18n.js
./serve.sh
```

Open `http://localhost:8765`. `serve.sh` resolves `dist/` relative to itself and does not stop or replace any process. The page refreshes `data.json` once per minute. The builder's base graph-data path uses Python standard-library modules; forward-data generation additionally imports the existing `forward_test.status` module and its runtime dependencies. The browser view uses vendored Three.js r160 and OrbitControls through a local import map; network access and external CDNs are not used. The graph uses instanced spheres, weighted cylinder links, approximate metadata links, Korean labels, and deterministic 3D force placement. Run `npm test` for all Python and JavaScript behavior checks, then run the syntax checks shown above. `node --check dist/app.js` checks the ES module syntax.

Paper DB copies are read from $TRADING_DATA_DIR/cache/forward/<profile>/forward.db (default ~/CODE/trading_data). SQLite opens each database with mode=ro. The profile directory names are l5_4h, l5_12h, and jbb_1h. COPIED_AT.txt in the common forward directory supplies the UTC copy time. The builder never copies or modifies a database.

## Inputs and interpretation

Paper database copies live outside the repository at $TRADING_DATA_DIR/cache/forward/<profile>/forward.db (default ~/CODE/trading_data). The builder opens them only with SQLite mode=ro, and reads the shared UTC copy time from cache/forward/COPIED_AT.txt. The expected directory names are l5_4h, l5_12h, and jbb_1h. A missing copy is shown as not loaded. No database is copied or modified by the builder.

Forward status imports the existing forward_test package and therefore must run in the project environment that has its numerical dependencies installed. The fixture-only builder and front-end tests do not open live databases.

Run ./refresh_forward.sh from a local terminal to read-copy the three databases from linuxserver with rsync and regenerate the local page data. This script is intentionally not run by the builder. It writes the local copy timestamp only after all three rsync operations succeed.

When forward data is supplied, the builder reuses forward_test.status.status_data for the book-specific closed-trade count, elapsed days, marked return, last candle/update times, and stale status. It adds realized net return and a compact equity series using read-only SQL. The l5 12-hour backtest period length is absent, so no pace-adjusted expectation is fabricated for that profile.

- `strategy_archive/*/strategies/*.json` provides each strategy description, category, source reference, claimed instruments, and mechanical-spec flag.
- `scratchpad/strategy_bt/results/slice_*/summary.csv` provides implementation status, null percentile, plateau, raw/adjusted verdict, parameters, and historical returns.
- `results/ledger.csv` provides the trial-count field. The displayed total is the **maximum** `n_candidates_tested` value, not a sum, because ledger rows can describe overlapping search records.
- `verify2a/a1_results.csv` provides A1; `verify2b/results/group_b.csv` provides B1-B6; `verify/cost_stress.csv` provides doubled-cost results; `regime/results/results.csv` provides the regime gate. Since Group B and cost-stress rows omit timeframe, `verify/reproduce.csv` supplies a candidate-to-timeframe crosswalk; unmatched timeframes remain not run. `verify/REPORT.md`, `verify2a/REPORT.md`, `verify2b/REPORT.md`, and `regime/REPORT.md` were inspected to interpret the CSV names, test rules, and limitations. Report prose is not parsed as a per-strategy test result.
- Sphere size is passed-check count only. Historical train/test returns are secondary details and are never read by the size function.
- Metadata links connect exact matches on family, timeframe, symbol set, and direction. A sorted chain limits edges and keeps large shared-bet groups connected. Their visible label says they are approximate. The measured correlation links use thickness, opacity, and color, with strong at 0.7 or above, medium from 0.5 to 0.7, and weak below 0.5. These links describe only recorded past co-movement.

## Verdict and verification rules

The color priority is forward-confirmed, forward-running, adjusted PASS, raw PASS with a non-PASS adjusted verdict, failed raw FAIL, then not tested. The supplied `forward_test.status` considers ongoing paper progress but does not define a “confirmed” threshold; therefore Stage 1 never labels a strategy forward-confirmed. No strategy is a confirmed real winner today. A future stage must define that confirmation gate before assigning the bright-green state.

Depth checks use recorded fields: null percentile >=95; plateau `PASS`/`ROBUST`/`TRUE`/`YES`; exact adjusted verdict PASS; A1 exact PASS; B1-B3 failures from candidate-specific `FINAL` tag labels; B4 positive walk-forward result; B5 failed years no more than half the recorded years; B6 exact PASS; `cost_stress.csv` 2x-cost test return >0; and any regime V1/V2/V3 `PASS=true`. Absent rows are `not_run`, not failed. The `FINAL` tag lets the builder assign the B1, B2, and B3 decisions without mistaking `DONE` (computation completed) for PASS. Non-applicable B6 is marked not run. The forward band reports closed trades, elapsed days, equity snapshot count, historical-rate expected trades, and remaining days/trades to the evidence threshold. `jbb_1h` attaches to the known `jesse_simple_bollinger` strategy node when loaded; L5 database identity is left unassigned. This is tracking information, not proof of profitability.

See [data.schema.md](data.schema.md) for the JSON contract and sources.
