# Binance raw-trades ↔ 1m-kline checker implementation audit — 2026-11-19

## Scope and result

This is a synthetic-only implementation check of `scripts/research/audit_binance_trades_kline_reconciliation.py` against frozen preregistration v4 in `binance-trades-kline-integrity-prereg-2026-11-19.md`. No Binance archive, market outcome, forecast label, or strategy result was accessed. The 80-symbol-day source-integrity audit remains unrun.

An independent read-only review found two specification gaps before any source archive was acquired:

1. OHLC mismatch counts used only the intersection of native-active and raw-active minutes. A native-active minute with no raw-trade bucket was omitted from the OHLC denominator, despite the preregistration requiring one-sided minutes to remain mismatches.
2. The report contained only active-minute counts and did not retain the exact native/raw active-minute sets, their differences and union, or timestamp range evidence.

## Changes made

- OHLC now evaluates every native-active minute; a missing raw bucket is counted as a field mismatch.
- Per symbol-day output now records sorted native-active, raw-active, native-only, raw-only, and union minute timestamps in epoch milliseconds.
- Integrity output now records minimum and maximum parsed raw-trade timestamps and native-kline open timestamps.
- Added a deterministic synthetic 1,440-minute fixture with two raw trades in one active minute. The tests cover successful OHLCV/taker reconstruction, full-grid zero minutes, a taker-buy-quote mismatch, and a native-only active minute's OHLC denominator and set diagnostics.

The preregistration remains unchanged and frozen. These tests validate checker behavior only; they do not establish Binance archive integrity or any predictive property.

## Verification

Command:

```text
/opt/anaconda3/bin/python3 -m pytest chart_predictor/tests/test_binance_trades_kline_integrity.py -q
```

Result: **3 passed**. `py_compile` for the checker and new test, and `git diff --check`, also passed. No raw archive downloads were attempted. At check time `/Volumes/HDD2TB/Trade` was not mounted; `/private/tmp` had 50 GiB available. This note does not claim that the fixed audit has run or that the sample is stored durably.
