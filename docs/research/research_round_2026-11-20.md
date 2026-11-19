# Research round — 2026-11-20

## Objective and decision rules

The sole optimization objective is maximum after-cost compounded wealth across bull, bear, and sideways regimes. For KR/US equities, CAGR ≥20%, MDD ≤30%, Sharpe ≥1.0, and OOS completed trades N≥200 are candidate gates, not the optimization objective. For crypto signals, target-first M2 ≥80% is a required accuracy gate, not a profitability proxy; fee/slippage-adjusted expectancy must also be positive. A candidate does not pass without non-overlap OOS N≥200, at least 20 symbols, at least 10% signal coverage, and a sealed evaluation.

## Four independent research roles

| Domain/role | Finding | Status |
|---|---|---|
| KR equities | Point-in-time PEAD/SUE is distinct from tested price-only candidates. Requires timestamped as-reported EPS, revisions, delisted-security history, and corporate-action-adjusted prices. | Conditional candidate; no backtest. |
| US equities | Monthly ETF dual momentum (12–1 month ranking, top two, absolute 12-month T-bill filter, next-session open rebalance) is a distinct hypothesis. Requires point-in-time ETF universe, delisted products, total-return prices and cash-rate history. | Candidate; no backtest. Low-frequency trade-count gate is a material concern. |
| Crypto candidate | Cross-sectional 60m relative-return mean reversion: among a fixed 20-symbol universe, long bottom four and short top four by prior 24h return less cross-sectional median; next-60m open entry; 0.5 ATR target, 2 ATR invalidation, 12h vertical barrier. | One fixed development test is worth preregistering only after data/engine gates. No result yet. Reward/risk is 1:4 before fees, so 80% M2 alone cannot imply positive expectancy. |
| Crypto red team | Found optimistic gap fills and missing-bar omissions in setup backtests; M2 coverage denominator excluded unscorable actionable predictions; fee-only runs falsely reported slippage tested. | Corrected in this branch; full test suite passes. |

These are research proposals, not verified market edges. Equity data eligibility and point-in-time rights remain unverified; no equity performance test was run.

## Read-only rescoring of stored crypto forecasts

The two local prediction databases were evaluated in memory with `target-first-v2`, reading `chart_predictor/data/candles.sqlite` read-only. Neither the prediction databases nor candle data were changed. The source is a historical stored-forecast sample, not a preregistered sealed OOS experiment. Its constituent predictions overlap; no non-overlap count or portfolio compounding result is asserted.

| Forecast database | Actionable issued | Scorable actionable | Target first | Wilson 95% CI | Scored / issued |
|---|---:|---:|---:|---:|---:|
| `pred_llm.sqlite` | 172 | 87 | 74/87 = 85.1% | 76.1–91.1% | 50.6% |
| `pred_llm_r2.sqlite` | 1,220 | 351 | 280/351 = 79.8% | 75.3–83.6% | 28.8% |

The first sample's point estimate exceeds 80%, but its 95% lower bound is 76.1% and it has only 87 scorable actionable cases. The second misses the 80% point estimate and its interval includes materially lower accuracy. Most rescoring exclusions were invalid directional target/invalidation geometry: all 739 unscorable Codex records in `pred_llm_r2.sqlite` failed the new level-bracketing rule; 130 Claude records also failed it. These old forecasts cannot establish present strategy performance.

Cost-adjusted trade returns were negative for each model/side subgroup in both historical databases. Mean net return per scored signal, calculated using the stored leverage suggestion, was:

| Database | Model / side | N | Mean net return on suggested leverage |
|---|---|---:|---:|
| `pred_llm.sqlite` | Claude long / short | 11 / 27 | −0.13% / −0.80% |
| `pred_llm.sqlite` | Codex long / short | 22 / 27 | −0.80% / −0.39% |
| `pred_llm_r2.sqlite` | Claude long / short | 137 / 144 | −0.39% / −0.45% |
| `pred_llm_r2.sqlite` | Codex long / short | 41 / 29 | −0.81% / −0.69% |

