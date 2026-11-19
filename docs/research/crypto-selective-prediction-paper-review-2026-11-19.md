# Selective prediction paper review — 2026-11-19

**Decision: methodology reference only; not a strategy candidate and not an 80% result.** No market rows, labels, Binance Vision files, or local outcomes were opened or downloaded for this review.

## Source and reported design

Hao, Chen, and Qi, “Coverage-Constrained Selective Prediction for Short-Horizon Cryptocurrency Event Contracts via Adaptive Quantile Thresholds,” *Algorithms* 19(8), 704 (published 2026-08-21), <https://doi.org/10.3390/a19080704>. The authors use BTCUSDT and ETHUSDT, 1-minute bars and auxiliary Binance Vision perpetual-futures inputs from 2023-05-25 through 2026-06-10. Their selective model combines a five-seed gradient-boosting ensemble over 90 causal features with daily adaptive score quantiles based on the prior 14–28 days. They evaluate 5- and 10-minute fixed-expiry binary event contracts, not futures entries with target-first/stop-first exits.

The abstract reports 10.4–11 trades/day and win rates above the paper's 55.56% break-even for a stylized 0.8 payout; 3 of 4 headline cells remain significant under a dependence-aware block bootstrap, while 2 of 4 survive Holm correction in the 32-test family. Coverage is within its operating band in 26/28 re-frozen windows. These are not 80% target-first precision results, and the two-symbol design cannot meet this project's ≥20-symbol OOS requirement. The paper itself frames the work as a proof of concept, not a claim of cryptocurrency predictability.

## Relevance to the frozen mandate

The transferable idea is selective abstention: emit only when a causally computed score is sufficiently extreme, while monitoring emission coverage. The paper does not validate this idea for the project's estimand. Its label is price direction at a fixed expiry; the project scores whether a target is reached before invalidation within a horizon. Its payout and concurrency assumptions are stylized event-contract mechanics, not a net-perpetual execution simulator. The disclosed implementation is not public, so an independent reproduction of the reported model is not presently possible from the article alone.

Applying adaptive thresholds to the already exposed Phase 0–8 signals would be post-selection, not confirmation. A valid future test would require a new, untouched chronological OOS interval, a frozen target-first label and execution model, threshold updates using only fully matured prior outcomes, explicit delay/embargo for overlapping trades, ≥20 eligible symbols and ≥200 non-overlapping OOS signals, and the already frozen multiplicity, Monte Carlo, and parameter-stability gates. Until those prerequisites exist, do not tune thresholds on current historical outcomes or present paper metrics as project performance.

## Source

- Publisher abstract and full article: <https://www.mdpi.com/1999-4893/19/8/704>
- Data availability statement identifies Binance Vision perpetual data and the 2023-05-25–2026-06-10 interval; the article says implementation code and frozen configurations are not released.
