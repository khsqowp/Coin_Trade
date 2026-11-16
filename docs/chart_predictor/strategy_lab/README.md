# Strategy Lab

This directory holds preregistered portfolio-strategy studies that compare net performance with a matched Buy-and-Hold baseline. These studies are separate from P5–P9 intraday signal tests and from the chart-prediction M4 accuracy objective. No result in one track satisfies another track's gate.

Each study uses an immutable run directory with `plan.md`, `manifest.json`, `results.json`, `decision.md`, and `handoff.md`. Large inputs and machine-generated row-level outputs remain under ignored `chart_predictor/data/strategy_lab/<run_id>/`; source datasets are never overwritten or committed. Plans precede any performance metric calculation. A run that lacks required data is recorded as blocked at the data gate, with no performance claim.

## Current objective

Find two portfolio strategies that outperform a matched Buy-and-Hold baseline after costs and risk controls. The attached master prompt dated 2026-11-15 is the governing protocol. Existing P5–P9 and the MACD-zero/RSI-50 experiment remain immutable prior evidence and are not rerun under new names.

## Current run

- `runs/2026-11-15-r001-readiness/`: data and evaluation readiness review; no strategy performance grid was run.
- `runs/2026-11-16-r018-vision-terms-data-gate/`: official historical-use terms and local SQLite schema audit; no performance metrics were calculated. Personal non-production historical backtesting is expressly permitted by the current terms, but the inspected candle DBs lack funding and point-in-time contract-universe data.
- `runs/2026-11-16-r019-vision-archive-coverage-smoke/`: preregistered 54-object Vision metadata check; all requests were `UNKNOWN` because local DNS failed, not 404. No market data was downloaded.
- `runs/2026-11-16-r020-equity-source-sample-quote-audit/`: public official-source audit for KRX and CRSP stock/ETF history samples and pricing; no account, purchase, provider contact, or strategy metrics.
- Status: `blocked_data_gate` for a qualifying result. The repaired long-history dataset is a six-current-symbol USDⓈ-M perpetual sample, lacks funding cashflows and point-in-time universe membership, and has only a metadata/coverage fingerprint rather than a full candle-content hash. It is exploratory only for portfolio B&H comparison.
- Next: secure a separately fingerprinted dataset and a valid universe/cost model before preregistering a performance grid. Spot history avoids perpetual funding but does not by itself solve point-in-time universe and delisting bias.