These returns use the stored leverage suggestion and scorer assumptions of 0.05% taker fee plus 0.02% slippage per side. They are per-signal diagnostics, not portfolio CAGR: simultaneous positions, capital allocation, and overlap were not simulated. This directly demonstrates why M2 hit rate cannot stand in for wealth growth.

## Engine corrections in this branch

- Require a contiguous 1m execution path; trades crossing missing minutes become explicitly unscorable instead of being resolved from incomplete observations.
- Model stop gaps at the 1m open and preserve adverse stop-first handling when barriers collide in the same minute.
- Make P5 evaluator output say slippage was not tested when only fee costs were included; support a user-level skill installation when the ignored repository-local copy is absent.
- Report M2 coverage against all issued actionable long/short signals, separately from the actionable signal rate.

Verification history: the initial engine-correction batch passed 217 tests. A later patch added an explicit `m2_nonoverlap` report, per-symbol and day-cluster summaries, and deterministic longest-horizon tie handling; `chart_predictor/tests` then passed 247 tests with one non-fatal Joblib CPU-detection warning. The change was committed as `adbf3de` and pushed to `research/scorer-fixes-20261120`. No deployment occurred. The existing M2 Wilson intervals do not correct for cross-symbol dependence; day clusters are diagnostics, not a clustered bootstrap confidence interval.

## Next research steps

### Follow-on crypto and equity research (2026-11-20)

- The preregistered 60-minute cross-sectional relative-return mean-reversion candidate was executed and rejected in `results/cs_mr_20261120_dev.md`; its validation interval remained unopened.
- Four independent research roles then returned: US PEAD/SUE candidate, KR PEAD/SUE candidate, crypto 3-minute candle-pressure proxy candidate, and crypto red-team/funding-carry data audit. The stock candidates are research hypotheses only; historical point-in-time earnings/universe inputs and usage rights were not established. Funding carry remains unscorable without historical funding and aligned spot/perpetual data.
- The crypto 3-minute close-location proxy was preregistered as `crypto_pressure_20261120_01`, executed once on the development split, and rejected. M2 was 8.88% all signals and 8.67% non-overlap (N=169,619); mean net return was -0.183% per signal; 1x capped portfolio final NAV was 8.49e-19 with 100% MDD. BTC buy-and-hold ended at 1.2786. Its 2x-slippage and 1-minute-delay checks also failed. No validation, Monte Carlo, block bootstrap, parameter grid, or walk-forward was run after failure.
- Source data remained read-only. The exact preregistration, compact JSON aggregates and decision report are linked in the registry at trial 98. This is not evidence that all regimes or all strategies have been exhausted.

### Cross-domain audit and BTC→alt lag-flow screen

- Four new independent reviews examined (1) crypto candidate distinctness, (2) US OHLC quality and strategy/data eligibility, (3) KR candidate/data eligibility, and (4) objective and red-team evidence. Their conclusion: KR and US have no currently qualifying new backtest candidate because rights/PIT/data quality are not established; the 92-file US cache has 62 OHLC range violations concentrated on four dates, with no evidence sufficient to repair the source. These are `NOT_EVALUABLE` data gates, not strategy rejections.
- The only new crypto mechanism worth a bounded development screen was BTC directional shock + aligned 4-hour regime + lagging-alt 30-minute return + taker-flow confirmation. It was separately preregistered as trial 99 before candidate outcomes were computed. The implementation used only completed 1m bars and historical Binance Vision data; the confirmation period was held unopened.
- Trial 99 failed: 5,071 issued/scorable signals; M2 20.86% (Wilson 95% CI 19.77–22.00%); non-overlap M2 20.82% (N=4,865; CI 19.70–21.99%); expiry direction accuracy 48.47%; base/stress mean net returns −0.1795%/−0.2595%. Base final NAV was 0.000147 versus matched leader 0.000152, cash 1.0, and BTC buy-and-hold 6.597. Base MDD was 99.9854%. M2 and wealth gates both fail; the lagging-alt selection did not improve the leader control. See [`results/btc_alt_lag_flow_20261120_dev.md`](results/btc_alt_lag_flow_20261120_dev.md).
- Trial 99 was rerun with identical input and produced byte-identical JSON. A separate read-only red-team found no result-reversing implementation or metric bug, while noting the synthetic tests do not cover every possible execution boundary. `chart_predictor/tests`: 238 passed, one non-fatal Joblib CPU-detection warning.
- The Vision-derived report and aggregate JSON carry source attribution and CC BY-NC-SA 4.0 notice. The 2.56GB source DB was not copied or modified. The screen has six current symbols, a short development interval, survivor/universe bias, and no live fills, funding or liquidation model; even a pass could not satisfy the final multi-symbol/forward evidence gate.
- Trial 99 is rejected without tuning. Do not open its confirmation interval or use its historical output as a live/manual signal. This rejection narrows one mechanism; it does not prove no profitable strategy exists.

