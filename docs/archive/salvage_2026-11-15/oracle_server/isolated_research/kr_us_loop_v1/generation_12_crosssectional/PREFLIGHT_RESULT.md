# Generation 12 PIT endpoint-coverage preflight

**Disposition: `FAILED_DATA_COVERAGE`. Stop here. No signal, score, return, rank, portfolio weight, backtest, or performance metric was calculated.**

## Frozen snapshot

The hash freeze was computed before opening any parquet columns. It commits the preregistration/plan, the local PIT file, SPY parquet and metadata, all expected PIT-ticker parquet/metadata files (and absent-file names), plus the listed loader/simulator/metric source files.

- Candidate: `GEN12-US-PIT_MONTHLY_LOSER_REVERSAL_BOTTOM_DECILE`
- Preregistration SHA-256: `5037a310e29481d41e15a24d8228adbd35156dc6bd9f6470e637cf7ea01733c5`
- Implementation-plan SHA-256: `a1751d4f3de683d7e8fdea8541100f82c5a4a00d5b203a2287b0e09b72ac742a`
- PIT CSV SHA-256: `b2f4fe2f2e4dce8eaf0eb4fbd3946a32a20c1ddfe69687dfca3b6b59a0b71f9f`
- Frozen inventory-root SHA-256: `829577fc3bcfac052f2a2dca8dcfeedb4df5c8b10ec010d2f72dbf2aa30f64dc`
- Frozen data-inventory SHA-256: `2e302a1df10438a8a536b5b523a0b3e4e2ce18a21dbdecf69f792eb515bbd1a0`
- PIT membership: 1,262 rows, 1,209 unique normalized tickers; no overlapping normalized membership spells found.
- Input inventory: 1,444 files hashed, 204,678,630 bytes; 984 expected per-ticker parquet/metadata files absent. Of the 1,209 PIT tickers, 717 parquet files had a readable date index and 492 had no parquet file.
- Source hashes: `generation_01/run_gen01.py` `0801a95324cf598a91483ff54ef70aa72a530a78bc6ba41fb41680972268874d`; `generation_03/run_gen03.py` `2be8b342e154952d2536308311db38eaf875f5267a9fce64dc24791c6161e3cc`; `generation_04/run_gen04.py` `a3720b907a93ef974dbbe880167f80d44c5c7b9aa782fdad9fbddc04d118b731`; `generation_05/run_gen05.py` `e705d9296f83544aaace24b6379884e81595b801246c175f95fcb28121e15c47`; `generation_07/run_gen07.py` `62b948d2405eec05c29da3c3cea35074ae212020bcb4ebfe3cb68d0700037fde`.

## Gate measurement

Method: the PIT membership CSV and parquet `date` columns only. The date-column inspection checked whether every active PIT ticker had a row on both the previous and current SPY month-end session. No OHLC, adjusted-close, or volume values were used for this gate. Row presence is a necessary but not sufficient condition for a valid finite positive adjusted-close score, so this is an upper bound on actual score coverage.

The SPY date index contains 8,498 unique ascending sessions from 1993-01-29 through 2026-11-02. The incomplete final calendar month, 2026-11, was excluded. There were 405 PIT month-end decisions from 1996-01 through 2026-10. The frozen requirement is at least 85% of all active PIT members with both endpoint rows in **every** tested month.

| Measure | Observed |
|---|---:|
| Months meeting 85% date-row coverage | 120 / 405 |
| Months below 85% | 285 / 405 |
| Monthly PIT denominator range | 487–505 |
| Both-endpoint-row coverage, minimum | 37.1663% |
| Both-endpoint-row coverage, median | 69.2153% |
| Both-endpoint-row coverage, maximum | 100.0000% |
| First failed month | 1996-01 |
| Last failed month | 2019-09 |
| Months passing this necessary date-row check | 2019-10–2026-10 |

First failure, with exact denominator/missingness: January 1996 used the 1995-12-29 and 1996-01-31 SPY endpoints; 181 of 487 active PIT names (37.1663%) had both date rows. There were 252 active names with no local parquet and 54 additional names whose parquet lacked the prior endpoint date row; no present-file ticker lacked the current endpoint row. This alone is far below the 85% gate. Every later month through September 2019 also failed. Since valid adjusted-close coverage cannot exceed date-row coverage, the candidate fails without inspecting price values.

The full date-index-only monthly scan returned exact denominator, endpoint-row, and missing-file/date counts for every month; its aggregate values are preserved above. The output was not expanded into a second artifact after the first below-threshold result, to honor the stop-after-failure boundary. No market-value payload was decoded by the coverage scan.

## Process deviation and attempt record

One initial Parquet schema-probe command printed row-group minimum/maximum metadata for OHLC columns while checking the file layout. It did not decode rows or calculate a return, but the printed extrema are price-valued metadata and exceeded the strict no-price-values boundary. Those extrema were not used in the coverage calculation or candidate decision. The deviation was immediately disclosed to the root reviewer and is retained here for audit.

A first date-column scan invocation also stopped on a pandas timezone-conversion API error after reading the SPY date column only; it produced no coverage result. The corrected metadata-only scan produced the single candidate preflight outcome below. These are tooling notes, not extra strategy candidates or performance runs.

- Attempt ID: `GEN12-20261106-US-PIT_MONTHLY_LOSER_REVERSAL_BOTTOM_DECILE`
- Terminal status: `FAILED_DATA_COVERAGE`
- Failure boundary: 285/405 months are below the preregistered 85% minimum even under the more permissive date-row-presence test.
- No score computation or backtest is authorized by this result. Do not rerun, alter the universe, loosen the threshold, or call this a strategy-performance rejection.
- Next dependency: obtain a reconciled local PIT member-price snapshot with at least 85% coverage in every historical month, then preregister a new candidate/data freeze if the root chooses to reopen the hypothesis.
