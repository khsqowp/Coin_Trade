# Rebalance cadence preregistration

Protocol frozen before the cadence sweep. UTC start is 2022-01-01 00:00. Research only: no network, exchange calls, live or container writes, orders, state-file edits, or git operations.

## Hypothesis and grid

H0: no p in 1..71 hours dominates p=72 hours on annualized log growth and risk-adjusted growth. The full fixed grid is p=1..72 inclusive, with every offset o=0..p-1 (2,628 paths per configuration/window). No post-hoc cadence is added. Engine parameters are lev=4, deploy=.95, K=8, 336h cross-sectional rank z-score, BTC 336h crash threshold -10%, kill=.35, cooldown=14 days, maintenance=.5%, funding on, and start equity W=1. Decision times are UTC start+o then every p hours. V0 kill (daily close equity vs HWM) is primary; hourly lambda=.15 kill-fidelity is secondary. Kept same-side quantities are preserved unless resize is on; resize threshold is 15%.

## Costs, paths, and windows

Fee is .05% per traded notional per side. Primary cost is fee plus 0bp slippage; sensitivity is 2, 5, and 10bp per side. Both resize off/on are run. IS is 2022-01-01 through 2024-06-30; OOS is 2024-07-01 through panel end with W=1 restart; FULL is continuous from 2022-01-01 with W=1. All offsets are required; there is no sampling reduction in this protocol. A p=72 path offset maps to its stated UTC hour, while V0 legacy comparison maps day-close phases to 23,47,71 hours.

## Metrics and inference

Primary statistic is annualized log growth g=365*mean(daily log return). Report daily Sharpe (annualized sqrt(365)), close MDD, hourly-worst MDD, Calmar, kills, liquidation diagnostic flags, turnover, fills, transaction costs, and cost drag (g at zero cost minus g at charged cost). For each cadence show offset p10/median/p90. Paired comparison uses phase-averaged daily log-return differences against the mean of p=72 offsets, circular 15-day block bootstrap B=4,000, seed 20261101, two-sided 95% percentile CI. Individual cadence family p=1..71 uses Holm and BH, two-sided. Primary family is five coarse groups 1-6, 7-12, 13-24, 25-48, 49-71 hours, each versus p=72 with Holm. Report adjacent ±3h moving-average plateau, IS/OOS Spearman rank correlation and sign agreement, IS-best p's OOS rank, CSCV PBO with S=16 time blocks, DSR with N=72, trend slope g versus ln(p) with block bootstrap, and MDE=2.8*SE in annual g units.

Decision: (1) shorter cadence is supported only if a coarse group has Holm-adjusted CI lower bound >0 in both IS and OOS, sign remains positive at 5bp, resize on and off both qualify, and neighboring cadence regions are positive; (3) harmful requires Holm-adjusted upper bound <0 in both IS and OOS; otherwise (2) indistinguishable. Confidence cannot be 100%. If code reconciliation is materially failed, label the conclusion exploratory and do not call it evidence about the live strategy.

## Model limitations and execution accounting

Hourly funding uses local cached rates only and must reconcile to daily FD. If it does not, use funding spread uniformly or at 00/08/16 UTC and disclose the error. Small-account minimum notional/quantity steps are not modeled; reference account is about $124 with ~$32 per-leg notional. Survivorship bias (45 currently listed symbols), one 4.8-year regime, correlated offsets, approximate wick/liquidation and kill fidelity, and omitted latency, partial fills, API costs, and slippage uncertainty are reported. No network lookup or external data is permitted.

## Reconciliation disclosure

Initial V0 check was run before this freeze. Funding reconstruction matched FD exactly (max absolute error 0). Daily close equity did not match Sim.run: preliminary FULL maxima were absolute 21.92, 29.79, 28.00 for mapped phases 0,1,2, and maximum relative discrepancies 0.921, 0.964, 0.995. Cause is unresolved. Reconciliation is therefore failed, all sweep results are exploratory until root-caused; no strategy-performance conclusion is permitted from the current engine output. This disclosure does not change parameters or thresholds after sweep.

## AMENDMENT (pre-performance bugfix)

2026-11-01 parity debugging corrected the hourly engine's turnover scheduling: forced crash-state transitions do not reset the periodic rebalance clock in `Sim._sim`. The preregistered grid, windows, metrics, bootstrap, multiplicity control, and decision thresholds above are unchanged. The corrected engine passed the 9 mapped V0 paths and p=24/p=48 generality checks at relative error below 1e-9. The hashes log records this amendment before any cadence sweep outcome was inspected.
