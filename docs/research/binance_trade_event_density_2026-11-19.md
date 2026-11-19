# Binance USD-M raw-trade event density — 2026-11-19

**Classification:** descriptive source-resolution audit only. Not a strategy test, predictive result, or evidence of trading edge.

## Frozen sample and checks

- 20 symbols × four isolated UTC dates (2025-01-01, 2025-04-01, 2025-07-01, 2025-10-01): 80 symbol-days.
- 85,632,531 raw trade rows; 43,235,452 buyer-initiated and 42,397,079 seller-initiated under the Binance buyer-maker convention.
- All 80 archives passed manifest SHA-256 + publisher sidecar, expected CSV member/header, increasing trade ID, nondecreasing in-day timestamp, and nonempty-file checks. No row was dropped.
- Five symbol-days had previously recorded cross-source quote-volume/taker-buy-quote mismatches. They were retained rather than used to select the event-density sample; these mismatches remain separate data-quality caveats.

## Fixed-bin counts pooled over all 80 symbol-days

| Bin width | Expected bins | Nonempty | Active share | All-bin p50 / p95 / p99 / max | Nonempty-bin p50 / p95 / p99 / max |
|---:|---:|---:|---:|---:|---:|
| 1 second | 6,912,000 | 4,653,777 | 67.33% | 2 / 53 / 144 / 6,498 | 6 / 70 / 178 / 6,498 |
| 10 seconds | 691,200 | 686,044 | 99.25% | 56 / 441 / 1,076 / 21,882 | 57 / 443 / 1,081 / 21,882 |
| 1 minute | 115,200 | 115,200 | 100.00% | 363 / 2,531 / 5,824 / 68,283 | 363 / 2,531 / 5,824 / 68,283 |

All-bin percentiles include empty bins and use nearest-rank `ceil(p*n)`. The raw aggregate JSON contains per-symbol-day totals and density summaries in [binance_trade_event_density_2026-11-19.json](/private/tmp/cointrade-round5-ready/docs/research/binance_trade_event_density_2026-11-19.json). The protocol and limitations are in [binance-trade-event-density-prereg-2026-11-19.md](/private/tmp/cointrade-round5-ready/docs/research/binance-trade-event-density-prereg-2026-11-19.md).

## Interpretation

The fixed archive is dense enough to measure trades in 1-second and coarser bins on these four dates. It does not establish continuous coverage, representative regimes, executable spread/depth, signal frequency, target-first precision, or predictive performance. No candidate was tested or promoted; the crypto ≥80% target-first gate remains unmet and unassessed by this audit.

Source: [Binance Public Data README — USD-M trades schema and checksums](https://github.com/binance/binance-public-data/blob/master/README.md#trades). Preserve attribution and applicable CC BY-NC-SA 4.0 terms. Raw trade archives and the input audit manifest remain outside Git.
