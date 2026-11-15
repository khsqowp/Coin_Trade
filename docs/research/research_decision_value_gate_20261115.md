# Research decision-value gate — 2026-11-15

Status: evidence review and read-only local-data inventory. No strategy backtest, parameter search, public-data collection, account access, purchase, order, or server operation was performed.

## Decision

Do not run another strategy grid on the currently exposed crypto candles or the existing KR/US price cache. Every proposed experiment must name the decision its result can change, the independent evidence it needs, its stop condition, and the result that would invalidate the hypothesis. If it cannot change a decision, do not run it.

The user requires four parallel research roles for future substantive work: two KR/US equity specialists and two crypto signal researchers. Each role must first analyze prior reports and raw evidence available in its assigned scope, distinguish direct inspection from supplied summaries, and return a falsifiable recommendation. Agent count or repeated agreement is not evidence of a trading edge.

## Evidence reviewed

### Crypto

- The fixed BTC 4-hour regime / coin 5-minute sweep→MSS probe is rejected as a candidate: target-first 13.38%, coverage 1.7688%, and mean net R -0.294 under the assumed 0.10% round-trip fee-only scenario on exposed history. Its momentum comparator was structurally forced to match its direction, so it was not an informative baseline. The rule and opened interval must not be tuned or relabeled as validation.
- Earlier momentum, streak, volume, sweep, multi-timeframe, and lead/lag results are exposed development results, frequently low-coverage or negative after assumed costs. None establishes 80% calibrated M4 target-first precision.
- L2 liquidity recovery after one-sided flow is a distinct hypothesis, not a discovered edge. The existing candle-only cache cannot answer it. A two-to-five-minute collection smoke test can establish only basic connection, snapshot/delta synchronization, timestamp capture, and write-path behavior. It cannot establish rare-gap resilience, process-restart behavior, the 24-hour connection rollover, event frequency, execution economics, or predictive value.
- The current L2 gate does not yet specify one executable event/recovery rule or numeric acceptance criteria. Do not call a short smoke test “Gate 0 passed.” First make the hypothesis, measurement window, invalidation conditions, trade geometry, and data-quality acceptance criteria operational. Only then decide whether a bounded plumbing smoke test is worth running. No signals or outcome scoring belong in that smoke test.

### Korea and United States

A read-only inventory of `/Users/user/CODE/Coin_Trade/.kis-cache-local/*.csv` on 2026-11-15 found 184 files: 92 `KR_` and 92 `US_`. All 184 files have the same six columns: `timestamp, Open, High, Low, Close, Volume`. Observed date spans across files:

- KR earliest available start: 2010-05-28; latest start: 2023-01-05. Earliest file end: 2026-08-28; latest end: 2026-11-12.
- US earliest available start: 2010-01-27; latest start: 2021-07-29. Every US file ended on 2026-11-12.

This inventory establishes the current files and schema only. The schema has no explicit corporate-action, dividend/distribution, listing/delisting, permanent-identifier, or historical-universe-membership fields. File presence does not prove active/inactive coverage or adjusted-price semantics. The prior reports independently document a selected/current cohort and unresolved point-in-time universe and corporate-action provenance. These data cannot decide whether a new equity strategy generalizes to the historical investible universe.

The existing KR tests already rejected/failed their stated evidence gates; the US ETF study did not meet the 20% return aspiration and was selected on exposed data, with maximum drawdown tolerance still undefined. Do not run more strategy permutations on this cache. The next useful step is read-only data provenance/coverage reconciliation. Any provider account, quote, purchase, or contact action requires separate authorization.

## Required decision-value contract for any next test

Before a test or collection begins, its one-page preregistration must state:

1. The exact unresolved decision the result can change.
2. Prior findings that motivate the hypothesis and why it is not a renamed failed rule.
3. Exact point-in-time inputs, timestamps, and how completeness/survivorship are established.
4. Frozen entry, invalidation/stop, target, expiry, overlap, and no-signal behavior where trading outcomes are evaluated.
5. Fees, spread, slippage, funding, fill assumptions, and adverse ambiguity resolution.
6. The development/calibration/evaluation boundary and how results remain unopened until the rule is frozen.
7. A minimum information threshold, quantitative pass/fail/inconclusive criteria, and a stop rule.
8. What action follows each possible result, including a result that ends the research line.

No threshold, timeframe, symbol, or model may be chosen because it looked best in the exposed results. Missing evidence must produce `BLOCKED` or `INCONCLUSIVE`, not a relaxed threshold or another sweep.

## Immediate next actions

1. **Crypto:** specify a single measurable L2-resilience hypothesis and decide whether its data requirements are observable with public streams. If that cannot be written without outcome-driven threshold selection, stop the L2 line before building a collector. If it can, run only a short no-signal plumbing smoke pilot with explicit acceptance criteria; keep 24-hour/restart resilience as a separate gate.
2. **KR/US:** reconcile the local files against provider provenance and the required historical universe/corporate-action fields. If local assets do not contain them, stop performance research until an authorized, suitable dataset is available.
3. **All agents:** deliver evidence-linked analysis and a recommendation before any execution. Agents must say which files/data they actually inspected and must not claim access they lacked.

These actions do not claim that 80% crypto accuracy or 20% equity CAGR is attainable. They prevent more compute and reports from being mistaken for progress.
