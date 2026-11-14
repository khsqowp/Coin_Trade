# Generation 11 freeze

Pre-performance freeze timestamp: `2026-11-06T12:40:22Z`.

The strategy rule, candidate scope, data boundary, accounting, fees, benchmark, sample handling, and rejection criteria are preregistered in `PREREG.md` before any performance statistics were computed. Final pre-run SHA-256 values:

- `PREREG.md`: `d69c543ec24f2a6ca2a18fdc5af546eb2adff77484e358fe73ba7308af86adda`
- `run_gen11.py`: `a7a97c455a32dcbdf89cd2ddc5ac4441ee0c67b5ea50a99b5d79a992cbe8c1bb`
- `test_gen11.py`: `9823b64383bf70824cfda7ff5d55ab6b2584d2dbc49b660a713e65e8e2855b8c`

Do not edit any of these frozen files after approval without a dated addendum and new attempt. Any future source correction must preserve this freeze and its outcome.

Pre-performance input audit only: the nine specified sector ETF parquets exist, each has 7,008 rows, and their date indexes run 1998-12-22 through 2026-11-02. All nine indexes are exactly equal; SPY has a superset index. The raw OHLC and adjusted-open checks passed. No return series, rankings, holdings, or performance statistics were computed. Parent's independent review of the final hashes is required before the single market performance run.
