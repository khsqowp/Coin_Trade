# R027 — Reproduce reported Vision archive defects

Status: bounded historical data-quality audit; **not a strategy trial**.

## Question

Do selected current Binance Vision USD-M daily archives reproduce the missing/duplicate timestamp and missing-field defects reported in the public `binance-public-data` issue #484, and does the issue's closed status prove all cited cases were fixed?

## Frozen sample

- Metrics: BTCUSDT and ETHUSDT on 2024-02-16, 2024-04-08, 2024-05-01, and 2025-07-22.
- Mark-price klines: BTCUSDT and ETHUSDT, 5m, on 2023-11-10.
- Ten ZIP files total, each verified against its adjacent publisher `.CHECKSUM` file.
- The files were downloaded on 2026-11-17 to `/private/tmp/r027_binance_archive_repro/`; no raw archive was committed.

## Checks and decision criteria

1. Reject any archive whose SHA-256 does not match its publisher checksum.
2. For daily 5m files, compare timestamps against the UTC 00:00–23:55 grid: 288 expected points, with missing slots, duplicate rows, and off-grid timestamps reported separately.
3. For each metrics field, count blank and non-finite/non-numeric values; do not impute or forward-fill.
4. Treat only exact archive contents as evidence. A GitHub issue's status or aggregate summary is not a substitute for current object inspection.
5. Do not calculate signals, labels, returns, or performance; do not infer a broad cohort-wide defect rate from these selected dates.

## Evidence source

The sample dates are anchored to the reported missing periods and duplicate timestamps in [Binance public-data issue #484](https://github.com/binance/binance-public-data/issues/484). The issue is a user-submitted report in Binance's public repository, not a Binance specification or a confirmation that all archive defects were corrected.
