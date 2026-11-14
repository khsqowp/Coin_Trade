# Addendum A2 — runner parity and execution-safety corrections

Date: 2026-11-06. No preregistered candidate execution had completed when this addendum was made.

The initial loader and synthetic smoke checks exposed a pandas 3.x API incompatibility in true-range construction. Independent review also found mismatches in the KAMA efficiency-ratio units and ATR lookback, the persistence exit rule, the execution-frequency description, and drawdown initialization. These defects invalidate any candidate output from the initial runner version; no completed candidate output exists.

Corrections before the first candidate execution:

- Compute KAMA ER from absolute 20-session percentage return divided by the sum of absolute daily percentage returns; this is scale invariant and matches the amended preregistration.
- Use ATR20 in `ATR_NORM_SMA100`; retain ATR14 for explicitly ATR14-based candidates.
- Implement `PERSIST63` with the registered 60% entry and 50% monthly exit hysteresis.
- Make the registered monthly evaluation contract explicit: indicator/rank/overlay entry and exit rules are sampled only at month-end and fills occur at the next open. The daily gap event remains the sole daily exception.
- Construct true range using NumPy elementwise maximum to avoid removed pandas `groupby(axis=1)` behavior.
- Include initial equity 1.0 when calculating maximum drawdown.
- Use population variance consistently for the residual-momentum beta covariance window.
- Give every runner invocation a unique run ID and separate manifest, attempt log, and curve output. A market load or benchmark failure emits one failed attempt per preregistered candidate for that market; it cannot silently abort the remaining ledger.
- Reject a benchmark if its IS metric is not valid before executing candidate tests.

The candidate roster and thresholds are unchanged. The runner and preregistration hashes are captured per run immediately before execution. Attempts from the initial preflight are preserved in `attempts_preflight.jsonl`; they are not counted as completed candidate tests.
