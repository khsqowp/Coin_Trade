# Trial 100 — fixed 28-day / 5-day market time-series momentum

**Decision: REJECT on the frozen development gates. The 2024+ interval remains unopened.** The strategy made money against cash in the selected 2020–2023 development sample, but it did not maximize compounded wealth: it ended far below both the fixed six-coin buy-and-hold and BTC buy-and-hold comparators. It also failed the growth-concentration gate. Funding is absent, so the results are optimistic price-only USD-M proxies, not a futures profitability estimate.

## Frozen test and data integrity

- Preregistration: [`prereg_market_tsmom_28_5_2026-11-20.md`](../prereg_market_tsmom_28_5_2026-11-20.md).
- Rule: at daily close, rank the completed 28-day equal-weight major-coin market return against only its expanding prior history; after 252 prior observations, activate one of five long-only sleeves when the return is in the prior-history top tercile. Enter at the next UTC open, hold each signal sleeve for five full UTC days, otherwise hold cash. No leverage or shorting.
- Window: 2020-09-15 through 2023-12-31 UTC. The source range after 2024-01-01 was not queried. There were 10,393,920 source minute rows, equal to 1,204 complete days × six symbols × 1,440 minutes. The loader required every minute of every day, valid OHLC, and common coverage; it rejected incomplete data rather than filling or dropping rows. SQLite integrity check passed.
- Symbols are BTC, ETH, BNB, DOGE, SOL, and XRP, fixed from the current dataset snapshot. This leaves survivorship/selection bias and cannot establish a broad-market result.
- Base costs: 5 bp taker fee + 4 bp slippage per traded side. Stress: 5 bp + 8 bp per side. Funding is unavailable and omitted. Binance Vision historical data is used for personal, non-production backtesting only; this is not a live/manual signal.

## Primary result

| Metric | 28/5 strategy, base | 28/5 strategy, stress | Six-coin static B&H, base | BTC B&H, base |
|---|---:|---:|---:|---:|
| Final NAV from 1.0 | 1.2269 | 1.2159 | 15.0706 | 3.9193 |
| Total compounded return | +22.69% | +21.59% | +1,407.06% | +291.93% |
| CAGR | 6.40% | 6.12% | 127.87% | 51.39% |
| Maximum drawdown | 40.30% | 40.49% | 85.97% | 76.67% |
| Daily Sharpe | 0.385 | 0.374 | 1.254 | 0.965 |

The six-coin static benchmark is survivor-selected and its extraordinary return is not a valid expectation for a future tradable universe. It is still the preregistered matched-sample benchmark; the candidate must beat it to continue. The candidate also failed to beat BTC buy-and-hold and cash, so that bias does not reverse the decision.

Strategy exposure averaged 14.0%; there were 923 eligible signal dates and 171 long signals. Total traded-notional turnover was 22.38 NAV units. Annual strategy returns were 2020: 0.00% (warm-up/cash), 2021: +16.95%, 2022: −26.24%, and 2023: +42.22%. The 2023 year supplied 69.2% of positive annual log-growth, above the frozen 60% cap.

## Robustness and chronology

- 1,000 random reorderings of base daily net returns: observed-order MDD 40.30%; median reordered MDD 31.50%; 95th-percentile reordered MDD 43.23%. Stress 95th-percentile MDD was 43.46%. This is a sequence-risk diagnostic, not an independent profitability test.
- 1,000 circular 7-day block bootstraps of base daily returns: annualized arithmetic-mean 95% interval −12.31% to +30.06%; CAGR interval −15.01% to +32.05%. Stress intervals were −12.57% to +29.75% and −15.32% to +31.63%. Both include negative outcomes.
- Fixed-rule chronological half-sample diagnostics (no fitted parameters): first half NAV multiple 1.109; second half conditional NAV multiple 1.107. This is not an optimized train/test walk-forward; the strategy has no fitted parameters.
- Preregistered robustness-only neighbors, not substitutes for the primary rule: (25,4) NAV 1.501 / CAGR 13.12% / MDD 35.96% / Sharpe 0.621; (25,6) NAV 1.335 / 9.18% / 36.44% / 0.483; (31,4) NAV 1.126 / 3.68% / 33.74% / 0.283; (31,6) NAV 1.123 / 3.59% / 32.95% / 0.277. None beat the benchmarks or meet all frozen gates. No neighbor was selected.
- The six-symbol development window contains 0 off-grid minute timestamps; the loader also rejects off-grid rows even if row count and endpoints appear complete. The aggregate daily input panel SHA-256 is `108fe9d81b3ab35c575369358901f4f344bcfa873bae4c482f300c23e8b26651`. Synthetic tests cover causal threshold exclusion, future-mutation invariance, warm-up, exposure bounds, entry/exit fee reconciliation, refusal of missing/off-grid data, and deterministic panel fingerprinting. The full `chart_predictor/tests` suite passes: 246 passed, one non-fatal Joblib CPU-detection warning.
- A second run of the same frozen script and source window produced byte-identical JSON after the final loader correction. Funding omission remains an evaluation limitation, not a defect repaired by this price-only test.

## Gate decision and limits

The candidate passed positive base/stress CAGR and Sharpe and reduced drawdown versus the exceptionally volatile six-coin static B&H. It failed both base/stress terminal-wealth comparisons against cash/BTC/B&H, and failed the positive-growth-concentration cap. It is rejected; no 2024+ validation was opened, no parameters were tuned, and no deployment decision follows. The favorable return against cash is not enough for the user's sole objective of maximizing after-cost compounded wealth.

The literature’s 28/5 pair was selected from many alternatives in its source paper and may itself be data-mined. This adaptation uses only six current-survivor symbols, expanding thresholds, equal weights, and a five-sleeve portfolio implementation; it is not an exact replication. Missing funding, real historical universe membership, live spreads, and liquidation mechanics prevent any claim of real futures performance.

## Reproduction

```bash
/opt/anaconda3/bin/python3 -m chart_predictor.ts_momentum_market \
  --db /Users/user/CODE/Coin_Trade/chart_predictor/data/vision_dev_repaired.sqlite \
  --out docs/research/results/market_tsmom_28_5_20261120_dev.json
```

Trial JSON: [`market_tsmom_28_5_20261120_dev.json`](market_tsmom_28_5_20261120_dev.json).

SHA-256: code `62836ae11b18f2036a96ca606c2c08978737f2b0cc00e447c3a76bd75fb34925`; preregistration `c158a40aa7d041e7ec4eb9c54ecd01801cd0b9381fd617b08204b2ebb6b5c86b`; result JSON `245ecf2e4a6341ec542c18c4c39fc30f31e2ae31371fedb0a0bf57a67c226502`.
