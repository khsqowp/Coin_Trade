# Research decision-value gate — 2026-11-15

Status: evidence review, read-only local-data inventory, and one preregistered targeted MACD/RSI backtest. No parameter grid, public-data collection, account access, purchase, order, or server operation was performed.

## Decision

Do not run another strategy grid on the currently exposed crypto candles or the existing KR/US price cache. Every proposed experiment must name the decision its result can change, the independent evidence it needs, its stop condition, and the result that would invalidate the hypothesis. If it cannot change a decision, do not run it.

The user requires four parallel research roles for future substantive work: two KR/US equity specialists and two crypto signal researchers. Each role must first analyze prior reports and raw evidence available in its assigned scope, distinguish direct inspection from supplied summaries, and return a falsifiable recommendation. Agent count or repeated agreement is not evidence of a trading edge.

The user's latest instruction further rules out tests whose result cannot change a concrete decision. A backtest, indicator sweep, data-collection pilot, or agent-generated strategy list is not progress by itself. Before any such work, require (a) a specific unresolved decision, (b) why the result is not a repeat of a failed or exposed-data test, (c) the minimum evidence needed, (d) frozen pass/fail/inconclusive criteria, and (e) an explicit stop consequence. If any item is missing, do not execute the test or collection.

## Evidence reviewed

### Crypto

- A separately requested 5-minute long rule entered on a closed-bar MACD(12,26) zero-up-cross with RSI(14)>50, next-bar open; four fixed exits were compared with a 2-ATR stop and 20-bar horizon. On the BTC/ETH July 17–October 9, 2026 development window, each exit had 537 trades. Training win rates were 20.3–33.7%, average net result −0.519R to −0.562R, and profit factors 0.343–0.394 after 0.10% round-trip fees. BTC and ETH were both negative for every exit. No candidate met positive mean R and PF>1, so the preregistered rule did not open the later segment. Reject this exact entry/exit family on this exposed window; do not tune it here or treat it as a signal-accuracy validation.
- The fixed BTC 4-hour regime / coin 5-minute sweep→MSS probe is rejected as a candidate: target-first 13.38%, coverage 1.7688%, and mean net R -0.294 under the assumed 0.10% round-trip fee-only scenario on exposed history. Its momentum comparator was structurally forced to match its direction, so it was not an informative baseline. The rule and opened interval must not be tuned or relabeled as validation.
- Earlier momentum, streak, volume, sweep, multi-timeframe, and lead/lag results are exposed development results, frequently low-coverage or negative after assumed costs. None establishes 80% calibrated M4 target-first precision.
- The two crypto-agent reviews found no decision-value in another exposed-history sweep. The MTF audit relied on the prior saved reports; the second review could not access the checkout and reasoned from supplied excerpts. Their shared next gate is a genuinely future cohort with a code/data manifest and independent append-only boundary; neither supplied new performance evidence.
- L2 liquidity recovery after one-sided flow is a distinct research question, not a discovered edge. Existing candle-only data cannot answer it. A two-to-five-minute connection smoke test would establish only basic transport, snapshot/delta synchronization, timestamp capture, and write-path behavior; it cannot establish rare-gap resilience, restart recovery, the 24-hour rollover, event frequency, execution economics, or predictive value.
- Agents found no outcome-independent basis for fixing the event/recovery thresholds or proving that a short smoke changes the next decision. Therefore **do not run the smoke test yet** and do not describe it as a research gate passed. Resume only if an executable event definition and numeric data-quality criteria can be specified from market mechanics before outcomes are observed, and if passing changes a named next action. Otherwise stop this L2 line before collector implementation.

### Korea and United States

A read-only inventory of `/Users/user/CODE/Coin_Trade/.kis-cache-local/*.csv` on 2026-11-15 found 184 files: 92 `KR_` and 92 `US_`. All 184 files have the same six columns: `timestamp, Open, High, Low, Close, Volume`. Observed date spans across files:

- KR earliest available start: 2010-05-28; latest start: 2023-01-05. Earliest file end: 2026-08-28; latest end: 2026-11-12.
- US earliest available start: 2010-01-27; latest start: 2021-07-29. Every US file ended on 2026-11-12.

