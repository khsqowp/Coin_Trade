# KR/US cross-sectional candidate forward-window protocol

Status: frozen before the first evaluation-window price read. This is a one-shot development-to-forward-window probe, not authorization to trade. Whether prior sessions or other agents accessed these exact post-cutoff prices has not yet been independently proven; do not describe the result as a pristine sealed OOS unless that audit passes.

## Data boundary

- Evaluation signals: timestamps from `2024-11-12T00:00:00Z` inclusive through `2026-10-13T00:00:00Z` exclusive.
- Rows before the start are permitted only for the already fixed five-session KR return and 252-session US momentum lookback; they do not contribute evaluation signals or returns.
- Rows at/after the end are not parsed beyond their timestamp. The source caches may end earlier than the exclusive end.
- No threshold, lookback, cohort, cost, entry, or exit changes after this file is committed. One run only. A failed or undersized sample is inconclusive, not permission to retune on the same window.

## Frozen candidates

### Korea — stress-day short-term reversal

Use current cached KR non-ETF stock files and 069500 as a broad-market proxy, not as historical KOSPI200 membership. A stress date is a one-session 069500 close-to-close return at or below −2%. Rank stocks by their prior five-session close-to-close return, select the bottom decile, enter next session open, and exit at the close after five sessions. Require all signal-lookback and holding-session rows. Costs: 0.015% commission per side, 0.18% sell tax, and 0.10% slippage per side base / 0.20% stress. Compare the same-date 069500 next-open to fifth-session-close return under the same cost case. Resample six-calendar-month moving blocks.

Evidence gate: at least 30 distinct stress dates spanning at least two calendar years, and stock-minus-069500 mean net return greater than zero with six-month-block 95% CI lower bound above zero under both base and stress costs. Otherwise classify as inconclusive/reject, never promoted.

### United States — monthly 12–1 cross-sectional momentum

Use the current 54 cached stock files after excluding the fixed 38-symbol ETF list in the source. On each month's final SPY session, rank by `Close[t−21] / Close[t−252] − 1`; require every session in the 252-session lookback and valid next-session entry/next-month-end exit rows. Buy the top quintile at the next SPY-session open and exit at the next calendar month's final session open. Compare paired monthly returns against the same-date eligible-stock cohort and SPY. Costs: 0.36% round trip base / 1.22% stress. Resample six-calendar-month moving blocks.

Evidence gate: at least 18 monthly cohorts, and paired top-quintile excess over both comparison series positive with six-month-block 95% CI lower bound above zero under base and stress costs. Otherwise classify as inconclusive/reject, never promoted.

## Interpretation limits

This is an event/cohort comparison, not a capital-weighted portfolio. Position sizing, maximum drawdown tolerance, PIT historical membership, delisted securities, corporate-action adjustment, borrow, liquidity and actual fills remain unresolved. Passing this narrow gate would justify only further independent data and portfolio-policy research; it would not establish the 20% annual target, readiness for autonomous trading, or live-trading authorization.
