# Crypto L2 liquidity-resilience research gate — 2026-11-15

Status: evidence synthesis and feasibility gate only. No new strategy backtest, live market-data collection, account access, purchase, or order was performed. The goal is to choose a research question that is materially different from the rejected OHLCV indicator sweeps without misrepresenting a literature signal as a validated trading edge.

## Decision

Do not run another historical OHLCV strategy grid. The only materially distinct crypto direction worth preparing is **state-conditioned liquidity resilience after a one-sided trade-flow shock**: with the completed BTC higher-timeframe regime as context, test whether the depleted-side L2 book recovers or remains impaired, and whether that state adds target-first price information beyond price-only and signed-trade baselines.

This is a research hypothesis, not a strategy recommendation or a claim of 80% accuracy. It is not yet preregisterable: the existing local OHLCV cache has neither synchronized L2 book changes nor historical liquidation-level data, and the exact event, risk, execution, and confidence rules have not been frozen. Do not score a strategy until a new prospective dataset has been captured and the development/calibration boundary is fixed.

## Why this is not another indicator permutation

Prior project trials already covered candle momentum, trend and mean-reversion indicators, volume/taker-flow signals, BTC lead/alt lag, multi-timeframe candle filters, and the corrected macro-to-micro sweep/MSS candidate. The latest fixed sweep/MSS candidate was rejected on exposed history: 23,823 scored events, 13.38% target-first, 1.7688% coverage, and mean net R -0.294 at an assumed 0.10% round-trip fee before spread, slippage, funding, depth, and actual-fill effects. Its momentum comparator was structurally forced to the same direction. This period cannot serve as validation and the rejected candidate must not be tuned or forwarded.

The new question is about **liquidity-state transitions and recovery**, not another price-only trigger or raw taker-imbalance threshold. The independent agent synthesis likewise found no basis for a new price-only historical candidate and identified liquidity recovery after one-sided forced flow as the one genuinely different mechanism, conditional on new data.

## Evidence reviewed

