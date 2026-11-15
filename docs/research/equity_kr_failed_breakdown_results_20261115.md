# KR daily failed-breakdown reversal: exploratory result

**Decision: reject this fixed candidate on the development cache.** It produced negative average net returns under both stated cost assumptions; this is not evidence that every KR strategy fails, and it is not an OOS result.

## Frozen rule and data

The rule and cost assumptions were written in [`equity_kr_failed_breakdown_preregistration_20261115.md`](equity_kr_failed_breakdown_preregistration_20261115.md). At close `t`, a stock triggers when its low falls below the lowest low of the previous 20 market sessions but closes back above that prior floor. Buy at the next session open; exit at the close of the fifth holding session, counting entry day as session one. No stops, targets, trend filters, or parameter sweep. New entries for a stock are suppressed while its previous event is open. This is a non-overlapping event study, not a sized portfolio.

Input: 92 local KIS daily files (64 common stocks and 28 ETFs including the 069500 comparator), with pre-cutoff observations from `2010-05-28` to `2024-11-11`. The exclusive cutoff is `2024-11-12`; later OHLCV was not parsed. The source is a selected current cache, not a point-in-time or delisting-complete universe. Adjusted-price and historical revision provenance are not independently verified. Per-file pre-cutoff hashes and event-row SHA-256 are in the [machine-readable result](equity_kr_failed_breakdown_results_20261115.json); event-row SHA-256 is `47324aa46deed59a5e519da324b40241f0bcab60177f57171875040ba463a0d5`.

The first exploratory implementation of the uncertainty interval compressed out months with no events, which shortened nominal six-month blocks. That interval was discarded. The bootstrap was corrected to retain every calendar month between the first and last event (including empty-event months) and resample circular six-calendar-month blocks; the corrected run kept the same event counts and point estimates. Because this inference correction followed an initial result inspection, the final interval remains post-hoc descriptive, not a fully preregistered confirmatory test. The sorted manifest of pre-cutoff per-file hashes is `4cb4ca918a3eba08b2877e3e9b9ce319be8e584f39bc1def5edf395b79296d1b`.

The engine identified 197,511 eligible symbol-session anchors, 7,464 raw signals, and 5,355 non-overlapping executed events; 2,109 overlapping signals were suppressed. Executed-event coverage was 2.71% of eligible anchors. The result contains 64 per-symbol aggregates and yearly summaries.

## Results

Stock base costs are 0.015% commission per side, 0.18% sell tax, and 0.10% slippage per side. Stress doubles slippage to 0.20% per side. For the paired 069500 comparator, commission and slippage are applied but no sell tax is assumed. These are scenario assumptions, not measured fills.

| Measure | Base | Stress |
|---|---:|---:|
| Mean net return per event | **−0.315%** | **−0.515%** |
| Six-calendar-month block-bootstrap 95% CI for mean | **−0.625% to −0.011%** | **−0.831% to −0.206%** |
| Median net return | −0.410% | −0.609% |
| Positive event-return fraction | 45.49% | 43.45% |
| Wilson 95% interval for positive fraction | 44.16–46.83% | 42.13–44.79% |
| Six-month block interval for positive fraction | 43.33–47.77% | 41.21–45.76% |
| Paired mean excess vs 069500 | −0.133% | −0.133% |
| Paired six-month block 95% CI vs 069500 | −0.288% to +0.022% | −0.285% to +0.018% |

Across 64 current-cohort stocks, 46 had a negative mean base-cost event return. Per-symbol means ranged from −2.285% to +0.797%; the small event counts for some recently listed securities make these individual values unstable. The full per-symbol counts, coverage, mean returns, positive rates, and per-file hashes are in the JSON artifact.

| Signal year | Events | Mean base net return | Positive fraction |
|---:|---:|---:|---:|
| 2010 | 68 | +1.384% | 67.65% |
| 2011 | 336 | +0.009% | 46.73% |
| 2012 | 326 | −0.145% | 48.77% |
| 2013 | 305 | −0.946% | 38.69% |
| 2014 | 345 | −0.122% | 45.22% |
| 2015 | 367 | +0.482% | 48.50% |
| 2016 | 380 | −0.252% | 49.21% |
| 2017 | 309 | +0.113% | 45.63% |
| 2018 | 460 | −0.398% | 43.91% |
| 2019 | 412 | −0.410% | 44.17% |
| 2020 | 339 | −1.028% | 45.13% |
| 2021 | 361 | −0.003% | 48.48% |
| 2022 | 523 | −1.463% | 35.37% |
| 2023 | 438 | +0.329% | 49.32% |
| 2024 through Nov 11 | 386 | −0.522% | 46.89% |

## Interpretation and limits

The base-cost block interval for the average event return lies just below zero; the stress result is more clearly negative. The paired return difference versus 069500 is uncertain and its interval crosses zero, so this event rule did not establish benchmark-relative underperformance, but it also did not establish positive absolute returns. A 45.49% positive-trade fraction and negative expectancy are not consistent with a useful standalone entry signal.

Block-bootstrap intervals resample contiguous circular six-calendar-month blocks and preserve same-month cross-symbol observations. They do not cluster repeated observations by symbol, and the wider project history contains many strategy trials; no multiplicity-adjusted significance claim is made. No portfolio CAGR, annual return, turnover, or max drawdown is inferred from event averages because the user has not specified portfolio allocation or concurrent-position sizing. Slippage is assumed rather than observed. The 2010–2024 cache has already been inspected in prior work, so chronological splits within it are not untouched validation.

Reproduction from the Coin_Trade checkout:

```sh
python -m pytest tests/test_equity_kr_failed_breakdown_probe.py -q
python scripts/research/equity_kr_failed_breakdown_probe.py \
  --cache /Users/user/CODE/Ochestration/.kis-cache \
  --output /private/tmp/equity_kr_failed_breakdown_20261115_final.json
```

The source uses a read-only-by-convention CSV path, stops at the exclusive cutoff before converting cutoff-row OHLCV fields, and writes results only to the explicit output path. Three focused tests passed, including a malformed post-cutoff row that must remain unparsed. This candidate should not be tuned on this same cache.
