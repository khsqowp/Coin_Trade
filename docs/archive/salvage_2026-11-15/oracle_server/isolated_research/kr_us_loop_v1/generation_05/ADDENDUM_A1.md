# Addendum A1 — invalidate daily-reset execution and correct monthly trading

Timestamp: 2026-11-06, after code review and before the corrected rerun.

## Finding and impact

The first implementation (`GEN05-20261106T102256-93331`) forward-filled each month-end equal-weight target to every session. The strict simulator interprets every row as a new open-order instruction, so it rebalanced daily, charged daily turnover costs, and did not implement the preregistered buy-and-hold-with-weight-drift behavior. The reported US metrics and the KR failure from that execution are retained for audit but invalid as results for the registered strategy. No performance interpretation may use them.

## Correction

- The target matrix is now sparse: only month-end close rows contain orders; other rows are NaN/no-order.
- The corrected simulator shifts a month-end close decision to the following open, charges transaction costs only at that rebalance, preserves holdings without trading on intervening sessions, and allows portfolio weights to drift with asset returns.
- Strict OHLC checks continue to fail closed for any held or entering asset with invalid/missing bars.
- A synthetic unit test now verifies no turnover between month-end order dates and turnover after a later rebalance.

No signal, lookback, eligibility, K, cost, benchmark, or performance rule is changed. The corrected runner has a new hash and run ID. The previous ledger, manifest, and curves remain unchanged.
