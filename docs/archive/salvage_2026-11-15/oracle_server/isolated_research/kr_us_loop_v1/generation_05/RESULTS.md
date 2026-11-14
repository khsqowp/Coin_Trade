# Generation 05 — low-MAX21 results

Runs `GEN05-20261106T102256-93331` and `GEN05-20261106T102632-99205`; local snapshots only. The first is invalidated by Addendum A1; the second failed its own no-order-row preflight due to an implementation defect documented in Addendum A2. Neither may be used as strategy evidence. Complete attempt ledgers and input/code hashes are in the matching `attempts_*.jsonl` and `manifest_*.json` files. All generated outputs are retained.

The corrected execution run is `GEN05-20261106T102735-1318` (runner SHA is stored in its manifest). It is the only usable exploratory screen for this candidate.

## Outcome

- **US:** corrected monthly-only execution completed. IS (2001-01-04 to 2016-12-30): strategy CAGR 9.49%, Sharpe 0.67, MDD -44.72%; SPY benchmark CAGR 5.22%, Sharpe 0.36, MDD -55.19%. Later inspected/contaminated period (2017-01-04 to 2026-11-02): strategy CAGR 7.06%, Sharpe 0.52, MDD -35.44%; SPY benchmark CAGR 14.84%, Sharpe 0.86, MDD -33.72%. It beats the benchmark in this IS partition but loses materially in the later partition, so it is not a qualifying strategy.
- **KR:** corrected monthly-only execution stopped on strict OHLC integrity at 2024-09-24 for held ticker `119860` (invalid/missing OHLC). No performance result is reported. This is a data-integrity failure, not a strategy failure or pass.

## Interpretation boundary

The corrected US screen is mixed across the inspected partitions and does not meet the requested all-regime/OOS standard; KR remains unmeasured because strict data validation halted it. US PIT price coverage remains incomplete (688 local files versus 1,209 membership names), corporate-action/delisting integrity is unresolved, and cumulative historical trial count is unknown. No global DSR/PSR/multiple-testing correction or confirmatory significance claim can be made.

## Candidate distinction

This is a trailing 21-session MAX adaptation, not an exact replication of the cited paper's calendar-month, low-minus-high decile long-short portfolio. It tests a long-only low-MAX basket under the existing no-short constraint. This difference must remain explicit in future summaries.
