# R019 — USD-M Vision archive coverage smoke check

Date: 2026-11-16
Parent: `2026-11-16-r018-vision-terms-data-gate`
Status: source-object availability audit; **not a strategy performance trial**

User scope decision: Binance Vision may be used for historical backtesting only. No live or manual trading signals derived from this data are in scope.

## Question

Do official USD-M Vision monthly archives for premium-index, mark-price, and index-price klines exist for each of the six symbols in the repaired local candle cohort at three calendar checkpoints?

## Why this is useful

Four independent reviewers found the premium/index basis mechanism potentially distinct from previously exposed price-only rules, but blocked a performance test until the supplemental inputs are demonstrated. This round checks actual archive-object presence without downloading market data. It cannot establish complete history, quality, non-survivor membership, funding completeness, or strategy performance.

## Frozen request set

- Symbols: `BNBUSDT`, `BTCUSDT`, `DOGEUSDT`, `ETHUSDT`, `SOLUSDT`, `XRPUSDT`.
- Data families: `premiumIndexKlines`, `markPriceKlines`, `indexPriceKlines`.
- Interval: `1h`.
- Monthly checkpoints: `2020-01`, `2023-01`, `2025-01`.
- URL pattern: `https://data.binance.vision/data/futures/um/monthly/{family}/{symbol}/1h/{symbol}-1h-{YYYY-MM}.zip`.
- Method: one HTTP HEAD per symbol/family/month (54 requests), record HTTP status and advertised Content-Length only. Do not retrieve archive bodies.

## Decision rule

- `200` means the exact monthly archive object is advertised as present.
- `404` means that sampled object is absent; it does not distinguish pre-listing from missing archive without independent listing evidence.
- Any other status or transport error is `UNKNOWN` and must not be converted to absence.
- The sample is a smoke check only. No extrapolation from three monthly points to continuous coverage is allowed.

## Prohibited in this round

No OHLC/premium/funding values, indicators, trade outcomes, strategy parameters, or sealed-period results may be read. Do not download, cache, or write source market data. Do not infer point-in-time contract eligibility from current symbols.
