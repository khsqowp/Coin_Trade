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

The inspected current BTCUSDT archive objects do **not** reproduce issue #491's description of the 2026-06-24 file ending at 2026-06-25 00:00 and overlapping the next file. In this four-day BTCUSDT sample, both sides of the alleged transition use the same start-of-day labeling pattern. This is a direct observation of the objects fetched on 2026-11-19, not proof that the issue report was false.

A cross-symbol check reproduced the issue's additional AERGOUSDT observations. The 2026-01-06, 01-20, 01-22, and 03-18 files each have one timestamp with seconds `02` rather than a five-minute-grid timestamp. The 2026-06-11 and 06-27 files end at next-day 00:00, while the following daily files begin at 00:00; each adjacent pair therefore has one duplicated label whose six metric values differ. In contrast, BTCUSDT's 2026-06-23 through 06-26 files are consistently start-labeled. Current archive evidence thus shows symbol/date-dependent timestamp conventions and conflicts; a single global shift or naïve timestamp deduplication is unsafe.

The samples only establish present-object checksums and these exact row/timestamp observations. They do not establish when values were observable, whether a timestamp is an observation instant or interval boundary, field units/provenance, historical publication versions, or point-in-time causal availability. Therefore `metrics` remains **ineligible as a strategy feature** pending a broader preregistered provenance/availability audit. Do not use a blanket five-minute shift or naïve timestamp deduplication.

## Reproduction manifest

Each SHA-256 below was computed from the downloaded ZIP and matched that archive's published `.CHECKSUM` sidecar. No archive was retained in the repository.

| Symbol | Archive date | SHA-256 | Specific timestamp observation |
|---|---|---|---|
| BTCUSDT | 2026-06-23 | `df14d71acd73d1349eaeae6e281d8eacc7187dfca966c599ff051de0a76f6820` | 288 rows, 00:00–23:55 UTC |
| BTCUSDT | 2026-06-24 | `6bb5ab473189fa7c935b4d9a58d34b2c96cc329cd74fd6f9f17f8abc48ece649` | 288 rows, 00:00–23:55 UTC |
| BTCUSDT | 2026-06-25 | `56e0751dabd8108d61d1f9de86931ac68e901dad202d4dbac03173e2768be68e` | 288 rows, 00:00–23:55 UTC |
| BTCUSDT | 2026-06-26 | `c06c1de4e3ab250acff83e71feb56344ae5b3cf31cd420f3ea9cfcf492976b0c` | 288 rows, 00:00–23:55 UTC |
| AERGOUSDT | 2026-01-06 | `cd95a32779f351c1ccaf142c45123da42796c349751d3906687dfed9349d00c5` | off-grid `02:35:02` |
| AERGOUSDT | 2026-01-20 | `bcf874b41cd030efd052ecd09c6507c1c26036e2e696c33f1a78cf277696276d` | off-grid `20:25:02` |
| AERGOUSDT | 2026-01-22 | `4feb74d2265f636ad720c5765096fcc7efe73262649f945b017ef73717966a87` | off-grid `15:30:02` |
| AERGOUSDT | 2026-03-18 | `7850b49a9a8d0b7139fe9cb5a344d32d7507744f79e5c9ee058b5063838b5b00` | off-grid `19:25:02` |
| AERGOUSDT | 2026-06-11 | `49bcebe61ef32043cb2a115b79ce1883644be7d48f6626e5552859f599661e76` | ends 2026-06-12 00:00 UTC |
| AERGOUSDT | 2026-06-12 | `a9c6e5c3d0fa6ad1c2ca117dd06e4cb03db0e94e46bc754eeb9700bbaf2f2505` | starts 2026-06-12 00:00 UTC; shared row differs |
| AERGOUSDT | 2026-06-27 | `6a86e64e17b8b5c40ba3960c4a446e41db005d3d1653bd9066267b396ff657bf` | ends 2026-06-28 00:00 UTC |
| AERGOUSDT | 2026-06-28 | `8c407b1630a7234e1f9c406550332dd6634b5acb42fe76fe4b96fed0bb683f7c` | starts 2026-06-28 00:00 UTC; shared row differs |

Issue #491 and follow-up issue #509 are community reports/questions in Binance's public-data repository, not Binance confirmations. The underlying sample checksums and rows were independently inspected here; the broader issue claims were not.

## Source references

- Binance Public Data issue #491: https://github.com/binance/binance-public-data/issues/491
- Binance Public Data issue #509: https://github.com/binance/binance-public-data/issues/509
- Sample archive base: https://data.binance.vision/data/futures/um/daily/metrics/BTCUSDT/
- Binance Vision terms: https://github.com/binance/binance-public-data/blob/master/TERMS_AND_CONDITIONS.md
