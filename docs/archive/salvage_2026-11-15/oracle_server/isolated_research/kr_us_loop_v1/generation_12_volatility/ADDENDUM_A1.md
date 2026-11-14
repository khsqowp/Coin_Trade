# Addendum A1 — align benchmark entry to the first executable target

Date: 2026-11-06 (Asia/Seoul)  
Reason: independent review found that the initial simulator description and implementation did not align: the candidate remained in cash during its 63-return warm-up, while its SPY buy-and-hold comparator was exposed from the first observed interval.

## Clarification (candidate signal and risk rule unchanged)

The first valid 63-interval downside-risk forecast occurs at the close of row 63 when rows are zero-indexed. Its target is first executable at the next observed open, row 64. The strategy and matched SPY buy-and-hold benchmark both remain in cash before that open and begin exposure at that same open. Their performance curves retain the full shared date index, including the shared zero-return warm-up. At the first executable open, each pays its own entry cost: the candidate pays 10 bp times its target risky weight; the benchmark pays 10 bp times 100% notional.

The return observation labeled by open row `i` covers the preceding open-to-open interval and any trade cost charged at open `i`. On the shared first-entry row, the previous interval is cash for both portfolios, so the only nonzero return component is that open's entry cost. On later rows, each portfolio first earns the prior open-to-open interval using its prior-open holding, then applies any rebalance at the current open. At the final observed open, no new target is entered; both portfolios first mark the preceding interval and then pay 10 bp on their remaining risky notional to liquidate. All timestamps and curve rows remain the same between candidate and benchmark.

This addendum changes only comparator timing/accounting clarification. It does not alter the 63-interval downside RMS, 10% target, exposure cap, signal cadence, data selection, trading cost, metric windows, or decision rule. A1's exact file hash must be included in the root-reviewed freeze; without that hash and root GO, no market input may be opened.
