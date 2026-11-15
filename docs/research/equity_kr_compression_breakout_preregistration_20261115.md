# Korea ETF volatility-compression breakout — preregistration

Status: frozen before the reproducible implementation/run in this repository. This is a development-data test, not out-of-sample evidence. The same pre-2024-11-12 history has already been inspected in earlier research.

## Hypothesis and scope

Test one long-only signal on KODEX 200 (`069500`) daily bars. A 20-session closing-price breakout that occurs after unusually low realized volatility and above the 200-session trend may have a positive net return and a lower drawdown than buy-and-hold. No parameter sweep or threshold adjustment is allowed after results are observed.

Input: `.kis-cache-local/KR_069500.csv`, fields `timestamp,Open,High,Low,Close,Volume`. Read rows strictly before `2024-11-12T00:00:00Z`; stop parsing OHLCV at the first timestamp on or after the exclusive cutoff. The cache is a current local historical series; corporate-action and distribution adjustment are not independently verified.

## Signal and execution

1. At session close `t`, compute close-to-close daily returns and the sample standard deviation of the latest 10 daily returns (`vol10[t]`).
2. Define the compression threshold as the 30th percentile of the previous 252 available `vol10` observations, excluding `vol10[t]`. Require `vol10[t] <= threshold[t]`.
3. Require `Close[t] > max(Close[t-20:t])`, `Close[t-1] <= max(Close[t-21:t-1])`, and `Close[t] > SMA200[t]`. All indicators use data no later than the signal close.
4. Enter at the next session open. Invest all available NAV in fractional ETF shares. Do not open another position while one is active; ignore signals observed while invested.
5. At each invested session close, exit if `Close < SMA20` or the position has completed 10 sessions (entry session counts as session 1). Execute the exit at the next session open. A signal/expiry on the final available session without a following open is censored, not filled. Only trades whose complete entry and exit are strictly before the exclusive cutoff enter the primary results.
6. While flat, hold cash at 0% return. No dividend/distribution reinvestment is modeled.

## Costs and baselines

Apply 0.015% commission and 0.10% per-side slippage in base; 0.015% commission and 0.15% per-side slippage in stress. Apply each side to its executed price. ETF sell tax is set to zero. Report 069500 buy-and-hold, a close-confirmed SMA200 long/cash filter, and cash at 0% over the same eligible evaluation dates. No leverage.

Report complete trades, skipped/censored signals, exit reasons, calendar years with trades, annualized return, maximum drawdown, total turnover (gross buys plus sells divided by mean NAV), and six-month circular moving-block 95% bootstrap interval for CAGR (10,000 draws; seed 69500). Preserve the full event/trade list.

## Decision rule

This test is a candidate screen, not an investment approval. Reject as a demonstrated candidate if either base or stress buy-and-hold-relative six-month-block CAGR interval includes zero, stress CAGR is non-positive, fewer than 100 completed trades or fewer than 8 trade-active calendar years are available, or strategy MDD is at least 10 percentage points worse than buy-and-hold. Report each gate independently. Passing would justify only a new-data/forward validation; it cannot establish OOS success or the 20% annual target.

## Reproducibility and causal checks

Record the source-data SHA-256, exclusive cutoff, signal count, execution rules, code revision, and exact command. Unit tests must verify that the current volatility observation is excluded from its own percentile threshold, that future rows cannot alter a past signal, that entry occurs no earlier than the next open, and that stop/time exits occur at the next available open. Do not describe the already-viewed post-cutoff portion as OOS.
