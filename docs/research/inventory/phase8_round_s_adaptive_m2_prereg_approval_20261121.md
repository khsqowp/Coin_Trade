# Phase 8 / Round S — adaptive M2 preregistration approval

Date: 2026-11-21. This file records the approval state **before** outcomes were
opened. The approved, immutable specification is
`PREREG_ADAPTIVE_SELECTIVE_M2_20261121.md` with SHA-256
`e8cf770edacc024da36cc07e04b3cbe3eed11cf668e3c9cd7c5475d2121d13bc`.

## Panel decision

The first exact-specification panel returned HOLD from Blue, Red, Data/Methods,
and Judge. One bounded clarification pass then fixed the replayed calibration
schedule, pinned funding mapping, and global non-overlap treatment for a
missing next-minute entry. A fresh independent review of that exact file
returned unanimous **`CLEAR_PREREGISTRATION`** for one exposed historical
walk-forward diagnostic only.

| Role | Decision | Scope limit |
|---|---|---|
| Blue | CLEAR_PREREGISTRATION | One fixed historical diagnostic; no Core or sealed-OOS claim |
| Red | CLEAR_PREREGISTRATION | No tuning or second optimization round after results |
| Data / Methods | CLEAR_PREREGISTRATION | Existing archive and point-in-time universe limitations remain |
| Judge | CLEAR_PREREGISTRATION | Only the frozen 2026-07-01..2026-10-01 historical simulation is authorized |

Approval did **not** authorize strategy changes, another search over
parameters, Phase 9 combination, deployment, live trading, or a claim of
predictive reliability. Core eligibility requires untouched prospective
evidence and measured execution costs.

## Frozen implementation identity

- Preflight data-record SHA-256: `9954df43e1dbc44d71d109550246b62033c1111ab0e967a6aa0a54a279cafef9`.
- Code SHA-256: `13a7d442bd00510a2c73ed23be052c347901bf078878fd75ffee3cc02879e269`.
- Test SHA-256: `6c6e92749b107d4c3c7c01ccb74089d8342eff46e1b7c44ee7e5d4d32ed6a947`.
- Frozen runtime: Python 3.13.5, scikit-learn 1.7.2, NumPy 2.2.6, pandas 2.3.3, PyArrow 21.0.0.
- Data-only preflight: 576 required Parquet inputs; the evaluation interval's full 32-symbol UTC contract/mark grids, funding alignment, and required schemas/dtypes passed; every file was hash/state checked before and after reading. Training-period minute gaps were not silently filled; only contiguous feature windows were eligible.

This is a contemporaneous approval record. The subsequent score and final
verdict are recorded separately in
`phase8_round_s_adaptive_m2_historical_diagnostic_20261121.md`.
