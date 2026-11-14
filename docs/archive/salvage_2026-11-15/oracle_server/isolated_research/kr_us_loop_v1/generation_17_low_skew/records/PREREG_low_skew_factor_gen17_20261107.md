# Gen17 preregistration — 63-session low realized-skewness factor

Status: draft for independent review. No Gen17 performance values, returns, signal ranks, or factor-overlap diagnostics have been opened or calculated. Do not run performance unless this complete document is reviewed, frozen by hash, and the synthetic/independent implementation gates pass.

## 1. Research question and interpretation boundary

Test one fixed cross-sectional hypothesis: among a frozen set of current US and KR large-cap survivors, names with lower trailing 63-union-session close-return skewness may outperform the same-cohort equal-weight buy-and-hold after registered costs. “Lower” is a signed rank and may include strongly negative-skew names; this is not a claim that left-tail risk is safer or that lottery preference explains the result. This is a survivor-cohort exploratory screen, not historical index evidence, a new independent factor discovery, or proof of executable returns. The hypothesis may fail; do not alter the 63-session window, K, score, rebalance cadence, cost cases, sample, or pass gate after seeing results.

Low own-return skewness is a known cross-sectional/factor concept and may overlap with volatility, lottery-demand, and value/quality effects. Gen17 must not be presented as a novel strategy family merely because it uses a different statistic. The requested cumulative two-valid-strategy count does not change from an exploratory screen, even if this candidate passes the numerical screen.

## 2. Frozen files and data gates

- Read only `timestamp` and `Close` from `.kis-cache/{US,KR}_{symbol}.csv`. Do not use `Open`, `High`, `Low`, `Volume`, fundamentals, membership data, future prices, or external signals.
- Cohorts remain exactly those frozen for Gen16: US `AAPL, AMZN, GOOGL, META, MSFT, NVDA, TSLA`, K=2; KR `000270, 000660, 000810, 005380, 005490, 005930, 006400, 009150, 012330, 017670, 028260, 032830, 034730, 035420, 055550, 068270, 086790, 105560, 316140, 373220, 402340`, K=5. These are not point-in-time index constituents. K is copied from Gen16; do not imply the earlier draft's KR K=7 was frozen.
- Recompute the full 28-file canonical manifest before any signal or metric. Expected manifest: `395e3acc608493164700e2fcdfebebe9bca541bfa6e952a3cebdb15ab81a85b4`. Serialization is bytewise UTF-8 path sort, then `relative_path + TAB + lowercase SHA256(file bytes) + LF`, SHA-256 of the concatenation. Any mismatch blocks the run.
- Parse ISO-8601 timestamps only when an explicit timezone offset exists; convert to UTC date. Reject duplicate or non-increasing dates within a ticker and reject every non-finite or nonpositive close. Require the expected exact cohort. Do not repair or remove rows.
- Construct each market's sorted union calendar from all frozen cohort dates. It is an observed-data proxy, not an authoritative exchange calendar. No forward-filled close may form a signal or fill.
- A ticker is eligible at a signal date only if it has a valid actual close on each of the 64 consecutive union-calendar dates ending on that date. If not, it is ineligible at that decision. This yields exactly 63 actual close-to-close returns. A zero-variance window is ineligible. No shorter lookback or imputation.
- Interim portfolio NAV may mark a held position at its last actual close when that ticker has no row on a union date. A required scheduled or terminal exit without a valid actual close blocks the cell. No stale-price liquidation.
- Before performance, validate every input and the exact manifest. A failed gate is `DATA_BLOCKED`, with no signal-performance comparison or metric calculation.

## 3. Frozen signal and rebalance rule

### Signal

At each decision date `t`, for each eligible ticker `i`, take its 63 actual simple close-to-close returns `r[1..63]` over the 64 consecutive union dates ending at `t`. Compute the bias-corrected Fisher–Pearson sample skewness exactly as:

`G1 = n / ((n-1)(n-2)) * sum(((r[j]-mean(r))/s)^3 for j=1..n)`

where `n=63` and `s = sqrt(sum((r[j]-mean(r))^2)/(n-1))` is the sample standard deviation. If `s == 0` or the result is non-finite, the ticker is ineligible. Use no winsorization, clipping, outlier filtering, alternative skew estimator, or standardization beyond this formula.

