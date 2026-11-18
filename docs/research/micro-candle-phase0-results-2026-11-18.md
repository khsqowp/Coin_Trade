# Micro-candle phase 0: reproduced results

Status: completed as a historical direction-classification diagnostic. This is not an M2 target-first evaluation, a trading strategy, profitability evidence, or sealed OOS evidence.

## Frozen question and data

- Question: after a completed 1-minute candle, classify the next completed 1-minute candle close versus the current close as UP, DOWN, or FLAT.
- Protocol: `micro-candle-phase0-preregistration-2026-11-18.md`.
- Read-only source: `/Users/user/CODE/Coin_Trade/chart_predictor/data/vision_dev_repaired.sqlite`.
- Cohort: BNBUSDT, BTCUSDT, DOGEUSDT, ETHUSDT, SOLUSDT, XRPUSDT.
- Train anchors: 2025-10-01 through 2025-12-31 UTC. Evaluation anchors: 2026-01-01 through 2026-03-31 UTC.
- Anchor rows were retained only when prior, anchor, and target opens were consecutive one-minute timestamps. Exact equal closes map to FLAT. No incomplete bar or future input was used.
- Each symbol had 132,479 train labels and 129,599 evaluation labels. Evaluation totals 777,594 labels over 90 shared UTC dates. No excluded anchors were found by the consecutive-timestamp condition in this run; the one-row difference from 90×1,440 is the final anchor whose next-candle open lies outside the half-open evaluation interval.
- The repaired database fingerprint cited by the source quality report is metadata/coverage-derived, not a full-content hash. Earlier strategy research examined this historical corpus; this evaluation is not untouched/sealed.

## Baselines

Three-class accuracy (percent):

| Symbol | Eval labels | Actual DOWN / FLAT / UP | Train-majority prediction | Persistence | Reversal | Train majority | Fixed SHA random |
|---|---:|---:|---|---:|---:|---:|---:|
| BNBUSDT | 129,599 | 62,837 / 2,959 / 63,803 | UP | 47.020 | 48.803 | 49.231 | 33.329 |
| BTCUSDT | 129,599 | 63,517 / 1,965 / 64,117 | UP | 47.590 | 50.061 | 49.473 | 33.430 |
| DOGEUSDT | 129,599 | 61,047 / 8,077 / 60,475 | UP | 42.858 | 46.060 | 46.663 | 33.510 |
| ETHUSDT | 129,599 | 63,960 / 1,216 / 64,423 | UP | 47.815 | 50.484 | 49.709 | 33.280 |
| SOLUSDT | 129,599 | 60,513 / 8,742 / 60,344 | UP | 42.899 | 45.385 | 46.562 | 33.226 |
| XRPUSDT | 129,599 | 62,133 / 6,095 / 61,371 | UP | 44.466 | 47.107 | 47.355 | 33.176 |
| Pooled | 777,594 | 374,007 / 29,054 / 374,533 | UP per symbol | 45.441 | 47.983 | 48.166 | 33.325 |

The pooled seven-day circular moving-block bootstrap (5,000 draws, fixed seed 20261118; same sampled UTC dates across symbols) yielded 95% intervals:

| Baseline | Accuracy | 95% block-bootstrap interval | Paired difference vs majority | Paired 95% interval |
|---|---:|---:|---:|---:|
| Persistence | 45.4413% | 44.9785–45.8760% | −2.7243 pp | −3.1457 to −2.2930 pp |
| Reversal | 47.9833% | 47.4343–48.5175% | −0.1824 pp | −0.6529 to +0.2945 pp |
| Per-symbol training majority | 48.1656% | 47.9008–48.4088% | 0 pp | 0 to 0 pp |
| Fixed SHA random | 33.3250% | 33.2575–33.3943% | −14.8406 pp | −15.1151 to −14.5479 pp |

Pooled balanced accuracy / directional-only accuracy conditional on a non-flat target / predicted non-flat coverage were: persistence 33.9315% / 46.8944% / 96.2636%; reversal 35.6919% / 49.5350% / 96.2636%; per-symbol majority 33.3333% / 50.0351% / 100%; fixed SHA random 33.3734% / 33.3189% / 66.6204%. Majority's balanced accuracy is one-third because it predicts only UP. Its directional-only accuracy is the conditional UP share and should not be read as a long/short strategy hit rate.

Pooled confusion matrices use actual labels as rows and predicted labels as columns, in `DOWN, FLAT, UP` order:

| Baseline | Actual DOWN row | Actual FLAT row | Actual UP row |
|---|---|---|---|
| Persistence | 175,367 / 13,273 / 185,367 | 13,215 / 2,326 / 13,513 | 185,422 / 13,455 / 175,656 |
| Reversal | 185,367 / 13,273 / 175,367 | 13,513 / 2,326 / 13,215 | 175,656 / 13,455 / 185,422 |
| Majority | 0 / 0 / 374,007 | 0 / 0 / 29,054 | 0 / 0 / 374,533 |
| Fixed SHA random | 124,339 / 124,754 / 124,914 | 9,688 / 9,728 / 9,638 | 124,391 / 125,076 / 125,066 |

