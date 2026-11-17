# R033 — 37-symbol multi-timeframe replay

**Status: exploratory development result; no strategy passes the crypto target-first gate.**

## Frozen test

- 37 fixed USDT-margined futures symbols, trimmed at five official settlement timestamps.
- Four existing signal atoms; every nonempty subset: 15 combinations.
- Nine closed-bar intervals (1m through 240m), 10- and 20-bar deadlines, with and without a fully closed UTC daily SuperTrend(14, 3×ATR) direction filter.
- 540 unique cells. Next-bar-open entry, median structural stop among agreeing signals, 2R target, stop-first same-minute ties, gap-through stop at observed open, 0.05% fee per side.
- Run time: 10,184.9 seconds (2h 49m 45s). Candle input SHA-256: `660f3eaded31188ae75c3e75c8b28b3858bf15485bfc91c15b9a182850176802`.

## Results against the registered crypto criterion

| Measure | Result |
|---|---:|
| Cells with at least 200 events | 494 / 540 |
| Cells with target-first rate ≥80%, across any sample size | **0 / 540** |
| Cells with target-first rate ≥80% and N≥200 | **0 / 494** |
| Target-first rate across cells, median | 12.44% |
| Highest observed target-first cell (descriptive scan only) | 28.33%, N=267,319; Wilson 95% interval 28.16–28.51% |
| Deadline-close direction accuracy across N≥200 cells, median | 47.39% |
| Highest deadline-close direction accuracy among N≥200 cells | 55.31%, N=1,327; Wilson 95% interval 52.63–57.97% |

The descriptive maximum target-first cell was the single `vwap_band_fade` rule on 15m bars, unfiltered, with a 20-bar deadline. Its mean event net return was **−0.1033%** after the modeled fees and its entry coverage was 3.64%. It is not a selected strategy. The highest deadline-direction cell was `volume_climax_exhaustion`, 240m, daily-SuperTrend aligned, 10-bar deadline; its 55.31% direction rate is also not evidence of a usable signal.

The scan maximum is far below the required 80%. The 494 cells meeting N≥200 are development-sample counts, **not OOS evidence**. Events are non-overlapping within each individual cell; cells share symbols, dates, and signals, so results across the 540-cell grid are dependent. No multiple-testing-adjusted significance claim is made, and neither scan maximum qualifies for forward evaluation.

## Limitations and data handling

- R033 reuses a development panel and previously inspected signal atoms. It cannot satisfy the registered out-of-sample requirement, regardless of its event counts.
- Modeled fees are included. Funding, spread, market impact/depth, mark-price liquidation, and exchange execution latency are not modeled. Positive cell means are not portfolio CAGR.
- Incomplete/stale execution windows and settlement-crossing horizons were censored. Five official settlement cutoffs were applied; no unused settlement mapping remained.
- The original execution JSON was sorted by observed mean net return and printed a `best` cell, conflicting with the preregistered no-selection rule. The exact original file is preserved as `results_original_ranked.json`. `results.json` retains the same metric values in frozen configuration order, adds explicit metric units, and reports Wilson bounds in percentage points. The research script was corrected so future runs neither rank cells by performance nor print a `best` cell. No strategy was approved or selected.
- Focused tests after the reporting correction: 10 passed. `git diff --check` passed.

## Decision

**Reject all R033 cells as candidate strategies.** No cell approaches the user's 80% target-first threshold; deadline-close direction results are near coin-flip. Do not tune these atoms or select the descriptive maximum. A future confirmatory attempt requires a new, untouched forward/OOS window and must preserve per-claim N≥200, target-first confidence bounds, symbol coverage, execution costs, and predeclared evaluation rules.
