# Phase 4 M2 denominator clarification — 2026-11-19

This addendum clarifies reporting only. It does not alter the frozen Phase 4 signal, execution rule, barriers, costs, dates, result JSON, or rejection decision.

## Evidence and governing definition

The product contract in [`SPEC.md` §5](../chart_predictor/SPEC.md) makes M2 the primary all-issued-signal target-first measure, keeps unresolved paths separately visible, and applies a path-resolution gate. The Phase 4 preregistration said “all emitted signals with resolved outcomes,” while the result JSON persisted both `target_first` (resolved-only fraction) and `target_first_all_issued_conservative` (target-first count divided by all issued signals). That wording left the primary denominator ambiguous even though both numbers were recorded.

For consistency with the user-confirmed all-issued M2 definition, report `target_first_all_issued_conservative` as the Phase 4 all-issued denominator rate. Keep unresolved paths separately reported as `UNRESOLVED_DATA`; do not reinterpret an individual unresolved path as a known stop or timeout. The resolved-only rate remains a labeled sensitivity. The JSON's legacy field name “conservative” describes the denominator calculation, not a new outcome label.

## Reconciled primary results

| Horizon | Issued | Resolved | Unresolved | All-issued M2 | Resolved-only sensitivity |
|---|---:|---:|---:|---:|---:|
| 10 minutes | 75,349,453 | 75,349,399 | 54 | 47.9771977% | 47.9772320% |
| 20 minutes | 75,347,346 | 75,347,237 | 109 | 49.3788102% | 49.3788817% |

The M2 verdict is unchanged: both all-issued rates are far below the fixed 80% target, and the original report records negative cost-adjusted mean net R. The missing-path fraction is tiny in this archive, but the already-exposed dataset is not sealed evidence. No additional performance run was made.

## Required interpretation

- The original result JSON and preregistration remain immutable historical artifacts.
- The main result table should identify all-issued M2 separately from resolved-only sensitivity; these values must not be collapsed into a single unlabeled rate.
- The Phase 4 rejection stands before any Monte Carlo or parameter-plateau work. This clarification does not reopen that strategy family.
