# KR/US cross-sectional candidate forward-window protocol

Status: the protocol was frozen before this chat first read evaluation-window prices. However, the pre-existing research handoff already reports KR/US price analyses through 2026-11-12. Therefore the 2024-11-12–2026-10-12 window is **not untouched OOS** and every result is development/retrospective analysis only. This protocol is not authorization to trade.

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

## Execution erratum — 2026-11-15

The first evaluation-window run is **invalid**. The SPY cache ends on 2026-10-12, and the implementation treated that truncated date as October's final market session when exiting September's cohort. Preserve `docs/research/equity_forward_validation_first_run_INVALID_20261115.csv` only as an audit record; none of its forward-window conclusions or gate outcomes are valid.

The corrected implementation rejects any signal or exit month whose last observed session lies more than six calendar days before month-end. This fixes the incomplete-month boundary without changing the strategy rule, but the correction was identified after the first output was visible. Any rerun on the same post-cutoff prices is a post-hoc corrective diagnostic, not a preregistered OOS result. Record the corrected output separately and do not use it to tune parameters.

The corrected post-hoc diagnostic used the same 2024-11-12 inclusive to 2026-10-13 exclusive window and excluded the incomplete October 2026 cohort. KR produced 56 stress dates; the stock-minus-069500 spread was +0.093 percentage points base (six-month block 95% interval −1.221 to +0.813) and +0.093 stress (−1.198 to +0.828), so the KR gate failed. US produced 22 complete monthly cohorts; top-quintile excess over the eligible-stock cohort averaged +3.036 percentage points/month (95% interval +1.301 to +6.383 base; +1.374 to +6.225 stress), and excess over SPY averaged +3.847 points/month (base +2.148 to +8.055; stress +2.087 to +7.909). Those US statistics satisfy the numeric screen, but the run is post-hoc after the first result was seen and the prior handoff shows this period had already been analyzed. It is not a preregistered or untouched OOS pass. It only supports a new, independent prospective/data-source validation. Corrected output: `docs/research/equity_forward_validation_corrective_diagnostic_20261115.csv`.
