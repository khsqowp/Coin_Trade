# Gen12 US monthly loser-reversal audit

**Disposition: NO-GO for performance execution on the frozen local snapshot.** This is a static preregistration, status, hash, and overlap audit only. No market-price values, signals, returns, or performance metrics were opened or calculated in this review.

## Evidence checked

- `generation_12_crosssectional/PREREG.md` defines one US-only test: rank all active PIT S&P 500 members by the immediately preceding complete calendar month's adjusted-close return, select the bottom 10% (ceiling), equal-weight long-only, decide at month-end and enter at the next observed open. It fixes a full-PIT endpoint-row coverage floor of 85% in every complete tested month, 10 bp per side, and explicitly excludes parameter sweeps.
- `IMPLEMENTATION_PLAN.md` is planning-only. It specifies synthetic-only unit tests, a source/data manifest freeze, and root approval before the one allowed attempt.
- There is no candidate `run_gen12.py`, test file, or freeze manifest in this directory. Implementation and executable hash freeze are therefore not ready.
- `PREFLIGHT_RESULT.md` and `attempts.jsonl` already record a terminal `FAILED_DATA_COVERAGE` preflight for attempt `GEN12-20261106-US-PIT_MONTHLY_LOSER_REVERSAL_BOTTOM_DECILE`. The date-index-only gate found 120/405 months passing and 285/405 failing; minimum both-endpoint row coverage was 37.1663%. The preregistration's 85% threshold cannot pass on that frozen snapshot. This is a data-coverage failure, not a negative strategy-performance result.
- SHA-256 values for the current preregistration and implementation plan match the values recorded by the preflight (`5037a310…733c5` and `a1751d4f…c742a`). That does not make the candidate executable: the preflight has already terminally failed, and no runner/tests are present.
- The preflight report also records a process deviation: an initial schema-probe printed OHLC row-group min/max metadata. This review did not repeat that action and did not use those extrema.

## Duplicate / family assessment

This candidate is not a duplicate rule, but it is not a new independent alpha family. Its cross-section is individual equities and its formation/holding cadence is monthly; Gen11 ranked sector ETFs on the preceding calendar month, while US v2 X6 is a weekly bottom-50 five-session stock reversal. The exact universe and cadence differ, but all are short-horizon loser-reversal hypotheses. `PREREG.md` correctly labels the candidate correlated with prior reversal research. It must be counted as another reversal-family trial, not as independent evidence.

## GO dependencies

1. **Do not issue GO against the existing snapshot.** Its preregistered hard gate has already failed before any portfolio-return simulation.
2. Obtain and locally stage a reconciled PIT constituent-price snapshot (including absent/delisted constituents) with date coverage sufficient to satisfy the frozen every-month gate, plus the matching benchmark and corporate-action basis. Reconcile member identifiers and period coverage; do not shrink the PIT denominator to available files.
3. Treat the replacement snapshot as a new research input. Create a new preregistration/addendum and attempt ID, hash the exact data inventory and code, and disclose non-atomicity/provenance before reading price values for signals. Do not overwrite the failed preflight record.
4. Only then implement the runner and synthetic tests, obtain independent static review, freeze all transitive source/test/data hashes, and request a fresh root GO. The existing prereg hash alone is insufficient because input coverage is the failed gate.

Until these dependencies are met, the defensible work is data acquisition/reconciliation or selecting a different candidate whose required point-in-time inputs are available—not relaxing the threshold after seeing the coverage result.
