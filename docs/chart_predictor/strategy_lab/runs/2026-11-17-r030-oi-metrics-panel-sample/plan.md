# R030 — fixed broad-panel OI metrics archive quality sample

Date: 2026-11-17 (Asia/Seoul)

Status: preregistered source-quality audit only; not a strategy trial.

## Question

Do a fixed sample of daily USD-M `metrics` archives provide intact 5-minute OI series across the selected OHLCV seed cohort and several years, or are there archive/content defects that require stronger field-level exclusions before any OI-based strategy can be registered?

## Frozen sample

- Symbols: the exact 37 symbols whose local 1-minute archive row counts cover all 70 months from 2021-01 through 2026-10 in `chart_predictor/data/vision_pit_dev_sample.sqlite`. The cohort is availability-selected, not a point-in-time eligible futures universe.
- Dates: `2021-12-01`, then every three months on day 1 from `2022-03-01` through `2026-09-01`, inclusive. This yields 20 dates per symbol and **740 fixed symbol-days**.
- The set, cadence, archive fields, and pass/fail checks are fixed before downloading these 740 sample archives. Do not replace absent dates or symbols with alternatives.
- This schedule is separate from R028's Jan/Apr/Jul/Oct sample dates. R028 may be used as background only; do not silently mix its archives or findings into R030's denominator.

## Frozen checks

For each requested symbol-day, record object status for both ZIP and publisher `.CHECKSUM`, download only when both objects exist, and verify SHA-256. For each acquired archive, record symbol/date consistency, CSV schema, row count, expected 288 five-minute UTC slots, duplicate timestamps, missing/off-grid timestamps, and blank/nonfinite values by field. Do not interpolate, forward-fill, or substitute REST data. Distinguish absent objects, failed downloads, checksum mismatches, and malformed contents.

## Decision boundary

- Do not compute signals, labels, target-first rates, directional accuracy, returns, or strategy parameters.
- A clean fixed sample is evidence only for the sampled files/fields, not proof of full archive completeness, historical contract identity, OI availability time, executable costs, or OOS performance.
- Any sample defect must be reported and must not be excluded from the denominator without an explicit reason. Preserve raw downloads outside Git.
- Crypto promotion remains OOS target-first precision ≥80% with at least 200 non-overlapping events; deadline-close direction accuracy is reported separately. No performance claim is in scope for R030.

## Source and artifacts

- Public source: Binance Vision USD-M daily `metrics` ZIPs and adjacent `.CHECKSUM` files, within the previously approved personal, non-commercial, historical-backtest-only use.
- Validator: `scripts/research/audit_vision_daily_archive.py`.
- Raw files: `/private/tmp/r030-oi-metrics-panel-sample/`; never commit raw market data.
