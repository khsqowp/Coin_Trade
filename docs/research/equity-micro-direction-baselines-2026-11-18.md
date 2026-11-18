# KR/US daily micro-direction baselines (exploratory)

Decision: no strategy candidate is promoted. These are next-observed-session direction classifications, not executable trade simulations or portfolio returns. The 2021–2024 window is already exposed by earlier repository research and is not untouched OOS.

## Data and fixed classification

- Read-only cache: `/Users/user/CODE/Coin_Trade/.kis-cache-local`.
- KR: 92 daily CSVs, 326,225 rows, 2010-05-28–2026-11-12. Using the repository's fixed ETF tickers, 26 cached files classify as ETFs and 66 as non-ETF symbols.
- US: 92 daily CSVs, 339,303 rows, 2010-01-27–2026-11-12. Using the repository's fixed ETF list, 38 are ETFs and 54 are stocks.
- All 92 symbols in each market had evaluation labels. Timestamp duplicates: 0 in both caches. OHLC shape violations: 0 KR; 62 US. The US violations occur on 2021-05-05 (36 files), 2023-06-05 (22), 2018-11-15 (3), and 2017-07-03 (1). Cause is unknown; do not infer an adjustment/vendor explanation without source verification.
- Split: training labels whose signal date and next observed session date are both before 2021-01-01; evaluation signal dates 2021-01-01 through 2024-12-31, with the next observed session also before 2025-01-01.
- Label: compare next observed session close with signal-session close; exact equality is FLAT. Baselines: prior-session close direction (persistence), inverse prior-session direction (zero maps FLAT), and per-symbol training-majority class (ties: FLAT, DOWN, UP). No macro feature, parameter search, entry/exit, or transaction cost is involved.

## Observed next-session labels

| Market | Eval observations | Actual DOWN | FLAT | UP |
|---|---:|---:|---:|---:|
| KR | 89,052 | 43,076 | 3,699 | 42,277 |
| US | 92,224 | 43,627 | 778 | 47,819 |

## Three-class accuracy

Pooled means weight every asset-day equally; equal-asset means compute each symbol's accuracy first, then average symbols equally.

| Market | Baseline | Pooled accuracy | Equal-asset mean |
|---|---|---:|---:|
| KR mixed cache | Persistence | 45.587% | 45.604% |
| KR mixed cache | Reversal | 47.069% | 47.081% |
| KR mixed cache | Per-symbol train majority | 46.760% | 46.131% |
| US mixed cache | Persistence | 49.751% | 49.753% |
| US mixed cache | Reversal | 48.882% | 48.877% |
| US mixed cache | Per-symbol train majority | 50.921% | 50.843% |

### ETF versus non-ETF sensitivity

| Market / cohort | Baseline | Raw accuracy | Excluded invalid-adjacent rows | Accuracy after exclusion |
|---|---|---:|---:|---:|
| KR ETF | Persistence | 48.144% | 0 | 48.144% |
| KR ETF | Reversal | 47.341% | 0 | 47.341% |
| KR ETF | Train majority | 49.577% | 0 | 49.577% |
| KR non-ETF | Persistence | 44.559% | 0 | 44.559% |
| KR non-ETF | Reversal | 46.960% | 0 | 46.960% |
| KR non-ETF | Train majority | 45.628% | 0 | 45.628% |
| US ETF | Persistence | 49.492% | 69 of 38,152 | 49.476% (N=38,083) |
| US ETF | Reversal | 48.291% | 69 of 38,152 | 48.302% (N=38,083) |
| US ETF | Train majority | 51.140% | 69 of 38,152 | 51.099% (N=38,083) |
| US non-ETF | Persistence | 49.933% | 105 of 54,072 | 49.919% (N=53,967) |
| US non-ETF | Reversal | 49.299% | 105 of 54,072 | 49.315% (N=53,967) |
| US non-ETF | Train majority | 50.766% | 105 of 54,072 | 50.740% (N=53,967) |

The sensitivity exclusion drops an evaluation observation when any of its prior, signal, or target session bars fails `High >= max(Open, Close)` and `Low <= min(Open, Close)`. The label-only comparison moves modestly, but this does not certify the remaining rows or remove unknown adjustment and survivorship problems.

## Interpretation and next gate

- These simple daily baselines did not demonstrate a reliable directional edge: the training-majority baseline was strongest in the pooled KR non-ETF, KR ETF, US ETF and US non-ETF cohorts, while reversal led only the pooled KR mixed cache by a small amount. No date-block confidence interval was calculated in this descriptive pass.
- No CAGR, MDD, Sharpe, round-trip count, fees, taxes, slippage, corporate-action cash flows, fills, or risk sizing was simulated. The stock acceptance gate remains CAGR ≥20%, MDD ≤30%, Sharpe ≥1.0 and at least 200 OOS round trips; this diagnostic evaluates none of those gates.
- Existing sources state that these caches lack reliable point-in-time/delisted membership and verified corporate-action adjustment provenance. The current selected cohort and previously examined history therefore cannot support a sealed generalization claim.
- Do not expand to candle patterns on this evaluation set as though it were confirmatory. The next useful step is a fresh, predeclared hypothesis on the smallest available daily bars (with explicit event/entry timing), while securing an actually unused or forward period and validating price adjustment provenance. Until then, pattern results on these files are exploratory only.
