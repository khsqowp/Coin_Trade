# Independent review — Generation 11 and next research direction

Date: 2026-11-06 (Asia/Seoul)  
Scope: read-only review of recorded Gen11 results, current Gen12 proposals, local data-feasibility evidence, and candidate evidentiary gates. No market returns were calculated, no remote command was run, and no Gen11 candidate was rerun.

## Bottom line

The user’s criticism is correct in an important sense: these results establish only that this search has not found a qualifying rule yet. They do not establish that profitable systematic trading is impossible, or that this agent exhaustively searched the strategy space. The Gen11 evidence is narrow, correlated, and mostly based on a previously inspected Yahoo-derived snapshot. A better next step is not another large indicator permutation grid; it is to resolve data limits and test one genuinely different, economically motivated source of return with time-stamped point-in-time inputs.

## Gen11 evidence review

| Item | Review conclusion |
|---|---|
| SPY overnight-only schedule | A valid descriptive rejection of that fixed timing rule versus the stated matched-endpoint SPY benchmark. Its interval risk differs from continuous buy-and-hold, auction fills are unobserved in daily bars, and the assumed 2 bp/side is not measured execution. It cannot reject overnight-return strategies as a family. |
| SPY volatility-burst + momentum event rule | A valid descriptive rejection of this single fixed event/holding rule on the local snapshot. It is closely related to prior momentum/volatility work; the full and later periods are contaminated, and corporate-action/vendor integrity is not independent. It is not a new-family test. |
| Bottom-three sector ETF reversal | Underperformed the benchmark on the declared metrics/windows, but is a sector-ETF heuristic rather than a replication of individual-stock reversal research. Its descriptive windows are not untouched OOS, and local price/event provenance is incomplete. Reject the fixed rule only. |
| US ETF dual momentum | Runtime/serialization failure after overflow warnings; this is neither a strategy pass nor a strategy rejection. The single attempt is consumed. Preserve it and do not infer performance from partial state. |
| Ex-dividend event lead | Correctly blocked before performance because local dividend events lack completeness/provenance and PIT member-price coverage is incomplete. That is a data blocker, not a negative test. |
| Sector breadth A1/A2 | A1's calendar-gate failure produced no strategy result; it was an implementation/input-contract failure, not candidate evidence. The corrected A2 ran once after independent freeze/hash review. It returned full-sample CAGR 2.98% and Sharpe 0.304 versus matched SPY 8.57% and 0.531. It also had a smaller reported full-sample MDD (-46.64% vs -55.42%), but failed its preregistered CAGR-and-Sharpe objective. Reject this exact 5-of-9/SMA200 rule on this local snapshot only; do not generalize to breadth strategies or profitable automated trading. |

The successful Gen11 candidates are mostly timing overlays or short-horizon price transformations on the same SPY/ETF historical snapshot. Their results are not independent replications. The common limitations—non-atomic unofficial data, historically inspected windows, incomplete cumulative trial count, and unmeasured execution—mean no Gen11 outcome can support a claim about a live edge.

## Next direction: point-in-time post-earnings-announcement drift (PEAD), only after data acquisition

This is materially different from the tested moving-average, momentum, short-horizon reversal, sector rotation, fixed schedule, and volatility-overlay rules. It has a plausible information mechanism: earnings information may be incorporated gradually. It is not ready to test with the current daily-price mirror alone.

Before any performance run, acquire a reproducible PIT dataset with permanent security IDs, historical active/delisted coverage, original and revised reported earnings, fiscal period identifiers, actual public-release timestamps/time zones, and source/version history. Analyst-consensus surprise is not mandatory for an initial variant; if used, consensus values and timestamps must also be point-in-time. Fix after-hours/holiday mapping to the first executable session, corporate actions, delisting returns, market-specific accounting definitions, liquidity eligibility, portfolio construction, turnover/cost assumptions, and one holding horizon before inspecting returns. If this data cannot be acquired, mark PEAD data-blocked and do not substitute a current constituent list, ticker-only joins, or price/volume proxies.

Why this is preferable to more indicator variants: it introduces a separately observable information event and can be falsified with timestamped data. Why it still may fail: publication lags, stale analyst estimates, reporting-quality differences, crowding, and transaction costs can eliminate the apparent drift. The research lead is justified; profitability is not assumed.

## Evidence required before calling any candidate credible

1. **Valid inputs:** independently sourced PIT universe and event/price records, permanent-ID joins, delisted names, reconciled splits/dividends, documented missingness, and a frozen data snapshot. The present local snapshot does not meet that standard.
2. **A clean test boundary:** choose and freeze the rule before examining a genuinely prospective/untouched interval. Previously inspected 2001–2016 and 2017+ partitions remain descriptive, never “OOS.”
3. **A complete search ledger:** count every tested family/variant across the project, including failed and invalidated attempts. If the count cannot be reconstructed, do not report DSR/PSR or multiplicity-adjusted significance as passed.
4. **Economic robustness:** compare net returns to a matched benchmark; include realistic spread, fees, slippage, turnover, and capacity; report all preregistered windows and drawdowns. A signal that only wins before costs or in one chosen regime is not credible evidence.
5. **Independent confirmation:** a second implementation should reproduce the frozen signal, timing, cost accounting, and metrics from the same inputs; then a separate future period or independent data source should confirm the candidate. Daily-bar simulated fills alone do not prove executable performance.
6. **Prospective paper observation:** only after historical gates pass, record signals and simulated/executable reference prices prospectively without orders. This tests data handling and operational assumptions; it still does not guarantee future profits.

## Decision for the current pipeline

- Continue searching; do not report “there is no strategy.”
- Keep candidate rejection, data-blocked, implementation failure, and statistical non-confirmation as separate statuses.
- Do not promote an indicator combination merely because enough variants make one historical result look good. Factorial expansion increases selection bias and is not a substitute for new information or clean validation.
- Prioritize sourcing PIT earnings/event data and reconstructing the full trial inventory. Meanwhile, Gen12 cross-sectional reversal is a correlated, likely data-gated exploratory test; the macro rule is blocked until its timestamped official event table exists; the downside-semivariance proposal is risk control, not a return-predictive strategy.
- Any positive local-mirror result remains a lead only. It must not be presented as validated, deployable, or evidence of expected returns.

## Sources reviewed

- Gen11 result/limitation records: `generation_11_overnight/RESULTS.md`, `generation_11_trend/RESULTS.md`, `generation_11_crossasset/RESULTS.md`, `generation_11_dualmomentum/RESULTS.md`, `generation_11_event/CANDIDATE_AND_BLOCKER.md`, `generation_11_breadth/RESULTS.md` (A2 outcome), `ADDENDUM_A2.md`, and `FREEZE_A2.json`.
- Current proposals: `generation_12_crosssectional/PREREG.md`, `generation_12_crosssectional/IMPLEMENTATION_PLAN.md`, `generation_12_macro/PREREG.md` and `STATUS.md`, `generation_12_volatility/PREREG.md`.
- Data and source limitations: `FEASIBILITY.md`.

