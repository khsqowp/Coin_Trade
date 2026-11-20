# Preregistration v7 amendment: executable edge cases and reporting

> Read v2–v7 as a version chain. v7 freezes implementation details raised by the independent scorer review before outcomes are opened. No strategy outcome has been calculated.

- Frozen: 2026-11-20, before outcome scoring.
- No changes to the signal hypothesis, 36-symbol cohort, date interval, horizons, barrier distances, fees, funding assumptions, statistical family, or historical/OOS restrictions.

## Timestamp gaps, coverage, and fixed clusters

1. Treat timestamps as a strictly increasing series that may contain gaps. At any gap from the preceding hourly timestamp, clear pending setups and previous same-type pivots; reset the CVD accumulation segment. Reset Wilder ATR state, use high-low as the first true range after the gap, seed ATR with the simple mean of the first 14 consecutive true ranges, then use Wilder recursion. ATR is unavailable until those 14 consecutive bars exist.
2. Strict 3-left/3-right pivots require every adjacent timestamp in the seven-bar pivot window to be exactly one hour apart. A pivot pair, pending confirmation, or breakout cannot cross a gap. Do not interpolate missing bars.
3. Coverage denominator consists of every bar open in the fixed date interval for which the 14-bar ATR was already available at that open (the previous contiguous bar's completed ATR; never use the current bar's later high/low/close) and whose own timestamp could be a valid entry open: its scheduled 20th hourly candle close (`bar_open_ms + 20*3,600,000 - 1`) must be strictly before the development endpoint. It is independent of actual signal confirmations. Signal numerator uses next-open entry timestamps under the identical scheduled-expiry rule.
4. Freeze the v5 common 20-hour non-overlap cluster timestamps immediately after both arms' signal-generation passes and before any outcome/barrier/funding code runs. Clusters depend only on generated `entry_open_ms` values, never realized exits or path results.
5. If an otherwise timestamp-eligible outcome path contains a missing/nonconsecutive hourly candle, retain the signal, label `DATA_GAP`, count an M2 miss, and mark net performance for that path unavailable. The affected cell cannot pass.
6. If the next expected hourly open after a valid breakout confirmation bar is absent, retain the issued forecast with its scheduled next-hour timestamp as `MISSING_ENTRY_BAR`; count M2 as a miss, leave M1/net return/net R undefined, and keep it in signal coverage and the fixed cluster timestamp set. Never enter at a later observed open.

## Net-return and funding output

7. For every executable signal, define initial risk fraction as `abs(entry - stop) / entry`; define `net_R_base = net_return_base / initial_risk_fraction` and `net_R_stress = net_return_stress / initial_risk_fraction`. Include per-event and aggregate mean/median/positive-rate net R. Invalid entries count M2 failure and zero net return/R; a missing path is not zero.
8. Report actual signed funding cashflow, conservative funding charged in the primary estimate, and the required sensitivity that removes all exit-candle funding settlements from the primary funding charge. Report base/stress fees and net returns with these costs explicit.

## Run evidence

9. Before scoring, run the per-symbol prefix-invariance and future-mutation checks for both price-only and CVD arms. A failure aborts the run.
10. Before reading any outcome, re-hash each of the 1,728 frozen kline/funding archive files against the passing input audit and preserved manifest. A mismatch aborts the run.
11. Resolve and validate the source commit and worktree status before any feature/outcome read; a missing commit identity aborts the run. Persist the fixed date grid, complete frozen cohort, source commit, SHA-256 of all scorer/feature/bootstrap/audit source files, hashes of every applicable preregistration version, manifest-file SHA and selected-data fingerprint, exact Python/NumPy/SciPy versions, fixed bootstrap settings, sampled date-index SHA-256 and denominator vectors/hashes for every bootstrap metric in the result record.
12. Outcome data remain historical development data already exposed to prior research. Even a quantitatively passing development threshold check is reject/debug-only; no OOS/core approval, paper promotion, production, Phase 9 mixing, or live/manual signal is permitted from this run.
