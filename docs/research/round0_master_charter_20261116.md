# Master strategy research — Round 0 charter

Date: 2026-11-16 (Asia/Seoul)
Status: numerical strategy gates fixed by the user; source-data gates remain open. Research is local-only. No broker orders, market-data purchase, account creation, or server deployment is authorized.

## Fixed objectives

| Track | Primary pass criteria | Accounting/interpretation |
|---|---|---|
| Korea stocks and ETFs | Portfolio CAGR >= 20%; maximum drawdown <= 30%; annualized Sharpe >= 1.0; at least 200 OOS closed trades | Calculate from marked-to-market portfolio NAV after registered fees, taxes, and slippage. Report gross and net returns, benchmark, years, turnover, trade count, and effective dependence clusters separately. The 20% is a research target, not a forecast. |
| US stocks and ETFs | Portfolio CAGR >= 20%; maximum drawdown <= 30%; annualized Sharpe >= 1.0; at least 200 OOS closed trades | Same accounting contract as KR, but use a market-appropriate benchmark and separately documented US costs. Never pool KR and US metrics. |
| Crypto USDT perpetual manual signals | OOS target-first precision >= 80%; at least 200 non-overlapping OOS signal events | A qualifying success is the pre-registered take-profit barrier touched before the invalidation/stop barrier and before the pre-registered deadline. Evaluate and report 10x and 20x signal-timeframe-bar deadlines separately; do not select one after seeing OOS. Same-bar stop/target ambiguity is stop-first. Timeout is not a target-first success. Report deadline-close direction accuracy separately; it is not the primary gate. |

The crypto signal contract also retains the applicable chart-predictor controls: report coverage and per-timeframe/per-side results, uncertainty, fee-adjusted expectancy/net R, and baseline comparisons; only closed candles may be used and entry occurs no earlier than the next executable bar. Do not infer profitability from precision alone. Existing MTF prospective protocol's symbol-diversity, coverage, and confidence-interval checks remain additional diagnostics/eligibility gates where that protocol applies; they do not replace the user's 80% and N>=200 criteria. Its frozen 0.10% round-trip fee is a historical-signal research assumption, not measured live slippage or a complete funding model.

## Research roles and limits

Four independent agents are assigned for this round: KR domain trader, US domain trader, crypto domain trader, and red team. The three domain traders each produce ten candidates (30 total). Each candidate must state a mechanism, structural novelty versus the prior registry, exact executable rules, fixed success criteria, failure regimes, required data, and data eligibility. The red team must classify each as `통과`, `반려`, or `조건부(1회 개선 후 재검증)` and identify duplicate logic, temporal leakage, survivorship, sample, regime, cost, and execution defects.

Only candidates that pass pre-test review may enter an eligible development experiment. A red-team conditional candidate receives at most one bounded revision. All trials, including rejected, failed, and unevaluable cells, count in the registry. No strategy becomes a core strategy until it clears its pre-registered gates on eligible OOS data. The final sealed evaluation is one-time and is not a tuning set.

## Evidence and data boundaries

- Current equity caches are not admitted for confirmatory results until usage rights, point-in-time active/inactive universes, delistings/mergers, corporate actions, ETF distributions/total-return treatment, benchmark, and execution costs are established. Prior results from these caches remain exposed exploratory evidence.
- Previously viewed crypto development rows are not sealed OOS. Binance Vision is permitted only within the agreed historical, non-production backtest scope; it cannot be used as a live/manual signal feed. A prospective signal evaluation must use a separately approved public live-data capture and a frozen signal contract.
- No backtest may substitute absent funding, open-interest, mark/index, order-book, delisting, or corporate-action fields with invented values or proxy them without explicit disclosure and a separate hypothesis.
- No source-data rows may be read from a candidate sealed partition before its independently recorded access boundary and manifest are established.

## Portfolio-level policy

The three market products remain separate research books. No cross-market pooled CAGR, combined allocation, or joint portfolio claim will be made. Per-strategy capital cap and cross-domain correlation ceiling remain unset; no cross-domain portfolio will be approved until those limits and aligned return series are specified.

## Round 0 audit record

| Decision | Value | Source/status |
|---|---|---|
| KR/US CAGR target | 20% per year | User-confirmed 2026-11-16 |
| KR/US maximum drawdown | 30% | User-confirmed 2026-11-16 |
| KR/US minimum Sharpe | 1.0 annualized | User-confirmed 2026-11-16 |
| KR/US minimum OOS sample | 200 closed trades per market/strategy claim | User-confirmed 2026-11-16 |
| Crypto primary metric | Take-profit-before-stop target-first precision >= 80% | User-confirmed 2026-11-16; deadline-close direction accuracy is secondary |
| Crypto minimum OOS sample | 200 non-overlapping signal events per claim | User-confirmed 2026-11-16 |
| Capital/position and cross-market correlation limits | Unset; separate books only | No allocation claim until specified |
| KR/US numerical fee, tax and slippage model; market benchmark | Unset | No confirmatory pass/fail claim until frozen per market |
| Final holdout status | Not eligible/untouched status not proven | Existing reports; do not relabel previously viewed rows |

## Starting disposition

Round 0 is numerically complete for the user-specified primary performance thresholds, but the broader risk budget and equity transaction-cost/benchmark settings remain open. The experiment is **not yet data-eligible**: the current equity and crypto audits document unresolved source/universe/access boundaries. No new strategy performance trial is authorized until a specific candidate's data gate and preregistration pass. Strategy proposals and feasibility checks may proceed without opening a sealed set. Current lack of an eligible holdout means there is no approval, rejection, or claim of success for a new candidate.

## Round log

| Round | State | Decisions and evidence | Revision count |
|---|---|---|---:|
| 0 | Fixed | User-confirmed KR/US and crypto thresholds above; current data readiness remains NO-GO for confirmatory performance tests. | 0 |
| 1 | Candidate screen complete; data gate blocks performance tests | KR/US/crypto agents proposed 30 candidates; row-by-row red-team disposition: 0 pass, 16 reject, 14 conditional. Chief scope veto rejects US-10 index options because the mandate is stocks/ETFs only. Final disposition: 0 pass, 17 reject, 13 conditional. No performance trials or OOS events. | 0 |
| 2 | Rule review complete; data gate still blocks trials | One-time definitions recorded for the 13 conditional candidates. Chief line-by-line comparison rejects KR-01, KR-04, KR-07, and US-04 for omitted/changed registered rules or unresolved stop semantics. Final current disposition: 0 pass, 21 reject, 9 conditional. No Round 2 performance trials or valid OOS events; see [`round2_rule_review_20261116.md`](round2_rule_review_20261116.md). | 1 |
