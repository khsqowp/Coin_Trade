# Research continuation — micro-first order and current data state (2026-11-18)

## Decision

Continue research from the smallest candle behavior and expand only when a frozen gate passes. The current two-bar candidate is rejected before M2 outcome evaluation: its raw issue coverage is **1.0590%**, below the fixed 10% threshold. It emitted 181,512 raw events over 17,139,961 scheduled 1m anchors and 156,809 events after a per-symbol 10-minute cooldown. The cooldown event-count gate passes, but coverage fails. No forward OHLC path, target/stop, realized return, or M2 label was queried. Do not tune this candidate or expand it to higher timeframes.

This is a candidate-family rejection on an already-exposed development dataset, not proof that all two-bar patterns fail and not a live-performance claim. Its reversal premise is adjacent to prior reversal/pullback studies; the exact rule was not found in the local setup list, but global novelty is not claimed. The candidate proposer reported that prior outcome text appeared during its source search, so this round is not independent of prior research. The frequency-only measurement itself did not read forward outcomes.

## Updated local checkout and data cleanup

The current primary checkout is `/Users/user/CODE/Coin_Trade`, `main` at `origin/main`, with five modified tracked files and fifteen untracked files in the cleanup/repair work. Those user-owned changes were not staged, edited, or merged in this research worktree.

Read-only audit was rerun against `/Users/user/CODE/Coin_Trade/chart_predictor/data/candles.sqlite`:

| Property | Current audit |
|---|---:|
| Rows / symbols | 17,142,161 / 100 |
| Missing minutes within observed symbol spans | 0 |
| Duplicate keys / off-grid timestamps | 0 / 0 |
| Invalid OHLCV / null rows | 0 / 0 |
| Full file SHA-256 | `cac23a3d18be66e226bdf8c3dbc0d08f5c6c185d4f18ed2a8687f08d2b6f67b1` |

The quality checks establish structural consistency only. The database has no retained page-level collection provenance; the dated reconciliation report matches logged row counts for 97/100 symbols only. Its universe metadata is a volume-ranked collection snapshot and was not joined to point-in-time exchange contract metadata; the user's COIN-underlying-only requirement is therefore unverified for these 100 names. The Jul–Nov 2026 window is already used by P5–P9, so it is not sealed OOS data. The separate six-symbol `vision_dev_repaired.sqlite` is a historical 2020–2026-06 input with repair pages recorded; it is not interchangeable with `candles.sqlite`.

The dirty collector diff adds run/page provenance tables, but the existing SQLite file predates those tables. A prior isolated mock reproduction also found an empty-page pagination defect: the same page number can be reused by a later missing interval, causing a unique-key failure after candle rows may already have been committed without matching page provenance. Do not rely on its new lineage claims until that path is corrected and tested. This report does not modify that user-owned collector diff.

## Micro-first sequence and measured record

1. **One completed 1m candle:** Phase 0 measured next-close UP/DOWN/FLAT on six symbols. Pooled accuracy was 48.17% for per-symbol training majority, 47.98% reversal, and 45.44% persistence. It was a direction diagnostic, not M2 or PnL; history was previously exposed.
2. **One-candle close-location:** The prior round's top/bottom-20% close-location rule reached 46.28% all-issued M1 accuracy and 48.32% conditional non-flat direction, below its deterministic SHA-256 random baseline at 47.88% for the all-issued comparison. No target-first edge was established.
3. **Three-bar impulse/pullback/confirmation:** Frequency 1.5108%, below the 10% coverage gate and structurally adjacent to R021; rejected without M2 evaluation.
4. **Longer two-bar range compression candidate:** Frequency 3.3518%, below 10%; rejected without M2 outcome evaluation.
5. **Current two-bar impulse + opposite-quartile inside acceptance:** Frequency 1.0590% of all scheduled anchors; rejected before M2. It is not promoted by the large raw event count because the denominator is every valid 1m anchor after warm-up.

No macro, BTC regime, or higher-timeframe filter is to be added at the beginning of the next study. Future research must progress in order: one-candle behavior → a distinct two-candle rule → short local sequences → broader patterns/timeframes, with each step stopping at its predeclared data/coverage gate. Do not keep testing longer patterns after the current family fails its frequency gate.

## Four-agent review

| Role | Conclusion |
|---|---|
| KR equity | No intraday KR data. Current daily CSVs contain 92 symbols, but no proven PIT membership, delisted names, adjustment/dividend lineage, or file manifest. Begin only with a one-ETF daily raw-candle data audit, not performance optimization. |
| US equity | No intraday US data. Current cache has 92 symbols (54 equities, 38 ETFs) through 2026-11-12, but no proven PIT/delist universe or corporate-action lineage. Existing 12–1 momentum results have been exposed; genuine 200-trade OOS requires a frozen future cohort and at least 19 monthly cohorts at approximately 11 holdings/month. |
| Crypto micro | Proposed a two-bar impulse/inside-bar opposite-acceptance setup; no outcome test was performed by the agent. Local frequency screen was run by the primary process and failed coverage. |
| Red team | Confirmed the repaired six-symbol DB is only conditionally suitable for 1m OHLCV research, not tick/L2 microstructure. Existing results cannot be completely linked to immutable content inputs in all run artifacts. The current candidate is adjacent, not demonstrably novel; frequency-only gating is the right early stop. |

The stock agents made readiness assessments, not strategy-performance tests. Their proposals do not meet the user's stock gates and are not approved candidates. The four agents did not independently execute or verify each other's work.

## Reproduction and controls

The preregistration is `micro-candle-phase3-prereg-2026-11-18.md`; its machine-readable frequency report is `micro-candle-phase3-frequency-2026-11-18.json`; the read-only counter is `chart_predictor/micro_pattern_feasibility.py`. The script opens SQLite using `mode=ro`, checks timestamp continuity, reads only bars through the candidate anchor, and reports `outcome_rows_read=0` and `target_stop_labels_read=0`.

The final script was syntax-compiled in memory and run with the system Python 3.9 using only the standard library. It streams each symbol in timestamp order, uses only the already-seen bars at each anchor, fails on any missing minute, and writes only the JSON frequency report. A synthetic one-signal fixture test passed (`1 passed`) under the available Anaconda pytest environment. No repository source in the primary checkout or source DB was changed.

## Next decision

Do not read M2 outcomes for the current candidate. The next useful work is to resolve the collector's empty-page page-number bug and add a reproducible content-level lineage manifest for the 100-symbol collection, while preserving the current user's uncommitted changes. A new strategy family should only be opened after a structurally distinct one- or two-candle mechanism is frozen and its label-blind coverage is plausible; it must use genuinely forward append-only data for any validation claim.
