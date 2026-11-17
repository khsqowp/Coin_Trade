# Crypto divergence study: preregistration and mandatory robustness gates

Status: preregistered design and tested validation primitives, including a long/short OHLC path resolver; the market-data divergence backtest has not yet run, so no strategy result is available.

## Decision rule

This is a research-only long/short study on historical crypto perpetual candles. No exchange order/API calls are permitted. A candidate is rejected if it fails any of the three mandatory robustness tests below, or the repository's frozen signal-quality contract. A promising in-sample score is never sufficient for promotion.

The frozen primary signal metric is M2 target-first precision, calculated over every emitted OOS signal including overlaps, with target-first defined as a target touched before stop/invalidation and within the registered horizon. Timeout and same-path target/stop ties are failures. Report deadline direction accuracy separately. In addition, require an outcome-blind non-overlap sample of at least 200 signals and 20 distinct symbols for eligibility. Report coverage, fee/slippage-adjusted expectancy, uncertainty, and same-anchor baselines; do not describe M2 as profitability.

## Hypothesis and signal timing

Hypothesis: a regular bullish divergence (lower confirmed price low and higher oscillator value at the two pivot anchors) during a bullish closed-4h macro regime identifies an intraday pullback resumption; a regular bearish divergence (higher confirmed price high and lower oscillator value) during a bearish closed-4h macro regime identifies a rally resumption.

Primary oscillator is RSI(14); MACD histogram (12,26,9) is a separately reported, pre-registered replication family, not a substitute selected after seeing results. The 4h regime is close above EMA(50) and EMA(50)>EMA(200) for longs, mirrored for shorts. A pivot with lag L is usable only at its confirmation candle; the oscillator is sampled at the pivot anchor, not the confirmation bar. Signal features use closed candles only. Earliest fill is the next executable bar open. No signal is backdated to its pivot anchor.

## Frozen candidate grid

- Timeframes: 1m, 5m, 15m, 30m, 60m; outcome horizons: 10 and 20 native bars.
- Pivot confirmation lag L: 2, 3, 4 bars.
- Entry: next-bar open; or stop-entry only after signal-bar high (long) / low (short) breaks, valid for 3 bars, otherwise expire.
- Stop: latest confirmed divergence pivot plus 0 or 0.25 ATR(14) adverse buffer, measured at signal time.
- Target: 1.0R, 1.5R, 2.0R, or 3.0R; time exit at registered horizon. A newly confirmed opposite divergence is reported as a diagnostic exit only and is not tuned into the primary grid.
- Fees: repository contract's round-trip 0.10%; add a separately reported 2x-slippage stress using adverse execution on entry and exit. Use minute-path stop-first resolution where data supports it; unknown path ordering fails conservatively.
- No further indicators, thresholds, filters, or grid expansion after OOS results are viewed.

## Mandatory tests

1. **Trade-order Monte Carlo:** for each frozen OOS candidate, reorder its complete realized net-R outcome multiset 1,000 times with a deterministic recorded seed. At a fixed 1% equity risk per trade, report historical chronological MDD, permutation MDD median/95th percentile/maximum, and 95th-percentile MDD. This is a sequence-risk diagnostic, not a market-path forecast; it does not model changing trade distributions, signal dependence, or simultaneous portfolio exposure. Do not claim live position sizing from it.
2. **Walk-forward:** five chronological windows, each trained on 504 calendar days and tested on the immediately following 252 calendar days; advance by 252 calendar days. Apply the same date boundaries to every intraday timeframe, so a 504/252 split does not collapse into a few hours on 1m data. Select only from the frozen grid using training data, then freeze parameters throughout that test window. Purge at least the maximum 20-native-bar outcome horizon across each boundary. Report every window, including empty/failed windows, pooled OOS outcomes, and train-to-test degradation. No test-window retuning. At least 1,764 days of usable history plus 4h-indicator warm-up are required; if the dataset cannot supply this, report `INCONCLUSIVE` rather than shortening the windows.
3. **Parameter sensitivity:** on each training window, evaluate all adjacent cells in the frozen grid. Define a passing cell before evaluation as train M2 >=80%, at least 30 resolved training signals, and positive net expectancy after costs. A selected candidate is plateau-robust only if at least 80% of its one-step neighbors pass and adjacent median M2 is within 10 percentage points of the selected cell. Unresolved or under-sampled neighbors count as failures. Report neighbor count and pass fraction; a cell with fewer than 4 neighbors is non-evaluable, not robust. No isolated peak passes.

## Causal and data checks

Before backtesting, unit-test pivot-anchor oscillator sampling, confirmation delay, next-bar entry, closed-4h alignment, stop/target tie handling, timeout, short symmetry, and parameter bounds. The shared OHLC resolver marks missing/malformed required paths unresolved, applies adverse stop-gap fills, and resolves same-bar barrier ties as stop-first. Run prefix-invariance and deliberate future-peeking injection checks. Audit gaps, duplicate candles, symbol listing periods, and delisted/contract universe availability before selecting the data window. Freeze an immutable data fingerprint and trial manifest. Split chronologically; never use final sealed data to choose the grid or filters.

Initial read-only source audit: `vision_pit_dev_sample.sqlite` contains 86 symbols and monthly archive metadata from 2021-01 through 2026-10. 67 symbols have a manifest entry for every month in that span; 19 have shorter or incomplete archive histories. Eight monthly archive files are listed as rejected due to taker-buy volume validation. This is an 86-symbol archived universe, not proof of complete exchange-wide point-in-time membership. Any signal whose required candle path crosses a missing minute must be marked unresolved, never silently dropped or called a win. Re-check candle-level gaps and all five walk-forward windows before the backtest is permitted to report performance.

## Promotion gate

`REJECT` if any required Monte Carlo, walk-forward, sensitivity, causal, sample, or frozen SPEC gate fails. `INCONCLUSIVE` if required OOS sample or data provenance is insufficient. Only a candidate passing all gates can be labeled `FORWARD-TEST CANDIDATE`; this study alone never authorizes live trading. Results must include all attempted cells and negative outcomes.

## Scope warning

An earlier `rsi_divergence` setup exists in `chart_predictor/setups.py` and was covered by prior P5 research. This study is not a claim that divergence is new or untested: it is a separately specified correction/replication with anchor-aligned oscillator values, macro regime, execution variants, the user's requested 504/252 walk-forward, 1,000 trade-order permutations, and explicit sensitivity-plateau criteria. Prior P5/P8 results remain separate and must not be merged as if generated by this protocol.
