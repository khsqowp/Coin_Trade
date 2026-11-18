# Micro-first research and R019 gate audit — 2026-11-19

## Scope and decision

This is a dated status reconciliation. It does not amend the frozen R018/R019 preregistrations, select a strategy, or authorize market-label access. R018 remains rejected. R019 has partial synthetic-method passes, but its full gate remains incomplete. The next research stage remains synthetic-only and must be single-candle-first; no macro or higher-timeframe filter is included in that first stage.

No market outcomes, target/stop labels, realized returns, M2 labels, or directional labels were queried for this audit. Focused synthetic unit tests were run only.

## Micro-first record

Existing records already cover the earliest candle steps; they are not independent OOS evidence because the history was previously exposed.

| Stage | Recorded result | Decision |
|---|---|---|
| One completed 1m candle → next 1m close direction | Phase 0 was a UP/DOWN/FLAT diagnostic, not a trade. Pooled accuracy: per-symbol training majority 48.17%, reversal 47.98%, persistence 45.44%. | Do not call it M2 or PnL evidence. Do not rerun against the same labels as independent confirmation. |
| One-candle close-location | All-issued M1 accuracy 46.28%; deterministic random baseline 47.88%. | Reject; no edge demonstrated. |
| Existing two-/three-candle candidates | Recorded coverage: 1.059%, 1.5108%, and 3.3518%, all below the fixed 10% coverage screen. | Reject before M2; do not tune or widen these same candidates. |
| Existing 10m/15m Phase 8 cells | All eight registered cells passed outcome-blind frequency eligibility but failed M2 and cost-adjusted screening in their existing report. | Rejected; not independent OOS. |

The next market study, if later authorized by all method gates, must be one frozen 1m claim with explicit signal time, next-bar entry, stop, target, 10/20-minute deadline, all-issued denominator, and a predeclared comparator. Higher-timeframe or macro filters are prohibited at this first stage. Wider patterns/timeframes require a separate preregistration after the preceding stage passes.

## R018 and R019 inference status

### R018

R018 paired-inference calibration remains **REJECT** because Profile B at the 20-calendar-day block had a 95% Wilson upper bound of 6.0614%, above the frozen 6% limit. This failure is not removed by other passing cells and must not be tuned away.

### R019-N and R019-P

- R019-N A/B/C synthetic null calibration reports 5,000 panels per profile, 1,999 multiplier draws, and the registered 1/2/5/10/20-day scales. The frozen all-scale/two-baseline intersection met its registered familywise gates. Individual-scale diagnostics did not: at the 20-day scale, standalone family error was 12.90–13.92%. No single scale is validated for standalone inference.
- R019-P alternative and partial-null reports record their registered synthetic gates as passed. These are method simulations, not strategy performance. The full-rule promotion rate at true candidate M2=0.80 and baseline=0.50 was approximately 49.6–50.6%; there was no preregistered minimum-power gate. The registered 80% point-estimate rule does not establish that the true market M2 exceeds 80%.
- R019-P missingness diagnostics have zero eligible claims and zero paired coverage in all five applicable missingness cells. These are not passes and show that the frozen fail-closed method is unusable under those simulated missingness conditions.
- The R019-P report claims archive SHA-256 verification, but no independent expected-hash sidecar or manifest field was found for `r19p_panels.tar.gz`. A currently computed hash alone would only establish a new baseline; it cannot retrospectively prove the archived bytes match the original run.
- Preregistration files and the R019-N report contain registration-time status wording that is now stale (for example, “not run” or R19-P listed as future work). This dated audit records current status without editing the frozen preregistration or prior reports. The R19-P preregistration also says “six” missingness cells while only five are applicable; Profile A common-shock missingness is structurally inapplicable.

Therefore **market-label access remains closed**. Remaining gates include an integrated synthetic OHLC execution-path review, resolution of archive/preregistration provenance gaps, independent review of exact runner/config/manifests, and a preregistered one-candle-only study calibrated to its exact claim family. Passing existing low-level tests does not waive these gates.

## Synthetic tests run in this audit

Command scope: existing unit tests only; synthetic fixtures; no source DB opened.

- `test_crypto_divergence_engine.py` and `test_crypto_divergence_robustness.py`: **31 passed**. Covered complete-minute aggregation, entry handling, same-bar stop-first ties, adverse/favorable gaps, missing paths, cost reduction, causal prefix behavior, and robustness helpers.
- In the prior audit turn, `test_crypto_r019_block_multiplier_calibration.py`, `test_crypto_r019_power_missingness.py`, `test_micro_candle_m2.py`, and `test_crypto_divergence_robustness.py`: **33 passed**.
- In the prior audit turn, cleanup/data-quality focused tests: **14 passed**, and `test_micro_pattern_feasibility.py`: **1 passed**.

