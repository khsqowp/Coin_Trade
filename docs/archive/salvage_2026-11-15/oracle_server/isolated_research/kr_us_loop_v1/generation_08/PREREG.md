# Generation 08 — US low market-model residual skewness

Registered: 2026-11-06 (Asia/Seoul). Exactly one exploratory US equity screen. No KR performance run: the KR loader's split repair/universe/benchmark issues remain unresolved. No remote commands, live trading, commit, or push.

## Rationale and evidence boundary

Boyer, Mitton, and Vorkink (2010) study expected idiosyncratic skewness and returns, while cautioning that lagged realized skewness alone does not adequately forecast expected skewness. This candidate is a simple historical realized-residual-skew proxy, **not** their expected-skewness model or a replication. It is economically adjacent to Gen05's MAX21 lottery-tail proxy and other low-risk sorts, but uses the distribution-wide market-model residual asymmetry rather than the single largest daily return.

Primary source: https://doi.org/10.1093/rfs/hhp041 . A high/low result on these inspected and incomplete data would be a lead only; it cannot validate the literature, establish an independent alpha family, or pass the project's untouched-OOS gate.

## Frozen signal and portfolio

1. Market: US only. Use adjusted close returns from the existing loader: stock total return `r_i=C_i[t]/C_i[t-1]-1`; market total return `r_m=SPY[t]/SPY[t-1]-1`. There is no risk-free series in the mirror; the signal is a **SPY market-model residual skew**, not CAPM excess-return skew.
2. At each completed calendar month-end close t, use the trailing 252 exchange-session rows ending at t, including t. For each PIT member with a finite positive close on t, use only rows with finite stock and SPY returns. Require >=200 paired return observations. Fit the OLS model with an intercept on this window: `r_i = alpha + beta*r_m + e`. Compute the population standardized third central moment of the in-window residuals: `mean((e-mean(e))^3) / mean((e-mean(e))^2)^(3/2)`. Require finite residual variance strictly greater than `1e-20` (daily-return variance units), a fixed numerical floor to reject effectively constant residual series; no imputation or ffill.
3. Coverage denominator: all **unique** S&P 500 tickers active on t in the PIT membership file, including names without local price files. Reject the attempt if any normalized ticker has overlapping active membership intervals. Numerator: those active members with a local finite score under rule 2 and the existing equity-type filter. Require >=85% full-PIT score coverage. A failing month targets 100% cash until the next monthly decision. If no completed decision month passes, fail the attempt.
4. When coverage passes, rank score ascending, ticker ascending for exact ties; hold the lowest-skew 50 names equal weighted, long-only, with cash for fewer than 50 valid names. No leverage, shorting, sectors, volatility scaling, stop, or alternative parameters.
5. Form after the month-end close and execute at the next exchange session open. Hold until the next month-end order. Use existing strict Gen05 OHLC simulator and existing US costs (10 bp buy and sell). Any invalid/missing OHLC for a held or entering name fails the attempt; no stale-price or zero-return substitution. Exclude the final observed calendar month as incomplete.

## Evaluation / stop rules

- Exactly one planned candidate-market attempt. Compare net returns against local SPY and report existing IS / later-inspected windows descriptively only. They are not untouched OOS. Report full-PIT score coverage, qualifying months, invested exposure, turnover, cost assumptions, and actual data availability/hash scope. The reproducibility fingerprint must include content hashes of the complete PIT membership CSV, SPY parquet, and every member ticker's price/metadata file (or explicit absent status); mark the snapshot non-atomic.
- Fail closed on unavailable/invalid benchmark, invalid date/membership intervals, non-finite weights/returns, execution integrity failure, or zero coverage-passing completed months. Record failures and return a non-zero process status.
- Historical all-project trial count remains unresolved. Do not claim DSR/PSR/BH significance or a confirmed edge. No post-result tuning. A correction needs a dated addendum and preserved earlier artifacts.

