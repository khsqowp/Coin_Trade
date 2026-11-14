# Addendum A2 — allow explicit no-order rows in portfolio validation

Timestamp: 2026-11-06, before the next rerun.

## Finding and impact

The A1-corrected run `GEN05-20261106T102632-99205` failed both markets before simulation because its portfolio-bound preflight required every target cell to be finite. In A1, all-NaN rows intentionally encode no-order days, as specified in Addendum A1. These are not invalid weights. Both market failures are retained as implementation/preflight failures; neither is a strategy result.

## Correction

Validation now accepts only two row shapes: a complete finite target vector on a registered rebalance date, or an all-NaN no-order row between rebalance dates. Partial-NaN rows fail. Long-only, finite-weight, and gross exposure checks apply to complete order rows only. The strategy rule and execution semantics are unchanged.
