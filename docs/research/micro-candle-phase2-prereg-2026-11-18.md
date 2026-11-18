# Crypto micro-candle phase 2 preregistration — expansion then compression

Status: exploratory development trial. The historical sample is already exposed to prior research; this file does not create a sealed or confirmatory test. No outcome data may be read until this rule and the feasibility stage are fixed.

## Question

After a one-minute range-expansion candle is followed immediately by a range-compression candle, does the expansion candle's direction identify a subsequent 1R target-before-stop opportunity?

This is a two-candle, price-only continuation hypothesis. It does not use the failed close-location forecast, a macro filter, or a three-candle breakout. It is adjacent to the repository's BB-squeeze family and must be interpreted as a distinct fixed rule within a related volatility-compression family, not as a wholly independent market mechanism.

## Frozen input and signal

- Read-only input: `chart_predictor/data/vision_pit_dev_sample.sqlite`, table `candles`.
- Initial feasibility cohort: BTCUSDT, ETHUSDT, BNBUSDT, SOLUSDT, XRPUSDT, DOGEUSDT. If the signal rate is viable, expand without changing the rule to every eligible symbol in the same database before any M2 claim.
- Bars are UTC one-minute bars. At the close of bar `t`, require the 21-bar sequence `t-20 ... t` to be present at exact one-minute spacing.
- Let `r[i] = high[i] - low[i]`. Let `M[t]` be the median of `r[t-20 ... t-1]` (20 completed bars, including the expansion candidate at `t-1`).
- Long signal at `t` iff `close[t-1] > open[t-1]`, `r[t-1] >= M[t]`, `0 < M[t]`, and `r[t] <= 0.5 * M[t]`.
- Short signal is the exact directional mirror: `close[t-1] < open[t-1]` with the same range conditions.
- A doji at `t-1`, invalid OHLC, or a missing minute in the feature window produces no signal. No further indicators, symbol-specific thresholds, or filters are permitted in this trial.

## Execution and labels

- Emit the forecast only after `t` closes. Planned entry is the next one-minute bar open.
- Long stop is `low[t]`; short stop is `high[t]`. If the next open is on the wrong side of the stop, retain the issued forecast in the M2 denominator as a non-success and record `invalid_entry` separately; do not silently drop it.
- For a valid entry, define `R` as entry-to-stop distance and target at exactly `1R` in the forecast direction.
- Evaluate separate 10-bar and 20-bar horizons, each from the next bar after entry. M2 success requires target to trade before stop and within the named horizon. Timeout is not success. If the same one-minute OHLC bar touches both barriers, count stop-first. A stop gap fills at the worse open; target gaps receive no improvement over the target price.
- Report M1 horizon-close direction separately. Never merge M1 and M2.
- The M2 denominator is every forecast emitted under the fixed signal rule, including overlapping forecasts and invalid entries. Separately select outcome-blind non-overlapping samples by earliest signal per symbol, skipping signals until the corresponding horizon expires.

## Minimum feasibility and full gates

1. First perform outcome-blind counts only: eligible anchors, signals, directional split, symbol dispersion, and `signals / eligible anchors`. Do not inspect future prices in this stage.
2. If coverage is below 10%, fewer than 20 symbols can emit a signal, or either 10/20-bar claim cannot plausibly reach 200 non-overlapping signals, reject before outcome evaluation.
3. If feasible, run one frozen full-universe development evaluation. Required promotion gates remain: M2 point estimate >=80% for a separately named horizon, non-overlapping N>=200, >=20 symbols, coverage>=10%, positive cost-adjusted expectancy, and dependence-/multiplicity-adjusted comparison against matched 10-bar momentum and a fixed-seed random baseline.
4. Base assumed trading costs: 5 bp fee + 2 bp slippage per side (14 bp round trip). Stress: double both (28 bp round trip). Apply recorded funding only if an actual settlement is crossed; otherwise record zero funding crossings.
5. Preserve all-issued and non-overlap results, per-symbol/side/year strata, invalid/unresolved/timeout counts, and confidence intervals. Use shared UTC-date 7-day block resampling for descriptive uncertainty; it is not an independent confirmation interval.
6. Since the historical panel has already been examined, even a passing development result cannot be called independent OOS or promoted. A later forward stream must use an append-only registry and frozen code/rule before collecting outcomes.

## Duplicate and multiplicity note

The repository already contains BB squeeze breakout and several reversal/continuation setups. This rule is not a license to repeat their parameter grids. It is one fixed two-candle hypothesis with a one-time feasibility gate. Record it as a separate trial; do not tune it on this panel or select a favorable horizon after observing outcomes.

## Provenance and current known data bounds

The database is a large historical Vision research sample. A six-symbol metadata query observed 18,345,600 rows from 2021-01-01 00:00 UTC through 2026-10-31 23:59 UTC. That metadata query did not inspect or validate the future-label path. The separate 2026-11-15 data-quality reports cover a different six-symbol repaired database; they do not prove this 86-symbol sample has no OHLC defects. Validate only the fields and rows used by this trial before any outcome calculation.
