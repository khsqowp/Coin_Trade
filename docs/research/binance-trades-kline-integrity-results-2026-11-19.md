# Binance USD-M trades ↔ 1m kline source-integrity results — 2026-11-19

## Decision

**The raw `trades` archives reproduce price OHLC, base volume, trade count, taker-buy base volume, and the kline quote totals when recomputed as `price × qty` across this fixed 80-symbol-day sample. The publisher-provided `quote_qty` field has eight severe row-level arithmetic anomalies, causing 8 quote-volume and 3 taker-buy-quote minute mismatches.** The preregistered full-field gate therefore fails: raw `quote_qty` is not certified for this sample. This is a source-quality result only; it says nothing about predictive or trading value.

## Fixed sample and integrity

- Frozen scope: 20 USD-M perpetual symbols × four UTC dates (`2025-01-01`, `2025-04-01`, `2025-07-01`, `2025-10-01`) = **80 symbol-days**.
- Downloaded inputs: 80 daily raw-trades ZIPs and 80 native 1-minute-kline ZIPs, each with a publisher checksum sidecar (**320 files total**). All 160 ZIP/checksum pairs were re-verified from the local cache on the final run.
- Raw-trade rows parsed: **85,632,531**. All native kline grids contain exactly 1,440 ordered minute rows. There are no missing files, checksum errors, malformed rows, off-day timestamps, duplicate/non-monotone IDs, or active-minute-set discrepancies in the final audit. Trade-ID gaps were recorded in all days (67,274 missing IDs counted by the frozen diagnostic); they are not an automatic failure under v4, and per-minute trade counts still match exactly.
- Full grids: **115,200 minute slots** across 80 symbol-days.

## Field reconciliation

| Field | Mismatches / denominator | Result |
|---|---:|---|
| Open / high / low / close | 0 / 115,200 each | Pass |
| Base volume | 0 / 115,200 | Pass |
| Trade count | 0 / 115,200 | Pass |
| Taker-buy base volume | 0 / 115,200 | Pass |
| Primary `Σ(quote_qty)` vs kline quote volume | 8 / 115,200 | Fail |
| Primary taker-buy `Σ(quote_qty)` | 3 / 115,200 | Fail |
| Diagnostic `Σ(price × qty)` vs kline quote volume | 0 / 115,200 | Pass in this sample |
| Exploratory taker-buy `Σ(price × qty)` | 0 / 115,200 | Pass in this sample; non-gating |

All 8 quote-volume discrepancies were isolated to exactly one raw trade row in each affected minute. Each row's stored `quote_qty` is roughly 10 million times smaller than its `price × qty`; the source archive's publisher checksum still verifies. Three of the eight rows have `is_buyer_maker=false`, matching the three taker-buy-quote discrepancies. This demonstrates the observed arithmetic anomaly, not its cause.

| Symbol / date | Trade ID | UTC timestamp | Price × qty | Stored quote_qty | is_buyer_maker |
|---|---:|---|---:|---:|---|
| BTCUSDT / 2025-01-01 | 5794628446 | 21:06:36.970 | 13,170,396.7500 | 1.3170396 | true |
| BTCUSDT / 2025-01-01 | 5794644675 | 21:21:12.148 | 50,151,765.2800 | 5.0151765 | false |
| ETHUSDT / 2025-01-01 | 4937402465 | 09:18:47.816 | 12,499,998.3500 | 1.2499998 | true |
| BTCUSDT / 2025-04-01 | 6154099212 | 16:49:07.595 | 11,811,090.0000 | 1.181109 | false |
| BTCUSDT / 2025-07-01 | 6441320241 | 14:41:22.868 | 10,275,409.1925 | 1.0275409 | true |
| BTCUSDT / 2025-07-01 | 6441614749 | 15:35:52.776 | 15,853,927.1000 | 1.5853927 | true |
| BTCUSDT / 2025-07-01 | 6442004125 | 19:43:44.525 | 12,709,107.9500 | 1.2709107 | false |
| ETHUSDT / 2025-07-01 | 5899938102 | 07:35:22.461 | 10,142,013.2550 | 1.0142013 | true |

## Limits and next step

The raw `trades` source is a better tested route than `aggTrades` for reconstructing these minute price/size fields, but the full v4 certification fails because the published `quote_qty` is defective in the eight rows above. Do not silently patch or replace `quote_qty` in the v4 result. `price × qty` matched native quote aggregates here, including the separately calculated taker-buy quote diagnostic, but this is an exploratory repair hypothesis on already inspected dates—not independent evidence of universal correctness or an approved strategy feature.

Next permissible work is a separate source-method review: determine whether the official trade schema guarantees `quote_qty = price × qty`, assess whether it is safe to derive quote amounts from price and quantity rather than the defective field, and review archive-vintage/publication behavior. Any follow-up using the already inspected sample remains exploratory. No performance labels, signals, entries, exits, target-first outcomes, costs, or returns were calculated. The sample and derived report are subject to Binance Vision attribution and applicable CC BY-NC-SA 4.0 terms; raw ZIP files remain outside Git.

Machine-readable output with per-minute sets, hashes, and mismatch values: [`binance-trades-kline-integrity-results-2026-11-19.json`](binance-trades-kline-integrity-results-2026-11-19.json). Reconciliation code: [`audit_binance_trades_kline_reconciliation.py`](../../scripts/research/audit_binance_trades_kline_reconciliation.py). Frozen specification: [`binance-trades-kline-integrity-prereg-2026-11-19.md`](binance-trades-kline-integrity-prereg-2026-11-19.md). Exploratory root-cause protocol: [`binance-trades-quoteqty-forensic-addendum-2026-11-19.md`](binance-trades-quoteqty-forensic-addendum-2026-11-19.md).
