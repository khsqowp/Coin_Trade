# US cross-backtest reconciliation audit

Date: 2026-11-05 (Oracle)

## Finding

The ticker sets match exactly (653 included; no set differences), the evaluation window is 2022-01-03 through 2026-10-30, and per-side fee values match (KIS 0.36%, low-cost 0.08%). However, the reported US return metrics are not a valid numerical cross-check: both independent runners execute different historical state and, for S1, different target-selection behavior. Treat the US cross-check as **failed / not reconciled** until those differences are aligned and both runs are repeated.

## Trade-count discrepancy

Agent1's `runner.py::run_slots` returns a list of trade returns without dates; `main()` writes `trade_count=len(tr)` after simulating from the first date in the full source panels. Thus its reported 7,550 S3 trades include warmup-period exits before 2022-01-03. This runner's `run_us_slots` starts from data trimmed to 2021-01-01 and `met()` further counts only exits between 2022-01-03 and 2026-10-30. Therefore S3 counts 7,550 versus 1,097 are different populations; neither figure is a comparable evaluation-window count. The same mismatch affects S4, Mach7, squeeze, and pullback trade counts.

## Return differences and concrete causes

| Strategy | Agent1 KIS CAGR / trades | This run KIS CAGR / exits | Reconciliation |
| --- | ---: | ---: | --- |
| S1 momentum | 41.40% / n.a. | 53.02% / n.a. | Not comparable. This runner clipped input history to 2021 for memory, while Agent1 uses full available history. More directly, Agent1 refreshes its `base` portfolio on every rebalance even while the SMA200 market gate is risk-off, then restores that last saved base when the gate turns risk-on. This runner sets zero while risk-off and recomputes a fresh base upon recovery. The 0/7/14 phase calendars are also anchored to different first panel dates. |
| S3 EMA9/21 | -5.04% / 7,550 | -2.67% / 1,097 | Trade count periods differ. Return path can differ because Agent1 simulates all source history and carries positions into evaluation; this run begins at 2021, changing pre-evaluation portfolio state and EMA initialization. |
| S4 swing6 | -33.11% / 6,518 | -31.80% / 1,004 | Trade count periods differ. Full-history versus 2021-start portfolio state and signal initialization differ. |
| S5 Mach7 | +27.50% / 1,633 | +30.82% / 212 | Trade count periods differ. Full-history versus 2021-start state differs; EMA initialization and missing-value handling also differ. |
| S5 squeeze | -3.26% / 4,724 | -6.10% / 608 | Trade count periods differ. Full-history versus 2021-start state differs; SMA/whipsaw warmup and missing-value handling differ. |
| S5 pullback | -47.44% / 11,977 | -44.12% / 1,629 | Trade count periods differ. Full-history versus 2021-start state differs; rolling-volume warmup and missing-value handling differ. |

Additional implementation difference affecting slot strategies: Agent1 computes entry allocation as `min(equity/slots, cash)` and then deducts fees, while this runner caps allocation at `cash/(1+fee)`. This can slightly alter cash, exposure, and later position sizing. Agent1 also forward-fills panel prices before signal calculation; this runner calculates most signals on the unfilled panel. These should be aligned before comparing returns.

## Evidence locations

- Agent1: `/home/opc/trading/research/cointrade_us_independent_2026-11-05/runner.py`, `strategy_metrics.csv`, `manifest.json`.
- This independent run: `/home/opc/trading/research/agent_crosscheck_20261105T140804Z/runner.py`, `us_strategy_summary.csv`, `strategy_summary.csv`, `manifest.json`.
- Shared Coin_Trade revision recorded in this run: `37af45ac328c8cbb232adce113642fda8485b3a2`.

## Required alignment before claiming cross-validation

1. Use the identical full-history input window and full-history engine state in both runners; if memory limits prevent this, both must use the same explicitly declared common warmup start.
2. Make S1 risk-off rebalance/base-state rules and 0/7/14 phase anchors identical.
3. Apply identical forward-fill rules, fee-aware allocation constraints, and stop/exit timing.
4. Report trade counts only for exits within the evaluation window, separately from full-run lifetime totals.
5. Rerun both implementations and compare daily normalized equity curves, trade ledgers, and metrics.
