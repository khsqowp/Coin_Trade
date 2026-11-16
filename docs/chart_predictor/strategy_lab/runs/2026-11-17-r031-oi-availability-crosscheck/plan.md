# R031 — multi-symbol recent OI timestamp cross-check

Date: 2026-11-17 (Asia/Seoul)

Status: preregistered source-semantics validation only; not a strategy trial.

## Question and hypothesis

Check whether the Vision USD-M daily-metrics `sum_open_interest` labels across a broad symbol sample align with the USD-M OI-statistics REST endpoint at `create_time + 5 minutes`, as previously observed for BTCUSDT and ETHUSDT. The frozen hypothesis is a timestamp-label alignment, not a claim of the exact first-publication latency or predictive value.

## Frozen sample

- Symbols: all 37 symbols selected for the R029/R030 OHLCV seed cohort, read from the versioned R030 manifest. No symbol substitution.
- UTC dates: **2026-11-04, 2026-11-08, 2026-11-12** (three fixed, nonconsecutive dates inside the currently documented one-month REST history window).
- Maximum requested pairs: 37 × 3 = **111 symbol-days**. A missing archive, unsupported symbol, empty REST response, or contract no longer trading remains a recorded unavailable sample, not an exclusion followed by replacement.

## Frozen procedure

1. Obtain the Vision daily `metrics` ZIP and adjacent publisher `.CHECKSUM` for each symbol-day. Verify ZIP SHA-256 before parsing.
2. Query only the public, read-only USD-M `GET /futures/data/openInterestHist` endpoint with `period=5m`, bounded start/end times covering that UTC date, and `limit=500`. No API key, account endpoint, order, or live signal is involved.
3. For each metrics `create_time`, compare `sum_open_interest` against REST `sumOpenInterest` at offsets −5, 0, and +5 minutes. Preserve exact timestamps, total REST rows, exact matches, relative-error summaries, and unmatched grid slots.
4. Report complete denominators by symbol-day; do not fill REST gaps, interpolate, alter the date set, or infer the exchange's actual first dissemination time from the timestamp match.

## Decision boundary

- This checks cross-path timestamp semantics for these recent dates only. Both paths are published by Binance and are not independent exchange observations.
- The REST documentation states that only the latest one month is available and that no-trade periods can be omitted. Handle returned gaps as missing observations, not zero OI.
- A successful `+5m` alignment permits only a conservative period-end label for these observations; it does not validate every historical date, all fields, delisted contracts, or arrival latency.
- No signal, label, target/stop outcome, candidate rule, or performance metric may be computed. OOS crypto acceptance remains target-first ≥80% over at least 200 non-overlapping events; deadline-close direction accuracy remains separate.

## Sources and implementation

- Binance USDⓈ-M OI statistics documentation: `https://developers.binance.com/docs/derivatives/usds-margined-futures/market-data/rest-api/Open-Interest-Statistics`.
- Binance Vision daily USD-M metrics and publisher checksums.
- Existing local semantics validator: `scripts/research/verify_vision_metrics_timing.py`.
- Raw inputs remain outside Git under `/private/tmp/r031-oi-availability-crosscheck/`.
