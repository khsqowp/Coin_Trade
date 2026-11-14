# Addendum A1 — derived adjusted-OHLC floating-point tolerance

Recorded: 2026-11-06 12:42 UTC (Asia/Seoul). This amendment was made after independent pre-run review and before any candidate-period performance values were read.

## Reason

The frozen preflight requires valid adjusted OHLC ordering, but applying the per-row `adjclose/close` factor can create a roundoff-only ordering excess of approximately `1.82e-16` on the local SPY snapshot. A strict bitwise float comparison would reject a mathematically ordered bar due only to multiplication rounding.

## Narrow change

- Keep raw OHLC ordering checks strict and unchanged.
- For derived adjusted OHLC only, accept ordering when any excess is no greater than `1e-12 * max(1, abs(actual), abs(required))` for that row. Larger discrepancies still fail closed.
- No indicator, signal, price source, execution, fee, holding horizon, window, or metric definition changes.
- The original frozen `RUN_ID` is superseded without execution. New attempt ID: `GEN11A1-20261106-SPY_VOL_BURST_MOM5_H5`.
- New runner/test/prereg/data hashes are written to `FREEZE_A1.json` after the amended tests pass. No parameter variants or second attempt are allowed.

This does not establish price-data correctness or vendor provenance; it only avoids a false rejection from machine precision in derived values.
