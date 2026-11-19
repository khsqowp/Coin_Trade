# Micro-candle flow-incremental comparison — preregistration (2026-11-19)

Status: frozen before this trial reads next-candle outcome labels. The historical evaluation period has been exposed by Phase 0 and other research; this is a development-only exploratory diagnostic, not confirmatory OOS, not a strategy approval, and not an M2 test.

## Question

On the same completed 1-minute candles and the same symbols/time split, does adding the completed candle's taker-buy quote imbalance to a fixed one-candle OHLC/volume model improve prediction of the next candle's close-to-close direction?

## Cohort and periods

- Read-only SQLite input: `chart_predictor/data/vision_pit_dev_sample.sqlite`.
- Fixed cohort: BNBUSDT, BTCUSDT, DOGEUSDT, ETHUSDT, SOLUSDT, XRPUSDT. No symbol selection based on outcomes.
- Training anchors: 2025-10-01 00:00 UTC through 2025-12-31 23:59 UTC.
- Evaluation anchors: 2026-01-01 00:00 UTC through 2026-03-31 23:59 UTC.
- The target candle must also open before the end of its respective split. The source is already exposed; the evaluation is not called untouched or independent OOS.
- Both model variants use precisely the same anchor rows. Require the prior 20 feature candles, anchor, and next target candle to be valid, consecutive one-minute bars. Never bridge gaps.

## Estimand and frozen features

At the close of anchor candle `t`, predict whether `close[t+1] > close[t]` (UP) or `< close[t]` (DOWN). Exact equality is excluded from this binary directional estimand and counted separately. No unfinished bar or future field is an input.

For each symbol, use two independently fitted but otherwise identical models:

1. **OHLCV:** L2 logistic regression (`C=1`, intercept enabled, `lbfgs`, fixed seed), using only the anchor and its past: close-to-close log return; candle range / previous close; body, upper-wick, and lower-wick fractions of range; log quote-volume divided by the median quote-volume of the 20 immediately preceding bars.
2. **OHLCV + taker flow:** the exact OHLCV model plus `2*taker_buy_quote/quote_volume - 1` from the completed anchor candle.

Standardization is fitted on the training split only. No hyperparameter search, feature selection, threshold tuning, refits during evaluation, symbol selection, or post-result revisions. Reject a row from both variants if any required input is non-finite, quote volume is non-positive, taker-buy quote is outside `[0, quote_volume]`, or required timestamps are not consecutive. Report all exclusions before interpreting model scores.

## Baselines and metrics

- Primary metric: binary directional accuracy; compare the two model predictions paired on identical evaluation anchors.
- Required safeguards: balanced accuracy; UP and DOWN precision/recall; Brier score and log loss; predicted UP share; exact-flat count; per-symbol metrics; pooled metrics; train-majority, persistence, and reversal predictions on the same eligible anchors.
- Uncertainty: 5,000 paired moving-block bootstrap replicates of 7 consecutive UTC dates, resampling the same dates synchronously across all six symbols, fixed seed `20261119`. Report the 95% interval for the paired accuracy difference (flow model minus OHLCV model). The six symbols and minute rows are not independent observations.
- No PnL, fees, funding, target-first rate, calibration gate, or trade result is inferred from this classification comparison. Accuracy cannot pass the separate crypto M2 ≥80% target-first gate.

## Decision rule and limitations

This is a single fixed exploratory comparison to decide whether the added flow field merits a new prospective capture/validation study. It is not eligible for tuning based on this evaluation split. If paired accuracy does not improve and log loss does not improve, reject the incremental-flow hypothesis for this sample. If it improves, classify the result as a historical lead only; any confirmatory claim requires a separately preregistered, untouched forward period and verification that the live source provides the same taker field at the forecast time.

Binance Vision is used only for the previously approved personal, non-commercial historical-backtest scope. These findings must not be used as real-time/manual trading signals or redistributed as source data.
