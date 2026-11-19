# Hourly TA-Lib pattern feasibility review — 2026-11-19

## Decision

The corrected scan finds that the post-hoc two-sided union passes the historical **frequency-only** gate at both deadlines; this is not a performance result. No target-first outcomes, stop/target paths, returns, or future price paths were read. The candidate was assembled after viewing single-pattern and directional-union frequency counts, so it is exploratory and cannot be treated as preregistered confirmation.

## Method and data integrity

- Candidate family: the 30 bullish and 25 bearish reversal labels in Moser & Brauneis (2026), mapped to 40 TA-Lib Python 0.6.5 functions; 15 functions provide both signs. Signal becomes available only at the completed hourly candle close.
- Trend filter: paper's strict 144-hour SMA slope over seven consecutive SMA observations (`MA[t-6] ... MA[t]`), evaluated at the completed signal bar.
- Input: read-only `vision_pit_dev_sample.sqlite`, 86 symbols and 5,522 manifest rows, interval `[2021-01-01, 2026-11-01)` UTC. Manifest SHA-256: `63dd2082c07279f4e2aa8b36df5b6a8dd17512a097f1f4babb73e4a9ef97d45d`.
- Expected and observed one-minute rows both equal 241,389,061. Present-manifest symbol-month row counts match; 498 scheduled symbol-months have no archive manifest and are counted as unavailable. This check does not verify archived-file hashes or candle row contents. Complete hourly bars: 4,023,147 of 4,396,320 scheduled symbol-hours (91.5117%). Feature-eligible anchors after continuous history and 150-hour warmup: 3,999,307.
- Seven unit tests pass, including pinned manifest/cohort rejection, absent-month accounting, monthly row-count mismatch rejection, prefix invariance, a deliberate future-peeking negative control, exact hourly aggregation/gap rejection, pattern mapping, and expiry-boundary non-overlap.

## Frequency screen

| Claim family | Result | Eligibility |
|---|---|---|
| 55 individual direction-specific patterns × 10h/20h (110 rows) | 0 pass; maximum scheduled coverage 3.174% (feature-eligible diagnostic 3.489%) | Fail: each misses 10% scheduled coverage |
| All bullish patterns OR, long | 435,413 signals; scheduled coverage 9.904% (feature diagnostic 10.887%); non-overlap N=140,154 (10h), 84,668 (20h); 86 symbols | Fail: scheduled coverage below 10% |
| All bearish patterns OR, short | 396,498; scheduled coverage 9.019% (feature diagnostic 9.914%); N=128,372 (10h), 77,732 (20h); 86 symbols | Fail: scheduled coverage below 10% |
| Two-sided OR: bullish-long or bearish-short | 831,911; scheduled coverage 18.923% (feature diagnostic 20.801%); N=266,666 (10h), 155,890 (20h); 86 symbols | Pass frequency only at both horizons |

The two-sided claim deduplicates same-side pattern collisions at each symbol-hour. Opposing raw TA-Lib sign collisions are reported separately; the mutually exclusive trend filter determines which directional union may issue at an anchor. The 10h and 20h counts are separate claims and do not establish independent outcomes.

## Interpretation and next gate

The narrow result is that a mechanically fixed, all-pattern two-sided union has enough historical signal volume to justify a separately preregistered **development performance screen**. The bullish-only union appeared to pass under the earlier, incorrect feature-anchor denominator; it fails the corrected scheduled-slot coverage gate. The two-sided union remains above 10% under the corrected denominator. Neither finding establishes ≥80% M2, positive net expectancy, a robust edge, or a deployable signal. This dataset is already exposed development history and does not provide a sealed OOS period. Any later confirmatory evaluation must use a prospectively sealed period and meet every frozen SPEC requirement.

The development performance preregistration remains a draft and must be paired with its evaluator, tests, frozen hashes, and final red-team lock before any outcome path is read. It defines next-minute entry, ATR barriers, 1-minute tie/gap rules, timeout and unresolved-data handling, costs, baselines, 24-month/6-month walk-forward with boundary purge, Monte Carlo order-sensitivity, parameter robustness, and the post-hoc selection family. The local historical database has no funding-rate table or funding-rate files; funding-inclusive expectancy is unverified until an approved historical funding input is available. The recorded 86-symbol archive cohort also does not prove point-in-time contract eligibility or remove survivorship bias.

## Files

- [`Hourly TA-Lib preregistration`](crypto-hourly-talib-pattern-feasibility-prereg-2026-11-19.md)
- [`Individual-pattern frequency output`](results/hourly_talib_feasibility_20261119/REPORT.md)
- [`Directional-union frequency output`](results/hourly_talib_feasibility_union_exploratory_20261119/REPORT.md)
- [`Two-sided-union frequency output`](results/hourly_talib_feasibility_two_sided_exploratory_20261119/REPORT.md)
- [`Corrected SPEC-coverage recheck`](results/hourly_talib_feasibility_spec_coverage_recheck_20261119/REPORT.md)
- [`Scanner`](../../chart_predictor/hourly_talib_feasibility.py) and [`tests`](../../chart_predictor/tests/test_hourly_talib_feasibility.py)

The derivative output folders include Binance Vision attribution and CC BY-NC-SA 4.0 notices. No raw dataset was copied into these reports. See [official Binance Vision terms](https://github.com/binance/binance-public-data/blob/master/TERMS_AND_CONDITIONS.md) and the [paper](https://www.sciencedirect.com/science/article/pii/S1059056026002716).