Rank every eligible ticker by `G1` ascending (lowest skew first), then ticker string ascending for exact ties. Do not require positive or negative skew; do not select from a post-result subgroup. At the decision close, retain the full eligible ranking for execution-time fallback.

### Decision schedule and execution

- OOS is 2023-01-01 through the final observed union date. The account starts fresh at NAV 1.0, all cash, with no pre-OOS holdings. Earlier closes are indicator warm-up only.
- Anchor the decision schedule to the first OOS union date. Signal dates are OOS union index `0, 21, 42, ...`; a date without a usable eligible cross-section still consumes its scheduled decision slot. Each decision uses data through that date's close only. A scheduled signal on the final OOS union date creates no order because there is no subsequent in-segment execution date; record it as a skipped terminal decision.
- Execute on the first subsequent observed union-calendar date's close, identified only when that date occurs. On an execution date, first liquidate all positions from the preceding holding block at that actual close, then enter names selected at the preceding scheduled decision. Do not recompute the old block's signal or choose an execution date by looking ahead.
- Attempt ranked names until K slots are filled or the eligible ranking is exhausted. If a ranked name lacks a valid execution-date close, skip it and try the next rank. If fewer than K valid names can be entered, unused slots remain cash. No shorting, leverage, stops, intraday orders, or carried unfilled orders.
- For each execution batch, capture one `NAV_batch` after due exits and before buys. Each filled name's total spend including its buy cost is `NAV_batch/K`; gross notional is `(NAV_batch/K)/(1+buy_fee)`. Shares are fixed until that lot's scheduled exit. No cash may go negative.
- A lot entered after decision at OOS union index `i` is entered at `i+1` and exited at the close of the execution date for the next scheduled decision `i+21`, namely `i+22`; holding length is exactly 21 union-session intervals. On the anchored schedule, decisions/executions are `(0→1), (21→22), (42→43), ...`. If the next scheduled execution is outside the OOS segment, hold to the final OOS date and liquidate there at its valid actual close.
- Never initiate an entry on the segment's final union date. Any scheduled signal whose execution date would be the final date is skipped and recorded; the final-date signal itself creates no order. Prior holdings are liquidated at that final date's actual close. If final close is missing for any holding, mark the cell `DATA_BLOCKED`.

## 4. Costs, comparator, and accounting

- Use Gen16's one-way cost cases unchanged: US base/stress buy and sell 0.08%/0.36%; KR base buy 0.065%, sell 0.245%; KR stress buy 0.115%, sell 0.295%. Charge each gross buy and sell.
- Fills are idealized at observed closing prices with fractional shares. Proceeds from same-close exits may fund same-close entries. Settlement lag, dividends, interest, financing, taxes beyond the registered costs, market impact, and execution slippage beyond the fixed stress rate are not modeled. Results remain exploratory, not executable-performance claims.
- Compare against the same fixed-cohort, cost-matched buy-and-hold account from the same OOS start to end. Allocate each name a fixed all-in budget `1/N`, gross `1/(N*(1+buy_fee))`; if its first valid close is delayed, retain its budget in cash until then, but do not enter on the segment's final union date (that slot remains cash). Hold shares to the final date and liquidate at an actual final close with sell cost. Missing required terminal price blocks the benchmark cell.
- Record each fill (date, ticker, side, close, shares, gross, fee, cash before/after, rank, reason), each union-date NAV/cash/holdings/stale-mark state, and per-rebalance eligibility, full rank, filled names, and unused slots. Reconcile the independent cash/share ledger to NAV within `1e-10` each union date.

## 5. Frozen metrics and numerical screen

