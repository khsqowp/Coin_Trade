# Independent candidate/readiness review — third backtest role

Checked 2026-11-07. This was a read-only readiness/candidate review. No new price-value read, signal calculation, return calculation, or performance run was made.

## Decision

There is no responsibly runnable new performance candidate in the currently frozen queue. Proceeding anyway would require either reopening a terminally failed attempt, bypassing an explicit calendar/PIT gate, or repeating a consumed one-run candidate. None is valid research progress.

## Candidate disposition

| Candidate | Current evidence | Decision |
|---|---|---|
| Gen12 US PIT monthly loser reversal, bottom decile | Preregistration required at least 85% date-row coverage for every tested month. Existing metadata-only preflight reports 285/405 months below that threshold and 120/405 passing. The current local file/universe comparison independently shows 715 matching PIT tickers out of 1,209; 494 missing, 22 extra files. No runner or tests exist. | Do not issue GO or rerun. `FAILED_DATA_COVERAGE` is terminal for that input snapshot; it is not evidence against the strategy. Requires a new, reconciled snapshot and new registration.
| Gen12 SPY/Fed tightening overlay | No frozen complete policy-event table including exact verified release timestamps/no-change decisions, no runner, and no independently pinned complete exchange session calendar. Local SPY is Yahoo-derived and not independently audited for corporate actions. | `DATA_BLOCKED`; collect and reconcile event/calendar/price evidence before reviewing a new execution freeze.
| Gen13 SPY DMI14/Choppiness14 hysteresis | Rule and synthetic tests are frozen; its gate explicitly requires an authoritative calendar matching the SPY date index. The local repo contains no such historical calendar file. | Do not read price values or run this candidate until calendar gate is satisfied. No threshold relaxation or substitution of observed bars as the calendar.
| Gen11 SPY ETF dual momentum | Its one authorized execution failed with nonfinite overflow/serialization; the one-run allowance is consumed. | No patch-and-rerun. A corrected implementation requires a genuinely new candidate/registration and fresh review; it cannot inherit the old result.
| Gen11 sector breadth and volatility-burst trend | Fixed rules were tested and rejected against matched SPY under their stated exploratory comparisons. They are not independent confirmations, and reported partitions are already inspected. | Preserve outcomes in the ledger; do not relabel them as new or OOS winners.

## New-family screen

The remaining local daily OHLCV candidates recorded in `FEASIBILITY.md` either repeat dependent momentum/reversal/trend/volume/calendar families or require inputs absent from the mirror: PIT cross-sectional prices, verified split-adjusted volume, corporate-action/delisting proceeds, fundamentals/event timestamps, or an independent market-session calendar. The proposed ORB route requires minute data not present locally. Reusing SPY alone is possible for exploratory single-instrument hypotheses, but not enough to satisfy the mission's KR/US PIT, untouched-OOS, or multiplicity-corrected success criteria.

## What would make a next backtest executable

1. Acquire a licensed, retention-compatible PIT price + delisting/corporate-action dataset and authoritative membership history; do not substitute surviving tickers or reweight around missing names.
2. Obtain a validated complete KR/US benchmark/total-return series and historical exchange calendars independent of the price file.
3. Reserve genuinely prospective untouched data or begin forward paper observation; previously inspected historical partitions cannot be turned back into virgin OOS.
4. Reconcile the global historical trial count and family dependencies before any significance claim.
5. For each new candidate, lock the exact rule, inputs, code/tests, and attempt identity before accessing performance values. Preserve every failure and do not reopen terminal attempts.

## Scope boundary

This review does not conclude that a profitable or useful strategy cannot exist. It concludes only that currently frozen candidates are blocked or already terminal on the available snapshot, so no honest new performance verdict can be produced before fixing the input gates.
