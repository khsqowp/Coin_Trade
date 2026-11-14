# Generation 04 — candidate review (not a performance run)

Date: 2026-11-06  
Purpose: preserve independent candidate proposals after the initial three exploratory generations.  
Status: **no candidate was backtested in this review**. The entries below are hypotheses, not evidence of profitability.

## Why this is not a “no edge exists” conclusion

Failure to identify an edge in Generations 01–03 is a failure of this search to identify one. It does not show that systematic trading cannot be profitable. At the same time, simply adding more variations until one looks good increases selection bias and cannot substitute for an untouched validation period.

The current price-only mirror cannot support a valid confirmation: its later period has already been inspected, the global historical trial count is unknown, KR data has known integrity/universe/benchmark defects, and US PIT coverage is incomplete. New results on these same data can only be exploratory unless those limitations are resolved.

## Consolidated candidates from three independent reviews

### Event and fundamental data hypotheses

These are unavailable for immediate testing because the local mirror contains no timestamped point-in-time event/fundamental feed.

1. **Post-earnings announcement drift (PEAD).** Rank eligible firms by standardized earnings surprise using the last consensus snapshot available before the earnings release; enter only after the public release, at the next executable session, and use one frozen holding period. Requires release timestamps, PIT consensus estimates, delistings, and total-return corporate actions. Reject if cost-adjusted performance fails on a genuinely untouched period or depends on a small number of events.
2. **Analyst estimate-revision breadth.** At month-end, measure the 60-day change in next-twelve-month EPS consensus and the fraction of analysts revising upward; require a fixed minimum coverage and rank within industry. Requires timestamped PIT consensus/revision history and PIT industry mappings. Reject if the effect disappears after costs, industry controls, or out-of-sample replication.
3. **Public insider cluster buying.** Aggregate only disclosed open-market cash purchases by at least two distinct insiders, excluding grants, option exercise, tax withholding, and transfers; first enter after disclosure becomes public. Requires timestamped original and amended filings, transaction classifications, insider roles, market cap, and PIT membership. Reject if filing-delay, classification, or concentration controls remove the effect.
4. **Net share issuance.** Rank firms by PIT-adjusted 12-month change in common shares outstanding, separating issuance/repurchases from splits, mergers, conversions, and ADR changes. Rebalance only after the relevant filing is public. Requires PIT share counts, filing timestamps, corporate-action classifications, and delisted names. Reject if the result is explained by small-cap/distressed exposure or disappears after costs and industry/size controls.
5. **Dividend initiation/increase events.** Separately define regular cash-dividend initiations and increases; exclude special and stock dividends and account for ex-dates/tax in total returns. Enter only after public disclosure. Requires PIT dividend history, disclosure timestamps, and consistent total-return data. Reject if the effect is seasonal, concentrated, or absent after costs.

### Portfolio and risk hypotheses

These are not independent alpha signals; they must be evaluated against a paired baseline and counted within their related strategy family.

6. **Correlation-constrained allocation overlay.** Keep the exact names selected by a frozen 12–1 momentum baseline; compare equal weights with a single fixed shrinkage-covariance minimum-variance allocation, 126 valid daily returns, shrinkage `0.5 * sample_covariance + 0.5 * diagonal(sample_covariance)`, and per-name cap `2/K`. Rebalance next open. Do not tune lookback/shrinkage/cap. Reject if net risk-adjusted performance and drawdown do not improve after turnover costs. Needs complete PIT prices and holdings.
7. **Post-gap exposure throttle.** For a verified broad-market proxy, compute overnight gap `ln(open_t / close_(t-1))` divided by the standard deviation of the prior 60 gaps. If `z <= -2.5`, cut a frozen base portfolio to 50% exposure from the next open for five sessions, then restore; charge both legs. Pre-register one risk objective and one acceptable CAGR cost. Needs trustworthy benchmark OHLC and daily portfolio holdings. A KR attempt is prohibited until an authoritative benchmark is present.
8. **Multi-asset risk allocation.** Compare a fixed equity/bond/gold universe, inverse-volatility weights from the prior 63 sessions, 20–60% per-asset bounds, monthly next-open rebalance, with preregistered 60/40 and equal-weight comparators. This tests risk allocation, not whether equities are always beaten. Requires survivorship-safe total-return series, fees, currency and corporate-action handling; none are in the present equity-only mirror.

## Decision

