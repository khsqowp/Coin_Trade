# Rebalance cadence study C — preregistration

Registered before computing any cadence outcome. Scope: determine whether a credible 1–72 hour comparison can be executed from the available source and data without altering existing files or contacting a live system.

## Hypothesis and decision

Primary comparison: each cadence p=1..72 hours against p=72 hours, measured on paired identical market paths and random seeds. Do not select the single best p. A shorter interval is supported only if a contiguous interval shows positive out-of-sample paired improvement after multiplicity correction, with tolerable tail/liquidation and operational costs. Otherwise classify as indistinguishable or harmful. If required data, hourly execution semantics, or baseline parity cannot be established, report the study as not identified; do not substitute a daily cadence grid and label it hourly.

## Frozen requirements

- Universe: OLD 45-symbol survivor panel; NEW 2020-03..2021-12 PIT panel including delisted symbols; OLD-PIT. Market regimes including bull, bear, sideways, crash, and 2025-10-10 flash event.
- Strategy: 14-day momentum long/short, leverage 4, deploy 0.95, TOP_K 8 each side, kill DD 0.35, 14-day cooldown, BTC 14-day -10% crash filter, retained quantity and 15% resize rule as documented by owner.
- Cadence grid: integer hours 1 through 72 inclusive. At least 8 evenly distributed phase offsets per cadence; common random streams for paired candidates.
- Baseline: first reproduce the existing V0 72-hour result and verify execution-clock semantics. If parity fails or the legacy panel is unavailable, disclose and withhold aggregate performance verdicts.
- Costs: 0.05% per side plus slippage {0, 2, 5, 10} bp. Failure-to-fill scenarios {0%, 2%, 5%}, failed leg deferred until next scheduled rebalance. Common random draws.
- Kill fidelity lambda {0, 0.15, 0.30}; report path-dependent kill divergence separately from no-kill fixed-exposure diagnostics.
- IS 2022-01..2024-06; OOS 2024-07..2026-10. Compare paired cadence deltas with block bootstrap; correct 72 cadence hypotheses by Holm. Report plateau intervals, not peak cadence. Report MDE/power before claims.
- Tail diagnostics: MDD, kill count, liquidation cushion against maintenance, hourly worst and adjusted wick model. Operational estimates: rebalance/order count, API/ratelimit exposure, failed/partial fills, minimum quantity errors, and small-account slippage; distinguish measured evidence from scenario estimates.

## Execution limits frozen before outcome access

No live code/config/container/order changes, no exchange-authenticated calls, no key/environment-variable output, no git commit/push. Existing files read-only. New files only under this directory. Heavy arrays, if any, remain local. Runtime target is tens of minutes; reduce phase/replications before dropping any of the 72 cadence values. A feasibility failure is a valid result and must be reported as a limitation, not converted into a performance finding.

## Feasibility gate

Before backtest outcome calculation, verify: (1) OLD panel presence and hourly dimensions, (2) OLD-PIT presence and hourly dimensions, (3) NEW panel dimensions and timestamp range, (4) exact mapping of cadence and phase to hourly execution timestamps, (5) baseline V0 parity. Until all gates pass, no 1–72h performance estimates or winner classification may be published.

## AMENDMENT 2026-11-01 — executable data boundary and bounded run

This amendment is frozen before calculating cadence outcomes. The provided local scratch is used read-only as an input: `/private/tmp/claude-501/-Users-user-Desktop-CODE-Ochestration/b40d7700-4bab-493b-9b2c-b8bac464cd8e/scratchpad/panel`. Its OLD survivor panel has 45 symbols and 1,957 daily rows × 24 hourly OHLC observations, 2021-06-01 through 2026-10-09. The 1..72h cadence grid is retained. The OLD-PIT hourly panel is absent; the NEW PIT panel covers 2020-03..2021-12, so it cannot support the preregistered IS/OOS periods and is reported as separate historical context only, not pooled with OLD.

Due to the available OLD panel ending 2026-10-09, OOS is truncated at 2026-10-09; the 2025-10-10 flash episode is outside this panel. No substitute event is relabeled as that flash crash. Run all 72 cadences with eight evenly spaced phase offsets (0..p-1 when p<8 use all phases; otherwise eight integer quantiles), shared deterministic order-failure random streams, and lambda {0, 0.15, 0.30}. To keep compute bounded, slippage is the preregistered base 0 bp plus 5 bp stress; failure rates are {0%, 5%}; report this reduction and do not claim results for omitted 2/10bp and 2% scenarios. Include 15% retained-position resizing as live-like primary; run the 72h V0 kept-quantity parity separately. Costs remain 0.05% per side.

