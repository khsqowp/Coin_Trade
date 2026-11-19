# Crypto liquidation-flow candidate gate — 2026-11-20

## Decision

No liquidation-flow performance test is authorized by the available data. Two independent researchers proposed opposing mechanisms from the same event family: fade an extreme liquidation/OI contraction, or trade continuation after a liquidation imbalance. Neither has performance evidence. Do not select between them from intuition or reuse the already-viewed development/sealed windows.

The shared objective remains maximum after-cost compounded wealth across market regimes. Crypto target-first M2 >=80% is a separate signal-quality gate; neither an M2 pass nor a directional hit rate substitutes for positive net expectancy and portfolio NAV growth.

## Primary-source findings

- Binance USD-M's official `!forceOrder@arr` WebSocket documentation calls the feed an all-market liquidation *snapshot*: for each symbol, only the latest liquidation order within each 1,000 ms interval is pushed. It is not a complete liquidation-event tape. A strategy depending on tail-event counts or aggregate liquidation notional must treat this as censored input, not complete event truth. Fields include symbol, side, quantity, average price, status, and order/trade time. [Official WebSocket documentation](https://developers.binance.com/en/docs/catalog/core-trading-derivatives-trading-usd-s-m-futures/api/ws-streams/market)
- Binance's official USD-M `openInterestHist` endpoint supports periods including 5m, but documents only the latest one month, a maximum of 500 rows, and omission of periods with no trades. Its timestamp is the end of the period. This cannot supply multi-year OI history; missing intervals must not be forward-filled or treated as known at interval start. [Official REST documentation](https://developers.binance.com/en/docs/catalog/core-trading-derivatives-trading-usd-s-m-futures/api/rest-api/market-data)
- The Binance Public Data README documents USD-M archive families for klines, aggregate trades, and trades. The reviewed archive index does not document a historical force-order archive. This is a scoped finding about the reviewed public index, not proof that no other licensed provider has such history. [Official public-data README](https://github.com/binance/binance-public-data)
- Binance Vision terms version 1.0, updated 2026-08-26, explicitly apply to derived data, charts, models, and indicators; permitted uses include personal non-production historical backtests, while live proprietary trading and signal distribution are prohibited under those terms. Therefore Vision-derived data cannot be the source for a future personal live/manual signal absent separate written permission. [Official Vision terms](https://github.com/binance/binance-public-data/blob/master/TERMS_AND_CONDITIONS.md)

## Competing hypotheses, not results

1. **Exhaustion / reversal:** an extreme one-sided liquidation snapshot plus falling OI signals forced positioning has been removed; enter against the liquidated side.
2. **Cascade / continuation:** the same event indicates marketable forced flow and constrained liquidity; enter in the price-pressure direction.

The mechanisms make opposite predictions. They must be registered together as a two-hypothesis family before an eligible unseen dataset is inspected, with multiplicity correction and one shared execution/cost model. Testing either after seeing outcomes and then promoting the winner would be data snooping.

## Minimum gates before any test

1. Obtain a lawful, research-eligible source with historical event-level liquidation records and reliable event-time plus first-available/publication-time fields. Confirm whether records are complete or sampled and identify correction/deletion behavior.
2. Obtain aligned OI snapshots and perpetual mark/trade prices, funding, point-in-time listed/delisted contracts, and spread/fee/slippage assumptions. Binance's one-month OI endpoint alone is insufficient for a multi-regime test.
3. Preserve a genuinely unseen validation period and forward interval; do not reopen Trial 99/100 sealed intervals or reuse prior OOS as new confirmation.
4. Pre-register both directional hypotheses, universe construction, signal anchor, entry/exit, tie/gap rules, max holding time, sizing, cost stress, benchmark/cash, event de-duplication, M2 denominator, coverage, and rejection rules.
5. Judge first by cost-adjusted portfolio compounded NAV across regimes versus cash and an eligible benchmark. Report CAGR, Sharpe, MDD, trade count, turnover, regime and symbol breakdown, uncertainty, and target-first M2 separately. No signal-quality gate can rescue negative portfolio growth.

## Current status

- No event data was downloaded or collected; no backtest was run; no outcome was calculated.
- The present local candle database and previously inspected OOS are ineligible as fresh confirmation for this candidate.
- The snapshot feed's documented 1-second sampling further limits use as an exhaustive liquidation-flow signal.
- Next action is source/rights diligence for an event-history provider, not parameter optimization. If a complete, licensed history and untouched evaluation interval cannot be obtained, reject this candidate family as untestable rather than substitute candle-volume proxies.