- No proposal is designated a winner or run-ready strategy.
- The five event/fundamental proposals need licensed or otherwise authoritative timestamped PIT data before implementation; replacing those inputs with OHLC proxies would change the hypothesis and is not allowed.
- The allocation proposals need a new preregistration, paired baselines, and explicit risk/performance gates. Gen04 must not inspect a “final OOS” repeatedly or present the already-viewed later partition as confirmation.
- Future attempts must be entered in an immutable per-attempt ledger before results are inspected. Invalid/failed attempts remain counted; failed KR data gates are not dropped from the record.

## Generation 04 execution update

Three independent source-review agents found no additional, mechanically specified daily-OHLCV strategy family in the local trading sources that is both clearly distinct from prior equity-transfer tests and ready to reproduce. The review confirmed that Aroon/TRIX/PSAR, Ichimoku/Keltner/Donchian, Heikin-Ashi, Fibonacci/Elliott, FVG/order-block/liquidity-sweep, FRVP/VWAP proxies, and many other source families already have prior transfer/screening exposure. Remaining ideas such as PEAD, insider activity, revisions, issuance, accruals, or fundamental quality require timestamped PIT data not present in the local mirror. Minute/session strategies such as ORB require missing intraday data. Wider-universe peer-pairs or weekly reversal would be replications of previously negative families, not new discoveries.

### Attempt history

| Run | Status | Recorded outcomes |
|---|---|---|
| `GEN04-20261106T100527-66055` | First implementation, retained but invalid for CLV mechanics | US TEMA completed; both CLV results invalid because overflow events could enter late and hold fewer than five sessions. KR TEMA rejected due invalid held OHLC. |
| `GEN04-20261106T101019-73296` | A1 implementation attempt, retained but invalid | CLV metrics were `INSUFFICIENT` because missing data in an unheld symbol propagated NaN through the portfolio calculation. Both TEMA attempts rejected on strict OHLC integrity. |
| `GEN04-20261106T101249-77989` | Corrected run, exploratory | All four planned attempts recorded. US/KR TEMA rejected at the strict OHLC gate. US/KR CLV completed and underperformed the benchmark in both reported partitions. |

### Corrected CLV results (net costs; not confirmatory)

| Market / partition | CLV CAGR | Sharpe | Max drawdown | Benchmark CAGR | Benchmark Sharpe | Benchmark max drawdown |
|---|---:|---:|---:|---:|---:|---:|
| US IS 2001–2016 | −4.61% | −0.113 | −77.78% | 5.22% | 0.358 | −55.19% |
| US later 2017–2026-11-02 | approximately 0.00% | 0.095 | −47.27% | 14.84% | 0.856 | −33.72% |
| KR IS 2012–2019 | −41.37% | −2.822 | −98.07% | 0.13% | 0.096 | −38.25% |
| KR later 2020–2026-11-03 | −35.85% | −1.475 | −94.78% | 1.99% | 0.212 | −48.47% |

The US mirror contains 688 local-price tickers from about 1,209 PIT members; the KR benchmark remains an equal-weight available-universe proxy because KODEX 200 is absent. The later periods have already been inspected. These figures reject this particular CLV adaptation on the current sample; they do not establish that all CLV use is unprofitable or that no other strategy works. TEMA produced no usable performance result because the strict simulator correctly stopped on corrupt/incomplete held OHLC (`UA` on 2021-05-05 in US; `130960` on 2018-07-18 in KR).

The corrected run manifest records content fingerprints for 1,378 US input files and 3,234 KR inputs; its ledger has 8 events (four starts and four finishes/failures), and the curve file and ledger are hash-recorded. The code review's three findings (late CLV entry, incomplete OHLC validation, missing data fingerprint) were corrected; follow-up tests cover overflow rejection, held-bar OHLC failure, and missing unheld rows. The source reviewer found no additional ready-to-run untried price-only source family under the stated constraints.

### Search interpretation and next expansion

The result is “the tested candidates did not qualify,” not “profitable algorithms do not exist.” Continuing to combine indicators factorially on the same inspected history would increase selection bias rather than improve evidence. The next search expansion must add independent information or a genuinely untouched test stream: (a) obtain authorized PIT fundamental/event data for PEAD/revisions/insider/issuance/accrual hypotheses; (b) obtain complete and versioned PIT prices, corporate actions, delisted outcomes, and benchmark files; or (c) pre-register a prospective paper-only signal and wait for new data. Until one of these gates is satisfied, further price-only backtests on this mirror remain exploratory and cannot establish a valid edge.