### Published market time-series momentum 28/5 trial

- A single fixed 28-day/5-day long-only market timing hypothesis was preregistered as trial 100 based on Han, Kang & Ryu’s study; the paper itself selected 28/5 after many tested pairs, so its headline is treated as selection-biased prior evidence. This adaptation used a causal expanding threshold, five daily sleeves, equal-weight six-coin basket, and no short exposure.
- The fixed development window was 2020-09-15..2023-12-31 UTC; 10,393,920 Binance Vision rows aggregated to 1,204 complete days × six symbols. Each day had all 1,440 aligned minutes and valid OHLC; 0 off-grid rows. No post-2023 data was queried.
- Primary base/stress CAGR 6.40%/6.12%, Sharpe 0.385/0.374, MDD 40.30%/40.49%, final NAV 1.227/1.216. Both cases failed to beat cash, BTC B&H (NAV 3.919), and the fixed six-coin B&H (NAV 15.071). The latter is current-survivor biased and not a future expectation, but was the preregistered same-sample comparator. The candidate also failed the ≤60% annual positive log-growth concentration cap: 2023 contributed 69.2%.
- 1,000-order Monte Carlo 95th-percentile MDD was 43.23% base/43.46% stress. 1,000 seven-day block bootstrap CIs for base annualized arithmetic mean and CAGR were −12.31%..+30.06% and −15.01%..+32.05%, including negative outcomes. Predeclared nearby parameter diagnostics did not beat benchmarks and were not selected. The 2024+ confirmation interval remains unopened.
- Red-team found one loader issue: off-grid rows could preserve daily row count/endpoints. It is fixed by explicit minute-grid validation and a regression test. All 246 chart_predictor tests pass; one non-fatal Joblib CPU-detection warning remains. The script and source-window rerun produce byte-identical JSON. No funding history is available, so this is an optimistic price-only USD-M proxy and cannot establish futures profitability.
- Trial 100 is rejected. This is a candidate-level result, not proof that all crypto timing strategies have been exhausted. See [`results/market_tsmom_28_5_20261120_dev.md`](results/market_tsmom_28_5_20261120_dev.md).

1. Merge these engine corrections only after final diff review and remote-state verification.
2. Do not reopen either rejected crypto candidate by changing parameters. Choose a distinct, evidence-based hypothesis, or acquire the specific historical funding/order-flow data required by a separately preregistered hypothesis.
3. For KR/US PEAD, establish data rights and point-in-time histories (including delisted names, as-reported earnings, and timestamped consensus) before any performance test. Mark unavailable data as `NOT_EVALUABLE`, not a strategy rejection.
4. Keep validation/sealed windows untouched until a candidate's rules are frozen; never claim all-regime success from these short development screens.

### Data-gate decision after four independent reviews

