# R006 handoff

## What is established

- The strategy target remains two strategies with net, risk-aware performance above matched buy-and-hold; no strategy has qualified, so the count remains 0/2.
- The requested MACD zero-up-cross with RSI(14)>50 was already tested in R004. Validation selected zero policies, zero validation cells beat matched B&H net CAGR, and final holdout stayed unopened. The exact setup is not to be repeated on exposed data.
- Four assigned reviews surfaced only non-evidential hypotheses: a VWAP mean-reversion idea that overlaps prior tests, a breadth/regime overlay blocked by historical-universe requirements, an L2 replenishment idea belonging to the separate M4 accuracy objective, and an independent audit supporting the data gate.
- Official Binance public-data documentation describes archive candles and aggregate trades, but the current official helper scope and terms do not establish delisted point-in-time universe completeness or permission for the product's eventual use. No data was downloaded and no terms were accepted.

## Next decision gate

1. Identify a data provider and source that can supply point-in-time contract eligibility, delistings, funding, and integrity/provenance fields.
2. Verify permitted-use scope for private research and intended manual signal use. Do not assume public access equals unrestricted rights.
3. Freeze universe, dates, costs, benchmark, splits, test family, and correction method before reading new performance outcomes.
4. Only then run a central batch. Keep M4 target-first accuracy separate from portfolio B&H excess-return evaluation.

## Current R005 engineering branch status

R005 remains an integrity-only prototype. The latest targeted package suite passed 273 tests (one environment-only joblib warning); 35 focused R005 tests passed. The original raw L2 capture is not accessible in the current checkout, so the latest code could not be replayed against that pilot. No R005 performance cells or labels were produced. See the R005 handoff for exact verification limits.
