# Generation 06 — cross-sectional low-beta long-only

Date: 2026-11-06. Local exploratory test only. No remote commands, live orders, commit, or push.

## Hypothesis

Test whether a monthly equal-weight basket of the lowest market-beta eligible equities has better risk-adjusted return than the available broad-market benchmark. This is a long-only, unlevered adaptation of the beta-sorted evidence in Frazzini & Pedersen (2014), not a replication of their leveraged low-beta / short-high-beta BAB factor. Primary source: https://doi.org/10.1016/j.jfineco.2013.10.005

This signal is distinct from total-volatility ranking: beta measures covariance with the market relative to market variance, whereas volatility measures total return dispersion. They may be correlated; any result will be treated as an adjacent hypothesis, not independent evidence. Prior code/catalog audit found explicit 252-session total-volatility selection and beta-adjusted momentum, but no explicit low-beta portfolio. This bounded text/source audit is not proof of absence across every historic run artifact.

## Frozen rule and execution

- At each calendar month-end close t, compute daily simple adjusted-close returns for each eligible stock and the market return series from close-to-close data.
- Estimate each stock's OLS market beta with an intercept over the trailing 252 exchange sessions ending at t; require at least 200 finite paired daily stock/market returns, including a valid paired return on decision day t. Beta is sample covariance(stock, market) divided by sample variance(market), using only paired observations in that trailing window. Require market variance > 0. Report the paired-observation count for every selected stock/month; never forward-fill or replace missing returns with zero.
- Select the 20 eligible lowest-beta names in KR and 50 in US. Eligibility additionally requires a finite beta. Rank ascending; ticker is deterministic tie-break. Equal weight selected names, cash for unfilled slots. No leverage, shorting, beta scaling, sector constraints, filters, alternate lookbacks, or parameter grid.
- Signals are formed after close t and execute at open t+1. Hold through the next month-end order; portfolio weights drift between rebalance dates. Use strict Gen05 A1/A2 corrected month-end-only simulator, Gen01 cost assumptions, and strict OHLC validation. Any invalid/missing bar for a held or entering position fails the market attempt, with no imputation.
- US market series: SPY adjusted-close benchmark in the local snapshot. KR market series: for each stock, a leave-one-out daily equal-weight eligible-universe return proxy because KODEX 200 is absent. The proxy is rebuilt from eligible panel returns and excludes the evaluated stock on each date; it is not an official KOSPI total-return index or independently investible market benchmark. All KR conclusions must retain this limitation.
- Use the fixed Gen01 IS / previously inspected later partitions only as exploratory partitions. Do not claim untouched OOS. Universe, corporate-action, delisting and historic trial-count deficiencies remain as in `../FEASIBILITY.md`.
- Exactly two planned new strategy-market hypotheses (one fixed rule in each market). Record start, failure, completion, metrics, data snapshot hashes and curves. No post-result changes; any correction requires a dated addendum and preservation of all previous runs.
- Historical cumulative trial count is unresolved. Do not claim global DSR/PSR/BH or confirmatory inference. A positive screen is only a lead for an independent, repaired-data holdout.

## Stop rules

Fail closed on missing benchmark, invalid or insufficient paired data, lookahead/execution inconsistency, invalid held/entry OHLC, non-finite order weights or gross exposure above 100%. Preserve the failed attempt. No results from this generation establish a deployable edge.
