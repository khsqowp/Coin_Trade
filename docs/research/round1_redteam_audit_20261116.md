# Round 1 candidate-level red-team audit

Date: 2026-11-16 (Asia/Seoul)
Input: [`round1_candidate_register_20261116.md`](round1_candidate_register_20261116.md)
Scope: all 30 proposed candidates; compare with Round 0 charter, strategy catalog, equity data readiness, Round 5–7 records, and crypto preregistration. No backtest, sealed-data inspection, or file edit by the red-team agent.

## Disposition

**Red-team table recount: 0 pass, 16 reject, 14 conditional. Final chief disposition: 0 pass, 17 reject, 13 conditional.** The agent's opening summary stated 12 reject and 18 conditional, inconsistent with its own row verdicts. A separate scope veto rejects US-10 because the user limited the US/KR program to stocks and ETFs, while US-10 is an index-options strategy. Conditional permits only the single bounded correction stated; it does not waive market-data rights, point-in-time universe, corporate-action, cost, execution, or holdout gates. None is an approval to run performance trials.

| Candidate | Verdict | Reason / single allowed correction |
|---|---|---|
| KR-01 Earnings surprise drift | Conditional | “EPS or operating income +10%” and consensus vintage/analyst count are ambiguous. Freeze the comparison field, denominator, as-of consensus timestamp, and minimum analyst count. |
| KR-02 KOSPI 200 reconstitution | Conditional | Revised/withdrawn notices, event identity, simultaneous additions, and reason handling are undefined. Freeze event identity and notice correction/withdrawal treatment. PIT constituent history remains a separate data gate. |
| KR-03 ETF NAV/iNAV dislocation | Reject | Duplicate of the Round 6 Korea ETF close-to-NAV/iNAV reversion hypothesis; new thresholds do not create a distinct mechanism. Prior data gate also lacks timestamped iNAV and executable quotes. |
| KR-04 Foreign-flow/price confirmation | Conditional | On-/off-market, lending/block trade, classification, and publication-time handling are unclear. Freeze included flow fields and availability; explicitly exclude unavailable off-market/lending data. |
| KR-05 Closing-auction program imbalance | Conditional | Top-1% comparison universe/window and next-open fill/miss rules are undefined; auction/NBBO history is absent. Freeze PIT comparison cohort/window and executable next-open rules. |
| KR-06 IPO lock-up supply absorption | Conditional | Actual unlock date, pre-unlock reference close, float denominator, and two-session volume sum are ambiguous. Freeze those definitions and missing-session treatment. |
| KR-07 Cash-dividend surprise | Conditional | Expected dividend/yield source and calculation are not specified; special dividend, share-count, currency, and fiscal-period effects remain. Freeze one PIT expected-DPS/yield source and adjustment rule. |
| KR-08 CB/BW dilution-overhang avoidance | Reject | A holding exit/avoidance overlay, not a standalone strategy: no entry, reference portfolio, holding horizon, or complete state transition is defined. |
| KR-09 Merger/demerger rights event | Reject | Event study and exit-avoidance proposal are conflated; direction, entry population, attribution, cancellation, consideration, and successor mapping are not frozen. |
| KR-10 Shareholder meeting/governance event | Conditional | Agenda text and amended notices are not reproducibly classified. Freeze a point-in-time text dictionary and correction handling; ensure vote outcomes never become entry inputs. |
| US-01 Form 4 insider cluster | Reject | Duplicate of an existing feasibility lead, not a structurally new candidate; filing vintage, inactive names, rights, and PIT data gates remain open. |
| US-02 13F ownership change | Reject | Duplicate of existing feasibility lead; manager deduplication, filing vintage, split adjustment, and inactive-security gates remain unresolved. |
| US-03 PEAD/SUE | Reject | Same core hypothesis as existing PEAD/SUE feasibility lead; entry/exit changes do not establish novelty or solve consensus-vintage/OOS issues. |
| US-04 Schedule 13D/13G activist ownership | Conditional | 13D and 13G differ in purpose and reporting. Restrict the candidate to new 13D filings; exclude 13G from this hypothesis. |
| US-05 Actual buyback execution progress | Conditional | Cumulative quantity, denominator, filing period, reporting lag, and correction handling are unclear. Freeze only the cumulative values available at filing, their period/denominator, and amendments. |
| US-06 ETF net creation/redemption flow | Conditional | Net flow/AUM calculation and availability, overlapping ETF exposure, leverage/inverse exclusions, and PIT fund universe are undefined. Freeze the flow formula/availability and ETF universe/exclusions. |
| US-07 Dividend initiation/increase | Conditional | Comparison period, currency, and split adjustment for regular dividend increases are not fixed. Freeze one filing-time comparison formula and regular-dividend classification. |
| US-08 IPO lock-up release short | Conditional | Contractual vs actual unlock, volume reference, borrow/recall costs, gap execution, and short-side ATR loss direction are unclear. Freeze actual-unlock confirmation and the complete borrow/cost/fill/stop rule. |
| US-09 Index inclusion/exclusion | Conditional | Long/short populations, unavailable borrow, amended notices, and repeat events are not governed. Freeze direction-specific populations, no-borrow exclusion, and repeated-event handling. |
| US-10 Index option volatility-risk premium | Conditional by red team; **rejected by chief scope veto** | ATM IV/RV timing and units, spread strikes/width/expiry/credit/size, early exercise, and costs are unspecified. More decisively, options are outside the user's stocks/ETFs-only scope; do not revise or test this candidate. |
| C-01 Market breadth thrust | Reject | Candidate register only specifies 5m entry and omits the requested multiple micro-timeframe coverage; point-in-time synchronized cohort of at least 20 symbols is also unavailable. |
| C-02 Breadth-price divergence resolution | Reject | Same timeframe-scope and cohort defects; divergence has no maximum waiting/expiry rule, so signal lifetime is not codeable. |
| C-03 Cross-sectional volatility compression/expansion | Reject | Same timeframe-scope defect; “normalized” true range, rolling percentile reference, and tie handling are undefined; synchronized PIT cohort is unavailable. |
| C-04 Return-dispersion shock continuation | Reject | Same timeframe-scope defect; MAD/relative-return population, alignment, and percentile window are undefined; current data cannot control PIT cohort dominance/survivorship. |
| C-05 HTF tail-shock acceptance | Reject | Same timeframe-scope defect; holdout is not sealed, and qualified aligned 1m path data for stop-first resolution is not established. |
| C-06 30m efficiency transition + 5m confirmation | Reject | Same timeframe-scope defect and substantial overlap with existing trend/EMA/MTF breakout families; no distinct mechanism established. |
| C-07 Semi-variance imbalance extension | Reject | Same timeframe-scope defect; semivariance sample/zero-denominator/inverse threshold are undefined, and OHLC alone cannot establish intrabar stop/target ordering. |
| C-08 Volume participation directional efficiency | Reject | Same timeframe-scope defect; quote-volume divided by absolute candle body explodes on doji and does not identify aggressor direction. |
| C-09 Multi-close range-break acceptance | Reject | Same timeframe-scope defect; overlaps Donchian/range-break/squeeze/ORB families, while stop and boundary-return rules are not precise. |
| C-10 Cross-sectional synchronized wave laggard join | Reject | Same timeframe-scope defect; likely duplicates exposed R023 BTC-lead/alt-laggard work already rejected in development. The same data cannot be retuned. |

## Gate decision

- Red-team row tally: KR 7 conditional / 3 reject; US 7 conditional / 3 reject; crypto 10 reject. Total: **14 conditional, 16 reject, 0 pass**. After chief scope veto of US-10, final disposition is KR 7 conditional / 3 reject; US 6 conditional / 4 reject; crypto 10 reject: **13 conditional, 17 reject, 0 pass**.
- No strategy from Round 1 advances to performance testing. Equity legal/data/universe/action/cost/benchmark gates are still closed. Crypto candidates also fail requested timeframe breadth; existing historical inputs are exposed and do not establish a sealed OOS cohort.
- No candidate has a validated return, precision, or OOS sample from this round. The count of performance trials is **0** and OOS events are **0**.
- Next permissible research is limited to one-time clarification of the 14 conditional rules, strategy novelty checks, and data-source eligibility. Do not reinterpret a conditionally corrected proposal as tested or approved.

## Evidence limitation

The red-team report was returned in an agent message. The row-level reasons and single corrections above are transcribed and normalized from that report; its tally was independently recomputed because the agent's summary arithmetic conflicted with its table. A separate chief scope veto was applied to US-10. Repository data readiness records remain the evidence for the NO-GO gate; this review did not independently acquire or verify third-party datasets.
