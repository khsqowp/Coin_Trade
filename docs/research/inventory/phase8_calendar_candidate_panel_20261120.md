# Phase 8 external research panel — UTC calendar candidate

Date: 2026-11-20. This record captures a four-role review of external candidate
families and one fixed calendar-conditioned candidate. It does not report a
backtest result or authorize a Core designation.

## Candidate sources and disposition

| Scout | Finding | Disposition |
|---|---|---|
| Public social media | No complete, materially distinct setup with precise entries and exits; examples were anecdotal, incomplete, or overlapped reversal/SMC families. | Reject for current test batch. |
| TradingView/Pine indicators | Turtle Soup and TTM Squeeze have interpretable mechanisms, but public rules lacked complete execution/exit definitions or overlapped prior sweep/breakout families. | Not eligible without a new distinct, complete hypothesis. |
| Public communities | No sufficiently specified candidate; common mean-reversion and failed-breakout ideas were incomplete or already represented. | Reject for current test batch. |
| GitHub strategy/skills | A 72-hour BTC absolute-price z-score reversion implementation was found, but lacked stop, target, and maximum holding time; its public repo had no license. | Reject as proposed; do not copy code. |

## Candidate review

The candidate is the UTC weekday×hour return-sign majority rule specified in
[`PREREG_UTC_WEEKDAY_HOUR_SIGN_M2_20261120.md`](PREREG_UTC_WEEKDAY_HOUR_SIGN_M2_20261120.md).
It is not the funding-session opening-range breakout (P8-B), which was already
rejected, and it is not the funding-tail or prior-hour reversal candidate.
However, UTC hour features and time-conditioned crypto behavior have appeared
in earlier research. Novelty is incremental, not a new market mechanism.

| Reviewer role | Vote | Main reason |
|---|---|---|
| Blue team | Revise / retain for one fixed test | Calendar-cell direction persistence is testable, but literature supports volatility/volume periodicity more strongly than directional predictability. Freeze all rules and do not score before data QA. |
| Red team | Hold pending gates | 168 symbol-specific slots create estimation noise; calendar and time features were previously explored; crypto symbols and hours are dependent; no spread/slippage evidence. |
| Data/method reviewer | Exploratory M2 inputs available with exclusions | All 1,728 selected ZIPs for 2025-06..2026-09 matched audit SHA. Monthly mark files have a 24-hour 2026-06-29 gap for 36 symbols; daily recovery files can be overlaid read-only. Exclude IMXUSDT × 2026-06 for funding interval inconsistency. |
| Judge | Approve one exploratory preregistration and score, conditionally | Full raw audit, recovery overlay, exclusions, baseline, and execution rules must be frozen first. June–September is previously source-audited and is not sealed/live-forward evidence. No numerical pass can establish Core status. |

## Research order and gates

1. Reconcile prior registry families and all four source scouts. Complete; no
   rejected scout candidate is being carried into scoring.
2. Freeze one calendar hypothesis, rules, cost assumptions, data window, and
   exclusions. The candidate preregistration is the controlling record.
3. Before scoring, independently verify all required archive SHA values,
   continuous hourly trade-price bars, mark-price alignment after read-only
   daily recovery overlay, funding intervals, and exact eligible symbols.
4. Freeze the development-selected directional baseline using only the stated
   development window. Do not inspect candidate holdout metrics while choosing
   that baseline.
5. Run the one exploratory 2026-06..2026-09 event-path evaluation once. Report
   all issued and non-overlap events, M2, M1 separately, coverage, symbol/time
   concentration, funding, fees, and cluster-aware uncertainty. Preserve any
   failure or data-blocked outcome.
6. Only if the exploratory result clears every fixed numeric gate, conduct an
   independent ledger/code red-team and acquire eligible spread/slippage and
   point-in-time universe evidence. Then obtain a genuinely untouched forward
   sample before any Core decision.
7. Phase 9 remains blocked until at least one standalone strategy satisfies the
   full market-specific Core gate. Do not blend failed or exploratory sleeves.

## Final candidate result and panel decision

The one approved exploratory test was executed after preflight and baseline
freeze. It produced 14,724 target-first outcomes from 39,410 issued entries
(M2 37.36%), versus a frozen development short baseline of 37.70%. Coverage
was 38.50% across 35 symbols; per-symbol non-overlap count was 39,410 and
market-time non-overlap count was 821. Mean return was negative before fees
(-1.394 bp) and remained negative under both fee scenarios. The candidate
failed M2 ≥80% and positive-net gates.

Blue and judge voted **REJECT** after seeing the result. Red independently found
no timing or M2-label defect that changes the rejection, but flagged funding
amount basis and six trades exiting at the period endpoint as cost-estimate
limitations. No rule retuning is allowed on this interval. The detailed
figures, data audit, and ledger validation are in
[`runs/weekday_hour_m2_20261120/report.md`](runs/weekday_hour_m2_20261120/report.md).

## Evidence limits

The 2026-06..2026-09 interval is a chronological extension after the existing
2026-05 endpoint, but the raw archives were previously downloaded and audited.
It is therefore not described as sealed or live-forward evidence. Existing
cost scenarios are fee proxies (10 bp base / 30 bp stress round trip) plus
archived funding; spread and slippage remain unmeasured. The current 36-symbol
cohort also has unresolved point-in-time listing/delisting survivorship risk.

External evidence supports treating calendar periodicity as a hypothesis, not
an edge: crypto volatility and liquidity periodicities have been documented,
while hourly day-of-week return effects have been reported as localized and
non-persistent. See [Wei et al., *Periodicity in Cryptocurrency Volatility and
Liquidity*](https://academic.oup.com/jfec/article-abstract/22/1/224/6759403) and
[Aalipour et al., *Are day-of-the-week effects in cryptocurrencies
real?*](https://www.sciencedirect.com/science/article/pii/S1544612326011621).
