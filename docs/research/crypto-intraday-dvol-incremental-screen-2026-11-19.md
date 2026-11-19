# Crypto intraday DVOL incremental-information screen — 2026-11-19

## Decision

**Candidate for preregistration review only; no data access or performance test is approved by this screen.** The only potentially distinct hypothesis is that completed intraday BTC/ETH implied-volatility changes add predictive information beyond the already-tested daily DVOL level/change features. Reusing DVOL under a finer candle label is not, by itself, a new edge.

The project objective remains maximizing net compounded returns. Target-first accuracy is a required signal-quality gate, not a substitute for positive cost-adjusted expectancy or return evaluation.

## Scope and evidence

- Two independent crypto reviews examined the narrow candidate against the repository's existing DVOL and M2/M4 research. Neither queried a market-data API, downloaded data, opened untracked M4 panels, calculated outcomes, or changed files.
- The existing `docs/research/map_api.md` documents **daily** Deribit DVOL for BTC and ETH from 2021-03-24 through 2026-10-13 (2,032 rows), with daily level/change regime flags in a 7,531-case strategy map. This is prior exposure; it cannot serve as untouched OOS.
- Deribit's official `public/get_volatility_index_data` documentation lists resolutions of 1 second, 60 seconds, 3,600 seconds, 43,200 seconds, and 1 day; it returns timestamped OHLC index candles for supported currencies. Documentation of an endpoint does not prove historical completeness, per-resolution start dates, missingness, response limits, or licensing for this particular experiment.
- The official Deribit terms page reviewed states that Market Data and Derived Data are for personal use and restricts non-personal aggregation, resale, publication, forwarding, or processing without approval. Current applicability and the exact boundary for private Mac/Linux research and any later Telegram output remain to be verified before collection or signal distribution.

## Narrow falsifiable hypothesis

With the existing signal, entry, target, stop, expiry, daily-DVOL controls, and cost assumptions held fixed, adding one prespecified feature—BTC and ETH **five-minute log changes computed only from the last fully completed 60-second DVOL candles**—improves forward out-of-sample target-first prediction and net expectancy for a frozen universe of at least 20 Binance USDⓈ-M COIN-underlying symbols, at both 10-minute and 20-minute horizons.

This is a conditional incremental-feature hypothesis, not a standalone directional strategy. A DVOL impulse has no inherent long/short sign. Direction and barrier rules must be fixed independently before any outcome is opened. Do not search over alternate resolutions, lookbacks, thresholds, symbol subsets, horizons, or DVOL transformations and then report only the best result.

## Gates before any data call or outcome test

1. **Novelty/preregistration:** Red-team the precise feature against the existing daily-DVOL map and other tested volatility/cross-asset families. Register one fixed 60-second resolution, one five-minute feature window, both 10/20-minute claims, the existing matched baselines, entry/target/stop/tie rules, and all trial-family corrections. If this is only a frequency re-expression or the underlying directional rule is not independently justified, reject it.
2. **Rights and source integrity:** Confirm current Deribit terms permit the private research, storage, derivative calculations, and intended local/server copies. Confirm the 60-second historical series' actual dates, fields, continuation behavior, gaps, duplicates, timestamps, and update/availability delay. Never infer data availability from the endpoint schema alone.
3. **Untouched OOS and storage:** Keep all previously exposed DVOL and price periods in development only. Require a chronological future panel, frozen eligible-symbol set, immutable input hashes, verified archive destination, and capped storage before acquisition. `/Volumes/HDD2TB/Trade` was absent in the current check; do not start a long capture or download into an unbounded local queue.
4. **Causal alignment:** At every forecast anchor, use only completed DVOL candles available by that anchor; never use an unfinished candle's final OHLC. Apply missing-data handling fixed in advance; do not interpolate future values. Preserve event-time and local receipt-time distinctions where available.
5. **Acceptance and objective:** Keep the current user-confirmed M2 contract: all issued signals in the precision denominator, target before stop within deadline, timeouts are not successes, and deadline-direction accuracy reported separately. Require M2 point estimate ≥80%, an outcome-blind non-overlapping OOS subset N≥200 across ≥20 symbols, coverage ≥10%, dependence/multiple-testing-adjusted comparison against both matched baselines, and positive net expectancy after costs. Report compounded net returns separately; M2 alone cannot establish return maximization.

## Frozen current-state interpretation

The current `docs/chart_predictor/SPEC.md` states M2 target-first ≥80% at §5 and §12; §14.1 also records replacement of a legacy 75% alert threshold with 80%. Some older research reports retain historical 75% gate wording and must not be mistaken for the current criterion. M4/selective-calibration and additional coverage/baseline gates are extra protocol conditions; they do not replace the user's all-issued M2 definition or the return objective.

No strategy result, accuracy estimate, return, OOS sample, or acceptance pass was produced in this screen. No backtest was run. The next admissible artifact is a preregistration and independent red-team decision, not a downloaded panel or tuned result.

## Sources

- Existing DVOL experiment: `docs/research/map_api.md`.
- Frozen target-first definition and acceptance gates: `docs/chart_predictor/SPEC.md` §§5, 12, 14.1.
- [Deribit official volatility-index history API](https://docs.deribit.com/api-reference/market-data/public-get_volatility_index_data).
- [Deribit Exchange Membership Terms](https://support.deribit.com/hc/en-us/articles/25944532191645-Deribit-Exchange-Membership-Terms-Deribit-FZE).
