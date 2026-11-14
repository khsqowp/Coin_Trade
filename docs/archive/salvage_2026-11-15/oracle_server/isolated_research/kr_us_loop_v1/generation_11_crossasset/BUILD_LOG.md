# Generation 11 build / verification log

All work and artifacts in this record are confined to this directory. No Oracle connection, remote command, production process, order, commit, or push was made.

| Stage | Outcome | Detail |
|---|---|---|
| Source/prior-run audit | Completed | Prior US v1/v2 includes sector momentum/rotation, broad trend timing, and volatility targeting. US v2 X6 tests weekly bottom-50 individual-stock 5-day reversal. No exact prior rule matching monthly bottom-three sector ETF reversal was found in the bounded preregistration/report scan. Candidate is correlated to the reversal and sector-rotation families, not independent evidence. |
| Frozen candidate | Completed | `PREREG.md` frozen before signal rankings or performance calculations; SHA-256 is in `FREEZE.md`. |
| TDD RED | Expected failure | Initial test import failed because `run_gen11.py` had not yet been created; no market data or performance was accessed. |
| Initial GREEN attempt | Found test issues | OHLC synthetic fixture lacked a DatetimeIndex; fee expectation omitted the second holding interval's return. Both were test-fixture/assertion errors, not strategy results. |
| Initial market-data integrity preflight | Failed before signals/performance | The runner initially added an adjusted-OHLC ordering condition beyond the frozen raw-OHLC rule. It rejected 37/7,008 XLB rows where derived adjusted-high versus adjusted-open/close differed only at floating-point precision; maximum relative excess was `1.82e-16`. Raw bars were ordered. No monthly ranks, holdings, return stream, or performance statistics were computed. |
| Preflight correction | Applied | Removed only that unregistered derived adjusted high/low ordering gate; retained raw OHLC integrity and finite/positive adjusted-open checks. Added a test that a valid raw bar with adjustment rounding is accepted. This matches the frozen specification; it does not alter the signal or data. |
| Current unit suite | Passed after correction | Eight unit tests cover deterministic ranking/tie-break, next-open scheduling, incomplete-month censoring, no future-month selection, weight drift, turnover/entry/liquidation costs, raw-OHLC rejection, adjusted-rounding acceptance, and metric definitions. |
| Market-data integrity preflight after correction | Passed | The nine sector date indexes match exactly (7,008 rows; 1998-12-22–2026-11-02), SPY covers all sector dates, raw OHLC and adjusted-open gates pass, and ten parquet SHA-256 hashes were recorded. This loader check computed no monthly ranks, holdings, return stream, or performance statistics. Parent independently reviewed the final preregistration/runner/test hashes and approved one run. |
| Frozen performance run | Completed once | `GEN11-20261106T124600-034`; all three frozen hashes matched before and after execution. No parameter variants or reruns. Detailed net results and artifacts are in `RESULTS.md`. The fixed strategy was rejected under its preregistered rule; this is not evidence that no profitable strategy exists. |

Source rationale: the local project has tested adjacent momentum/reversal and sector-rotation ideas; the one-month reversal literature is a primary-paper lead, not evidence that aggregate sector ETFs inherit the effect. See the source/overlap caveats in `PREREG.md`.
