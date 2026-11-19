# Binance USD-M metrics snapshot audit — 2026-11-19

## Purpose and scope

This is a narrow source-integrity check prompted by Binance Public Data issue #491, which alleges a USD-M metrics `create_time` labeling change at 2026-06-25 00:00 UTC. It is not a strategy experiment and no market-outcome labels, entry/exit rules, or performance results were opened or computed.

The read-only sample was limited to BTCUSDT daily Vision archives for 2026-06-23 through 2026-06-26. For each ZIP, the published `.CHECKSUM` sidecar was fetched and its SHA-256 matched the downloaded archive. The CSV header and `create_time` values were inspected in memory; no files were written to the repository.

## Observed results

| UTC archive date | Rows | First label | Last label | Off-grid timestamps | Publisher checksum |
|---|---:|---|---|---:|---|
| 2026-06-23 | 288 | 00:00:00 | 23:55:00 | 0 | Match |
| 2026-06-24 | 288 | 00:00:00 | 23:55:00 | 0 | Match |
| 2026-06-25 | 288 | 00:00:00 | 23:55:00 | 0 | Match |
| 2026-06-26 | 288 | 00:00:00 | 23:55:00 | 0 | Match |

Every row had a five-minute-aligned timestamp with zero seconds. Adjacent archive dates had no shared `create_time` labels. The column set was `create_time`, `symbol`, `sum_open_interest`, `sum_open_interest_value`, `count_toptrader_long_short_ratio`, `sum_toptrader_long_short_ratio`, `count_long_short_ratio`, and `sum_taker_long_short_vol_ratio`.

## Interpretation

The inspected current archive objects do **not** reproduce issue #491's description of the 2026-06-24 file ending at 2026-06-25 00:00 and overlapping the next file. In this four-day BTCUSDT sample, both sides of the alleged transition use the same start-of-day labeling pattern. This is a direct observation of the objects fetched on 2026-11-19, not proof that the issue report was false: archive replacement/history, symbol-specific behavior, and other dates remain untested.

The sample only clears basic present-object checksum, row-count, and timestamp-grid checks. It does not establish when values were observable, whether a timestamp is an observation instant or interval boundary, field units/provenance, historical publication versions, cross-symbol consistency, or point-in-time causal availability. Therefore `metrics` remains **ineligible as a strategy feature** pending a broader preregistered provenance/availability audit. Do not use a blanket five-minute shift based on the issue report.

## Source references

- Binance Public Data issue #491: https://github.com/binance/binance-public-data/issues/491
- Binance Public Data issue #509: https://github.com/binance/binance-public-data/issues/509
- Sample archive base: https://data.binance.vision/data/futures/um/daily/metrics/BTCUSDT/
- Binance Vision terms: https://github.com/binance/binance-public-data/blob/master/TERMS_AND_CONDITIONS.md