- Report OOS CAGR, Sharpe, MDD, terminal NAV, turnover, total costs, fill count, average cash share, eligible count, selected/filled names, skips, and the complete daily NAV path. Initial NAV=1.0 is dated one calendar day before the first OOS union date. Daily returns include initial-to-first-close change and each subsequent daily NAV ratio. Sharpe is population-standard-deviation daily Sharpe times `sqrt(252)`, risk-free rate zero; zero standard deviation is undefined and cannot pass. MDD includes initial NAV 1.0. CAGR is `terminal_NAV ** (365.2425 / elapsed_calendar_days) - 1`, with elapsed days `last_union_date - (first_union_date - 1 calendar day)`. The day-count numerator is explicitly fixed to remove Gen16's unresolved 365.2425/365.25 ambiguity. Daily turnover is `(gross_buys + gross_sells) / pre_trade_NAV`, where pre-trade NAV is after marking existing holdings at the date's close but before that date's transactions; total turnover is the sum over union dates. Average cash share is the arithmetic mean of post-close-action `cash_t/NAV_t` over OOS union dates. Fill count counts each buy and each sell as one fill. Report all costs in NAV units.
- A market candidate numerically passes only when both base and stress OOS CAGR and Sharpe strictly exceed same-cohort B&H and candidate MDD is no worse than B&H in both cost cases. A pass is exploratory only. No return/metric gate can be weakened after results.
- No DSR/PSR, Bonferroni/BH significance, or independent confirmation claim: complete global trial counts and admissible point-in-time data are unavailable. Keep all candidate/market/cost outcomes locally, including blocked and failed cells. Coin_Trade remains method/status/hashes only until data-use rights are cleared.

## 6. Overlap diagnostic and family classification

Before calculating candidate or benchmark performance metrics, report by market and decision date the Spearman rank correlation between the G1 scores and each of: (a) population standard deviation of the 63 returns; (b) compounded 63-return cumulative return `product(1+r)-1`; and (c) the signed maximum single-session simple return `max(r)` in the same window. Use the exact same eligible ticker cross-section for all four measures. Use average ranks for ties, then Pearson correlation of those ranks. If fewer than four tickers are eligible at a decision date, or G1 scores or any comparator have zero cross-sectional variance, record `NA` for that date/comparator. Summarize valid dates with `median(abs(rho_t))` separately for each market/comparator and report its valid-date denominator; if no valid dates, report `not estimable`. This is descriptive only: it does not gate market performance and cannot establish that this is an independent family. Report all dates and do not suppress unfavorable overlap.

## 7. Pre-performance independent gates

1. Three separately implemented engines must pass synthetic tests for the exact skew formula and tie order, equal-mean/equal-variance series with different skew, positive price-scale invariance, a single extreme-return sensitivity example (document the expected G1 movement; do not winsorize), 63-return/64-close boundary, missing and constant windows, UTC normalization, exact index schedule `0/21/42 → 1/22/43`, no signal recomputation at execution, 21-interval holding arithmetic, exit-before-entry, full-rank fallback, fee-inclusive batch sizing, fixed shares, missing execution close, a delayed benchmark first close on the final date remaining cash, final-date candidate entry prohibition, a final-date signal with no order, terminal liquidation, future-mutation/prefix invariance, overlap-correlation formula/tie/minimum-N behavior, and daily cash/share/NAV ledger reconstruction.
2. At least two independent engines must agree per union date within `1e-10` on overlap diagnostics, signal score/rank, entries/exits, shares, fees, cash, holdings and NAV for both markets and both cost cases.
3. Any manifest/specification hash mismatch, data gate failure, missing required exit, future leakage, or implementation disagreement stops the run before market performance metrics. A failure is `DATA_BLOCKED` or `IMPLEMENTATION_BLOCKED`, not strategy rejection. Do not alter this frozen specification after any signal, overlap, or performance values are seen; a repair requires a dated addendum/new preregistration frozen before re-execution.

## 8. Known limitations and deliverable

This reuses the same OOS period and a current survivor cohort across multiple prior generations; it is not untouched confirmation. The close-price source's rights, adjustment/vintage and corporate-action provenance are unresolved, and the union calendar is not an official exchange calendar. Rank concentration is high with US N=7/K=2 and KR N=21/K=5. The short interval between signal and next-close execution and one-session candidate gaps may cause substantial turnover. Sample skewness is sensitive to extreme returns and data-adjustment artifacts; no robustification is allowed in this hypothesis. A numeric pass cannot make these limitations disappear.

After independent review, freeze the final text and its SHA before testing. Preserve the rejected proposals and Gen16 results. If the candidate fails, log the failure and proceed to a materially different, separately preregistered hypothesis; do not endlessly tune skew windows or thresholds.
