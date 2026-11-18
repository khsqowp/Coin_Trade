# Micro-candle phase 5 — body-dominance M2 evaluation preregistration

Status: frozen after the label-blind frequency gate and before opening target/stop outcomes. This is an exploratory development test on an already exposed dataset, not sealed OOS evidence.

## Frozen candidate and data

- Candidate rule: at a completed 1-minute anchor, LONG when `close > open` and `(close-open)/(high-low) >= 0.80`; SHORT when `close < open` and `(open-close)/(high-low) >= 0.80`. Zero-range bars do not emit.
- Read-only input must match SHA-256 `cac23a3d18be66e226bdf8c3dbc0d08f5c6c185d4f18ed2a8687f08d2b6f67b1`, size 1,864,249,344 bytes, non-WAL journal mode, and no SQLite sidecars. The completed-bar cutoff is `2026-11-14T00:29:00Z`; a signal is allowed only for `t_open_ms + 60,000 <= cutoff`.
- The output records SHA-256 fingerprints for both the M2 runner and shared resolver before evaluation and verifies they remain unchanged at completion.
- Include all 100 available symbols, without outcome-based selection. The symbol list's underlying-asset eligibility is unverified; this is an exploratory archive, not a verified point-in-time futures universe.
- Data window is short (2026-07-16 through 2026-11-14), already examined in prior research, and cannot supply a genuine sealed/forward confirmation. Five fixed calendar evaluation blocks are used only to reveal temporal instability, not to claim independent OOS:
  1. `[2026-07-16T18:10:00Z, 2026-08-10T00:00:00Z)`
  2. `[2026-08-10T00:00:00Z, 2026-09-03T00:00:00Z)`
  3. `[2026-09-03T00:00:00Z, 2026-09-27T00:00:00Z)`
  4. `[2026-09-27T00:00:00Z, 2026-10-21T00:00:00Z)`
  5. `[2026-10-21T00:00:00Z, 2026-11-14T00:29:00Z)`

## Outcome and execution contract

- Every emitted signal with anchor inside a block remains in its all-issued denominator. The signal candle is not an entry bar. Enter at the next contiguous 1-minute open; the entry minute is the first outcome bar.
- A malformed OHLC row, off-grid timestamp, or missing minute is retained in the time series as a path break: it cannot emit a signal and any ATR/path that depends on it is unresolved. Non-integer timestamps are a hard data-integrity failure because their chronology cannot be safely aligned.
- Risk distance is the causal 14-bar simple-average true range (same convention as phase 4), computed only from completed bars through the signal anchor. Stop and target are each 1R in the signal direction.
- Evaluate 10-minute and 20-minute horizons separately. If target and stop occur in one 1-minute OHLC bar, stop wins. Stop gaps fill at the worse open; target fills exactly at its barrier. Timeout is not success. Missing, malformed, cutoff-crossing, or fold-crossing paths remain unresolved and are not deleted. Fold-crossing paths are not read.
- Primary M2 is target-first successes divided by **all issued signals**. Also report target-first among resolved paths, unresolved count/rate, and the conservative all-issued ratio. Deadline direction is a separate secondary measure.
- Baselines are matched to the same candidate anchors, entry, ATR, barrier, horizon, and resolver: signal-candle body direction (momentum) and the fixed SHA-256 fair-side control keyed by the existing seed. Because this candidate's side is itself the signal-candle body direction, the momentum comparator is identical by construction; report it as an implementation/plumbing check, not as an independent edge test. Report candidate and random control over all issued and resolved paths.
- Costs are 14 bp base and 28 bp stress round trip, applied to executable-price returns/net R; funding is unmodeled because settlement history is absent. Report conditional-on-resolved mean net R and its limitations.
- Select non-overlap signals outcome-blind within each symbol and fold: take the earliest anchor, then skip anchors until the registered horizon elapses. For a signal at anchor `i`, its outcome bars are `i+1..i+horizon`; a new signal at anchor `i+horizon` is allowed because it is emitted after that last bar closes and its entry/outcome bars start at `i+horizon+1`. Thus the trading/outcome bars do not overlap. Report counts and symbol dispersion separately; do not replace the all-issued M2 denominator with this subset.

## Decision and stop rules

For each horizon separately, `PRIMARY_SCREEN_SURVIVOR_REVIEW_REQUIRED` requires all frozen gates: M2 target-first/all-issued >=80%; base-cost mean net R >0; candidate M2 no lower than either matched comparator (the momentum comparator is an identity check); coverage >=10% of valid ATR-ready anchors, where the coverage numerator is only signals whose anchor has a valid ATR; path resolution >=95%; outcome-blind non-overlap N>=200; at least 20 symbols in that subset; and a passing deterministic scalar/vectorized resolver audit with zero label mismatches and absolute net-R error below 1e-12. Every emitted signal, including one without ATR, remains in the all-issued denominator. Coverage/N/resolution/scalar-audit failures are `INCONCLUSIVE_DATA_GATES`; performance-gate failures after all data gates pass are `REJECT_PRIMARY_SCREEN`. Direction at deadline remains secondary. These are point-screen gates, not statistical significance or OOS approval.

If both horizons fail performance gates, reject this fixed rule without parameter tuning, Monte Carlo rescue, or a plateau search. If a horizon unexpectedly passes, pause before any promotion claim and preregister dependence-aware inference, 1,000 trade-order permutations, parameter-neighborhood tests, multiple-claim adjustment, and a genuinely untouched forward evaluation. The five blocks are temporal diagnostics only: the input history was previously examined and is not independent OOS.

No symbol-specific threshold, alternative body fraction, reversed mapping, macro filter, or timeframe is permitted in this trial. Preserve every issued signal, unresolved path, fold result, and failure. No live signal or order is authorized.
