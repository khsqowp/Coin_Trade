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

## Round C — 1m/3m source screen and second four-role debate

Four scouts were assigned separately to public SNS/research, TradingView/Pine,
public communities, and GitHub/skills. They reviewed the local strategy
registry and the 1m/3m data gate. Each reported **zero eligible candidates**.

| Source | Closest lead | Decision |
|---|---|---|
| Public SNS / research | Kim & Hansen, [The Quarter-Hour Effect](https://arxiv.org/html/2607.09426v2): predicts the first 10-second return after 15-minute boundaries across six Binance USD-M symbols; source-reported rolling OOS direction accuracy is 57.12%. | Not an M2 strategy: no TP/SL/expiry or target-first outcome. Paper reports about 0.5 bp gross mean, below its cited taker fee. Requires trade/10-second data absent from the checked 1h input. A second positioning/OI BTC lead lacks one stable rule and point-in-time input availability. |
| TradingView / Pine | Public BTC breakout, EMA/ADX/ATR trend and pivot SuperTrend scripts. | Incomplete source-level execution/expiry/tie/gap semantics, unverified repaint behavior or reuse license, BTC-only or existing Donchian/EMA/RSI families. No eligible rule. |
| Public communities | A Reddit SOL 3m “99% win” claim; a BTC Bollinger breakout claim. | The SOL post omits its signal rules and TP and says it has no stop in the post; the BTC setup overlaps existing breakout work and lacks perp/funding, slippage, and tie/gap semantics. Claims are not independent evidence. |
| GitHub / skills | Upbit strategy toolkit and Hyperliquid paper-bot strategy examples. | Frameworks/examples rather than a new eligible USD-M strategy; spot-only license constraints or overlap with existing RSI/MACD/VWAP/breakout/order-flow/funding families. Exact execution semantics or commit/license checks are incomplete. |

The four scouts were then reassigned to **Blue, Red, Data/Methods, and Judge**.
All four independently concluded: **no current candidate advances to scoring;
wait for a complete, causal rule and required data evidence**. The Judge's
disposition is binding for this round. The debate separated the Quarter-Hour
paper's classification accuracy from target-first M2; neither is interchangeable.
The OI/positioning candidate remains blocked by first-availability provenance,
inconsistent rule versions, and missing local 5m inputs. This screen is bounded,
not evidence that every public strategy has been exhausted.

## Round D — local-data-constrained hypothesis generation

Four independent researchers were asked for at most one source-grounded,
structurally distinct strategy using only the present 1h USD-M OHLCV, mark-price,
and funding inputs. Each returned **zero eligible hypotheses**; none was
preregistered or scored.

- A futures-basis factor has literature support, but local spot OHLCV is absent
  and the family overlaps cross-sectional factor research. See [the futures
  risk-factor study](https://onlinelibrary.wiley.com/doi/10.1002/fut.22425).
- A perpetual-futures return-factor study analyzes basis, momentum, volume,
  size, and volatility, but does not specify a target-first entry/TP/SL/expiry
  strategy; overlapping factors are already represented in the registry. See
  [Anatomy of Cryptocurrency Perpetual Futures Returns](https://www.research.ed.ac.uk/en/publications/anatomy-of-cryptocurrency-perpetual-futures-returns/).
- A variance-decomposition paper reports return-prediction relationships but
  does not provide an M2 trading rule, and faithful variance decomposition at
  local hourly resolution was not established. See [Variance Decomposition
  and Cryptocurrency Return Prediction](https://www.cambridge.org/core/journals/journal-of-financial-and-quantitative-finance/article/variance-decomposition-and-cryptocurrency-return-prediction/9995E58095453CB44A3BC3C9C111969F).
- Quarter-hour order flow and OI/positioning still require finer-grained or
  point-in-time inputs. Mark-versus-perpetual-price is not an independently
  established spot basis; the local mark price embeds index/funding/futures
  components. See [Fundamentals of Perpetual Futures](https://arxiv.org/abs/2212.06888)
  and [Binance mark-price description](https://www.binance.com/en/support/faq/detail/360033525071).

The researchers did not attach new TP/SL/horizons to these papers and label
those additions as source rules. No data was acquired and no candidate was
tested. The result is not proof that no future custom hypothesis can exist; it
means this round found no defensible candidate within the stated data and
novelty constraints.

## Revised research order and current disposition

1. Preserve the frozen M2 gate. Do not invent a target, stop, expiry, timing,
   or fill assumption to complete a source's incomplete strategy.
2. Close the current public-source leads as **ineligible for scoring**. Re-open
   one only if new primary-source evidence resolves its exact rule, license,
   causal timing, symbol scope, and input availability.
3. Do not repeat the OI timestamp audit without independent authoritative
   evidence. The existing archive/REST comparison did not establish historical
   first availability; OI/positioning remains ineligible.
4. The next productive research unit is a new, preregistered hypothesis from a
   demonstrably distinct mechanism, with fixed entry/target/invalidation/expiry,
   signal-time data lineage, universe, costs, tie/gap handling, and one
   predeclared evaluation. First determine if the required fields and temporal
   resolution are present; acquire no new data until a candidate passes this
   gate.
5. Use exposed history only for clearly labeled development diagnostics.
   Keep the untouched forward period sealed from tuning; collect prospective
   signals until the frozen symbol, coverage, full-signal and non-overlap
   sample gates can be assessed. Its required calendar duration cannot be
   estimated before a frozen candidate's signal rate is known.
6. Only a candidate that clears all frozen M2, base/stress economics, breadth,
   sample, and robustness gates can enter further core-validation review.
   Phase 9 remains blocked at validated Core count zero; do not combine rejects.

## Sources and scope limits

This is a bounded source screen, not an exhaustive search of all public
strategies. It records four explicitly separated source classes, two
four-role debates, and one four-researcher constrained hypothesis round.
Source-reported performance has not been treated as fact.
External entries are linked above for attribution; licenses and reuse rights
were not presumed. No external code was installed or executed, no market data
was downloaded in these source rounds, and no new backtest was run.

## Round E — candle-turn and session-return follow-up panel

This follow-up inspected two primary studies and convened four independent
roles (Blue, Red, Data/Methods, Judge). It did not modify the frozen M2 gate.

| Source | New evidence | Panel disposition |
|---|---|---|
| Shanaev et al., [Turn-of-the-candle effect in bitcoin returns](https://researchportal.northumbria.ac.uk/files/121797908/1_s2.0_S2405844023014433_main.pdf), 2023 | The study reports positive BTC returns concentrated at 0/15/30/45 minute marks, and a Bitfinex 2021 timed-holding simulation. Its cost model depends on Bitfinex account-volume fee tiers and venue spreads. | Not a new candidate. Local registry row 23 already records a six-symbol 15-minute-boundary probe with 10/20-minute target-first rates around 47–49% and negative cost-proxy net returns. The paper's portfolio holding simulation does not specify M2 TP/SL/expiry barriers. Re-scoring the same boundary effect would duplicate exposed work. |
| Wu & Pinsky, [Lagged momentum and reversal across daytime and overnight sessions](https://www.mdpi.com/1911-8074/19/9/692), 2026 | Kraken BTC/ETH hourly data, 2016–2025; 12 session boundaries and 25 ordered position combinations. The authors report that bootstrap differences are not significant, Hansen SPA does not reject after 300 combinations, and BTC's training-selected rule underperforms buy-and-hold in the chronological evaluation. Reported 0–2 bp scenarios omit slippage, market impact, borrowing, and funding. | Blue: a 12-hour session lagged-sign reversal could be written as a distinct custom M2 hypothesis, but it would not be a paper replication. Red: reject advancing it now due to selection risk, limited BTC/ETH spot evidence, market mismatch, M2 mismatch, and overlap with local time/reversal families. Data/Methods: hourly USD-M inputs exist, but the interval is exposed and not sealed. Judge: no Core path is supported. Vote: 1 conditional research lead, 3 reject/no-advance. |

The source paper's selected BTC/ETH session rules have no fixed target, stop,
or expiry, so their reported portfolio returns cannot be converted into M2
target-first evidence. Adding ATR barriers would define a new adaptation and
must not be described as replication. The local nearest analogues—prior-hour
reversal (registry row 106), weekday-hour sign majority (row 108), and the
15-minute candle-boundary probe (row 23)—are already exposed; the fixed
weekday-hour M2 result was rejected at 37.36% with negative base/stress net
expectancy. No additional historical scoring is justified by this panel.

### Source-timing check: open interest

The official Binance USDⓈ-M API reference identifies `/futures/data/openInterestHist`
as a period-end timestamped aggregate and limits REST history to the latest
month; it also says periods without trades may be omitted. The already-recorded
2026-11-20 archive/REST comparisons disagree on whether an archive label maps
to same-time or +5-minute REST values, and neither establishes when a value was
first observable. This confirms that the old REST endpoint cannot resolve
older historical vintages; it does not resolve OI causality. Accordingly, this
is not grounds to repeat the completed OI audit or score OI signals. OI remains
ineligible absent independent point-in-time evidence.

### Research order after Round E

1. Do not re-score candle-boundary or session-position-return claims using the
   already exposed hourly/minute results; do not run Phase 9.
2. Continue source discovery only for a mechanism that is structurally distinct
   from the registry and stated with causal input timing plus exact target,
   invalidation, and expiry rules. Incomplete source recipes remain leads, not
   test candidates.
3. Before any new data request or scoring run, require a written single-rule
   preregistration and a four-role advance decision. Keep historical results
   labeled exploratory; Core requires genuinely untouched forward evidence.
4. No qualifying candidate emerged in this round. This bounded result does not
   establish that public strategies have been exhausted or that an edge exists.
