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
- Historical R018–R020 gate: the inspected candle DB lacked funding cashflows and point-in-time contract membership; its six-current-symbol sample was not suitable for portfolio Buy-and-Hold comparison.
- `runs/2026-11-16-r021-funding-macro-reentry/`: funding-crowding + BTC macro + pullback/re-entry signal experiment. First output was invalidated for crossing the exclusive development boundary; corrected `r021b` is the only result used. All target-first rates were below 49%, and all net-R means were negative after frozen base and stress costs.
- `runs/2026-11-16-r023-btc-shock-alt-laggard/`: retrospective exploratory pilot of BTC 4h shock + cross-asset beta-residual laggard + 5m range-break entry. The filter retained 25.7% of baseline trades, but target-first was 30.0% versus 29.2%, paired event-bootstrap difference CI crossed zero, and net expectancy was negative for both. This was not preregistered before execution and is not confirmatory evidence.
- `runs/2026-11-16-r022-equity-public-source-followup/`: official-source follow-up. KRX lists daily stock and ETF API data from 2010; CRSP documents active/inactive daily/monthly securities and corporate actions. No public numeric quote or directly downloadable authorized sample was verified; no account, API key, contact, or purchase occurred.
- Crypto status: `0` qualified M4 signals. R021b and R023 use six current survivors only and exposed development data; neither meets the 20-symbol/point-in-time/sealed gates. Both are rejection studies, not signal authorizations.
- Portfolio status: `0/2` qualified strategies. Equity agents returned hypotheses and a data-gate review only; no stock/ETF historical panel was available for performance testing. The 20% CAGR objective is not evidence of achieved performance, and maximum drawdown remains unset.
- Next: continue with a materially different, preregistered strategy mechanism only when it has decision value. For equity backtests, first obtain an authorized daily stock+ETF dataset with point-in-time membership, inactive/delisted names, corporate actions, and a cost model. KRX API key/account setup or CRSP sample/quote contact requires separate user authorization.
