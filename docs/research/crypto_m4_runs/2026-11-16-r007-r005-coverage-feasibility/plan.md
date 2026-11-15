# R007 plan — R005 acceptance-gate feasibility audit

Status: `infeasible_as_written`; this is a pre-performance arithmetic audit, not a strategy trial.

## Question

Can R005 satisfy its frozen per-timeframe coverage gate (at least 10%) while enforcing one selected event per symbol across all directions/timeframes and suppressing every subsequent event until the previous event's full 20T horizon has elapsed?

## Frozen inputs

- Source specification: `../2026-11-16-r005-liquidity-replenishment/plan.md`, especially sections 9 and 12.
- Coverage denominator: scheduled symbol × completed-T-bar opportunities with valid feed data, including suppressed eligible anchors and abstentions.
- Refractory rule: a selected event blocks that symbol until 20 bars of its own timeframe have elapsed; cross-timeframe selection can only reduce per-T coverage further.
- No price outcomes, signal labels, threshold performance, or final partition are opened.

## Calculation

For N consecutive eligible opportunities in one timeframe and a minimum spacing of 20 bars, the maximum number selected is `floor((N-1)/20)+1`. Therefore maximum coverage is that count divided by N. The script and values are recorded in `results.json`.

## Decision rule

If the mathematical maximum is below 10%, mark the plan infeasible as written. Do not relax either rule after observing results. Any future R005 redesign must be a separately versioned, pre-label protocol and must explicitly address overlap dependence, effective sample size, and symbol/day block uncertainty.

## Data and performance boundary

No market data is read by this audit. Performance cells: zero. Strategy metrics: none. This audit cannot qualify a strategy and does not open validation or final data.