These are focused unit tests, not the complete repository suite, not the full R019 simulation, not an integrated end-to-end R019 OHLC-path gate, and not a market backtest.

## Data-cleanup and repository boundaries

The primary `/Users/user/CODE/Coin_Trade` checkout contains user-owned, uncommitted cleanup changes. Its repair reports state that 14,400 missing SOL/XRP minutes were stored in a separate patch and merged into `vision_dev_repaired.sqlite`; the original `vision_dev.sqlite` remains the historical input. The 100-symbol `candles.sqlite` has structural consistency over its observed spans but lacks proven PIT universe and complete page-level lineage. A known collector edge case remains: after an empty page, `page_number` is not incremented before a later missing range, potentially colliding with the `(collection_id, page_number)` primary key. The current tests do not exercise that multi-range sequence.

No database was modified by this audit. No cleanup files were staged, committed, or pushed. The separate research worktree has no tracked source changes; its large untracked R018 panel outputs are preserved.

## Stock/ETF research status

The Korea and US agents found no candidate ready for a strategy backtest. Korea still requires data-use rights, adjustment/distribution treatment, reproducible vintage, and execution-cost evidence for a single ETF path. US requires licensed OHLC, point-in-time membership including delisted securities, corporate-action handling, and costs. The user-fixed per-market gates remain net CAGR ≥20%, MDD ≤30%, Sharpe ≥1, and at least 200 closed OOS trades. Neither market has a demonstrated pass.

## Next authorized research action

1. Independently review the synthetic path resolver against a scalar OHLC oracle for next-bar entry, long/short symmetry, gap-through stops, same-bar two-sided touches, fees/slippage stress, timestamp gaps, and deliberately injected future-peeking.
2. Preserve the R018 failure and R019 registered artifacts unchanged; add a separate immutable reconciliation record for any missing archive hash, runner, config, or preregistration hash evidence.
3. Only after those method/provenance gates pass, preregister and run an outcome-blind eligibility/frequency screen for one 1m claim. Do not open market labels until the exact claim family and its inference gates are independently approved.

## Follow-up — synthetic entry-path guard

An independent review found that `evaluate_divergence_event()` accepted a next-native-bar open that disagreed with the corresponding raw 1m execution open. The backtest currently derives both from the same source, but a mismatched caller input could otherwise be scored against a different execution path. The engine now fails closed as `unresolved` for that mismatch, with a synthetic regression test. The focused engine + robustness suite passes **32 tests**. This closes only that specific integrity gap; it is not the full integrated R019 matrix, does not test market labels, and does not unblock the R019 or strategy study.

Still required before any market-label study: synthetic long/short gap and tie integration, boundary/interior missing timestamps and malformed OHLC, exact registered base/stress-cost arithmetic, timeout semantics, full execution-path prefix/future-peek checks, and independent R019 archive/config provenance reconciliation. The first market hypothesis must remain a single completed 1m candle with no macro or higher-timeframe feature; prior Phase 0 and Phase 4–8 outcomes are exposed development evidence and cannot be reused as independent confirmation.

## Follow-up — integrated synthetic path checks

Added `chart_predictor/tests/test_crypto_event_path_integration.py`, which compares the production event evaluator to a separate scalar OHLC oracle for long/short target and stop touches, adverse/favorable gaps, same-bar stop-first ties, timeout, missing entry/interior/tail minutes, duplicate/unordered timestamps, malformed OHLC, and exact base/stress cost arithmetic. It also checks stop-entry trigger timing for long and short paths. Together with the engine and robustness suites, **55 synthetic tests pass**. The malformed-OHLC case exposed a real failure: the lower-level resolver returned `unresolved` with no exit price, then the wrapper attempted net-R calculation and raised `TypeError`; the wrapper now preserves the unresolved state. The next-open native/raw price mismatch guard from the previous follow-up remains covered.

This is still a partial method gate, not the complete R019 qualification: all registered timeframe/horizon combinations, deliberate signal-feature future-peek injection, and archive/config/preregistration provenance reconciliation remain open. The independent data review found the 100-symbol DB is a short 2026-07–10 development span with no taker-side/depth/funding/mark fields; the repaired six-symbol long-history data has taker aggregates and repair lineage but no point-in-time contract membership, historical funding, or mark-price series. Both are previously exposed and must not be represented as independent OOS. The next permissible market-data action remains one preregistered 1m hypothesis with outcome-blind frequency/causal gates first; no candidate currently clears novelty review.
