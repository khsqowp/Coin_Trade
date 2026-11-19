# Preregistration — KODEX 200 volatility-target exposure

- Trial: `KR-KODEX200-VOL10-LB20-20261120-DEV`
- Status: fixed before reading any strategy outcomes in this trial.
- Primary objective: maximize after-cost compounded wealth. CAGR >=20%, MDD <=30%, Sharpe >=1.0 and OOS completed trades >=200 are the previously fixed equity qualification gates; this exploratory development run cannot pass the OOS gate.
- Scope: one Korean ETF, KODEX 200 (`069500`), no shorting or leverage. This is a single-asset risk-allocation hypothesis, not an all-KRX market strategy.

## Hypothesis and fixed rule

Scaling KODEX 200 exposure inversely with its recent realized volatility may improve long-run compounded wealth by reducing the damage of high-volatility drawdowns while retaining exposure in calmer periods.

- Input file is supplied by explicit `--data`; read only. Expected fields: `timestamp,Open,High,Low,Close,Volume`.
- Only records with UTC timestamp strictly before `2024-11-12T00:00:00Z` may be parsed. Rows at or after the boundary are not parsed or used. This boundary preserves the already designated later holdout.
- Universe is the single fixed ETF `069500`; no constituent selection.
- At each month's final observed session, calculate the sample standard deviation of the latest 20 close-to-close simple returns, annualized by `sqrt(252)`. Target weight is `min(1, 0.10 / annualized_volatility)`. If volatility is zero, weight is 100%.
- Execute the target at the next observed session's open. Hold until the next scheduled monthly execution. Uninvested balance earns 0%; no yield or financing is assumed.
- Portfolio return uses adjusted-mode OHLC as supplied by the cache. Position returns are open-to-next-open; no same-close fills or forward filling. Corporate-action and distribution adjustment semantics remain unverified and are a stated data limitation.
- Base one-way cost is 0.115% of traded notional at every exposure change; stress cost is 0.165%. Charge the absolute change in portfolio weight at each rebalance and one terminal liquidation fee on any remaining position.
- Benchmarks over exactly the same execution intervals: 100% KODEX 200 buy-and-hold with entry/exit costs, and zero-yield cash.

## Fixed evaluation

- Development window: available data beginning 2010-08-09 through 2024-11-11. No data after the exclusive cutoff is eligible. This historical period has been inspected by related equity research; results are exploratory, not untouched OOS.
- Primary cell: 20-session volatility lookback, 10% annualized target, 0.115% one-way costs.
- Stress cell: same rule at 0.165% one-way costs.
- Predeclared sensitivity only: lookbacks `{16,20,24}` sessions × volatility targets `{8%,10%,12%}`, each at base and stress cost. Report all cells; do not choose or promote a neighbor based on results.
- Report after-cost terminal NAV, CAGR, Sharpe (252 sessions), MDD, annual returns, average exposure, turnover, rebalance count, and regime-period returns for 2010–14, 2015–19, and 2020–cutoff. Periods are descriptive, not independent OOS folds because no parameter is fitted.
- Run 1,000 deterministic 20-session moving-block bootstrap paths of paired strategy and buy-and-hold daily returns (seed `20261120`). Report p95 MDD and the fraction of bootstrap paths where the strategy's terminal wealth beats buy-and-hold. The bootstrap quantifies path sensitivity only; it does not repair selection bias or data provenance.
- No parameter search beyond the fixed sensitivity matrix, no rerun after seeing results, no sealed-period access, no live/manual signal use, and no orders.

## Advancement rule

This candidate is rejected for further promotion if the base case misses any stated equity gate that can be assessed on this development sample, if stress-case net terminal wealth is below cash, or if it fails to beat KODEX 200 buy-and-hold on paired block-bootstrap median terminal wealth. Because this run is not untouched OOS and has one ETF, even a favorable development outcome would remain exploratory and could not qualify the strategy. The >=200 OOS completed-trade gate is explicitly unmet until a separate, frozen, genuinely unseen evaluation is authorized.

## Data and licensing caveats

The local KIS cache file is not copied into Git. Public documentation confirms KIS Open API supports daily historical market-data queries, but the exact source request parameters, adjusted-price behavior, data-use rights for derived research, and completeness of corporate actions/distributions are not established by this cache alone. No account, key, purchase, or external data request is involved in this run. Any figures are internal exploratory results only; no raw market data is to be committed.
