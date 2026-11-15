# BTC 1m three-candle streak — result

Decision: reject this fixed setup. It does not approach the 80% precision target, and its fee/slippage-adjusted expectancy is negative. This is an exploratory development-data test, not OOS evidence.

## Run

The read-only input was chart_predictor/data/vision_dev.sqlite, BTCUSDT, exclusive cutoff 2026-10-09T00:00:00Z. The eligible cache contained 3,417,120 continuous 1m rows from 2020-01-01 through 2026-06-30. Its SHA-256 fingerprint over ordered used timestamps and OHLC columns is 0e612b0c58c2edf68b60a17e0a165402834c811c0cad87a12dec934ea7e2ecaf.

The single fixed rule generated 177,025 non-overlapping trades over 2,373 UTC calendar days:

| Measure | Streak rule | Same-anchor always-long baseline |
|---|---:|---:|
| Target-first rate | 47.67% | 48.95% |
| 95% Wilson lower bound | 47.44% | — |
| 7-calendar-day moving-block 95% interval, target-first | 47.39–47.95% | — |
| Direction correct at 15-bar expiry | 47.77% | — |
| Net-positive trade rate | 8.52% | 8.86% |
| Mean net return per trade | −0.1444% | −0.1412% |
| 7-calendar-day moving-block 95% interval, mean net | −0.1455% to −0.1435% | — |

The outcome model uses 1×ATR14 stop and target, a 15-bar expiry, stop-first same-minute ties, and adverse stop-gap fills. Round-trip costs are 0.10%; separate round-trip slippage is 0.04%. The 7-day intervals use circular moving blocks over a complete UTC-day grid, including days with no trades. The previous ephemeral agent output used a day-cluster bootstrap; these report intervals are recalculated with the stated 7-day block method.

The point estimate is below the same-anchor always-long target-first baseline. The Wilson lower bound is far below the frozen 80% gate. Net expectancy is negative and slightly worse than the baseline. No M4 calibration or confidence threshold was tested; the rule does not qualify as a high-confidence selectable signal.

## Reproduction and limits

Run from the repository root:

    PYTHONDONTWRITEBYTECODE=1 /opt/anaconda3/bin/python3 scripts/research/crypto_round11_streak_probe.py
    PYTHONDONTWRITEBYTECODE=1 /opt/anaconda3/bin/python3 -m pytest -p no:cacheprovider -q tests/test_crypto_round11_streak_probe.py

Source is [crypto_round11_streak_probe.py](../../scripts/research/crypto_round11_streak_probe.py); aggregate output is [crypto_round11_streak_results_20261115.json](crypto_round11_streak_results_20261115.json). The focused tests cover future-prefix invariance, missing-minute signal rejection, same-minute stop-first resolution, and adverse stop-gap fills.

The data window ends 2026-06-30, before the SPEC's 2026-06 model-knowledge boundary by only a short margin. Prior research already inspected the same development cache, so this is not a sealed sample. The fixed BTC-only rule is one of many tested ideas; no multiple-testing adjustment makes it promotable. Funding, leverage, liquidation, spread, and live fills are not modeled. Do not tune this cache after seeing these results.