- The KR-equity, US-equity/ETF, crypto-hypothesis, and crypto-red-team reviews found no justified new performance test that passes current data-eligibility gates. KR/US remain `NOT_EVALUABLE` pending point-in-time universes, delisted instruments, corporate-action provenance, lawful usage, and defensible cost/benchmark histories. Crypto OI/funding reversal remains a hypothesis only until aligned historical coverage and timestamp availability are verified. The broad 45-symbol cross-sectional screen at trial 78 means a relabelled momentum variant is not a new mechanism.
- Binance Vision's current terms distinguish permitted personal, non-production historical backtesting from live proprietary execution and commercial signal use. Research data and any future live/manual signal source must remain separate unless separate written rights are established. Historical USD-M metrics also have unresolved timestamp/provenance questions; no assumed timestamp shift is allowed.
- No strategy outcomes or validation/sealed data were calculated or opened in this review. The integrated data-gate decision and next steps are recorded in [`next_round_data_gates_2026-11-20.md`](next_round_data_gates_2026-11-20.md).

### Follow-up candidate review and official data-access checks

Four additional independent, read-only reviews proposed one distinct candidate per research lane. None ran a performance backtest, and none is a verified edge:

- **US stocks/ETFs:** monthly ETF dual momentum. At each month-end, rank a frozen point-in-time ETF universe by 12–1-month total return; hold the top two equally only when each has beaten the contemporaneous 1-year T-bill return, otherwise hold the allocation in cash; rebalance next-session open. Prioritized because earlier ETF rotation was rejected and a prior 12–1 momentum implementation failed before producing valid results. Required inputs are PIT ETF membership, inactive products, total-return history and cash-rate history. Trade-count N≥200 may be unattainable for a monthly design; do not loosen that gate after seeing results.
- **KR stocks/ETFs:** monthly 10% volatility-target exposure to KODEX 200 (069500), with weight `min(1, 10% / trailing 20-session annualized realized volatility)` and remainder in cash. This is a candidate, not a test result. Requires authorized adjusted total-return prices, ETF lifecycle history, costs/tax and a benchmark.
- **Crypto signal:** at UTC 15-minute boundaries, freeze the preceding 15 completed 1-minute candle range; after a close outside the range, require the last-five-bar taker-buy share to be ≥0.60 for long or ≤0.40 for short. Enter next 1-minute open, stop at 1×pre-signal ATR(14), target at 2×ATR, expire after 15 minutes, and count same-minute target/stop collisions as loss. The M2 mechanism is distinct only as a combination; taker-flow and boundary-event families were separately screened before. Current 6-symbol history cannot satisfy the 20-symbol M2 breadth requirement, so do not test this as confirmation.
- **Crypto compounding/portfolio:** fixed 50:50 capital split between the exact catalog Dual Thrust long/short rule and the 14/3/8 dollar-neutral rotation. Compare the combined daily NAV with both standalone NAVs and cash on the same aligned dates and cost/funding contract; use paired calendar-block resampling of the joint return path. Existing individual results do not prove the mix helps. No new portfolio result exists. The separate volume-climax failed-breakout candidate was already rejected in trials 27 and 30; it is not a surviving champion and must not be substituted into this portfolio test.