The per-symbol recall (DOWN / FLAT / UP) was:

| Symbol | Persistence | Reversal | Majority | Fixed SHA random |
|---|---|---|---|---|
| BNBUSDT | 47.690 / 5.678 / 48.277 | 50.195 / 5.678 / 49.432 | 0 / 0 / 100 | 33.292 / 33.592 / 33.353 |
| BTCUSDT | 47.869 / 15.013 / 48.312 | 50.849 / 15.013 / 50.353 | 0 / 0 / 100 | 33.312 / 33.639 / 33.540 |
| DOGEUSDT | 45.481 / 7.391 / 44.946 | 48.417 / 7.391 / 48.845 | 0 / 0 / 100 | 33.301 / 33.886 / 33.670 |
| ETHUSDT | 48.041 / 6.250 / 48.376 | 51.068 / 6.250 / 50.740 | 0 / 0 / 100 | 33.232 / 32.319 / 33.345 |
| SOLUSDT | 45.483 / 8.774 / 45.252 | 47.980 / 8.774 / 48.088 | 0 / 0 / 100 | 33.416 / 32.864 / 33.087 |
| XRPUSDT | 46.642 / 6.940 / 45.991 | 48.725 / 6.940 / 49.458 | 0 / 0 / 100 | 32.921 / 33.962 / 33.356 |

Per-symbol confusion matrices are also in actual-row / predicted-column `DOWN, FLAT, UP` order; each matrix is written as `D-row; F-row; U-row`:

| Symbol | Persistence | Reversal | Majority | Fixed SHA random |
|---|---|---|---|---|
| BNBUSDT | 29967,1329,31541; 1331,168,1460; 31539,1462,30802 | 31541,1329,29967; 1460,168,1331; 30802,1462,31539 | 0,0,62837; 0,0,2959; 0,0,63803 | 20920,20823,21094; 983,994,982; 21243,21280,21280 |
| BTCUSDT | 30405,814,32298; 826,295,844; 32285,856,30976 | 32298,814,30405; 844,295,826; 30976,856,32285 | 0,0,63517; 0,0,1965; 0,0,64117 | 21159,21120,21238; 661,661,643; 21214,21398,21505 |
| DOGEUSDT | 27765,3725,29557; 3742,597,3738; 29539,3755,27181 | 29557,3725,27765; 3738,597,3742; 27181,3755,29539 | 0,0,61047; 0,0,8077; 0,0,60475 | 20329,20338,20380; 2662,2737,2678; 20004,20109,20362 |
| ETHUSDT | 30727,570,32663; 544,76,596; 32688,570,31165 | 32663,570,30727; 596,76,544; 31165,570,32688 | 0,0,63960; 0,0,1216; 0,0,64423 | 21255,21591,21114; 407,393,416; 21516,21425,21482 |
| SOLUSDT | 27523,3956,29034; 3973,767,4002; 29018,4019,27307 | 29034,3956,27523; 4002,767,3973; 27307,4019,29018 | 0,0,60513; 0,0,8742; 0,0,60344 | 20221,20110,20182; 2958,2873,2911; 20090,20288,19966 |
| XRPUSDT | 28980,2879,30274; 2799,423,2873; 30353,2793,28225 | 30274,2879,28980; 2873,423,2799; 28225,2793,30353 | 0,0,62133; 0,0,6095; 0,0,61371 | 20455,20772,20906; 2017,2070,2008; 20324,20576,20471 |

## Decision and limitations

- No tested baseline approaches the user's separate crypto M2 target-first gate of 80%. This experiment did not define entries, stops, targets, or a time-to-target, so it cannot score that gate.
- Minute observations are highly dependent; 777,594 is not the number of independent observations. Inference uses 90 shared calendar-day clusters, still a short and already-exposed period.
- Accuracy is not expected value. No trade simulation, fees, funding, spread, slippage, position sizing, calibration, or liquidation risk is modeled.
- Results are not promoted. No macro features were introduced. The next permissible experiment is a newly preregistered, single 2-bar morphology hypothesis, compared on the same frozen cohort/split and baselines; it cannot be called a strategy unless it later passes the user's distinct trading-validation gates.
- Pooled class totals are sums of the six exact per-symbol label counts in the table; they sum to the evaluation total of 777,594.
- Boundary audit correction: the first calculation counted the final training anchor at 2025-12-31 23:59 UTC even though its target candle opened at the 2026-01-01 split boundary. The frozen protocol requires the target open to remain inside the training interval, so that one label per symbol was removed and the training majority recomputed. The majority remained UP for all six symbols; evaluation rows, candidate predictions, accuracies, and bootstrap results above are unchanged. Corrected train label counts are BNB 64,579/1,841/66,059; BTC 64,984/1,981/65,514; DOGE 63,322/5,265/63,892; ETH 65,565/739/66,175; SOL 63,312/5,314/63,853; XRP 64,092/4,274/64,113 (DOWN/FLAT/UP).