1. Albers et al., *Fragmentation, Price Formation and Cross-Impact in Bitcoin Markets*, uses synchronized order-book/trade information across venues and reports that linear models explain 10–37% of 500 ms future-return variation depending on target market; its taker PnL depends materially on fee regimes, while maker viability is checked in a live experiment. This supports measuring the order book and execution friction, not expecting that the result transfers to one Binance account or a 10–100 minute target-first task. [Open-access article](https://doi.org/10.1080/1350486X.2022.2080083)

2. Jeon, *When Does Order Flow Matter? State-Dependent L2 Liquidity-State Transitions in Crypto Futures* (2026 preprint), reports on Binance BTC/ETH futures that a coarse pre-event L2 state is predictive of post-event liquidity state; continuous-feature logits do not improve on that baseline, and a nonlinear L2-shape layer adds value. Order-flow adds only a small increment and is ETH-dominant; the BTC increment is not established. Its label is a **liquidity state**, not a directional trade outcome. Treat this as a useful experimental design reference, not independent validation of our target. [arXiv preprint](https://arxiv.org/abs/2607.09230)

3. Garcia Seuma, *Where does the criticality live?* (2026 preprint), studies seven BTC perpetual liquidation cascades and finds no event-invariant early-warning signature. Its text says Binance per-event `liquidationSnapshot` archives are discontinued and unavailable for those dates, so intraday liquidation state is proxied with open interest and aggressor flow. This argues against building a signal around historical liquidation counts or assuming one crash precursor generalizes. [arXiv preprint](https://arxiv.org/abs/2607.27070)

4. Binance's current USDⓈ-M documentation supports public WebSocket market streams and describes the depth-delta/snapshot synchronization rules. The local book must be rebuilt from a REST snapshot plus buffered updates; sequence continuity must be checked (`pu` must match the preceding `u`), otherwise the book must be reinitialized. The stream connection is forcibly limited to 24 hours, with keepalive and message/stream limits, so reconnect and gap recovery are part of data validity. [WebSocket connection and limits](https://developers.binance.com/en/docs/products/derivatives-trading-usds-futures/websocket-market-streams/Connect), [local order-book synchronization](https://developers.binance.com/en/docs/products/derivatives-trading-usds-futures/websocket-market-streams/How-to-manage-a-local-order-book-correctly)

5. Binance's liquidation stream is a lossy snapshot: at most the latest liquidation order for each symbol in a 1,000 ms interval is pushed; no event is sent in an interval without a liquidation. It cannot be treated as a complete liquidation count or full notional series. Use it only as a marked, incomplete context field, never as ground truth. [Official all-market liquidation stream documentation](https://developers.binance.info/en/docs/catalog/core-trading-derivatives-trading-coin-m-futures/api/ws-streams)

## Candidate research question

> Given a pre-existing BTC completed-4h regime, does an observable one-sided trade-flow/depth shock followed by a measured bid/ask depth recovery state add out-of-sample information about a coin's 5-minute-entry, 50-minute target-first outcome beyond (a) BTC-regime plus price-only features and (b) the same features plus signed trade flow alone?

This staged comparison attributes any gain to the order-book state and recovery layer rather than to adding more features indiscriminately. A higher-timeframe regime is fixed before micro features are evaluated. A positive liquidity-state classification result alone is insufficient; the end task is an actionable long/short forecast with next executable entry, explicit stop, target, expiry, calibrated confidence, and costs.

## Independent design review and why no more tests run now

Four independent reviews were asked to assess the evidence and the next decision, not to generate additional strategy permutations. They converged on three distinct conclusions:

1. **Equities are data-gated, not strategy-grid-gated.** The current KR/US cache has no verified file-level lineage, point-in-time active/inactive universe, or complete corporate-action/total-return treatment. A new equity strategy backtest on it would repeat the same survivorship and adjustment ambiguity, so the next useful work is provenance and licensing eligibility, not more parameter search.
2. **The rejected crypto OHLCV candidate is closed.** The sweep/MSS result is exposed development evidence and failed badly after costs. Re-tuning it, changing its timeframe, or expanding indicator grids would spend compute without changing the decision.
3. **L2 may justify a different experiment, but not a result claim.** Existing source history cannot answer the L2 question. The MTF target-first scorer is useful for barrier semantics, but it is not yet the prospective macro-to-micro signal ledger, and the shadow forecast log lacks entry/stop/target first-touch outcomes. These are integration/data-design gaps, not a reason to rerun old candles.

The review also identified protocol defects that must be closed before any outcome-bearing study: (a) overlapping 50–100 minute labels make raw event counts and ordinary binomial intervals overconfident; selected events must be non-overlapping and uncertainty clustered by symbol and UTC day, with purge/embargo around temporal boundaries; (b) a candle's next open is not automatically an executable fill, so decision, submission, first eligible quote/fill, fees, spread, slippage, funding, gaps, and same-bar stop-first treatment must be timestamped and frozen; (c) a model threshold selected on the final period invalidates that period, so model fitting, calibration, threshold selection, and one untouched forward evaluation need separate chronological slices; (d) “200 events / 20 symbols / 10% coverage / 80% precision” is not enough unless denominator eligibility, missing forecasts, abstentions, and the clustered lower-bound procedure are defined before collection.

Consequently, there is **no approved performance test or collection run in this round**. The next authorized research artifact is a preregistration/data-eligibility specification resolving the four defects above and tying each gate to a concrete decision: stop, repair collector, extend development capture, or open exactly one forward evaluation. A bounded collector pilot is permissible only after its sequence-integrity, restart/reconnect, disk-rate, and data-loss pass/fail rules are numeric and its result would change whether a longer capture is started. A pilot cannot count as strategy validation. Do not launch merely to produce activity or a new metric.

The provisional modeling comparison remains deliberately small: one frozen BTC completed-4h regime; then price-only, price plus signed trades, and price plus signed trades plus sequence-valid L2 recovery. Keep 5m decision anchors and 50-minute primary expiry for this question. Continuous L2 features at deterministic anchors are preferred over hand-picked shock thresholds unless the event rule is justified independently of labels. This is still a design proposal, not a frozen preregistration: exact feature windows, instrument cohort, execution/stop/target geometry, costs, split dates, missing-data handling, calibration, and inference remain open and must be resolved before collecting labeled outcomes.

The 80% objective is a target, not evidence and not a promise. If the data-quality gate, independent sample, coverage, cost-adjusted expectancy, or predeclared uncertainty criterion fails, record `REJECT` or `INCONCLUSIVE`; do not respond by changing horizons, thresholds, symbols, or outcome definitions on the opened evaluation set.

The above is a **research question**, not a complete preregistration. Before the first outcome labels are reviewed, freeze:

- one primary trading timeframe and its 10–20-bar outcome horizon (start with 5m entries and 50-minute horizon; do not search other timeframes in this round);
- point-in-time symbol eligibility and any dynamic liquidity ranking;
- exact completed-BTC regime rule and the timestamp at which each higher-timeframe state becomes available;
- order-book event and recovery definitions, including price-distance/depth normalization, shock threshold, recovery window, and gap handling;
- exact next executable entry, stop, target/R multiple, same-bar tie, timeout, overlap suppression, and no-trade behavior;
- account-specific taker fees and conservative spread/slippage/funding assumptions, with a separate stress case;
- development, calibration, and future evaluation boundaries; immutable rule/model/code identifiers; and append-only signal/outcome access logs.

Thresholds may be estimated only in the declared development segment. They must be frozen before any later evaluation labels are opened. The already exposed candle history cannot provide the forward labels for this test.

## Data feasibility and capture gates

### Gate 0 — no-performance data pilot

Before evaluating outcomes, demonstrate a short, bounded collector dry run on a small set of liquid symbols that:

1. captures synchronized trade flow and depth deltas with exchange event time, local receive time, symbol, and update IDs;
2. initializes each local order book from a depth snapshot and detects/resets on sequence gaps;
3. handles disconnects, the documented 24-hour forced reconnect, clock drift, duplicate/reordered messages, process restarts, and partially written output;
4. reports stream coverage, update gaps, reconnect count, bytes/hour, and CPU/disk rate without generating or scoring trade signals;
5. stores all raw/derived records append-only with a manifest and hash; never deletes or overwrites originals during the pilot.

This pilot answers a data-quality/storage question, not whether a strategy works. No 80% claim can be made from it.

### Gate 1 — freeze and collect prospective development data

If Gate 0 passes, freeze one point-in-time symbol cohort and collect the necessary L2/trade data prospectively. Do not treat the public liquidation stream as complete. Keep raw stream data separate from derived features and scores; each signal must retain exact event sequence, timestamps, feature-version hash, price source, and data-gap status. Only use complete, sequence-valid intervals.

### Gate 2 — one frozen forward evaluation

After development and calibration, lock the trigger, confidence selection, trade geometry, and comparator models. Evaluate once on subsequent unseen data. The existing project gate remains: at least 200 non-overlapping selected events across at least 20 symbols, at least 10% coverage, M4 target-first precision at least 80%, a Wilson lower bound above matched baselines, and positive cost-adjusted expected R. If the sample is short, label the result `INCONCLUSIVE`; do not extend or tune against the same opened period.

## Immediate prohibitions and interpretation

- No further sweep/MSS, EMA, RSI, Heikin-Ashi, volume, or taker-imbalance grid on the exposed candle cache.
- No use of same-event comparator labels that are mathematically forced to equal the candidate direction.
- No reporting a liquidity-state label, AUC, or chart forecast direction score as target-first trade accuracy.
- No assumption that the 2026 preprints establish a stable edge; their reported targets and data conditions differ from this project's trading objective.
- No Oracle/server deployment, live order routing, paid data, or API-key use is authorized by this research gate.

## Independent review

Four independent read-only research agents completed separate evidence reviews (crypto evidence synthesis, an evidence-supplied crypto hypothesis critique, Korea equities, and US equities) without running tests, backtests, edits, network access, or secret reads. The first Pine/crypto reviewer could not access its mounted repository; that failed review was discarded and replaced with an independent crypto analyst who received the fixed findings as prompt evidence rather than claiming direct repository inspection. The completed reviews concluded:

- Crypto: current exposed data do not justify another historical performance test; a genuinely prospective frozen evaluation is the next valid test.
- Korea: current survivor-only cache cannot support a defensible multi-stock strategy result; verify complete active/inactive histories, date-valid eligibility, identifiers, corporate actions/distributions, delisting outcomes, and rights first.
- United States: current S&P survivor list and selected ETF panel cannot support independent strategy evidence; validate a licensed active/inactive stock+ETF dataset first. Maximum acceptable portfolio drawdown is still unspecified.

No strategy result was generated in this round. The useful outcome is narrowing the crypto next hypothesis and identifying its data-quality gate; KR/US strategy performance loops remain blocked by specific data/readiness gates, not by a lack of parameter combinations.
