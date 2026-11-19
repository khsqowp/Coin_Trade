# One-minute candle + taker-flow diagnostic — 2026-11-19

**Decision: no meaningful improvement demonstrated.** This one historical exploratory comparison reached about 51.3% next-candle directional accuracy. Adding taker-buy imbalance changed accuracy by only **+0.0115 percentage points**, and the synchronized 7-day block-bootstrap interval includes zero. This does not pass, approximate, or measure the separate ≥80% target-first M2 requirement.

## Frozen test

The preregistered question compared a fixed per-symbol logistic model using one completed candle's OHLC/quote-volume features with the same model plus taker-buy quote imbalance. The label was the next completed 1-minute close relative to the anchor close; exact ties were excluded. The fixed cohort was BNB, BTC, DOGE, ETH, SOL, and XRP. Training covered 2025-10 through 2025-12; evaluation covered 2026-01 through 2026-03. No parameter search or model selection was performed.

The label history was already exposed in earlier Phase 0 research. The evaluation is therefore **not untouched OOS or confirmatory evidence**. It is a single development-only diagnostic, as recorded in the [preregistration](micro-candle-flow-incremental-prereg-2026-11-19.md). No trade entries, targets, stops, costs, funding, or PnL were simulated.

## Results

| Evaluation measure | OHLC + quote volume | + taker-buy imbalance | Difference |
|---|---:|---:|---:|
| Directional accuracy | 51.3059% | 51.3174% | +0.0115 pp |
| Balanced accuracy | 51.3034% | 51.3148% | +0.0114 pp |
| Log loss | 0.6926433 | 0.6926406 | -0.0000027 |
| Brier score | 0.2497473 | 0.2497460 | -0.0000013 |

Paired accuracy-difference 95% interval: **−0.0290 to +0.0458 pp** (5,000 synchronized 7-day UTC block-bootstrap draws; 90 shared dates). The interval spans zero and the point-estimate gains are negligible.

Same-row baselines were 50.0351% for training-majority, 48.6919% for persistence, and **51.3081% for reversal**. The flow model exceeded reversal by only about **0.0092 pp** in pooled accuracy. It was not consistently better by symbol: OHLC-only was slightly more accurate on BNB, BTC, DOGE, and SOL; the flow model was slightly more accurate on ETH and XRP.

There were 777,594 feature-eligible evaluation anchors. 29,054 exact-flat next-close labels (3.74%) were excluded from this binary UP/DOWN model, leaving 748,540 scored rows. Training had 794,874 feature-eligible anchors and 775,460 scored non-flat labels. Every fixed symbol had one split-boundary anchor excluded by rule; no other feature-validity or timestamp-gap exclusions were observed in the tested windows.

## Interpretation and next gate

- A bare next-candle direction model can score just over 50% on this particular already-seen period, but the gain is tiny and the bootstrap uncertainty does not support an improvement claim.
- Taker-buy imbalance did not add a practically meaningful lift to this fixed OHLC/volume model. Do not tune thresholds against this same evaluation segment or market the result as a signal.
- This test is useful as an early-stage baseline check, not a completed strategy search. The next confirmatory step must use an untouched forward period; the current live feature pipeline's ability to supply this exact taker field at prediction time is not established here.
- Historical direction accuracy is not entry/stop/target-first accuracy, profitability, or leverage suitability.

Reproduction: `/opt/anaconda3/bin/python3 scripts/research/micro_candle_flow_incremental.py --db chart_predictor/data/vision_pit_dev_sample.sqlite --output docs/research/micro-candle-flow-incremental-results-2026-11-19.json`.

Machine-readable per-symbol results and bootstrap output: [JSON report](micro-candle-flow-incremental-results-2026-11-19.json). Code: [fixed comparison script](../../scripts/research/micro_candle_flow_incremental.py).
