# Phase 8 external source rounds and candidate panel

Date: 2026-11-20. Scope: discover strategy hypotheses not already in the
Coin_Trade registry, then decide whether any can enter one frozen exploratory
M2 test. No strategy is approved as Core by this record. The crypto gate and
data boundaries in `docs/chart_predictor/SPEC.md` remain unchanged.

## Round A — four source scouts

| Source | Candidate / finding | Decision |
|---|---|---|
| Public SNS / authored research | SimpleMarkets' BTC USD-M 1h funding squeeze: realized funding below zero and RSI(14) crosses above 30; source describes a 2×ATR trailing stop. The source reports BTC-only results and later adverse-regime weakness. | Conditional lead only. The source does not specify a fixed TP or maximum holding period, so it cannot be scored under frozen target-first M2 without changing the strategy. Its metrics are unverified external claims. |
| TradingView / Pine | Synthetic implied APR, liquidation-range/OI visualization, and a derivatives dashboard were reviewed. | No eligible candidate: incomplete execution rules, extra inputs unavailable locally, or source/version/license ambiguity. |
| Public communities | Funding carry and funding-fade posts were reviewed. | No eligible candidate: rules incomplete or structurally overlap funding-tail / reversal work already in the registry. Community performance statements were not treated as independent evidence. |
| GitHub strategy / skills | Funding z-score and funding-arbitrage repositories/skills were reviewed. | No eligible candidate: missing fixed thresholds/exits or required inputs, no verified license, or overlap with prior funding-tail work. Frameworks and skills were not mistaken for strategies. |

### Four-role debate on the only conditional lead

The four agents were reassigned as Blue, Red, Data/Methods, and Judge. All four
voted **REJECT for an M2 test in the submitted form**. This is a testability
and promotion-gate rejection, not proof that the economic idea has no edge.

- No fixed profit target or expiry exists in the cited rule. M2 requires a
  target boundary and an invalidation boundary; substituting the trailing stop
  for a target or inventing a TP changes the hypothesis.
- The lead is BTC-only. The source reports 122 trades across two four-year
  windows; these are external claims, not a locally verified ledger, and do
  not establish the local 20-symbol and independent-sample gates.
- Historical local periods are already exposed to prior research. The newer
  period is too short to establish the required breadth and non-overlap sample.
- Funding timestamp availability at the signal time and the trailing-stop
  intrabar sequence are not fully resolved by the source description.

The source itself reports that the 1h BTC form passed two earlier windows, but
a later 46-trade window returned +0.9% and failed its strip-best check; its
reported latest-12-month gain was +8.5%. These are source-reported values, not
independent evidence. See the [source research log](https://simplemarkets.io/strategies/research-log/low-timeframe-crypto),
which specifies the funding-squeeze family and later-window qualification. No
code, source content, or backtest result was copied into Coin_Trade.

## Round B — focused perp/spot basis-convergence source screen

The final judge from Round A nominated basis convergence as a structurally
distinct source family. A second four-source scan found no candidate that met
the frozen test contract.

| Source | Lead reviewed | Why it is ineligible |
|---|---|---|
| Public SNS / authored research | [Presto Research, USDⓈ-M arbitrage evaluation](https://www.prestolabs.io/research/evaluation-of-arbitrage-strategies-on-usd-market), 2024-05-27: enter spot-long/perp-short at basis ≥+0.5%; exit near −0.1%. | Only BTC/ETH are described; no stop, maximum hold, or complete execution timing. No reuse license was established. |
| TradingView / Pine | [Crypto Spot/Futures Dominance indicator](https://www.tradingview.com/script/Q12JKQjL-Crypto-Spot-Futures-Dominance-Indicator-with-Alerts/). | Visualizes VWAP premium/discount but does not define deterministic entry, target, stop, or expiry. Requires spot input; implementation's repaint behavior was not verified. |
| Public communities | Reddit carry discussions and a [public basis research report](https://github.com/BrandonKKY/stat-arb-research/blob/main/RESEARCH_REPORT.md) describing thresholds. | Funding filter remains underspecified; the proposed trade is a two-leg delta-neutral spread and does not map to directional target-first M2. Public performance claims are not validation. |
| GitHub strategy / skills | [delta-basis-trading](https://github.com/mariamlulu/delta-basis-trading) proposes absolute z-score entry ≥2, exit ≤0.5, stop ≥4, and default 336h hold; Hummingbot spot-perpetual arbitrage source was also reviewed. | Exact candidate commit/license and broad eligible universe were not verified for the first; Hummingbot uses executable quote/profit thresholds but has no fixed stop/time exit. Neither establishes ≥20 symbols or local M2 eligibility. |

### Data gate

The checked local input root `/private/tmp/cointrade-50_50-data` contains
`klines_1h`, `mark_price_1h`, `mark_price_1h_daily`, and `funding`. It has no
spot OHLCV directory. Mark price is not spot price. A basis series cannot be
constructed from the present local inputs. Hourly highs/lows from spot and
perpetual contracts also cannot be paired into synchronized intrabar basis
extremes; doing so would invent simultaneous prices.

Basis convergence is a two-leg spread strategy. It requires a fixed spread
profit/stop/time outcome, synchronized spot/perp price evidence, funding cash
flows, and a two-leg cost model. Converting the spread close into directional
M2 by inventing a price target would change the estimand. Therefore no basis
candidate was preregistered or scored.

## Research order and current disposition

1. Keep the M2 gate frozen; do not invent missing targets, stops, horizons, or
   funding filters to make source material testable.
2. Next inspect the point-in-time availability of historical open-interest
   (OI) metrics before proposing an OI-shock/event-range strategy. A valid
   label timestamp alone is insufficient: field publication/availability time,
   archive provenance, gaps, and timestamp semantics must also be established.
3. If OI availability is not provable, do not backtest an OI strategy using
   that series. Move to another source/data family rather than substitute an
   OHLCV proxy and call it OI.
4. Any next eligible directional strategy needs exact causal entry, target,
   invalidation, expiry, tie/gap rules, costs, universe, and data cutoff frozen
   before scoring. A candidate that passes exploratory gates still requires
   robust validation and untouched forward evidence before Core status.
5. Phase 9 remains blocked: the validated standalone Core strategy count is
   zero. No combination of rejected candidates is authorized as a portfolio.

## Sources and scope limits

This is a bounded source screen, not an exhaustive search of all public
strategies. It records four explicitly separated source classes and the
review decisions. Source-reported performance has not been treated as fact.
External entries are linked above for attribution; licenses and reuse rights
were not presumed. No external code was installed or executed, no market data
was downloaded in these source rounds, and no new backtest was run.
