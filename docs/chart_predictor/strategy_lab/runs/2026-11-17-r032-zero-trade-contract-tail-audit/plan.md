# R032 — retrospective data-validity diagnostic

Date: 2026-11-17 (Asia/Seoul)

Status: post-hoc diagnostic prompted by R030/R031 anomalies; not preregistered and not a strategy-performance trial.

## Question

Can complete, checksum-valid Binance Vision OHLCV rows after futures settlement be treated as tradable observations, and do current replay paths enforce trade activity?

## Frozen diagnostic procedure

1. Use official Binance futures settlement notices for the already identified ALPHA, BLZ, REN, BAL, and ICX symbols; do not infer settlement time from current exchange metadata.
2. For ALPHA, BLZ, and REN, compare one fixed 1m day immediately before settlement with one fixed day after settlement using Binance Vision ZIPs and publisher checksums. Record every requested object, checksum result, timestamp grid, trade count, volume, and close range. Do not replace missing samples.
3. Query the local Vision-derived candle database read-only for each symbol's last candle with trades, final stored timestamp, and zero-trade row count.
4. Inspect current resampling, signal generation, and event execution code for explicit trade-validity checks. Do not change code or rerun strategy metrics in this diagnostic.
5. Report the boundary between proven data defects and performance impact not yet measured.

## Limits and decision boundary

- The three before/after daily samples demonstrate the defect for those exact contracts/dates only; they do not characterize every historical Vision file.
- A zero-trade row with copied OHLC is not evidence that an order could have executed at those prices. However, filtering it safely requires explicit semantics for signal bars, entries, stop/target touches, and timeout valuation; a simplistic volume filter can introduce gaps or bias.
- The five-symbol local tails and official settlement points establish a high-priority contract-epoch issue, not the numerical size or direction of any strategy-performance error.
- No strategy score, threshold search, parameter tuning, or OOS outcome inspection was performed for R032.

## Sources and inputs

- Binance Vision USD-M 1m Kline archives and publisher `.CHECKSUM` files.
- Official Binance notices linked in `report.md`.
- Read-only local DB: `chart_predictor/data/vision_pit_dev_sample.sqlite`.
- Code inspected: `scripts/research/crypto_exhaustive_consensus.py`, `chart_predictor/resample.py`, and `chart_predictor/setup_backtest.py`.
- Raw probe data remains outside Git at `/private/tmp/r032-contract-epoch-probe/`.
