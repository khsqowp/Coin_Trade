# Micro-magnitude Phase 1 — corrected replay

Date: 2026-11-19

Decision: **STOP this magnitude-diagnostic branch; no trading edge demonstrated.**

Evidence class: exposed historical development replay, not confirmation, M2, or a trading result.

## Frozen question and protocol

At a completed 1-minute candle, compare the prior 1-minute absolute log return as the next 1-minute absolute-return forecast against a per-symbol training-median forecast. The exact formula, data, dates, eligibility threshold, equal-symbol MAE, 7-day circular date-block bootstrap (5,000 replicates, seed `20261119`), and stop gate are in [`micro-magnitude-phase1-prereg-2026-11-19.md`](micro-magnitude-phase1-prereg-2026-11-19.md). No parameters, symbols, thresholds, or date windows were tuned after seeing results.

This rerun fixes the original implementation's protocol defects: it persists a complete all-symbol outcome-blind preflight before scoring, and assigns split membership by candle close (`open_ms + 60,000`) with half-open intervals. It remains a replay of the same already-exposed 2026-Q1 historical interval. Repairing implementation defects does not make that interval unseen or confirmatory.

## Reproducibility and data gate

- Input: read-only `vision_pit_dev_sample.sqlite`, 30,363,320,320 bytes, SHA-256 `bb64efa272bab6c5bed258ec7284f9212165c8912cfcd824f51863ae5d88fafa`.
- Runner SHA-256: `9d5af65db4d15282ba618812408a92a57b38fbbb95dedc8f48eee2252a0aaeb2`.
- Run fingerprint: `bc71f3b5f08cbcde27409596cb01771059c4275bf50254fb786b61788d0509f6`.
- Preflight completed and was atomically saved before scoring: 86 symbols; 75 eligible and 11 below the minimum evaluation sample. Quality scan: 218,497,381 rows, invalid OHLCV 0, off-grid timestamps 0, nonconsecutive-minute adjacencies 74. The 74 gaps are excluded by the registered consecutive-bar rule; there was no interpolation or forward fill.
- Eligible symbols had 2,579,035–2,629,438 training returns (symbol-dependent gaps) and 129,598 evaluation forecasts each. Total eligible evaluation forecasts: 9,719,850. These are serial observations, not independent samples.
- Run completed normally with exit code 0. Preflight and final status fingerprints match. No output file was overwritten; the machine-readable result is [`micro-magnitude-phase1-corrected-rerun-2026-11-19.json`](micro-magnitude-phase1-corrected-rerun-2026-11-19.json).

## Results

| Metric | Result | Frozen gate | Decision |
|---|---:|---:|---|
| Eligible symbols | 75 | ≥20 | Pass |
| Symbols with positive per-symbol MAE improvement | 14/75 (18.7%) | >50% | Fail |
| Equal-symbol relative MAE improvement | **−1.3008%** | >0% | Fail |
| Paired 7-day block bootstrap 95% interval | **−2.6533% to +0.2660%** | Entire interval >0 | Fail |
| Equal-symbol relative MSE improvement | −17.2071% | Secondary diagnostic | Worse |
| MSE 95% interval | −25.5466% to −11.5381% | Secondary diagnostic | Worse |
| All-forecast pooled relative MAE improvement | −2.0187% | Secondary diagnostic | Worse |

The machine decision is `STOP_MAGNITUDE_BRANCH`. The candidate loses to the training-median baseline on the primary point estimate, the interval includes zero, and only 14 of 75 symbols improve. Do not add direction, filters, patterns, thresholds, or broader timeframes to rescue this result.

## Independent checks and limits

- The full corrected replay reproduced the initial corrected run exactly for all primary/secondary metrics and every per-symbol training count, forecast count, MAE, and MSE. The additional endpoint candle loaded solely to exercise the exclusive close-time boundary did not alter any score.
- A deterministic five-symbol scalar recomputation (ADA, ETC, GRT, TRB, XLM; seed `20261119`) independently matched each symbol's train/evaluation counts. Candidate and baseline MAE absolute differences were below `9.6e-17`; relative-improvement differences were below `2.4e-13`.
- Follow-up audit on 2026-11-19 initially reported one extra training return per five-symbol sample. Its first scalar query filtered stored `close_ms` and selected training rows by `open_ms`, which differs from the preregistered interval-boundary convention (`open_ms + 60,000`). Boundary-row inspection confirmed that the final pre-end candle has stored `close_ms = TRAIN_END - 1` but interval close boundary `open_ms + 60,000 = TRAIN_END`; the frozen half-open boundary excludes it. A corrected, read-only scalar recomputation using the frozen boundary rule matched all five train/evaluation counts and medians; candidate and baseline MAE differences were about `1e-16`. Details are recorded in [`micro-magnitude-phase1-independent-scalar-audit-2026-11-19.json`](micro-magnitude-phase1-independent-scalar-audit-2026-11-19.json). This was an audit clarification, not a new strategy trial or a change to the frozen rule.
- Synthetic tests now explicitly cover a candle that opens before the evaluation start but closes exactly at the inclusive start, a candle closing exactly at the exclusive evaluation end, bootstrap interruption status, and resume from symbol checkpoints.
- `chart_predictor/tests/test_micro_magnitude.py`: 6 passed. Full `chart_predictor/tests`: **716 passed**, with one non-failing joblib physical-core detection warning.
- No forecast direction, entry/stop/target, return, fee, funding, M2 target-first rate, or manual-trading signal was calculated. The user's crypto gate (all-issued target-first M2 ≥80%, plus separate outcome-blind non-overlapping N≥200 across ≥20 symbols and robustness gates) is untouched and not passed.
- This diagnostic has no trades or fitted trading parameters; trade-order Monte Carlo and strategy walk-forward gates are therefore not claimed as passed. The result cannot justify deployment, live signals, or strategy promotion.

## Cross-market agent review in this continuation

Four independent read-only reviews covered KR equities, US equities, crypto candidate validity, and red-team controls. KR/US have no verified intraday stocks/ETF source in the current checkout; the smallest confirmed source is daily, with unresolved point-in-time membership, delistings, adjustment/dividend lineage, and rights. Existing daily candle diagnostics are exploratory and do not satisfy the fixed portfolio gates (net CAGR ≥20%, MDD ≤30%, Sharpe ≥1, ≥200 closed OOS round trips per market). No new KR/US performance test was opened because the present data would not support the requested claim.

The crypto review found no admissible new OHLC-only micro-pattern after the already-rejected Phase 0–8 family. The separate 20-symbol, one-day aggTrades reconciliation is documented in [`binance-aggtrades-vs-kline-pilot-20250101.md`](binance-aggtrades-vs-kline-pilot-20250101.md); it found unresolved minute discrepancies and an SOLUSDT daily-total discrepancy, so aggTrades-derived minute flow is not promoted as a validated feature.

Next useful crypto work is data/protocol validation, not another threshold mix: resolve event-to-minute reconciliation over multiple dates, or obtain a valid forward append-only data stream. A new result from the same exposed historical panel cannot be called confirmatory.
