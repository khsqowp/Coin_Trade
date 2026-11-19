# Binance USD-M trades `quoteQty` anomaly follow-up — 2026-11-19

Status: post-hoc source-integrity diagnostic only. This does not change the frozen reconciliation gates, certify a trading feature, or test a strategy.

## Scope and method

- Reused the fixed 20-symbol × 4-UTC-day sample from [`binance-trades-kline-integrity-prereg-2026-11-19.md`](binance-trades-kline-integrity-prereg-2026-11-19.md): 80 symbol-days, 2025-01-01, 2025-04-01, 2025-07-01, and 2025-10-01.
- Read the checksum-verified Binance Vision USD-M `trades` CSV archives and their matching native 1-minute kline archives. No source data was modified.
- Independently scanned all 85,632,531 trade rows. For each row, compared the archive's `quote_qty` with `price × qty` using relative tolerance `1e-8` and absolute floor `1e-10`.
- As a separately labeled diagnostic, accumulated `price × qty` by UTC minute and accumulated taker-buy quote value only when `is_buyer_maker=false`; compared those values with native kline `quote_volume` and `taker_buy_quote_volume` over all 115,200 minutes.

## Results

- Eight trade rows exceeded the row-level `quote_qty` tolerance, all in BTCUSDT or ETHUSDT. Each anomalous row's `quote_qty` is near 1–5 quote units while `price × qty` is about 10–50 million quote units.
- Reconstructed `price × qty` quote volume had **0 mismatches / 115,200 minutes** against native kline quote volume.
- Reconstructed taker-buy quote volume had **0 mismatches / 115,200 minutes** against native kline taker-buy quote volume.
- The original preregistered raw-`quote_qty` comparison remains a failure for five symbol-days and the 8 affected minutes. This follow-up does not replace that failure with a pass; it identifies a derived alternative and documents its separate result.
- No forecast, entry, exit, target-first outcome, return, M2 score, or strategy comparison was calculated.

## Eight anomalous rows

| Symbol | UTC date | Trade ID | Price | Qty | Archive `quote_qty` | `price × qty` |
|---|---|---:|---:|---:|---:|---:|
| BTCUSDT | 2025-01-01 | 5794628446 | 94,850 | 138.855 | 1.3170396 | 13,170,396.75 |
| BTCUSDT | 2025-01-01 | 5794644675 | 94,880 | 528.581 | 5.0151765 | 50,151,765.28 |
| BTCUSDT | 2025-04-01 | 6154099212 | 85,000 | 138.954 | 1.181109 | 11,811,090.00 |
| BTCUSDT | 2025-07-01 | 6441320241 | 106,077.5 | 96.867 | 1.0275409 | 10,275,409.1925 |
| BTCUSDT | 2025-07-01 | 6441614749 | 106,150 | 149.354 | 1.5853927 | 15,853,927.10 |
| BTCUSDT | 2025-07-01 | 6442004125 | 105,350 | 120.637 | 1.2709107 | 12,709,107.95 |
| ETHUSDT | 2025-01-01 | 4937402465 | 3,325 | 3,759.398 | 1.2499998 | 12,499,998.35 |
| ETHUSDT | 2025-07-01 | 5899938102 | 2,465 | 4,114.407 | 1.0142013 | 10,142,013.255 |

## Interpretation and limits

The eight rows are internally inconsistent in the published `quote_qty` field; the publisher checksums establish archive-byte integrity, not semantic correctness of every field. The exact cause of these exceptional records is unknown. `price × qty` reproduced the sampled native kline quote fields, but this result is confined to the fixed 80-day sample and is not a universal source guarantee. Preserve both the preregistered raw-field failure and this post-hoc reconstruction diagnostic in any downstream data-quality decision.

Source: Binance Public Data USD-M Futures `trades` and `klines` archives. Binance states the USD-M trade archive fields and kline field meanings in its [official public-data README](https://github.com/binance/binance-public-data/blob/master/README.md). The source terms specify historical, personal, non-production use and CC BY-NC-SA 4.0 for derivative works; this report is marked CC BY-NC-SA 4.0 and is not for live signal distribution or production trading. See the [official terms](https://github.com/binance/binance-public-data/blob/master/TERMS_AND_CONDITIONS.md).
