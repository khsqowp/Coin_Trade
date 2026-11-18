# Phase 6 preregistration — 2-candle extreme sweep and reclaim

Status: hypothesis frozen after the phase-5 result and before any phase-6 outcome labels.

## Hypothesis

A second 1-minute candle that briefly trades beyond exactly one extreme of the preceding candle, then closes back inside the first candle's range and beyond its midpoint, may represent a failed local breakout and short-horizon reversal. This is a testable mechanism, not a claim that stop-hunting can be inferred from OHLC candles.

## Exact signal

Use two adjacent, complete, valid 1-minute candles, `bar1` then `bar2`, with `bar2.open_ms = bar1.open_ms + 60,000`.

- LONG: `bar2.low < bar1.low`, `bar2.high <= bar1.high`, and `bar1.mid < bar2.close < bar1.high`.
- SHORT: `bar2.high > bar1.high`, `bar2.low >= bar1.low`, and `bar1.low < bar2.close < bar1.mid`.
- If both extremes are swept, either candle is malformed, the pair is non-contiguous, or the inequalities do not match, emit no signal.
- Emit after bar2 closes. Do not enter at bar2 close; enter at the next contiguous 1-minute open.
- Assign the signal to a calendar fold by bar2's close/availability time (`bar2.open_ms + 60,000`), not by its opening timestamp. The immediately preceding bar may fall before the fold start because it is already observed feature history. Any resulting trade path is still cut off at that fold's end. Non-integer timestamps abort the screen as a data-integrity failure; off-grid, missing, or malformed bars break adjacency and cannot form a valid pair.

## Fixed outcome rule

- Stop: bar2 low for LONG, bar2 high for SHORT. Risk is the positive distance from next-minute entry open to that stop. If entry is at/beyond the stop, count the issued signal as a resolved no-trade failure; never discard it from M2.
- Target: 1R from entry. Evaluate 10-minute and 20-minute horizons independently, starting with the entry minute. Stop wins if stop and target occur in the same OHLC bar. Stop gaps fill at the worse open; target fills at its barrier. A missing, malformed, non-contiguous, cutoff-crossing, or fold-crossing outcome path is unresolved and remains in the all-issued denominator.
- Costs: 14bp base and 28bp stress round trip. Funding is not modeled. Report target-first/all-issued M2, target-first/resolved, unresolved, deadline direction, and mean net R separately.
- Use the same five fixed calendar blocks and frozen 100-symbol database snapshot as phase 5. This archive was already exposed to prior research; blocks are diagnostics, not independent OOS.

## Label-blind frequency gate

First run only a signal-frequency screen; do not access future path labels. Report valid adjacent-pair opportunities, issued signals by side/symbol/fold, coverage, and outcome-blind non-overlap counts using actual elapsed timestamps. Report non-overlap counts separately for both horizons at symbol and fold levels. Proceed to outcome evaluation only if each horizon has at least 200 non-overlap issued signals across at least 20 symbols. Coverage is reported but has no arbitrary minimum for this sparse-pattern family. Otherwise mark insufficient frequency and reject before outcomes. A signal is assigned by its bar2 close; it stays in the issued/non-overlap frequency counts even if its next open or outcome path reaches a fold boundary. At outcome evaluation, any path crossing the fold end is unresolved and retained in that fold's all-issued M2 denominator.

## Decision gates after frequency pass

The matched momentum side is bar2 body direction (a flat bar uses deterministic SHA-256 side); the random side is deterministic SHA-256 keyed by `seed|tag|symbol|signal_close_ms`, with seed `20261118`. Both baselines use the same candidate anchors and horizon, but each side defines its own stop at the corresponding bar2 extreme and its own 1R risk/target. They are controls, not evidence of independent alpha.

The fixed candidate advances only to human review if all apply for a horizon: target-first/all-issued M2 >=80%; positive mean net R after 14bp; path resolution >=95%; non-overlap N>=200 across >=20 symbols; candidate M2 no lower than either control; deterministic scalar/vector resolver audit passes with at least one resolved scalar sample, at least one tradable sample, zero label mismatches, and net-R error <1e-12. If any no-trade signals occur, at least one no-trade sample must also be checked with zero no-trade mismatches. A next-open entry at or beyond the candidate's stop is an issued, resolved no-trade failure; it stays in M2 and contributes zero PnL/no fee, with its count reported separately. Because no risk unit exists for such a no-trade event, mean net R is calculated over resolved tradable events only; report its denominator explicitly. Any missing-data gate failure is inconclusive. Any performance-gate failure after data gates pass rejects this exact rule. No threshold tuning, parameter sweep, or Monte Carlo rescue is allowed. If both horizons fail, move to a separately preregistered pattern family; do not alter this rule. Any pass is only a review trigger, not OOS approval or a live-trading recommendation.

## Duplicate-control note

The repository already contains generic engulfing/hammer/pin-bar detectors and a multi-stage `sweep_choch_retest` setup. Source inspection found the latter requires a confirmed swing pivot, a later change of character, and a later retest; this exact 2-adjacent-bar previous-extreme sweep/reclaim trigger is structurally different, though the general market idea overlaps. No global novelty claim is made.

External background is motivation only: research on crypto intraday returns reports both reversal and momentum effects with dependence on jumps/liquidity, and a recent large candlestick-pattern study tests many conventional patterns. Neither establishes this one-minute rule's edge. [Wen et al. (2022)](https://doi.org/10.1016/j.najef.2022.101733); [Moser & Brauneis (2026)](https://doi.org/10.1016/j.iref.2026.105158).
