# Generation 12 macro candidate status

## Candidate

`GEN12-US-FED-TIGHTENING-12M-SPY-CASH-1X`, specified in `PREREG.md`.

## Current state

- Rule and decision boundaries are fixed in writing.
- No price values, signal series, return series, or performance metrics were accessed or generated for this candidate.
- The required frozen, timestamped FOMC policy-event table is absent from this candidate's local artifacts; candidate is **data-blocked**.
- This is not a strategy rejection. There is no result to interpret.
- No runner has been implemented or authorized. Next gate: independent review of the exact rule and any proposed event/price inputs, then explicit root GO before performance-data access.

## Distinction from earlier work

Earlier research already includes price-derived market filters, momentum/low-volatility switches, breadth gates, sector rotation, and a catalogued intraday FOMC time-window overlay. This candidate tests a different mechanism: a slow, trailing policy-rate-change state whose effective exposure changes only at the next regular-session open after an announced scheduled FOMC decision. It remains related macro-overlay evidence, not a wholly independent strategy family.
