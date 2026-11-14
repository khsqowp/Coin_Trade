# Generation 12 — US single-month cross-sectional loser reversal

Status: `PENDING_ROOT_REVIEW_NO_DATA_RUN`. This file defines one fixed candidate only. No market-data values, returns, signals, or performance metrics have been read or calculated for this candidate. Do not implement/run the performance path until the root agent records an explicit GO and freezes the runner/test hashes.

## Why this candidate

Test one equity-level, one-calendar-month cross-sectional reversal rule. It is distinct in unit of selection and signal construction from Generation 11's bottom-three **sector ETFs** ranked on the previous month, and from the prior five-session individual-stock reversal screen. It is nevertheless a correlated reversal-family hypothesis, not an independent discovery. It must not be presented as novel or expected to work. It is included as one bounded test, not as a parameter sweep.

This candidate is US-only. The local KR price repair and universe/benchmark issues remain unresolved; running a KR analogue would add data-integrity ambiguity rather than useful evidence. The local US PIT price mirror is known to have incomplete constituent price coverage, so the data-coverage preflight below is a hard gate.

## Fixed hypothesis and universe

- Candidate ID: `GEN12-US-PIT_MONTHLY_LOSER_REVERSAL_BOTTOM_DECILE`.
- Market: US common equities in the local point-in-time S&P 500 membership file. Use the existing project membership parser and the project-approved strict monthly simulator only after review. Do not substitute the current index constituents, the locally priced subset, ETFs, or a reconstructed current-only universe.
- Benchmark: local SPY adjusted-close total-return series, with the same scoring dates and the existing frozen US transaction-cost convention (10 basis points per side). SPY is a reference benchmark, not a constituent or signal input.
- Rebalance decision: the last observed exchange session of each **complete calendar month**. The last month in the file is excluded if incomplete.
- Signal: for PIT member `i` at month-end `t`, compute simple total return over the just-completed calendar month: `R[i,t] = adjusted_close[i,t] / adjusted_close[i, prior_month_end] - 1`. Both endpoints must be observed, finite, and strictly positive; there is no forward-fill, interpolation, or stale-close substitution. If either endpoint is unavailable, that constituent has no score for that month.
- Rank eligible scored PIT members by `R[i,t]` ascending, then normalized ticker ascending for deterministic ties. Select exactly the lowest `ceil(0.10 * N_scored)` names; no minimum/maximum count, volatility filter, sector constraint, exit overlay, leverage, short leg, stop, or cash yield is added. If `N_scored=0`, the target is 100% cash.
- Portfolio: equal weight across selected names, long-only, gross exposure at most 100%; fractional shares are permitted in the simulator. Signal is formed after month-end close and the target is applied at the next observed session open. Hold through the following monthly decision, with natural portfolio-weight drift between rebalances.
- No intramonth signal or discretionary trade. Final holdings are liquidated at the final valid scoring boundary under the same sell-cost rule. Exclude any signal whose next-open execution or full scored interval is not present.

## Data and coverage gates

Before loading price values for signal construction, freeze hashes for the complete local US PIT membership input, its parser, the SPY price/metadata inputs, all member price/metadata files and explicit absent-file statuses, the preregistration, runner, tests, and shared simulator dependencies. Mark the snapshot non-atomic unless proven otherwise. Do not refresh or alter the source snapshot within an attempt.

The denominator for each month is every unique security active in the PIT membership file on that month-end, including members without a local price file. Coverage is `number of active PIT members with both prior- and current-month-end closes and a valid one-month score / number of unique active PIT members`. Exclude the first partial calendar month in the price snapshot because it has no observed prior month-end. Reject the entire attempt as `FAILED_DATA_COVERAGE` before computing portfolio returns if fewer than 85% of active PIT members have scores in any subsequent complete month through the last complete month. This prevents a local surviving-price subset from silently becoming the tested universe. Report coverage by month only if the attempt reaches the approved data audit; do not dilute the denominator by removing missing-price members.

Fail closed on duplicate/overlapping membership spells, invalid membership dates, non-unique or nonascending price indices, missing benchmark sessions, non-finite/nonpositive close values at either required signal endpoint, invalid held/entering OHLC, adjusted-close discontinuities not cleared by the existing corporate-action audit, non-finite returns/weights, or portfolio gross exposure above 100%. Do not repair rows, silently sort calendars, forward-fill, or treat a data-gate failure as a strategy rejection.

### Known limitations before testing

- The local US files are unofficial vendor-derived snapshots, previously inspected in this workspace, and not independently reconciled to a licensed point-in-time total-return database.
- Previous feasibility work reports substantially incomplete local price coverage relative to PIT S&P membership. The 85% all-month gate may therefore block this candidate; this is a data limitation, not a negative return result.
- No virgin OOS period exists in this snapshot. Existing 2001–2016 and 2017+ partitions may be shown only as descriptive slices; repeated inspection contaminates both for confirmatory claims.
- The complete historical project-wide trial count is unresolved. No DSR/PSR, null-portfolio significance, Bonferroni/BH significance, or confirmatory inference may be claimed from this run.
- The screen cannot prove deployability, executable capacity, realized fills, market impact, borrow economics, tax treatment, or future profitability.

## Frozen evaluation and decision rule

If and only if all data, integrity, and implementation gates pass, execute exactly one US candidate-market attempt. Do not test alternate formation periods, top/bottom fractions, weighting schemes, universe thresholds, horizons, costs, or filters after seeing any result. Any necessary semantic or implementation correction requires a dated addendum, new hashes, and a new attempt ID; preserve the original failure or result.

Report net CAGR, annualized Sharpe (252 sessions, zero risk-free rate), maximum drawdown, total return, annual turnover, transaction-cost drag, active exposure, monthly selection count, average selected count, and monthly PIT coverage. Compare against SPY on identical intervals. Show full-history and the repository's fixed descriptive windows only; do not describe them as OOS. Report predeclared bull, bear, high-volatility, and sideways regime slices only if the project already has regime boundaries frozen independently of this candidate; do not invent or revise boundaries after viewing returns.

For this exploratory screen, the fixed rule fails the stated broad-market outperformance gate if it does not beat SPY on **both** net CAGR and Sharpe in the full sample and in each of the repository's required descriptive windows. Passing those comparisons would make it a lead for a later independent-data/prospective study only, never a validated or investable strategy. A data, runtime, or test failure is recorded as failure of the attempt mechanics/input gate, not as evidence against the strategy.

## Attempt discipline

- Exactly one performance attempt, once only, after explicit root GO.
- Before GO: no market-value read, indicator computation, signal generation, backtest, or result inspection. Synthetic tests and static code review are allowed after drafting but before final freeze only if they do not access market values.
- Persist start/failure/completion events, process exit status, source and input hashes, coverage diagnostics, metrics, and daily net-return/exposure/turnover curve. Use `allow_nan=False`; a serialization or runtime error is `FAILED_RUNTIME`, not a candidate result.
- Preserve all files, including failed attempts. No git add/commit/push, no remote operation, and no live trading/order code.
