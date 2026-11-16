# R031 — multi-symbol recent OI timestamp cross-check

**Result: the `create_time + 5m` label alignment generalizes across this recent sample, but true publication latency and long-history availability remain unproven.** Across 32 symbols and three dates, all 27,647 matched Vision OI values were exactly equal to the public USD-M OI-statistics REST value timestamped five minutes after the Vision label. This is a cross-publication-path consistency check from the same exchange, not an independent market-data source and not a strategy result.

## Frozen sample and results

- The preregistered universe had 37 symbols and fixed UTC dates **2026-11-04, 2026-11-08, 2026-11-12** (111 possible symbol-days). No replacements were made.
- All 111 read-only REST requests returned HTTP 200 arrays. Ninety-six symbol-days had a Vision ZIP and publisher checksum; all 96 passed SHA-256 validation. These cover 32 symbols × 3 dates.
- For the other 15 symbol-days (ALPHAUSDT, BALUSDT, BLZUSDT, ICXUSDT, and RENUSDT × the three dates), both Vision objects were 404 and REST returned an empty array. This means unavailable in the tested public paths; it does not by itself establish delisting or a precise contract end time.
- The 96 available daily metrics files contained **27,647 rows**: 95 had a complete 288-slot grid, and ZRXUSDT on 2026-11-12 had 287 rows, one missing 5-minute slot. No replacement or imputation was used.
- REST returned 27,743 observations. Overlapping comparisons:

| REST timestamp compared to Vision `create_time` | Matched values | Maximum relative error |
|---|---:|---:|
| −5 minutes | 27,550 | 21.58% |
| same label | 27,646 | 16.94% |
| +5 minutes | **27,647** | **0%** |

All 27,647 matched `+5m` values were exact under the parsed numeric representation. The only absent expected comparison is the missing Vision row in the ZRXUSDT archive noted above. Same-label and −5-minute matches were not exact throughout; the maximum errors show why joining on the display label would misalign the OI observation.

## Interpretation and limits

- For these 32 currently returning symbols and these three dates only, treat the Vision OI value as belonging to the five-minute interval ending at `create_time + 5m`; use it no earlier than that interval end in a causal replay.
- This does not reveal the exchange's actual first-publication or network-receipt time. A value timestamped at interval end may have been delivered later; timestamp matching alone cannot measure dissemination latency.
- Binance documents that the USD-M OI-statistics endpoint exposes only the latest one month, limits `limit` to 500, and omits intervals without trades. Those absences must remain missing, never be interpreted as zero OI. [Official OI Statistics documentation](https://developers.binance.com/docs/derivatives/usds-margined-futures/market-data/rest-api/Open-Interest-Statistics).
- Historical archive coverage, point-in-time contract epochs, fee/slippage data, and a sealed OOS candidate remain unresolved. No signal, outcome label, or performance score was generated. The target-first ≥80%, N≥200 gate remains unopened; deadline-close direction accuracy remains a separate metric.

Detailed per-symbol-day availability, checksums, grid counts, matched-point counts, and error summaries are preserved in `results.json`; raw response JSON and ZIP files remain outside Git at `/private/tmp/r031-oi-availability-crosscheck/`.
