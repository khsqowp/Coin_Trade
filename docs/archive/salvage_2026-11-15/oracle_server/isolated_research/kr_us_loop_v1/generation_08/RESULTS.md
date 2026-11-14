# Generation 08 — low residual-skew exploratory result

## Decision

**Reject the fixed low-residual-skew rule.** It underperformed SPY in the later inspected partition and did not invest during the IS partition because the full-PIT coverage gate never passed there. This rejects only this realized-residual-skew implementation on this snapshot; it does not show that systematic strategies do not exist.

Run: `GEN08-20261106T113802-4574`, status `COMPLETED_EXPLORATORY`. The exact PIT availability audit, coverage by decision month, selections, daily curve, ledger and manifest are retained beside this report.

## Outcomes

- Local price data covers 688 of 1,209 unique PIT members. Across 406 completed month-end decisions, full-PIT score coverage passed 85% in 83 months, from 2019-12-31 through 2026-10-30; median coverage was 63.9% (range 0–99.0%). The 2001–2016 IS period was entirely cash; its 0% returns are a data-coverage outcome, not evidence of no skewness premium.
- IS 2001-01-04 to 2016-12-30: strategy CAGR 0.00%, Sharpe 0.00, MDD 0.00%; SPY CAGR 5.22%, Sharpe 0.36, MDD -55.19%.
- Later inspected/contaminated period 2017-01-04 to 2026-11-02: strategy CAGR 7.36%, Sharpe 0.48, MDD -40.11%, mean exposure 69.5%, annual turnover 3.34; SPY CAGR 14.84%, Sharpe 0.86, MDD -33.72%.
- The strategy missed SPY materially on CAGR and Sharpe and had a deeper drawdown. The later period is contaminated, so this remains descriptive screening evidence, not untouched OOS.

## Verification / limits

- Seven unit tests passed under the configured Python environment; `compileall` passed. The reviewer checked OLS intercept/beta residual math, population skewness, future perturbation, unique full-PIT coverage, membership overlap rejection, complete input fingerprint (PIT CSV + SPY + member file presence/hashes), entry timing, and fail-closed status. No blocking issue remained before execution.
- This is realized SPY market-model residual skew, not the expected-idiosyncratic-skew predictor in Boyer–Mitton–Vorkink. It is adjacent to MAX/low-risk strategies and is not independent confirming evidence.
- PIT member price availability remains incomplete; corporate-action/delisting treatment and total historic strategy-trial count remain unresolved. No untouched OOS or global DSR/PSR/BH inference can be claimed.
