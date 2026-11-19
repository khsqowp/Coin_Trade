# Raw-trades quoteQty forensic addendum — 2026-11-19

## Status and boundary

This is an explicitly **post-result, exploratory source-diagnostic addendum** to the frozen v4 integrity audit. The v4 output had already exposed quote-volume discrepancies in eight UTC minutes. This addendum cannot retroactively turn those observations into confirmatory evidence, does not change the frozen v4 acceptance rule, and is not a forecast or strategy test.

## Frozen forensic checks

Using only the already downloaded, publisher-checksum-verified 80-symbol-day sample:

1. In the eight minutes already identified by v4 as primary `quote_volume` mismatches, inspect each raw trade row and compare its archived `quote_qty` with `price × qty` under the same `1e-8` relative / `1e-10` absolute tolerance. Report the full mismatching row identity and values. Do not select additional dates or symbols based on this result.
2. Across the full 80-symbol-day sample and all 115,200 minute slots, calculate derived taker-buy quote amount as `Σ(price × qty)` only where `is_buyer_maker == false`. Compare with native-kline `taker_buy_quote_volume` under that same tolerance. Keep this as a separate non-gating diagnostic; it does not replace the preregistered primary `Σ(quote_qty)` field or make a failing v4 cell pass.
3. Do not calculate labels, signals, target-first rates, returns, or strategy metrics. No parameter search or threshold change is permitted.

## Interpretation rule

The report may state whether row-level quoteQty anomalies explain the already observed discrepancies and whether the deterministic product-derived quote aggregates match this sample. It may not claim universal Binance archive correctness, causal source corruption, live-data suitability, or predictive value. Any future model using product-derived quote flow needs a new candidate-specific preregistration and an independently valid chronological evaluation.
