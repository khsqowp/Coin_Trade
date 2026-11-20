# Coin strategy source-scout and review panel — 2026-11-20

## Mandate and evidence boundary

Before portfolio Phase 9, four source roles were asked to find a strategy
mechanism absent from the existing Coin_Trade registry: public social/research
posts; TradingView indicators and custom Pine; public trading communities; and
GitHub skills/repositories. Four independent review roles then assessed
novelty, causal testability, implementation/data fit, and whether the evidence
justified a single preregistered experiment. Discovery is not evidence of an
edge. All Binance Vision use in this research is restricted to historical,
personal, non-commercial, non-production backtesting.

## Scout outcomes

| Source role | Outcome | Screening decision |
|---|---|---|
| SNS / research | No source supplied a complete, non-overlapping trigger, side, entry, stop, target, and fixed expiry suitable for the frozen M2 definition. Microstructure papers lacked directly testable rules on the available hourly archive. | No candidate; do not convert narrative claims into rules after seeing outcomes. |
| TradingView / custom indicators | Found WavesUnchained Regime Classifier v1.1.3 in the `casoon/pine-scripts` repository. It combines ER, FDI, and Choppiness into Trend/Range/Chaos context labels and `toTrend`; its own comments describe it as context, not a trade trigger. | One custom adaptation admitted: fixed `toTrend` transition plus signal-candle body direction. This is not a replication of a source-published trading strategy. [Pine source](https://github.com/casoon/pine-scripts/blob/main/indicators/trend_strength/regime_classifier/regime_classifier.pine), [repository MIT license](https://github.com/casoon/pine-scripts/blob/main/LICENSE). |
| Public communities | No eligible, fully specified novel setup. Cointegration overlapped previously screened work; exchange-flow discussions lacked a causal, timestamped, fixed trade contract. | No candidate. Keep community claims as leads, not proof. |
| GitHub skills / repositories | No repository or skill constituted a novel trading edge. Funding mean reversion, taker momentum, and open-interest concepts overlapped existing screened families; frameworks and agent skills are tooling, not validated strategies. | No candidate. Do not mistake reusable infrastructure for alpha evidence. |

An additional Regime Transition Engine (RTE) lead was deferred. Its state
machine overlaps prior trend-transition and compression-breakout families;
the source package was marked draft/untested and had a README/code dwell-time
discrepancy. The extra state complexity was not justified before the simpler
Pine adaptation was screened.

## Review-panel disposition

The four roles were Blue Team, Red Team, Data/Methods, and Judge. They
iteratively resolved three material ambiguities before agreeing to the exact
preregistration SHA-256
`a12d3aa5e34ced5efc96cfc3361019c9920c529669bb9fe00be9b8ae09f84b74`:

1. Red Team rejected outcome-dependent non-overlap selection. The final rule
   selects unique timestamps before examining outcomes, groups simultaneous
   symbols, and spaces retained timestamps by the fixed 20-hour maximum horizon.
2. Data/Methods fixed Pine warm-up/fallback and state-update order. Early Pine
   fallback values participate in the score; the state initializes on the
   first contiguous available bar; the first chart bar cannot emit `toTrend`
   because the previous label is `na`.
3. The Judge approved one development-only diagnostic, not a Core candidate.
   The source classifier has no trade trigger; body direction and 1R/2R/20-bar
   barriers are explicitly labeled as a custom hypothesis.

All four reviewers approved that same byte-identical hash. No reviewer vote is
treated as market evidence.

## Ordered research process

1. Search each source family independently and retain only claims with
   identifiable source/version/license and deterministic, causal rules.
2. Compare each lead against the existing strategy registry; reject overlap,
   missing data, and untestable claims before outcome inspection.
3. Have Blue Team specify a single executable hypothesis and Red Team attack
   leakage, selection, fills, dependence, costs, and data availability.
4. Have Data/Methods pin exact formulas, archive inputs, warm-up, censoring,
   funding timing, baseline, and a reproducible test contract. Judge approves
   only the exact preregistration hash.
5. Verify source/license bytes, archive hashes, timestamp/funding audits,
   indicator fixtures, prefix/future-mutation checks, and fill semantics.
6. Run one exposed-history development screen. Reject clear failures without
   parameter fishing. A screen cannot be upgraded into independent OOS.
7. Only a survivor may receive a new, separately preregistered sequential
   walk-forward and untouched-forward test, then sensitivity, regime splits,
   cost stress, block resampling, and independent ledger audit.
8. Only a strategy passing the market-specific frozen gates can be called
   Core. Portfolio Phase 9 is downstream of that gate; it cannot rescue a
   failed single strategy by mixing it with other candidates.

## Result of the admitted candidate

The fixed development screen is recorded in
[`runs/pine_regime_m2_20261120_v4/report.md`](runs/pine_regime_m2_20261120_v4/report.md).
This data was exposed to earlier research, so the result is not independent
OOS. A failure is a rejection of this exact candidate contract on this screen,
not proof that every use of the source indicator is ineffective. No parameters
were adjusted after scoring and no Core was promoted.
