# Micro-magnitude Phase 1 — result

**Protocol status: INVALID AS A PREREGISTERED RESULT.** The runner mixed source-quality counting and outcome scoring in the same per-symbol pass; the preregistration required the complete outcome-blind quality/eligibility preflight to be recorded before scoring began. The reported metrics below are retained as exploratory diagnostics only. They cannot trigger a preregistered gate or confirmatory claim.

## Frozen test

- Preregistration: [`micro-magnitude-phase1-prereg-2026-11-19.md`](micro-magnitude-phase1-prereg-2026-11-19.md).
- Runner: [`micro_magnitude.py`](../../chart_predictor/micro_magnitude.py); machine-readable results: [`micro-magnitude-phase1-results-2026-11-19.json`](micro-magnitude-phase1-results-2026-11-19.json).
- Runner SHA-256 at execution: `dc2ebc291b77e6528b9fab64d049175ccfe9a64982bb8674213bd4d23e6b9ee7`.
- Question: after the close of minute `t`, forecast next-minute movement size as `abs(log(C[t]/C[t-1]))`; compare with the per-symbol median absolute return estimated only from training returns.
- Source: read-only 30,363,320,320-byte SQLite file; SHA-256 `bb64efa272bab6c5bed258ec7284f9212165c8912cfcd824f51863ae5d88fafa`; 86 archived symbols.
- Training return endpoints: 2021-01-01 through 2025-12-31 UTC. Evaluation target-candle closes were intended as 2026-01-01 through 2026-03-31 UTC. The runner compared target `open_ms`, not stored `close_ms`; exact target-close boundary compliance was not implemented or tested. Do not assert split-boundary correctness for this run.
- The runner's combined pass counted 75 eligible symbols and 11 historic contracts without sufficient 2026-Q1 forecasts; eligible symbols had 129,598 forecasts each (9,719,850 total). These counts were not saved as a separate preflight artifact before scoring, so they do not satisfy the preregistration's sequencing requirement.
- In that same pass it counted 218,497,381 scanned source rows, zero invalid OHLCV rows, zero off-grid timestamps, and 74 non-consecutive minute adjacencies. Forecast triples crossing gaps were excluded. Because quality counting was not completed and recorded globally before target scoring, these numbers are exploratory run diagnostics, not a preregistered eligibility gate. This is a large archived sample, not a verified point-in-time contract universe.
- Primary metric: equal-symbol mean of per-symbol relative MAE improvement. Uncertainty: paired shared-date circular 7-day block bootstrap, 5,000 replicates, seed `20261119`.

## Result

| Measure | Result | Preregistered requirement | Status |
|---|---:|---:|---|
| Eligible symbols (exploratory count) | 75 | ≥20 | Not gate-valid |
| Symbols with positive MAE improvement | 14/75 (18.7%) | >50% | Exploratory fail |
| Equal-symbol relative MAE improvement | **-1.30%** | Positive | Exploratory fail |
| MAE improvement 95% block interval | **-2.65% to +0.26%** | Entire interval >0 | Exploratory fail |
| Equal-symbol relative MSE improvement | -17.21% | Secondary diagnostic | Worse |
| MSE improvement 95% block interval | -25.55% to -11.54% | Secondary diagnostic | Worse |
| All-observation pooled relative MAE improvement | -2.02% | Secondary diagnostic | Worse |

The exploratory metrics are unfavorable: the primary interval includes zero, most symbols perform worse than the median baseline, and the secondary MSE comparison is consistently worse. Separately, the execution-order violation invalidates the result against the preregistered gate. Do not use it to advance or formally reject any trading strategy. No adjacent-candle or broader-context experiment is run from these numbers.

## Interpretation and limits

- These exploratory numbers show no demonstrated forecasting gain for the simplest one-minute movement-size persistence feature on this exposed development panel; the sequence violation prevents a preregistered conclusion.
- Prior P4b/P4c work examined a related future-expansion family. This run uses a distinct continuous one-step target and MAE, but is close prior art—not a new market mechanism. Published prior results were visible during candidate review; this cannot be represented as preregistered before all prior exposure.
- No direction, threshold, long/short setup, stop, target, fee, funding, return, M2, or trade was evaluated. The user's fixed crypto gate remains all-issued target-first M2 ≥80%, plus outcome-blind non-overlap N≥200 over ≥20 symbols and the required robustness gates. This diagnostic cannot meet or weaken that gate.
- Monte Carlo trade-order, trading walk-forward, and parameter-plateau tests are not applicable because this is not a trading strategy and has no fitted parameters or trades. No live order, network collection, or external deployment occurred.
- The dataset's SHA proves the bytes used in this run, not point-in-time listing completeness or independent future validation.

## Verification

- Full input SHA-256 matched the frozen preregistration before scoring. The separate outcome-blind quality/eligibility preflight did **not** precede outcome scoring; this is the protocol failure.
- A synthetic SQLite fixture forced four-row chunk boundaries and an invalid OHLC candle; the runner counted nine train returns, excluded all three affected forecast triples, and reported the expected 15 valid forecasts.
- `chart_predictor/tests/test_micro_magnitude.py`: 1 passed.
- `python -m py_compile chart_predictor/micro_magnitude.py` and `git diff --check`: passed.
- Independent scalar/database audit: not completed. The red-team review was static and did not recalculate raw data; therefore numerical implementation accuracy remains unverified. The score remains exploratory even if the arithmetic independently matches.
