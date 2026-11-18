# Micro-candle phase 1: two-bar direction agreement (exploratory)

Decision: reject this fixed candidate. It materially underperformed the fixed per-symbol training-majority baseline. This is a post-hoc exploratory test on an already exposed evaluation period, not confirmatory evidence.

## Hypothesis and exact rule

At the close of the anchor candle, compare the close-to-close directions of the anchor candle and its immediately preceding candle. If both directions are equal and nonzero, predict that direction for the next completed one-minute close. Otherwise predict FLAT. The prediction uses only completed candles through the anchor. The label is UP/DOWN/FLAT from next close versus anchor close, with exact equality as FLAT. No thresholds or parameter sweep were used.

This simple two-bar continuation rule was selected after phase-0 baseline labels had already been examined. Therefore the January–March 2026 evaluation is reused, exposed data. The result cannot be called pre-registered, independent OOS, or sealed.

## Data and evaluation

- Same read-only `vision_dev_repaired.sqlite`, six-symbol cohort, split, label definition and continuity requirement as phase 0.
- Evaluation: 129,599 labels per symbol; pooled N=777,594 over 90 shared UTC dates.
- Compared with phase-0 per-symbol training-majority prediction, without recalibrating it on evaluation labels. A boundary audit removed the last 2025-12-31 training anchor because its target opened exactly at the split; the majority stayed UP for every symbol, so the reported baseline and candidate results did not change.
- Uncertainty: 5,000 circular moving-block bootstrap replicates of 7 UTC dates, shared across symbols, seed 20261118. Resampling used per-day hit and denominator aggregates.

| Symbol | Candidate 3-class accuracy | Signal coverage (predict UP/DOWN) | Candidate accuracy conditional on non-flat target | Training-majority accuracy |
|---|---:|---:|---:|---:|
| BNBUSDT | 23.417% | 46.891% | 22.622% | 49.231% |
| BTCUSDT | 23.341% | 47.362% | 22.717% | 49.473% |
| DOGEUSDT | 22.606% | 42.398% | 20.074% | 46.663% |
| ETHUSDT | 22.880% | 47.757% | 22.558% | 49.709% |
| SOLUSDT | 22.997% | 42.307% | 20.238% | 46.562% |
| XRPUSDT | 22.829% | 44.140% | 21.040% | 47.355% |
| Pooled | 23.012% | 45.142% | not separately aggregated | 48.166% |

Pooled candidate accuracy 95% block interval: 22.675–23.320%. Candidate minus training-majority: −25.154 percentage points; paired block interval: −25.611 to −24.702 points. Pooled coverage 95% interval: 44.629–45.633%.

## Interpretation

- The candidate fails even as a direction classifier; no reason exists to add thresholds or filters to rescue it on this same period.
- The result does not measure M2 target-first probability, trade returns, fees, funding, spread, slippage, or liquidation risk.
- This is one hypothesis and one post-hoc test. It cannot satisfy the separate 80% M2 target, minimum N=200 independent non-overlapping signals, Monte Carlo trade-order, WFA, or parameter-plateau gates.
- No broader candle family was tested in this phase. A future candidate needs a new trial record before querying its outcomes, and an actually untouched/forward period for confirmatory evaluation. The existing dataset has prior research exposure and cannot provide that independence.
