# R028 — fixed quarterly sample of USD-M metrics archive quality

Date: 2026-11-17 (Asia/Seoul)
Status: preregistered data-source/quality audit only; not a strategy trial.

## Question

Does a fixed, time-stratified sample of the Binance Vision USD-M daily `metrics` archives provide continuous 5-minute OI fields across multiple years and several long-lived contracts, or do missing rows/fields make the proposed OI inventory-shock research path unusable without further exclusions?

## Frozen sample

- Symbols: `BTCUSDT`, `ETHUSDT`, `BNBUSDT`, `XRPUSDT`.
- Dates: first UTC day of each calendar quarter from 2021-01-01 through 2026-10-01, inclusive: 24 dates per symbol, 96 symbol-days total.
- This is a deterministic coverage sample, not an assertion that these were the full eligible futures universe at every date.
- Previously sampled exact dates are excluded by construction: 2023-11-10, 2024-02-16, 2024-04-08, 2024-05-01, 2025-07-22, and 2026-10-31 through 2026-11-02.

## Frozen checks

For each daily ZIP and publisher checksum: record HTTP result, checksum match, CSV columns, row count, duplicate/off-grid/missing 5-minute timestamps against the expected UTC day, blank/non-finite values by field, and symbol/date consistency. Do not fill or interpolate gaps. Preserve raw files outside Git. Stop and record unavailable objects rather than substituting REST data.

## Decision boundary

- No trading signal, target/stop outcome, strategy parameter, or performance metric may be computed from this audit.
- A passing sample means only that these sampled archives are internally usable for the audited fields/dates. It does not prove archive-wide completeness, historical contract identity, real-time availability, data-use rights beyond the existing historical personal backtest scope, or OOS eligibility.
- Any archive-level defect requires a broader field-specific audit before any registered performance trial. A 96-day sample cannot authorize the target-first ≥80%, N≥200 OOS claim.

## Inputs and output location

- Source: public Binance Vision USD-M daily `metrics` archives and adjacent `.CHECKSUM` files.
- Raw download/output location: `/private/tmp/r028-vision-metrics-quarterly-coverage/`; do not commit downloaded market data.
- Archive-quality implementation: `scripts/research/audit_vision_daily_archive.py`.
