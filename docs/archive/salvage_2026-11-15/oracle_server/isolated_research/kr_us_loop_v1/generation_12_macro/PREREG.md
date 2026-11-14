# Generation 12 — US monetary-policy tightening regime overlay

Status: **preregistered proposal; awaiting independent review and explicit root GO. No SPY price values, signals, returns, or performance statistics were read or calculated for this candidate.** This is one fixed rule, not a parameter sweep and not an investment recommendation.

## Hypothesis

When the Federal Reserve has raised its announced policy-rate target materially over the trailing year, broad US equity exposure may have an unfavorable risk profile. A mechanical exposure reduction during that tightening regime may improve the net risk/return profile of a broad-market position. The rule is falsifiable: it fails if it does not improve both net CAGR and net Sharpe over SPY buy-and-hold in every prespecified reporting window. A positive descriptive result would still not prove a durable or deployable edge.

## Candidate identity and scope

- Candidate ID: `GEN12-US-FED-TIGHTENING-12M-SPY-CASH-1X`
- Market: US only. Korea is excluded from this candidate; do not infer a KR result from it.
- Instrument: SPY only, long-only or cash; no leverage, shorting, selection, or discretionary override.
- Family: scheduled macro-policy regime overlay. It is distinct from price-derived SMA/breadth gates, cross-sectional momentum, sector rotation, and fixed overnight timing, but is related to the previously catalogued FOMC exposure-filter idea. Count prior FOMC-overlay research as dependent evidence in any multiplicity accounting.
- Signal source: official Federal Reserve FOMC policy-decision statements and announced target rates. No market-implied expectations, revised macroeconomic series, or hindsight event labels.

## Frozen policy-state rule

1. Maintain the Federal Reserve's announced target rate as a dated event series. For decisions before the target-range era, use the announced federal-funds target. For target-range decisions, use the arithmetic midpoint of the announced lower and upper bounds. Do not splice in the realized effective federal-funds rate.
2. At each scheduled FOMC policy decision, compare the target value announced at that decision with the latest target value announced on or before the calendar date exactly 365 days earlier. If no such prior observation exists, the state is `UNKNOWN`.
3. Set state to `TIGHTENING` only when the current target is at least 0.50 percentage points higher than the comparison target. Otherwise set state to `NOT_TIGHTENING`. An `UNKNOWN` state is held in cash. The 50-basis-point threshold and 365-calendar-day lookback are fixed; no alternate thresholds or windows are allowed in this candidate.
4. The new state becomes effective at the first SPY regular-session open strictly after the official statement publication timestamp. The position remains unchanged between FOMC decisions. If the statement timestamp, date, rate, or next-session mapping cannot be verified, fail closed and do not fabricate an event or trade.
5. In `NOT_TIGHTENING`, target 100% SPY. In `TIGHTENING` or `UNKNOWN`, target 100% cash. Apply exposure changes only at that next regular-session open. Do not use the decision-session close or same-day SPY return to set the state.
6. At the final scored session, liquidate at the final observed regular-session open so the candidate and benchmark endpoints match. No signal is inferred beyond the last validated event.

## Execution, costs, benchmark, and windows

- Score daily open-to-open intervals. At each regular-session open, the target exposure set by previously published policy information is active for the interval through the next regular-session open. Derive SPY adjusted-open prices as `raw_open * adjclose / raw_close`; stop on non-finite/non-positive prices, invalid OHLC bounds, duplicate or non-ascending dates, or unexplained missing observations. Do not forward-fill.
- Charge 10 basis points of traded SPY notional on every entry, exit, or exposure change, including initial entry and final liquidation. Cash earns zero; no margin, financing, tax, dividends beyond the SPY adjusted series, or interest on idle cash is credited. This is a fixed-cost exploratory convention, not a claim about realized fills.
- Benchmark: 100% SPY adjusted-open buy-and-hold over exactly the same scored open-to-open intervals, with 10 basis points at initial entry and final liquidation. This is an unlevered but not risk-matched benchmark.
- Report the mechanically available full period and fixed descriptive partitions `2001-01-01..2016-12-31` and `2017-01-01..last complete common interval`, recalculating each partition's starting equity and drawdown. These periods are already inspected and are not untouched OOS.
- Report net CAGR, annualized Sharpe (252; sample standard deviation), maximum drawdown including initial equity 1.0, cumulative return, exposure, policy-state durations, entries/exits, and turnover, with matched benchmark values. Report every window, including failures; no ranking-based selection.
- Candidate rejection rule: reject this fixed rule for the stated objective if either net CAGR or net Sharpe fails to exceed matched SPY buy-and-hold in any reported window. If it passes descriptively, classify it only as a lead pending a genuinely prospective holdout, licensed/corporate-action-audited data, and reconciled cumulative trial counts. No DSR/PSR/BH significance claim is authorized by this candidate preregistration.

## Data integrity and leakage gates

- Before any price-value access, independently review this rule and the future runner/tests, freeze their hashes, and issue explicit root GO. This document alone is not GO.
- The event table must contain the publication timestamp, meeting classification (scheduled FOMC decision), announced target/range, source URL/document identifier, and an immutable source snapshot/hash. Include unscheduled target changes only if separately predeclared; this candidate excludes them.
- Event timestamps must be interpreted in `America/New_York`; SPY sessions use an authoritative US exchange calendar. Apply the event only at the first regular-session open strictly later than publication. Same-day publication before open still maps to that day's open only if it is strictly later; otherwise map to the next session. No date-only approximation for a statement whose time is unknown.
- Require a complete sequential event history sufficient to compute the trailing 365-day change and a verified SPY price/calendar snapshot. Do not infer missing FOMC events from price moves, fill missing rates, or remove inconvenient events.
- The local candidate directory currently contains no frozen FOMC policy-event table. Consequently this proposal is not yet runnable and no performance test is authorized. Data availability, event-table completeness, and provenance must be resolved without inspecting SPY price values before the independent review/GO gate.

## Multiplicity and interpretation

This is a single exploratory trial. It is conceptually related to the previously catalogued FOMC filter, broad-market trend filters, and cash overlays; it is not independent alpha evidence. The exact historical cumulative trial count remains unresolved. A descriptive pass must not be called statistically significant or generalized to KR. A failed, blocked, or invalid run is recorded separately and is not silently relabeled as a strategy rejection.