**Official data access checked read-only:** KRX OPEN API lists equity and ETF daily data from 2010-01-04. API use requires account login, an approved authentication key and application to each API; its terms state non-commercial use, a 10,000-request/day/key cap and no third-party provision. The public service listing does not establish that the daily APIs include delisted histories, full PIT membership or adjusted total-return corporate actions. No account/key was created and no API call requiring credentials was made. [KRX API catalog](https://openapi.krx.co.kr/contents/OPP/INFO/service/OPPINFO004.cmd), [KRX API terms](https://openapi.krx.co.kr/contents/OPP/INFO/OPPINFO002.jsp), [KRX use steps](https://openapi.krx.co.kr/contents/OPP/INFO/OPPINFO003.jsp).

The official CRSP/Morningstar page currently describes daily/monthly data and corporate actions for more than 36,000 active and inactive US securities, but does not publicly settle this project's ETF constituent-history coverage or price. The 2023 CRSP sample guide says promotional samples may be requested by email; because the product pages migrated in 2026, current sample availability must be reconfirmed. No email was sent, no sample or quote was obtained, and no account or purchase was made. [Current CRSP product page](https://indexes.morningstar.com/research-data-products/crsp-us-stock-databases), [CRSP sample guide](https://www.crsp.org/wp-content/uploads/2023/09/CRSP_Sample_Data_and_Software_Guide.pdf), [current product library](https://indexes.morningstar.com/research-data-products/document-library).

**Next decision:** no candidate is ready for a confirmatory performance test. Continue data eligibility work first; keep all previously opened validation/sealed intervals closed. The candidate rules above are research proposals and must be separately preregistered, with source terms and exact data fingerprints, before computing outcomes.

### Objective-first independent review — correction and next experiment

The optimization objective remains maximum after-cost compounded wealth across market regimes. The CAGR/MDD/Sharpe/trade-count and crypto M2/coverage/breadth requirements remain gates; no review found a verified strategy that satisfies the complete objective.

Four independent read-only reviews examined the existing strategy ledger and proposed experiments. They did not run backtests or access sealed data. Their most useful correction is that the KR ETF momentum screen above is **not untested**: the existing script and result artifact cover 2010-12-30 through 2024-11-11. The equal-weight top-3 126-session monthly momentum rule reported 5.21% CAGR, 55.42% MDD, and 0.340 Sharpe at 0.115% one-way cost; inverse-volatility weighting reported 6.82%, 54.02%, and 0.415. At stress cost, the corresponding CAGRs were 4.72% and 6.25%, with MDDs 55.86% and 54.55%. These exploratory results fail the frozen equity gates and do not justify another test of this candidate. Sources: `scripts/research/equity_etf_rotation_probe.py`, `docs/research/equity_etf_rotation_20261115.csv`, and the Round 5 section of `docs/research/strategy_research_round4_20261115.md`.

The highest reported KR stock CAGR surfaced by the review was 49% for a 60/5/21 momentum variant on a recent-liquidity universe, but the same record reports roughly 31% MDD, dependence on a few later winners, no delisted names, and a drop to 17% CAGR/40% MDD after removing the top 10 names. Treat it as a selection-biased historical observation, not a credible market-regime edge. The highest surfaced US exploratory report was 19.55% CAGR / 0.99 Sharpe / 29.20% MDD for residual momentum at 10 bp one-way cost (17.05% CAGR at 40 bp); it reused previously observed periods and had incomplete point-in-time membership and execution-cost evidence. It is not a pass. A fixed SPY/EFA/TLT/GLD multi-asset trend rule is a distinct US follow-up hypothesis, not a measured result.

The crypto portfolio reviews independently converged on the next high-value question: does a **fixed 50:50 capital split between the exact catalog Dual Thrust long/short rule and the 14/3/8 rotation** improve net compounded wealth across regimes versus each standalone sleeve and cash? This is a portfolio-interaction test, not a new standalone-strategy claim. It must use one aligned daily NAV path, identical universe/date/capital/execution rules, matched 0.10% fees plus conservative slippage and funding treatment, and a preregistered fixed weight; report net terminal wealth/CAGR, MDD, Sharpe, turnover, yearly and prespecified regime returns, and paired calendar-block uncertainty. Do not optimize the mixture weight after seeing results.

**Readiness gate:** no reproducible source package containing both sleeves' aligned daily holdings/returns and matching historical funding was identified in the repository review. The local long-history Vision database has six symbols through 2026-06-30 and no funding series; it cannot reproduce the documented 45-symbol portfolio as originally tested. Existing Dual Thrust headline results also omit funding and slippage. Therefore the proposed combination has **not** been tested in this round. First locate or rebuild both exact sleeves from a permitted, fingerprinted common source; if only a narrower price-only diagnostic is possible, preregister and label it exploratory, never as futures profitability or independent OOS. For stocks, the 184-file local KIS cache is not by itself proof of point-in-time universe, corporate-action adjustment, usage rights, or sealed-data eligibility; historical screens there remain exploratory.
