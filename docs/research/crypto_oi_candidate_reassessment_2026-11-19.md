# Crypto OI candidate reassessment — 2026-11-19

## Decision

**Do not run an OI performance backtest yet.** Two independent reviews found that `OI impulse → unwind` may be structurally distinct from prior work, but it is not a sufficiently defined candidate and its historical availability/contract universe is not established. The next valid step is to freeze one causal rule and then run only outcome-blind eligibility checks. No market labels or performance outcomes were opened in this review.

This preserves the micro-first sequence: Phase 0–8 already tested exposed single-/multi-candle OHLC families and did not meet the frozen target-first gate. Do not add another candle-shape threshold. An OI rule would be a new information-source rung, not evidence that the earlier stages passed.

## Independent reviews

| Reviewer | Finding | Disposition |
|---|---|---|
| Crypto candidate researcher | No defensible exact direction/entry/exit rule can be proposed without inventing thresholds or conflating OI with price-shock/reversal logic. | `NONE` for a performance candidate now. |
| Red-team/data reviewer | A limited outcome-blind archive/PIT/frequency eligibility gate is permissible after the rule, symbol/date cohort, denominator and missing-data handling are frozen. | `CONDITIONAL`; performance test remains `NO-GO`. |

Both reviews compared the proposal with R021 (funding-extreme/re-entry), R023 (BTC shock/relative lag and breakout), and R005 (trade shock plus displayed-depth replenishment). Different input data alone does not prove a distinct mechanism. Any rule based on OI contraction plus the same price-shock, flow, or book-recovery conditions needs a fresh duplicate review.

## Verified data limits from existing reports

- R030 fixed 37 symbols × 20 dates (740 symbol-days). Of these, 720 archive/checksum pairs existed and passed publisher SHA-256; 20 were absent. Five available files contained only 1–2 of 288 expected 5-minute rows, leaving 1,432 missing slots. OI values were numeric and finite only on rows present. Keep absent and defective rows missing; do not impute or interpret as zero.
- R031 compared recent archives for 32 symbols across three dates: 27,647 matched OI values aligned exactly to the public REST observation at `create_time + 5m`. This establishes timestamp-label consistency only for that recent sample. It does not establish first publication/receipt time or historical point-in-time availability.
- R029 object-key coverage is not file-content completeness. Historical contract listing/termination epochs and ticker identity remain unresolved. Costs, funding and executable-price assumptions are not frozen for this candidate.
- The recent OI archives and raw responses were not reopened in this review; these figures are carried from the named reports, not independently recomputed here.

## Required next gate

1. Define one OI event and directional mechanism without using outcome labels; state the exact observation availability time, signal anchor, next executable entry, stop, target, deadline, and duplicate-suppression rule.
2. Independently compare that exact rule with R021/R023/R005 and the prior trial registry. Reject it if it is a renamed variant.
3. Freeze symbols, dates, all-opportunity denominator, point-in-time contract-epoch evidence, missing-data policy, and frequency thresholds before examining any target/stop path.
4. Run only archive integrity, causal availability, contract-eligibility, coverage and non-overlap frequency checks. Quarantine the known five defective files and retain all absent requests in the denominator.
5. If these checks pass, separately preregister costs, paired baselines, WFA boundaries, Monte Carlo, sensitivity, and the untouched OOS boundary before any performance labels are opened.

The user's fixed pass gate remains OOS target-first precision ≥80% with at least 200 non-overlapping events; deadline-close direction accuracy is secondary. No qualifying crypto signal is established by this note. Binance Vision data remains restricted to historical personal, non-production research and must not feed live/manual signals or order execution.

## Sources in the checkout

- `docs/research/crypto_microtrial_ledger_2026-11-19.md`
- `docs/research/micro-candle-next-stage-screen-2026-11-19.md`
- `docs/chart_predictor/strategy_lab/runs/2026-11-17-r026-vision-metrics-timing/decision.md`
- `docs/chart_predictor/strategy_lab/runs/2026-11-17-r029-oi-metrics-object-index/report.md`
- `docs/chart_predictor/strategy_lab/runs/2026-11-17-r030-oi-metrics-panel-sample/report.md`
- `docs/chart_predictor/strategy_lab/runs/2026-11-17-r031-oi-availability-crosscheck/report.md`
- `docs/chart_predictor/strategy_lab/runs/2026-11-16-r021-funding-macro-reentry/plan.md`
- `docs/chart_predictor/strategy_lab/runs/2026-11-16-r023-btc-shock-alt-laggard/plan.md`
- `docs/research/crypto_m4_runs/2026-11-16-r005-liquidity-replenishment/plan.md`
