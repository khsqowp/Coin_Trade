# Generation 07 preregistration addendum A1

Registered after the first exploratory run and before the corrected rerun; 2026-11-06 Asia/Seoul.

The original preregistration `PREREG.md` and first run artifacts remain unchanged. The first runner's coverage denominator counted only PIT members with local price files, not every PIT member active on the decision date. This made its 85% gate materially too permissive. In addition, the shared month-end helper can treat the dataset's final, incomplete calendar month as a decision month. The first run also allowed an all-cash strategy caused by unavailable signal coverage to finish as a completed test.

## Corrections, frozen before rerun

1. Coverage denominator is the count of all PIT S&P 500 constituents active on each decision date, read from the registered membership file. Numerator is the number of these constituents with a locally available finite AB_NR score and existing loader eligibility. Names without local price history remain in the denominator.
2. Month-end decisions include only months strictly earlier than the final observed calendar month. The trailing month is excluded, even if it has 15 or more observed sessions; this prevents a partial month from being called a completed formation month.
3. A month below 85% full-universe signal coverage targets cash as preregistered. The attempt fails as insufficient evidence only if no completed decision month passes the coverage threshold. Cash months remain included in portfolio returns.
4. Failed attempts set a failed manifest outcome and non-zero process exit status. Successful runs state that data hashing is non-atomic (hashes follow loading) and therefore do not prove that inputs could not change during load.
5. The strategy, portfolio, costs, signal, threshold, benchmark, and periods are unchanged. No rule is tuned from the first observed performance result. The corrected run remains exploratory because its historical periods were already inspected and PIT price coverage / full trial count remain unresolved.

The first run is retained for audit but is invalid for interpreting the 85% coverage-gated strategy. The corrected rerun supersedes it only for execution-mechanics and descriptive screening; it is not confirmatory evidence.
