# Phase 8 Round I — source scan and BTC/ETH-to-alt lead-lag panel

Date: 2026-11-20. Four independent source lanes reviewed public SNS/research,
TradingView/Pine, communities, and GitHub/papers. A four-role panel reviewed
one proposed BTC/ETH-leader to lagging-alt adaptation. This was a read-only
source and data-eligibility review: no downloads, installs, comments, account
access, performance backtest, or order activity occurred.

## Source-lane findings

| Lane | Lead examined | Decision |
|---|---|---|
| SNS / research | Kitron and Wengrowicz short-horizon reversal paper and author code. It forecasts the next 15-minute return against the previous candle sign; it does not specify M2 entry/TP/SL/expiry. The authors report gross about 1.3 bp per trade against 5 bp costs. It overlaps the registry's reversal family. [Paper](https://arxiv.org/abs/2608.21888), [code](https://github.com/nadav2/short-horizon-reversion) | Reject for M2 scoring: cost result is negative before a complete M2 rule, and structure overlaps prior reversal work. |
| TradingView / Pine | QuantAlgo Fakeout/Breakout Probability (invite-only; exact rule, parameters, barriers unavailable) and Probability Cone (range-probability visualization, not a directional barrier strategy) | Reject: source rules cannot be independently reconstructed. |
| Public communities | 24-hour rollout effect: prior 24-hour largest positive/negative hourly move contrarian signal, next-hour open, one-hour hold. The source repo reports -6.3 bp at 10 bp taker and -0.3 bp at 4 bp maker; no TP/SL. [Repository](https://github.com/OctopusTakopi/24h-rollout-effect) | Reject for M2 and cost gate: no barriers and source-reported costs remain negative. The 14-day cross-sectional momentum lead duplicates registry rows 65/78 and has no M2 barriers. |
| GitHub / papers | ProSP probability-tail ranking uses private data and has no reproducible public code/data or fixed barriers. Cross-cryptocurrency return predictability reports short-horizon ranking results but no fixed target/stop/expiry M2 rule. [ProSP](https://www.sciencedirect.com/science/article/pii/S0378437126006473), [cross-crypto study](https://www.sciencedirect.com/science/article/pii/S0165188924000551) | Reject for M2 scoring: source evidence is not a complete reproducible barrier strategy. |

Source claims above are not independently reproduced performance estimates.
No source-complete M2 strategy emerged from the four lanes.

## Candidate deliberated: BTC/ETH leader, lagging-alt continuation

The SNS scout proposed a **new adaptation**, not a replication of the cited
cross-cryptocurrency study:

- Universe proposal: SOLUSDT perpetual; inputs are completed 1-minute BTC,
  ETH, and SOL candles and funding.
- After minute `t` closes, define each asset's latest completed 1-minute
  return. Long SOL if BTC and ETH returns are both positive and SOL return is
  below their mean. Short SOL if both leaders are negative and SOL return is
  above their mean. Enter at the next 1-minute open.
- Use prior completed SOL ATR(14) as 1R; TP=1R, SL=1R; expire after 10
  subsequent 1-minute candles. If both barriers occur within a candle, count
  stop first. Expiry is not target-first. Charge frozen base/stress costs and
  funding only at actual settlement times.

This rule is preserved as a **hypothesis only**. It is not a source-complete
strategy, a preregistered Core candidate, or evidence of profitability. In
particular, generalizing the single-SOL rule to 20+ symbols would be a new
specification and requires a separate pre-registration; it must not be
silently inferred from this proposal.

## Four-role panel

| Role | Vote | Evidence / reason |
|---|---|---|
| Blue | Conditional research lead; no score | Cross-crypto predictability provides a mechanism to investigate, but the proposed SOL barrier rule is a new adaptation. |
| Red | Reject current candidate for M2 progression | No source-defined TP/SL/expiry, overlap with relative-return and momentum families, and the proposed fixed rule lacks a complete frozen benchmark/cost protocol. Simultaneous close-to-close signals cannot fill at that same close; overlapping labels require purge/embargo. |
| Data/Methods | No eligible Core dataset | Existing 1m Vision history is six exposed symbols through 2026-06 and lacks established minute mark/funding. The hourly 36-symbol archive cannot resolve minute barrier order. Tick archive coverage/mark alignment is not verified as a >=20-symbol sealed panel. |
| Judge | No candidate advances to scoring | No complete source strategy and no data meeting the frozen Core gate. Keep the hypothesis only; do not promote it or proceed to Phase 9. |

Panel resolution: **NO SCORE / NO PROMOTION / PHASE 9 BLOCKED**. The one
conditional Blue vote does not override the independent red-team and data
gates. No strategy result, hit rate, or return is reported for this hypothesis.

## Data gate and next research order

1. Keep searching for original, reproducible source rules; require direction,
   signal timestamp, executable entry, TP, SL, expiry, cost/funding model,
   data requirements, and license before source-based strategy scoring.
2. Treat the SOL lead-lag rule as a research note only. Before any scoring,
   freeze a universe of at least 20 eligible perpetual contracts, causal signal
   and next-open execution, barriers, expiry, stop-first tie rule, fees,
   slippage, actual funding timestamps, baseline, event purging/embargo, and
   all trial counts. Any 20-symbol extension is a distinct preregistration.
3. Establish an independently eligible forward period with aligned minute
   price/mark/funding inputs and audit missingness, symbol eligibility, and
   outcome overlap. Existing exposed data can validate plumbing only, not
   qualify as sealed OOS.
4. Run one fixed test only after the data and preregistration gates pass. Keep
   the existing Core thresholds: target-first M2 >=80%, full-issued M2 plus
   separate non-overlap OOS N>=200 across >=20 symbols, coverage >=10%,
   positive net expectancy under base and stress costs/funding, frozen-baseline
   superiority, and independent robustness review.

Current disposition: no Core strategy exists; Phase 9 remains blocked. Round I
does not establish that all possible public strategies were exhausted.
