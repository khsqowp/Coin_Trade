# Addendum A2 — unheld-symbol missing-data handling

Timestamp: 2026-11-06. Applied after the first A1 corrected-code run and before the next rerun.

## Reason

The A1 rerun (`GEN04-20261106T101019-73296`) exposed another simulator defect. It computed a vector of open-to-close returns by direct division across every symbol, so missing prices in an unheld symbol propagated NaN through `dot(target, intraday)` even though that symbol had zero weight. Both completed CLV attempts therefore reported `INSUFFICIENT` metrics and are not strategy evidence. TEMA execution for both markets also failed/was invalidated by this simulator defect or independent OHLC gaps; inspect the row-level ledger before interpretation.

## Correction

- Set intraday returns to zero for symbols with invalid bars only when their target weight is zero; held/new positions continue to fail closed on any invalid OHLC.
- Extend tests to cover invalid OHLC on an already held position and missing OHLC on an unheld symbol; run candidate simulations through the Gen04 strict simulator.
- Preserve all earlier run artifacts as failed implementation attempts. Rerun the four preregistered market-candidate combinations with new runner and addendum hashes; do not overwrite or delete any prior attempt.

No signal rule, market universe, threshold, cost, or performance criterion is changed.