The hourly implementation uses observed hourly OHLC, close-based 336-hour momentum, hourly close execution, aggregate daily funding charged at UTC day-end (hourly funding allocation is not present in the panel), and the lambda-interpolated adverse wick kill model. It is a bounded research approximation, not exchange execution or authenticated API evidence. The 72h parity gate compares V0 kept-quantity outcomes against R2C on matched daily-close timestamps, with identical data, dates, parameters, phase, funding, fees, and lambda; any mismatch is reported numerically and limits causal cadence interpretation. Kill-free fixed-exposure diagnostics, block bootstrap, and multiplicity adjustment are retained where the available sample supports them. API rate limits, 418/recvWindow, lot filters, and partial fills are scenario estimates only; no authenticated calls are made.

## AMENDMENT 2 — fixed compute budget, before outcome run

The full 72-cadence × 8-phase grid will be run on OLD for lambda {0, 0.15, 0.30} at baseline fee/slippage and zero fill failures. To bound runtime, failure and slippage sensitivities (failure 0/2/5%, slippage 0/2/5/10bp) will use the fixed cadence subset {1, 6, 12, 24, 48, 72} and the same phase construction; this is a sensitivity sample and cannot establish a grid-wide cost-adjusted optimum. Full daily portfolio paths are used, but bootstrap uncertainty is based on 90-day non-overlapping OOS blocks; Holm correction covers all 71 shorter-vs-72 OOS cadence contrasts per lambda. No best individual cadence will be named. MDE is calculated from the paired phase-level dispersion and reported as exploratory because eight phases are not independent market samples.

## AMENDMENT 3 — parity implementation correction

The first outcome run exposed an implementation mismatch: its kill trigger used the lambda-adjusted hourly mark as intended, but it also updated the high-water mark from that adjusted mark. R2C updates the high-water mark from the hourly close equity after testing the adjusted mark. This is a code defect, not a protocol change. The first run is preserved as `exploratory_invalid_run1.*` and excluded from all reported inference. The engine is corrected to R2C high-water semantics; the confirmatory run will be regenerated from scratch. The parity threshold remains absolute final-equity relative error <= 2% plus identical kill count. If it still fails, cadence outcomes remain explicitly approximate and cannot support a strong directional verdict.

## AMENDMENT 4 — align daily funding timestamp for parity

After the high-water correction, the matched 72h paths still failed final-equity parity despite equal kill counts. Source tracing found the remaining known clock mismatch: R2C books each day's aggregate funding at UTC day start before its hourly path; the hourly prototype had booked it at day end. The confirmatory engine now books daily aggregate funding at UTC day start to reproduce R2C semantics. This is an explicit model amendment; prior runs 1 and 2 remain quarantined and excluded. The parity gate remains <=2% final-equity relative error and identical kill count.

## AMENDMENT 5 — align kill settlement mark for parity

The second corrected outcome run still failed parity. Source comparison found that R2C settles a triggered kill at the same lambda-interpolated portfolio mark used for the trigger, then charges close fees at the hour's close notional. The prototype had triggered from that mark but realized close-price PnL. The confirmatory implementation now realizes R2C's interpolated mark and close fee convention. Earlier exploratory runs remain preserved and excluded. No cadence, sample, or decision criteria are changed.

## AMENDMENT 6 — match crash-filter transition semantics

The third parity attempt still differed. Source tracing found that R2C forces a rebalance only when the BTC crash-filter boolean changes (entry or exit), while the prototype forced one at every daily close during an active crash state. The corrected engine now tracks the prior state and forces only on transitions. All earlier outcome runs remain quarantined; the final run uses unchanged frozen sample and cadence criteria.

## AMENDMENT 7 — restart schedule after cooldown

A fourth parity check still differed. R2C resumes at the close of the cooldown-expiry day, attempts a rebalance immediately, and restarts its `last_reb` clock from that event. The prototype remained anchored to the initial fixed phase. The confirmatory engine now uses stateful last-rebalance timestamps, restarts the schedule on crash transitions, and resumes at cooldown-expiry UTC close. Earlier runs remain excluded.
