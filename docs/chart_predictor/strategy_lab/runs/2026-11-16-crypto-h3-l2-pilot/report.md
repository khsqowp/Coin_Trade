# Crypto H3 L2 pilot — 2026-11-16

## Decision

Reject this frozen H3 rule as a candidate for the registered 80% high-confidence signal objective. Do not use it for discretionary entries. The one-hour, two-symbol development sample is not validation and cannot establish general performance.

The rule failed the directional threshold at all observed horizons and produced negative mean net quote-cross estimates after the preregistered 10 bp round-trip fee. No threshold or rule was tuned after seeing these results.

## Frozen experiment and input

- Rule: top-five depth quantity imbalance strictly above +0.60 or below -0.60 for three consecutive valid depth updates, followed by a one-tick same-direction mid-price confirmation within one second.
- One signal per symbol per five-second cooldown; markouts at 1, 3, and 5 seconds.
- Symbols: BTCUSDT and ETHUSDT; one captured hour; 194 signals total (BTC 89, ETH 105).
- Input: 121,098 JSONL records; 14,311 depth deltas; 4 snapshots; 0 sequence errors; 0 unbridged snapshots; 7,155 valid reconstructed quote points per symbol.
- Input SHA-256: `aff87b771f2494fdc70ccc424e0a383f32670183d9753a83e68a92b9ebb1a991`.
- Tick sizes were read from Binance `PRICE_FILTER.tickSize`: BTCUSDT 0.10, ETHUSDT 0.01. `pricePrecision` was not used as a tick size. See [Binance USDⓈ-M Exchange Information](https://developers.binance.com/en/docs/catalog/core-trading-derivatives-trading-usd-s-m-futures/api/rest-api/market-data).

## Results

| Horizon | Correct direction | Hit rate | Descriptive Wilson 95% interval | Mean signed mid markout | Mean quote-cross estimate after 10 bp fee |
|---:|---:|---:|---:|---:|---:|
| 1 s | 85/194 | 43.81% | 37.02–50.85% | +0.2885 bp | −9.7483 bp |
| 3 s | 116/194 | 59.79% | 52.77–66.44% | +0.5655 bp | −9.4711 bp |
| 5 s | 112/194 | 57.73% | 50.70–64.47% | +0.5607 bp | −9.4758 bp |

Per symbol, 3-second hit rate was BTC 52/89 (58.43%) and ETH 64/105 (60.95%). Mean estimated net quote-cross result was BTC −9.5920 bp and ETH −9.3687 bp. Signal coverage among valid depth updates was 1.244% for BTC and 1.468% for ETH.

## Comparator and inference cautions

- The fixed-seed random comparator scored 31.96%, 50.00%, and 50.52% at 1/3/5 seconds. This is one seeded draw, not a robust statistical baseline.
- The prior-1-second-mid-momentum comparator exactly matched the candidate at all reported horizons. It is mechanically overlapping with the required one-tick price confirmation and is not an independent benchmark.
- Wilson intervals are descriptive only; they do not account for serial dependence or event clustering. They are not evidence of an independent 194-sample population.
- The quote-cross estimate uses best quotes and subtracts a fixed fee. It omits execution latency, queue priority, market impact, and depth consumption, so it is not a fill simulation; its cost estimate is optimistic.

## Scope and next gate

This pilot has no stop/target outcome, triple-barrier label, macro/regime filter, multi-timeframe context, sealed holdout, or point-in-time 20-symbol universe. It cannot satisfy the registered M4 gate (at least 200 independent observations across at least 20 symbols, at least 10% coverage, target-first point estimate at least 80%, lower confidence bound above baselines, and positive cost-adjusted expectancy). Its two-symbol one-hour input is development data and must not be relabeled as sealed validation.

The observed outcome is a rejection for this objective, not a claim that all order-book strategies are impossible. Any new rule must be separately preregistered and evaluated on genuinely new data with realistic execution assumptions. No orders were placed.
