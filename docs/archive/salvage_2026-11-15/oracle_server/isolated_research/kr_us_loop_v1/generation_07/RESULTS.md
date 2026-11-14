# Generation 07 — AB_NR exploratory result

## Decision

**Reject this candidate as an investable/validated strategy.** The corrected exploratory screen did not beat SPY in the later inspected period and has no untouched OOS status. This rejects this fixed AB_NR implementation under this local snapshot; it does not show that no profitable strategy exists or that further search is futile.

## First run preserved but invalid for interpretation

Run `GEN07-20261106T111704-72994` completed before the red-team review exposed a denominator defect: its 85% coverage gate used only the constituents with local price files. It therefore overstated actual PIT-universe coverage and included the incomplete final calendar month. Its raw metrics remain in the ledger and manifest for audit only; they are not evidence for the preregistered coverage-gated strategy.

## Corrected rerun

Run `GEN07-20261106T112047-78406`; status `COMPLETED_EXPLORATORY`. Addendum A1 was frozen before this rerun. The attempt ledger, corrected monthly coverage audit, selected holdings, daily net returns, and manifest are retained beside this report.

- Universe: local prices for 688 of 1,209 distinct historical S&P 500 tickers; full PIT active-member count is used as coverage denominator. Input hash: `f71e1d3a3bd5e2a90e1e8cdf317005eabb4fd3e1e89d1c5cd9ccc53a37688e74` (1,378 loaded price/metadata/PIT/benchmark files; non-atomic after-load snapshot, not a hash of absent files or excluded-ticker state).
- The final observed month, November 2026, was excluded as incomplete. There were 406 completed monthly decisions. The 85% full-PIT signal coverage gate passed in 83 months, from December 2019 through October 2026. Median full-universe signal coverage was 63.9%. Before the gate passed, the strategy held cash.
- IS 2001-01-04 through 2016-12-30: strategy remained in cash (CAGR 0.00%, Sharpe 0.00, MDD 0.00%) while SPY returned 5.22% CAGR, Sharpe 0.36, MDD -55.19%. This is a data-coverage limitation, not evidence that the signal itself had zero return in that period.
- Later inspected/contaminated period 2017-01-04 through 2026-11-02: strategy CAGR 8.33%, Sharpe 0.53, MDD -39.60%, mean exposure 69.5%; SPY CAGR 14.84%, Sharpe 0.86, MDD -33.72%. The long-only strategy materially lagged SPY on CAGR and Sharpe and had a deeper drawdown.
- The strategy had 14.88 annual turnover in the later period after the existing 10 bp buy/sell assumptions. The 118-month metric window is the simulator's later period; monthly signal decisions are 406 overall and 83 meet the coverage rule. Exposure remains invested through drift between qualifying rebalance decisions.

## Verification and limitations

- Seven unit tests pass under `/private/tmp/kr-us-research-venv/bin/python -m unittest -v test_gen07.py`; `compileall` passes. A separate Python reviewer checked the corrected implementation, membership date count, trailing partial-month exclusion, and failed-attempt status handling; no rerun-blocking defect was found.
- The corrected strategy underperforms SPY in the later inspected partition, so it is rejected without searching parameter variants.
- Dataset PIT history is incomplete (688/1,209 constituents have local prices), corporate-action and delisting treatment remain imperfect, historical global trial count is unresolved, and the later period has already been inspected. No valid untouched OOS, global DSR/PSR, or multiplicity-adjusted claim is available.
- A later attempt to obtain a fresh server snapshot was blocked by local SSH network permissions. No server-side command or write was performed.