This inventory establishes the current files and schema only. The schema has no explicit corporate-action, dividend/distribution, listing/delisting, permanent-identifier, or historical-universe-membership fields. File presence does not prove active/inactive coverage or adjusted-price semantics. The prior reports independently document a selected/current cohort and unresolved point-in-time universe and corporate-action provenance. These data cannot decide whether a new equity strategy generalizes to the historical investible universe.

The existing KR tests already rejected/failed their stated evidence gates; the US ETF study did not meet the 20% return aspiration and was selected on exposed data, with maximum drawdown tolerance still undefined. Do not run more strategy permutations on this cache. The next useful step is read-only data provenance/coverage reconciliation. Any provider account, quote, purchase, or contact action requires separate authorization.

The four-agent review did not identify a currently eligible strategy test that would fix these blockers:

- **KR:** The 60-day monthly momentum portfolio's high historical return comes from a selected 64-stock survivor cohort, 144 tested parameter combinations, concentration in a few winning names, and strong 2023/2025/2026 dependence. Removing the top 10 winners reduces the reported 60/5/21 CAGR from 49% to 17%. The fixed KODEX 200 compression-breakout screen recorded 50 trades, base/stress CAGR −0.004%/−0.381%, and a strategy-minus-buy-and-hold block-bootstrap interval crossing zero. Its preregistered 100-trade and positive-stress gates failed. These are development results, not a new independent pass.
- **US:** The fixed six-ETF downside-beta rotation returned 3.21%/2.20% base/stress CAGR at 0.36%/1.22% assumed round-trip costs, below SPY's 13.88%/13.74%. The base downside-beta bootstrap interval crossed zero; the test was already exposed, used a selected ETF cohort, and lacks established point-in-time membership and complete corporate-action/distribution provenance. Its lower drawdown is not sufficient to promote it.
- These findings were supported by the KR agent's read-only report review, the US agent's supplied-evidence review (the agent could not access the checkout), and this local report inspection. They do not establish that equity edges are impossible; they show that rerunning price strategies on the same cache cannot repair universe, rights, or price-adjustment uncertainty.

## Required decision-value contract for any next test

Before a test or collection begins, its one-page preregistration must state:

1. The exact unresolved decision the result can change.
2. Prior findings that motivate the hypothesis and why it is not a renamed failed rule.
3. Exact point-in-time inputs, timestamps, and how completeness/survivorship are established.
4. Frozen entry, invalidation/stop, target, expiry, overlap, and no-signal behavior where trading outcomes are evaluated.
5. Fees, spread, slippage, funding, fill assumptions, and adverse ambiguity resolution.
6. The development/calibration/evaluation boundary and how results remain unopened until the rule is frozen.
7. A minimum information threshold, quantitative pass/fail/inconclusive criteria, and a stop rule.
8. What action follows each possible result, including a result that ends the research line.

No threshold, timeframe, symbol, or model may be chosen because it looked best in the exposed results. Missing evidence must produce `BLOCKED` or `INCONCLUSIVE`, not a relaxed threshold or another sweep.

## Immediate next actions

1. **Crypto:** no more exposed-OHLCV strategy tests. The targeted MACD/RSI trial also failed its positive-expectancy selection gate. Keep the L2-resilience idea as an unvalidated question only. Do not collect until an outcome-independent event definition, collection decision, and acceptance criteria exist; if these cannot be frozen without tuning to outcomes, abandon this research line rather than inventing thresholds.
2. **KR/US:** reconcile the local files against provider provenance and the required historical universe/corporate-action fields. If local assets do not contain them, stop performance research until an authorized, suitable dataset is available. Do not buy data, create an account, or accept terms without separate user authorization.
3. **All agents:** deliver evidence-linked analysis and a recommendation before any execution. Agents must say which files/data they actually inspected and must not claim access they lacked. Recommendations must explicitly state the decision value and why the proposed work is not a renamed repetition; “try more combinations” is not an acceptable recommendation.

These actions do not claim that 80% crypto accuracy or 20% equity CAGR is attainable. They prevent more compute and reports from being mistaken for progress.
