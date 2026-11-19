# Crypto signal data and divergence audit — 2026-11-20

## Objective and decision

Optimize after-cost compounded account wealth across market regimes. Crypto target-first M2 >=80% remains a separate signal-quality gate. This audit does not claim that any strategy is profitable, and it did not run a new backtest or acquire data.

Two decisions follow from the evidence:

1. **The existing RSI-divergence setup is already a failed development candidate; do not repeat its parameter grid.** Its actual Stage C report has been inspected, not merely inferred from the round headline.
2. **Tardis is the strongest identified route to historically replayable Binance futures liquidation/OI inputs, but it is a paid data option, not an approved purchase.** Public documentation supports multi-regime research and describes personal trading as a permitted use, but sampled liquidation input, point-in-time universe, API/data plan terms, and the specific personal Telegram signal path still require a pre-purchase check.

## Existing RSI-divergence result — exact report audit

The source report is the completed Stage C JSON `report_3d0e945841e734aa.json` in the existing main checkout's ignored `chart_predictor/data/setups` output. It corresponds to P5 in `docs/chart_predictor/rounds.md`; this is a read-only reinspection of a prior result, not fresh validation.

- **Rules:** successive confirmed swing lows with lower price and higher RSI(14) emit long; successive confirmed swing highs with higher price and lower RSI emit short. The pivot is emitted at its confirmation index with lag 3, not backdated to the pivot bar. Entry is next timeframe open. Exits use fixed 2R/3R target, the signal's swing-based stop and maximum 12 bars.
- **Evaluation:** 50 symbols, 1m/5m/30m/60m, base and trailing-seven-day volatility-top-third filters, 2R/3R, five chronological folds on the dev split dated 2026-07-17 through 2026-10-09. The report records 0.05% fee per side. This brief test window is not multi-regime or untouched OOS evidence.
- **Breadth:** 32 RSI-divergence cells; every cell had at least 469 signals. Zero cells reached M2 80%. M2 ranged 2.70%–16.84%; the best was long/60m/2R/base, N=1,752, M2=16.84%, Wilson 95% CI 15.16%–18.66%, stop-first 40.24%, timeout 42.92%.
- **Wealth warning:** the largest summed per-signal net return was +154.71% at long/60m/3R/volatility-top-third, N=469, but M2 was only 6.61%, expectancy was −0.0697R, and reported drawdown was 77.33%. This summed trade-return metric is not portfolio CAGR or compounded NAV. The best-M2 cell also had −0.0622R expectancy and 90.71% reported drawdown. All 32 cells had negative expectancy_R, drawdown >=76.64%, and REJECT evaluator decisions; none passed Holm adjustment.
- **Implication:** no M2/wealth edge is established. Changing only R, timeframe, or the same pivot/RSI thresholds and retrying the already viewed development interval would inflate selection bias. A genuinely different, pre-registered mechanism or unseen source-period is required.

The pivot implementation is causal at the confirmation index: `chart_predictor/indicators.py::confirmed_swings` places each pivot at `confirm` and uses bars through that index. The P5 candidate cannot be described as a profitable divergence signal based on the high total-return column.

## Historical liquidation data candidates

### Tardis — best technical fit, purchase not approved

