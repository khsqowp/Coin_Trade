# Generation 12 implementation and review plan

Status: planning only. No candidate runner or performance execution has been created. Proceed to implementation only after the root reviewer approves `PREREG.md` and records GO.

## Scope

Implement one US-only monthly long-only stock reversal screen exactly as frozen in `PREREG.md`. Reuse audited local project mechanics where possible; do not copy results or silently inherit a candidate rule from another generation. Keep the candidate code, synthetic tests, manifests, ledger, and any results in this directory. Do not alter existing generation files or shared loaders as part of this candidate. If a shared dependency needs modification, stop and report the required diff for separate root approval.

## Build sequence after root GO

1. **Freeze the source boundary.** Record SHA-256 hashes for the preregistration; candidate runner and tests; the exact existing membership parser, US price loader, strict simulator, metric functions, cost constants, and all transitively imported source files. Record Python, NumPy, pandas, and PyArrow versions. No output path may point to the Oracle host or a live-trading module.
2. **Freeze the data manifest.** Hash the complete local PIT membership file, SPY parquet and metadata, each active PIT member's local parquet and metadata when present, and a sorted manifest of absent files. Include file size and explicit snapshot root. Do not inspect remote state or refresh data during the attempt. A non-atomic source copy remains labeled non-atomic.
3. **Write deterministic pure functions.** Keep signal logic separated from IO and simulation:
   - parse/sort PIT membership spells and resolve the active unique ticker set as-of each observed month-end; reject invalid or overlapping membership spells;
   - derive complete observed month-end dates from the benchmark/session calendar, excluding the initial partial and final incomplete calendar month;
   - for each active ticker and month, compute the one-month adjusted-close return only if both exact month-end dates have finite positive observations; never fill missing prices;
   - calculate coverage using every active PIT member as denominator, including missing files/values; fail the attempt before signal ranking or return simulation when the frozen 85% monthly gate is violated;
   - rank valid scores ascending with normalized ticker as tie-break and select exactly `ceil(0.10 * scored_names)`; create equal weights summing to no more than 1.0, or cash if no scored names;
   - emit sparse close-time target rows; pass them to the approved next-open simulator so no same-close fill is possible.
4. **Build synthetic-only tests.** Tests may use handcrafted frames but must never load `data_mirror/`. Verify month-end alignment, no lookahead, no forward fill, missing-member denominator behavior, coverage fail-closed, deterministic ties, exact ceil decile selection, zero-score/cash behavior, long-only/gross bounds, next-open application, held/entry OHLC failure, costs on buys and sells, benchmark interval matching, terminal liquidation, incomplete-month exclusion, and JSON serialization with non-finite values rejected.
5. **Independent static review.** A second reviewer checks the frozen formulas, membership boundary logic, signal/fill timing, row shapes expected by the simulator, coverage denominator, cost conventions, terminal interval, and that tests are synthetic-only. Root independently verifies all hashes and decides GO / NO-GO.
6. **Pre-attempt gate.** Before one approved attempt, run only syntax/unit tests and verify exact code/preregistration hashes. Create a unique run ID and append the `attempt_start` event durably before any market-value read. A prior attempt artifact, existing candidate output, hash mismatch, or review not GO prevents execution.
7. **Single attempt.** Load and fingerprint the local snapshot. Run the full-universe coverage/integrity audit first. If the coverage gate fails, append `FAILED_DATA_COVERAGE` and do not generate portfolio returns. If it passes, compute the single frozen signal and one simulation. Append exactly one terminal completion/failure record; do not rerun or tune.
8. **Output and verify.** Save machine-readable metrics, daily net-return/turnover/exposure curve, input/source manifests, and concise `RESULTS.md`. Reopen outputs and verify hashes, finite JSON, one attempt ID, matching row counts, no unrecorded candidate variants, and agreement of independent metric calculations. Any infrastructure/serialization/data-gate failure stays labeled as such, not as a candidate rejection.

## Acceptance checklist before performance execution

- [ ] Root has explicitly approved the exact preregistration and implementation plan.
- [ ] The signal is a single previous-complete-calendar-month cross-sectional sort; no hidden second feature or parameter variant exists.
- [ ] The PIT membership denominator includes active names without local price files.
- [ ] The all-month 85% gate is evaluated before return simulation and cannot be bypassed by shrinking the universe.
- [ ] Missing observations are never forward-filled, sorted into compliance, or treated as zero returns.
- [ ] Every signal is known at month-end close and first affects holdings at the next observed open.
- [ ] Synthetic tests cover causal timing, selection, coverage, costs, benchmark alignment, strict bars, and serialization.
- [ ] All source and data hashes, including missing-file states, are frozen in the manifest.
- [ ] Exactly one start and one terminal ledger event exist for the only candidate ID; failures remain failures.
- [ ] No remote operations, live orders, commit, push, parameter search, or post-result edits occur.

## Static evidence consulted (no market-value execution)

- `generation_05/PREREG.md`, `generation_05/run_gen05.py`, and `generation_05/ADDENDUM_A2.md` for the strict monthly simulator, target-row conventions, and corrected no-order validation.
- `generation_07/PREREG.md` and `generation_07/RESULTS.md` for PIT coverage denominator and missing-member pitfalls.
- `generation_11_crossasset/PREREG.md` and `generation_11_crossasset/RESULTS.md` for the related sector-ETF previous-month reversal and its non-passing result.
- `FEASIBILITY.md` for the known local US coverage, provenance, and historical-trial limitations.

These are source/document inspections only. No parquet values, strategy scores, or candidate performance were examined for Generation 12.
