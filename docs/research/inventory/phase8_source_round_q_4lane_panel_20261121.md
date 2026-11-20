# Phase 8 — Round Q: four-source scan and adversarial panel

Date: 2026-11-21. Search and panel scope: public crypto-futures strategies
not represented by the registry through #118, especially after the expanded
minute-archive audit and the completed Round N contract/mark-deviation
diagnostic. No outcomes were inspected or scored in this source round.

## Scout results

| Lane | Closest leads | Result |
|---|---|---|
| SNS / papers | Quarter-hour boundary research by Kim and Hansen; prior-day volume-profile/POC mean reversion by Perera | 0 eligible. The abstract reports quarter-hour opening-return effects and 4–12-hour predictability, not M2 trades; the POC paper lacks a fully fixed entry, invalidation and expiry and overlaps registry #9. |
| TradingView / Pine | AetherEdge Kalman level/slope bands; Loft Kalman stop-and-reverse; Crypto Confirmation Engine; Lisan C4.2 | 0 eligible. These are indicators/bias tools or trend/reversal strategies without source-fixed M2 barriers/expiry; they overlap existing #6/#98 and adjacent #117–118 families. |
| Public communities | Liquidation-surge reversal and liquidation-map + RSI anecdotes | 0 eligible. No quantitative liquidation trigger, executable entry, target, invalidation or expiry. The local archive has no liquidation-event feed; RSI/sweep families are already represented. |
| GitHub / skills | NEDL rolling-cointegration pair trading; Nautilus `VolumeSpikeLong`/`PullbackLong` | 0 eligible. NEDL is daily and exits on mean reversion without fixed M2 target/expiry; the Nautilus examples are long-only, lack fixed expiry, and volume spike overlaps tested flow/momentum families. License/date evidence is incomplete for some pages. |

Sources: [quarter-hour paper](https://arxiv.org/abs/2607.09426), [volume-profile paper](https://papers.ssrn.com/sol3/Delivery.cfm/6932998.pdf?abstractid=6932998&type=2), [AetherEdge Kalman](https://www.tradingview.com/script/1coOxasg/), [Loft Kalman](https://www.tradingview.com/script/hMzmBTWO-Loft-Strategy-V1/), [Crypto Confirmation Engine](https://www.tradingview.com/script/YZUF32q6-Crypto-Confirmation-Engine-Auto-Detect-Coin/), [liquidation-surge community idea](https://www.reddit.com/r/Daytrading/comments/1xx3xkr/i_backtested_400000_crypto_strategies_on_6_years/), [liquidation-map/RSI anecdote](https://www.reddit.com/r/Daytrading/comments/1jnim18), [NEDL pair trading](https://github.com/djienne/pair_trading_NEDL/blob/main/README.md), and [Nautilus example strategies](https://github.com/AlexSilka/nautilus-trading#strategies). Source claims and dates are treated as the pages report them; they are not independent performance evidence.

## Four-role panel

| Role | Decision | Strongest evidence |
|---|---|---|
| Blue | HOLD / NO TEST | The quarter-hour paper is the closest quantitative mechanism, but the abstract does not define an M2 bracket and its opening-window data granularity must be checked in the full paper before any replication claim. |
| Red | HOLD / NO TEST | Every apparent path requires inventing essential rules or substituting a proxy. POC is a direct #9 overlap; trend/reversal is #6/#98 or adjacent to #117–118. |
| Data / Methods | HOLD / NO TEST | No candidate has a source-defined causal entry, TP, invalidation and expiry compatible with the fixed M2 scoring contract and available data. Liquidation events are absent. |
| Judge | HOLD / NO TEST | Four scouts returned zero eligible candidates; four panel roles independently retained the no-test disposition. |

The strongest dissent is that the quarter-hour paper may merit a separate
return-forecast falsification if its exact inputs and local data availability
are established. It is not a target-first M2 strategy and overlaps registry
#23/#108 at the clock/session mechanism level. The abstract does not establish
that a target-first effect exceeds fees. The community liquidation-surge idea is a distinct
mechanism in principle, but no local historical liquidation feed or frozen
source rule is available. Neither should be converted into a strategy by
adding researcher-selected barriers.

## Fixed gates and disposition

The M2 contract remains unchanged: count every issued actionable long/short
signal; use the specified next-candle-open entry; pre-entry barrier/gap
non-execution remains a failure in the main denominator; target must occur
before stop; same-candle target/stop ties are stop-first; timeout is failure.
Required gates remain target-first M2 ≥80%, non-overlap N≥200 across ≥20
symbols, coverage ≥10%, and positive net expectancy under both fixed fee
scenarios. No candidate is eligible for a preregistration or test in this
round. **Disposition: HOLD / NO TEST / NO SCORE / NO CORE / PHASE 9 NOT RUN.**

This was a bounded review of the four assigned source lanes and the near-leads
listed above, not proof that no public or custom strategy exists. No backtest,
outcome scoring, parameter search, download, installation, account access,
comment or file modification by scouts was performed. This file records the
first persistent Round Q panel outcome.
