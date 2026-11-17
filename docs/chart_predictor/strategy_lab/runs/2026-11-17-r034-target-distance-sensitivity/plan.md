# R034 — target-distance sensitivity after R033

**Status: preregistered dependent exploratory sensitivity; not confirmatory or OOS.** This round was designed after viewing R033. It may diagnose whether fixed structural-stop entries can reach the requested 80% target-first rate at shorter target distances, but no R034 result can qualify a strategy or select a future winner.

## Frozen design

- Exact same 37-symbol development cohort, five official settlement cutoffs, four signal atoms, 15 nonempty subsets, nine timeframes, two horizons, and two daily-SuperTrend regimes as R033.
- Target distance is the only changed variable: **0.25R, 0.5R, 0.75R, 1R, 1.5R, 2R, 3R**. Stop remains the median structural stop among agreeing votes; entry remains the next timeframe open.
- Expected output: 15 subsets × 9 timeframes × 2 horizons × 2 regimes × 7 targets = **3,780 cells**.
- Use the same eligible signal anchors for every target distance within a subset/timeframe/regime/horizon. Cooldown is applied once per anchor series, independent of target. Thus event counts and deadline-direction outcomes must match across all seven target variants in each such group.
- Scan the traded 1-minute path once per event. A target is counted only if its barrier is touched before the structural stop and within the fixed deadline. Stop-first ties remain in force. Gapped stops fill at observed open; targets fill at target price; timeouts close at the registered deadline mark.
- Fees remain 0.05% per side. No funding, spread, market impact/depth, liquidation or latency model is available.

## Acceptance and interpretation

- User's primary criterion remains target-first ≥80% with at least 200 OOS non-overlapping events per claim. R034 is development data and cannot meet the OOS part.
- Report all 3,780 cells, event count, target-first percentage and Wilson 95% interval, separate deadline-close direction accuracy, net event return, profit factor, coverage, and symbol distribution.
- Target levels are nested and all variants reuse the same signal anchors; the cells are strongly dependent. No multiple-testing-adjusted significance or winner claim will be made.
- Do not tune signal rules, alter stops, rank results by returns, or promote any R034 cell. Any prospective confirmation requires a new untouched forward interval and one frozen candidate selected without using that interval.

## Stop conditions and data integrity

- Read `vision_pit_dev_sample.sqlite` read-only; use the frozen R033 `symbols.json` and `settlements.json` without substitution.
- Drop pre-first-trade bars, trim official settlements, and reject unmapped terminal zero-trade tails. Preserve full-horizon/gap/settlement censoring and executable traded-minute rules.
- Require exactly 3,780 unique configuration keys and equal N/direction outcomes across target variants within each shared-anchor group. Fail closed on any mismatch.
