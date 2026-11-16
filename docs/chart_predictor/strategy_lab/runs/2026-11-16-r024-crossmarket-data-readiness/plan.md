# R024 — cross-market data readiness and next-step gate

Status: **read-only feasibility audit; no strategy performance trials run**.

## Objective

Determine whether the current repositories and publicly documented data routes permit another meaningful local-first research cycle for (1) KR and US stocks/ETFs, and (2) selective crypto long/short chart signals. Avoid repeating rejected or already-exposed strategy grids. Record the exact data blocker and the minimum condition for a legitimate next test.

## Scope and boundaries

- Read existing research reports and specifications in the isolated Coin_Trade research checkout.
- Query only aggregate metadata from the local repaired Binance Vision candle database and the current 100-symbol collector database, opened read-only.
- Use four independent agents: two for KR/US stock/ETF source feasibility and two for crypto M4-data/novelty red-team review.
- Read public official source/product documentation only. No account creation, API key request, provider contact, purchase, live signal, exchange credential, order, or server operation.
- Do not inspect or score sealed/validation price rows. Do not rerun MACD-zero/RSI-50, P5–P9, R021b, or R023.
- Binance Vision is restricted to the already-approved personal, non-production historical-backtest scope. No real-time/manual-trading signal may be derived from this data under this research authorization.

## Frozen decision rule

Run a new performance trial only if an eligible input set can meet the target track's pre-existing requirements before looking at any new result:

- Crypto M4: at least 20 eligible symbols; a synchronized historical/forward panel; no known exposure in the evaluation segment; a predeclared target/stop/time barrier and cost model; sufficient independent event clusters for N≥200; calibrated probability threshold with ≥10% coverage; final sealed evaluation available only once. A candidate must reach ≥80% point estimate, beat matched baselines by Wilson-95 lower bound, and have positive net expectancy after costs.
- KR/US stocks and ETFs: authorized reproducible prices, point-in-time universe including inactive/delisted instruments, corporate actions/total-return treatment, instrument-specific taxes/fees, execution assumptions, and the still-unset maximum drawdown policy.

If any required gate is absent, return `NO_GO_DATA_GATE`; do not fabricate a strategy trial or interpret missing data as a negative strategy result.

## Exclusions

Prior negative/exposed runs remain evidence and are not rerun under new names. This is a source/data readiness audit, not an alpha or strategy-performance test. Any accidental search output that may have touched validation-named material is treated as a boundary incident; affected material cannot be used as the final sealed set without a fresh independent audit and user-approved replacement boundary.
