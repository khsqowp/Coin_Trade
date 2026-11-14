# Addendum A5 — corrected run and data-quality disclosure

Recorded after the month-end-state code review finding and corrected full rerun.

- The initial `RESULTS.md` refers to run `GEN01-20261106T090344-73306`. Stateful candidates in it are superseded for preregistration parity; preserve its ledger and curves, do not erase or silently replace them.
- The corrected run `GEN01-20261106T092112-99213` completed 22/22 candidate-market attempts with a new immutable ledger and curves. Human-readable metrics are in `RESULTS_CORRECTED.md`.
- The corrected KR loader still emits `divide by zero` and `invalid value` warnings from split-adjusting volume (`run_gen01.py:55`). Treat volume-derived inputs as unverified until affected observations and downstream feature dependencies are audited. This warning does not itself establish that price returns were corrupted.
- There are 56 locally recorded candidate-market executions across the initial Gen01 run (22, later superseded for six stateful candidates), corrected Gen01 (22), and Gen02 (12). Superseded attempts still count as exposure to observed results and must not be erased from selection history. This is not the complete historical count; no global DSR/PSR or multiplicity-adjusted result follows from 56.
- Independent red-team reproduced a data-corruption defect in the shared KR split-repair path using `008080.parquet`. Therefore every KR result from both Gen01 runs and Gen02 is retained only as a failed data-integrity attempt, not as strategy-performance evidence. Gen03 must block KR market execution until the repair path and affected raw panels are audited; continue with US only if its own setup passes.
- No post-hoc threshold changes or candidate tuning were made in either corrected Gen01 or Gen02. All recorded results are exploratory, not a validated investment strategy.
