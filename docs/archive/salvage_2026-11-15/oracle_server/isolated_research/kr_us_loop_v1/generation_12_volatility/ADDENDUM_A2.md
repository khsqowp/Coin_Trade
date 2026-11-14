# Addendum A2 — exchange-session completeness and reporting gates

Date: 2026-11-06 (Asia/Seoul)  
Reason: independent review required an authoritative missing-session check, explicit cost-drag/holding-interval metrics, and a test that rejects unsorted dates.

## NYSE Arca session completeness — currently DATA_BLOCKED

SPY is listed on NYSE Arca. No authoritative NYSE Arca session-calendar artifact is present in the local research mirror, and neither `exchange-calendars` nor `pandas-market-calendars` is installed in the isolated Python environment. No exchange-session dates have been inferred from weekdays, price-file gaps, or observed bars. **The current candidate attempt is DATA_BLOCKED and must not be run.** This is a data-provenance/completeness block, not a strategy rejection and not evidence about returns.

Before any future root GO, an authoritative calendar file covering the entire candidate price interval must be supplied and frozen by SHA-256, together with its source/provenance and coverage dates. The runner will compare the normalized, unique, strictly ascending SPY date index with the exact expected NYSE Arca session dates in that coverage interval. It rejects multiple source timestamps that normalize to the same session date before comparing against the calendar; it does not treat set equality as permission to collapse duplicate rows. Any missing or unexpected session is `DATA_BLOCKED`; no rows may be silently dropped, filled, sorted, or relabeled. If a validated pinned calendar cannot be obtained, the correct terminal status remains `DATA_BLOCKED` and no performance result exists.

For this reason, the preregistration's historical-performance language is narrowed: the local mirror is an exploratory Yahoo-derived snapshot whose session completeness is **unverified**. Until the calendar gate passes, the data cannot even support the planned descriptive performance screen. A failed calendar gate is never entered into strategy pass/fail statistics.

## Required reporting fields

For every descriptive window, report gross (pre-cost) and net (after-cost) candidate metrics on the identical target/exposure path, along with the net-minus-gross total-return difference in percentage points and terminal wealth shortfall fraction attributable to costs. The gross comparison removes only transaction-cost multipliers; it does not change any signal, target, or holding path. Include `completed_open_to_open_holding_intervals`, counted as intervals whose beginning-open exposure was positive and whose ending open is observed, and distinguish that from trade/rebalance-event counts. Include total traded notional and fee rate so reported drag can be audited.

## Test requirement

Add synthetic unsorted-date and same-session-multiple-timestamp inputs and require fail-closed rejection before signal calculation/calendar acceptance. Keep both separate from the existing exact-duplicate-date test. The authorized synthetic lifecycle test may use a date fixture only to exercise exact-calendar matching; such synthetic calendar input is not evidence that the missing authoritative NYSE Arca file exists.

No market-price values have been read or performance statistics computed while preparing this addendum.