- Its Binance USD-M historical docs state all instrument data are available since 2019-11-17, OI (`derivative_ticker`) since 2020-05-13, and `forceOrder` liquidation messages since 2020-01-07. The force-order feed is Binance's per-symbol latest-liquidation snapshot within each 1,000 ms window, not a complete event tape. Data before 2020-05-14 had some missing-data/latency issues. Thus the usable historical intersection is not earlier than OI availability, and a test must model liquidation-feed sampling as an inherent limitation. [Binance USD-M coverage](https://docs.tardis.dev/historical-data-details/binance-futures)
- Normalized CSV schemas carry both exchange `timestamp` and `local_timestamp`; the latter is the collector's arrival timestamp, useful for causal replay but not identical to the user's production-feed receipt time. Use event-time and arrival-time separately and stress execution/processing delay. [CSV time/schema details](https://docs.tardis.dev/downloadable-csv-files/data-types)
- Tardis's current terms define permitted use to include a customer's internal research and personal trading; only Customer Users may access Data/Manipulated Data, and derived data sharing has explicit limits. A private one-user alert may fit, but keep any Telegram room private and verify the applicable exchange/provider plan restrictions before relying on this for personal manual signals. Do not expose alerts or data to third parties. [Terms, permitted use and redistribution limits](https://docs.tardis.dev/legal/terms-of-service)
- For the Solo subscription and Perpetuals data plan, the public pricing page currently displays $700/month. Yearly billing includes four years of history; monthly billing includes four months. Business yearly includes all history. The four-year range at current date is useful for several recent regimes but omits earlier market cycles; it is not automatically sufficient. No account, trial, contact, purchase, or data download was made. [Pricing and plan history](https://tardis.dev/), [billing/history rules](https://docs.tardis.dev/faq/billing-and-subscriptions)
- Instrument metadata offers listing/expiry/availability fields, but some changes are best-effort and Tardis-side availability is not guaranteed to equal exchange listing or data start. A point-in-time eligible contract universe remains a validation gate. [Instrument metadata caveats](https://docs.tardis.dev/api/instruments-metadata-api)

### CoinGlass — cheaper, but not sufficient for fast event testing

- Pair liquidation history returns USD long/short liquidation sums by interval start time, not individual event-level timestamps. Plans offer 4h+ (Hobbyist), 30m+ (Startup), or 1m+ (Standard and above). [Liquidation-history schema and intervals](https://docs.coinglass.com/reference/liquidation-history)
- The published history caps are 1m=6 days Standard / 12 days Professional, 5m=30/60 days, 30m=180/360 days, 1h=360/720 days, and 1d=full history for all plans. Therefore, 1m–5m liquidation pressure cannot be verified over multi-year regimes on these plans; daily liquidation sums are too coarse for the requested short-horizon setup. Historical candles may be backfilled and the provider says no uniform finalization delay exists. [Official history-range and revision notes](https://docs.coinglass.com/reference/intervals)
- Published API price is $35/month Hobbyist, $95 Startup, $379 Standard, and $879 Professional; usage scope is personal for the first two plans and commercial for the latter plans. However, the feature/history limits above make this a weak candidate for the event-level, short-timeframe objective. [Official plans and usage scope](https://docs.coinglass.com/reference/plans-and-permissions)

### CoinAPI and Kaiko — not yet eligibility-cleared

Official CoinAPI metadata lists Binance futures liquidation/OI metric IDs, but the provider explicitly warns that a listed metric does not guarantee support for every symbol or that it is currently active. Historical metric response periods are configurable but do not by themselves establish when the historical observation first became available to a user. Require symbol-specific coverage and source-time/receipt-time evidence before any purchase or test. [Metric catalog and caveat](https://www.coinapi.io/products/market-data-api/docs/metadata-tables/metric_id), [historical metric endpoint](https://www.coinapi.io/products/market-data-api/docs/rest-api/metrics-v1/metrics/symbol/history/get)

Kaiko has public documentation of liquidation/OI data, but this audit did not independently establish the needed Binance USD-M symbol coverage, historical receipt-time fields, or a price applicable to the requested paired fields. It remains a diligence candidate, not a backtest-ready source.

## Required gates before any new signal test

1. Confirm available fields, history overlap, per-symbol data gaps and sampling/completeness on provider documentation or an authorized sample before selecting a candidate.
2. Freeze use rights for private personal manual signals, applicable exchange/data licenses, retention and service-provider routing. No purchase or account creation without explicit approval.
3. Verify a point-in-time futures contract universe and delisted instruments. Provider's current symbols or current survivor set cannot define the historical universe.
4. Use event time and first-received time separately; prohibit any event that arrived after the signal anchor. Apply latency, spread, fee, slippage, funding and gap stress.
5. Register the exhaustion-reversal and cascade-continuation hypotheses as one multiple-testing family before opening outcomes. Do not choose the direction after inspecting the same holdout.
6. First compare after-cost compounded NAV against cash and appropriate futures benchmarks across bull/bear/sideways regimes. Report leverage, exposure, concurrent positions, turnover and drawdown. Report target-first M2 and its confidence interval separately.

## Work boundary

No new backtest, public sample download, API/account use, provider contact, purchase, or strategy selection occurred in this audit. The only performance numbers above are read-only extraction from the already-completed P5 Stage C report. This audit is not a forward/manual signal and does not claim the strategy objective has been achieved.
