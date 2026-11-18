# Micro-candle phase 0: one completed 1m candle ahead

Status: frozen before querying phase-0 outcome labels. This is a direction-classification diagnostic, not a trade strategy or an untouched/sealed test.

## Purpose and order of work

Begin with the smallest well-defined forecast: after a 1m candle has completed, classify the next completed 1m candle's close relative to the current close. Do not add macro regime, higher-timeframe indicators, multi-candle patterns, target/stop logic, leverage, or portfolio sizing in this phase. Broader pattern tests are a later, separately logged trial and may not reinterpret this diagnostic as trade performance.

## Input snapshot and cohort

- Read-only source: `/Users/user/CODE/Coin_Trade/chart_predictor/data/vision_dev_repaired.sqlite`.
- Snapshot reference: `vision_repaired_quality_20261115.json`, metadata fingerprint `2b421901d3777f6127c90772b090341b3947046c71d4e15e45ccf00e557c438a`. This is a schema/coverage metadata fingerprint, not a full candle-content hash.
- Fixed six-symbol cohort: BNBUSDT, BTCUSDT, DOGEUSDT, ETHUSDT, SOLUSDT, XRPUSDT. Use all six; no symbol selection by phase-0 outcomes.
- The snapshot has 19,790,858 reported rows, 6 symbols, and a 2020–2026-06 span. The data-cleanup record says the source had 14,400 missing SOL/XRP minutes and the separate repaired snapshot restores those minutes. The 2022 repair intervals precede this phase's train/evaluation windows.
- A prior strategy program has examined this history. Therefore chronological evaluation below is diagnostic only, not sealed or independent OOS evidence.

## Label, features, and fixed split

- Anchor `t`: UTC open time of a completed 1m candle. Inputs are limited to that candle and earlier candles.
- Label: compare `close[t+1]` with `close[t]`. Greater = UP, lower = DOWN, exact equality = FLAT. No after-the-fact deadband or threshold selection.
- Keep a row only if the prior, anchor, and next candle timestamps are consecutive 60,000 ms intervals. Never interpolate a missing bar. Count excluded anchors.
- Training anchors: `[2025-10-01T00:00:00Z, 2026-01-01T00:00:00Z)`; each target candle must also open before 2026-01-01.
- Evaluation anchors: `[2026-01-01T00:00:00Z, 2026-04-01T00:00:00Z)`; every target candle must open before 2026-04-01.
- Evaluation outcomes cannot choose a baseline, class mapping, symbol, threshold, or feature. Test results are not reused as a sealed validation set.

## Fixed baselines

1. **Persistence:** predict the sign of the completed anchor candle's close-to-close return from the prior completed close; zero maps to FLAT.
2. **Reversal:** invert the previous nonzero direction; zero maps to FLAT.
3. **Training majority:** per symbol, predict the most frequent training label throughout evaluation. Tie order is FLAT, DOWN, UP.
4. **Deterministic random:** `SHA256("micro1m-v1|seed=20261118|symbol|anchor_open_ms")`, first 8 bytes modulo 3 mapped to UP, DOWN, FLAT. This is a chance baseline, not a trading policy.

## Metrics and uncertainty

Report per symbol and pooled results: three-class accuracy, balanced accuracy, class support/recall, confusion matrix, direction-only accuracy conditional on actual UP/DOWN, and the fraction of evaluation rows predicted non-flat. Accuracy is not PnL. No trading costs are applied because no entries/exits or simulated trades are defined.

For pooled accuracy and paired accuracy difference versus the training-majority baseline, use a 7-consecutive-UTC-day moving-block bootstrap with 5,000 fixed-seed draws, resampling the same dates across all symbols to preserve shared market shocks. Also show the six symbol-specific estimates; the pooled minute count is not an independent-sample count. This bootstrap is not the required 1,000 trade-order Monte Carlo because this phase creates no trades.

## Stop and extension rule

Phase 0 can only establish whether these simple one-bar baselines contain measurable directional information in this already-exposed data. It cannot satisfy the user's M2 target-first ≥80%, stock CAGR/MDD/Sharpe goals, or mandatory strategy-validation gates. Any candidate later described as a strategy must separately pass 1,000 trade-order permutations, five chronological walk-forward folds and the preregistered parameter-plateau test; otherwise it is rejected or inconclusive. A later 2–3-bar morphology hypothesis must be registered as a new family before its labels are queried, with the frozen baselines retained and all tried candidates reported.
