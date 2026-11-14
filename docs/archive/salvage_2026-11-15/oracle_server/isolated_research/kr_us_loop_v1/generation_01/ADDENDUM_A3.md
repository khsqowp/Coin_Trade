# Addendum A3 — post-run interpretation audit

Date: 2026-11-06. This addendum does not alter or overwrite Generation 01 metrics.

An independent audit verified the Generation 01 ledger has 22 unique candidate-market attempts, each with one start and one completed result (11 US, 11 KR), and no unmatched or duplicate attempt IDs.

Additional interpretation limits:

- In KR, `load_market()` creates a daily equal-weight return proxy across that day's eligible names for the broad-market regime series used by `MOM_TO_LOWVOL_200SMA` and the market beta in `RESIDUAL_MOM126`. Separately, `benchmark_returns()` creates the headline monthly-rebalanced equal-weight comparison portfolio. They are distinct series and serve different purposes. The result's `data_note` compressed them together as “benchmark/regime”; that wording was imprecise. The headline benchmark return itself is the monthly portfolio, not the daily regime series.
- KR still lacks the registered constituent snapshot, has a mismatching raw universe, and uses a local available-name proxy rather than KOSPI/KODEX. Split repair is heuristic, so the extreme KR losses—especially GAP_REVERSAL_5D—need return-distribution and corporate-action attribution before economic interpretation.
- The US PIT file lists roughly 1,209 tickers, while only 688 had local price files in this mirror. This creates coverage and delisting bias.
- `RESULTS.md` is a derived exploratory report. The JSONL ledger and hash-pinned manifest remain authoritative for run values.
- The preregistered monthly-decision count is absent from Generation 01 result records. Generation 02 must emit it.
