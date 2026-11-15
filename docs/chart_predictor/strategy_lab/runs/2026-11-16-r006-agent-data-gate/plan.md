# R006 — Agent hypothesis and decision-value gate

Status: preregistered as a **read-only decision-value review**. No price-performance metrics, strategy grid, market-data download, or label generation are permitted in this run.

## Question and decision this run can change

Can any proposed strategy be fairly tested on the currently available and previously exposed Coin_Trade data, and is a public source presently eligible for the project's intended research/use path?

The decision is binary: either register one central performance grid against a complete, rights-compatible, point-in-time dataset, or remain blocked and do not calculate more in-sample performance. The target of two net strategies above matched buy-and-hold is unchanged; this review cannot count a strategy as a candidate or success.

## Prior evidence and duplicate controls

- The requested MACD(12,26) zero-up-cross with Wilder RSI(14)>50 was evaluated in R004 as a long-only strategy, next-bar-open entry, across 12 UTC timeframes and four frozen exits. Validation selected zero of 12 timeframe policies; none of the 48 validation cells beat matched buy-and-hold net CAGR. The final historical segment was not opened because validation selected no policy. This exact setup and its four exits are not to be rerun or retuned under a new ID.
- Prior catalog and decision-value reports reject further performance sweeps on exposed OHLCV histories. The repaired long-history file covers six currently surviving contracts, not a point-in-time futures universe, and funding/cost provenance is incomplete for the broader portfolio objective.
- Existing M4 signal prediction is a separate objective from portfolio net-CAGR versus buy-and-hold. L2 replenishment cannot satisfy the Strategy Lab objective merely by posting a target-first accuracy result.

## Agent roles and outputs

Four roles were assigned, with performance files and raw market datasets excluded from the agent tasks:

1. Trend/momentum: no eligible Strategy Lab test was found. The proposed L2 liquidity-recovery follow-through belongs to the separate M4 track and does not establish buy-and-hold excess portfolio return.
2. Mean reversion: proposed a 15-minute rolling-VWAP deviation/re-entry rule with six ATR-based settings. This overlaps an already explored VWAP/mean-reversion family and the proposed exposed-data run has no decision value.
3. Market regime/cross-section: proposed a market-breadth filter over assets positive on a 14-day lookback. This remains dependent on point-in-time listing eligibility and is not eligible on a current-survivor universe; prior regime-overlay searches also failed out of sample.
4. Independent auditor: confirmed that test purpose, inputs, time boundaries, execution costs, dependence-aware inference, and independent failure tests must be fixed before labels. The audit found no eligible performance test under current data/rights conditions.

These are hypotheses and audit opinions, not evidence of alpha. No trial grid is registered because the minimum data and rights gates fail.

## Data and rights gate

- The local repaired candle DB has historical prices for six selected/current USD-M symbols, but the relevant strategy history has already been viewed during prior research. It is not a sealed evaluation set for new parameter selection.
- Binance's [official public-data repository](https://github.com/binance/binance-public-data) documents daily/monthly USD-M futures klines and aggregate trades from 2020 onward, and its helper describes fetching currently running symbols. This does not establish a complete historical point-in-time tradable universe, delisted-contract history, or eligibility at each past date.
- Its linked [Binance Vision Dataset Terms](https://github.com/binance/binance-public-data/blob/master/TERMS_AND_CONDITIONS.md) are version 1.0, last updated 2026-08-26. The terms state that downloading, caching, querying, or otherwise using the datasets constitutes assent; the stated license is CC BY-NC-SA 4.0 for non-commercial uses, and the terms prohibit live proprietary trading execution and compensated signal distribution. Because the product's eventual use includes real-time chart signals for manual trading, applicability is unresolved. No data was downloaded and no assent was made in this run.
- A future dataset must pass both data completeness/provenance and use-rights review before any performance calculation. Do not assume that a public URL makes the data legally or statistically eligible.

## Frozen stop criteria

Stop without performance metrics if any condition remains true:

1. No point-in-time symbol/contract eligibility and delisting history for the evaluated market.
2. The data period was already exposed to candidate or parameter selection.
3. Dataset terms do not clearly allow the intended personal research and any eventual signal use, or separate written permission is required and absent.
4. Funding cashflows, executable costs, matched buy-and-hold construction, or full input hashes cannot be verified.

No threshold, timeframe, symbol set, or exit rule may be tuned against these exposed intervals. A qualified new dataset requires a separate versioned preregistration before metrics are opened.
