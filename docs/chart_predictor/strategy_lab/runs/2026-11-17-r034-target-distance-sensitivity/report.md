# R034 — target-distance sensitivity

**Status: completed exploratory development sensitivity; no strategy qualifies.** This round was designed after inspecting R033 and reuses the same development candles and signal rules. It is not independent out-of-sample evidence.

## Frozen experiment

- 37 fixed USDT-margined futures symbols, including five officially settled contracts trimmed at their recorded settlement timestamps.
- Four existing signal atoms; all 15 nonempty subsets; nine timeframes (1m–240m); 10- and 20-bar horizons; unfiltered and fully closed daily SuperTrend-aligned regimes.
- Seven target distances: 0.25R, 0.5R, 0.75R, 1R, 1.5R, 2R, and 3R. Entry, structural stop, signal rules, and event anchors stayed fixed.
- 3,780 expected unique cells; all 3,780 were produced. The common event loop applies all seven target levels to each admitted signal event. Across the 540 groups, event counts and aggregate deadline-direction outcomes match. Per-event anchor IDs/hashes were not serialized, so the output file alone cannot independently prove identity event by event.
- Entry at next timeframe open; stop is median structural stop among agreeing votes; stop-first same-minute ties; stop-market gap fills at observed open; target fills at its barrier; timeout at registered deadline mark. Fee is 0.05% per side.
- Input SHA-256: `660f3eaded31188ae75c3e75c8b28b3858bf15485bfc91c15b9a182850176802`. Runtime: 12,836.3 seconds (3h 33m 56s).

## Results

| Target | Cells with N≥200 | Median target-first | Maximum target-first (N≥200) | Cells ≥80% (N≥200) |
|---:|---:|---:|---:|---:|
| 0.25R | 494 | 75.89% | 80.69% | 13 |
| 0.5R | 494 | 59.12% | 66.90% | 0 |
| 0.75R | 494 | 45.71% | 56.58% | 0 |
| 1R | 494 | 34.85% | 48.06% | 0 |
| 1.5R | 494 | 20.54% | 35.98% | 0 |
| 2R | 494 | 12.76% | 28.33% | 0 |
| 3R | 494 | 5.47% | 18.55% | 0 |

Across all target distances, 3,458/3,780 cells had N≥200. Thirteen development cells with N≥200 reached a raw target-first rate of at least 80%; only one also had a Wilson 95% lower bound at or above 80%. That descriptive maximum was 0.25R, `orb_funding_session` alone, 240m timeframe, unfiltered, 20-bar horizon: **80.69%, N=20,307, Wilson 95% interval 80.14–81.23%**. The Wilson interval is an unclustered binomial description; it does not adjust for serial dependence, cross-symbol dependence, or scanning 3,780 cells. This is a scan result on reused development data, not a qualifying strategy or an OOS pass.

The same maximum cell had **−0.0639% mean net return per event**, 0.923 profit factor, and 4.43% entry coverage. A high chance of touching a very close target does not establish positive expectancy: adverse stop outcomes and fees dominate here. Across N≥200 cells, 156/3,458 had a positive mean net event return; the median mean net return was **−0.1092%**. These event statistics are not portfolio CAGR.

Deadline-close direction is a separate measure and does not improve with target distance because all seven variants share the same signal anchors. Among N≥200 cells its median was **47.39%**; the maximum was **55.31% (N=1,327; Wilson 95% interval 52.63–57.97%)**, from `volume_climax_exhaustion`, 240m, daily SuperTrend aligned, 10-bar horizon. This is not evidence of an 80% directional edge.

## Decision and limits

**Reject all R034 cells as deployable or qualifying candidates.** The 80% target-first rate was observed at a 0.25R target in development data, but the user's requirement is at least 200 OOS events per claim. No R034 cell is OOS, the maximum cell has negative mean net event return after modeled fees, and market frictions are incomplete.

The model includes 0.05% one-way fees but not funding, spread, market impact/depth, liquidation, or latency. The target-distance grid is nested and shares event anchors; cells are dependent. No multiple-testing-adjusted inference or winner selection is claimed. The very short target can raise touch frequency mechanically while worsening expectancy. No rule, stop, or target will be promoted from this exploratory scan.

An independent red-team review reproduced the row counts, 80% threshold counts, Wilson interval, mean net return, and profit factor from the saved JSON, and found no separate fill-arithmetic defect. It noted that the artifact does not preserve per-event anchor identifiers and that the code-level invariant compares aggregate N and direction metrics, not a persisted anchor digest. The report therefore limits the claim to the shared event-loop construction plus matching aggregates; event-level identity remains unverified by the saved output alone. The red team also confirmed that KR/US CSVs remain exploratory and ineligible for the locked OOS market gates.

Next valid step: define one candidate using development evidence and test it only on a newly collected, untouched forward interval, with the signal frozen in advance and at least 200 non-overlapping OOS events for that claim. Until that evidence exists, the crypto 80% criterion remains unmet.

## Verification

- Result row count: 3,780; unique configuration keys: 3,780.
- Shared-target groups: 540; missing target levels: 0; event-count and aggregate deadline-direction mismatches: 0. Exact per-event anchor identity is not persisted as a digest.
- Focused test suite: 15 passed.
- `git diff --check`: passed before report creation; rerun before commit.
