# Addendum A4 — monthly-state correction and rerun

Date: 2026-11-06. This addendum supersedes Generation 01 attempt results for any strategy whose position state used entry/exit hysteresis.

After the initial 22 candidate-market runs, an independent review found that `stateful()` updated HMA, OLS breakout, ATR-normalized, VHF, PERSIST63, and ATR-buffer position states every day, while the preregistration says all those signals are evaluated only at month-end. The monthly target sampler therefore inherited intra-month state changes. Those run results are preserved for audit but are **invalid for the preregistered monthly-only rules** and must not be used to promote or reject those strategies.

The runner now changes those position states only on month-end decision dates. It also rejects missing/non-finite US SPY daily returns after the initial observation instead of silently substituting zero. The original run's manifest, log, and curves are not overwritten. The corrected rerun must use a new unique run ID and preserve all 22 previous executions in the multiplicity history. Every new execution and failure is separately logged. No confirmatory claim is possible on the already inspected periods.
