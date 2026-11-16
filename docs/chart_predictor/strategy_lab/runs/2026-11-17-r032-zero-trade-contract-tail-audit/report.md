# R032 — zero-trade synthetic candle tails and contract-epoch audit

**Decision: block performance interpretation of the historical all-symbol consensus replay until zero-trade bars and contract epochs are handled.** A complete timestamp grid and publisher-valid checksum do not establish executable market prices: three official post-settlement Binance Vision 1m samples contain 1,440 rows of zero volume/zero trades with a constant close, and the currently inspected exhaustive replay does not filter those rows.

## Evidence

- Directly downloaded six Binance Vision USD-M 1m Kline ZIPs and publisher checksums for pre- and post-settlement days of ALPHAUSDT, BLZUSDT, and RENUSDT. All six checksum pairs passed; all six contained exactly 1,440 unique, on-grid timestamps.
- Each pre-settlement sample had 1,440 candles with trades and positive volume. Each post-settlement sample had **1,440/1,440 bars with zero trade count and zero volume**, plus a constant close throughout the UTC day:

| Contract | Official futures settlement (UTC) | Sample day | Bars | Zero-trade bars | Close range |
|---|---|---|---:|---:|---:|
| ALPHAUSDT | 2025-09-23 09:00 | 2025-09-22 pre | 1,440 | 0 | 0.01431–0.04181 |
| ALPHAUSDT | 2025-09-23 09:00 | 2025-12-01 post | 1,440 | 1,440 | 0.02027–0.02027 |
| BLZUSDT | 2024-12-23 09:00 | 2024-12-22 pre | 1,440 | 0 | 0.06568–0.07433 |
| BLZUSDT | 2024-12-23 09:00 | 2025-03-01 post | 1,440 | 1,440 | 0.06836–0.06836 |
| RENUSDT | 2024-12-03 09:00 | 2024-12-02 pre | 1,440 | 0 | 0.04424–0.05158 |
| RENUSDT | 2024-12-03 09:00 | 2025-03-01 post | 1,440 | 1,440 | 0.04800–0.04800 |

- Official Binance notices confirm the three settlement timestamps: [ALPHA](https://www.binance.com/en/support/announcement/detail/10fd115c29244067bd4566a70f77e327), [BLZ](https://www.binance.com/en-BH/support/announcement/detail/b140faee7cf9482cb10257308abda245), and [REN](https://www.binance.com/en-GB/support/announcement/binance-will-delist-gft-iris-key-oax-ren-on-2024-12-10-131b75b63a71490393034f36de70c92c).
- Binance's official ICX notice independently confirms the cohort's final contract settlement at 2026-08-26 09:00 UTC: [ICX futures delisting notice](https://www.binance.com/en/support/announcement/detail/d72915ed7a60473b92f0818d959a227a). For BAL, Binance's delisting-vote notice confirms futures settlement at 2025-04-14 09:00 UTC: [BAL and other contracts notice](https://www.binance.com/en/support/announcement/detail/fac9c3e401da4cc8b604566fd261d70c).
- Read-only local SQLite audit found long zero-trade tails through 2026-10-31 23:59 UTC: REN 697.6 days, BLZ 677.6 days, BAL 565.6 days, ALPHA 403.6 days, and ICX 66.6 days after each symbol's last traded candle. The local database held 3,067,200 rows per symbol; the corresponding zero-trade row counts were REN 1,006,749, BLZ 979,066, BAL 825,648, ALPHA 584,694, and ICX 133,566.
- R030 had already reported full-grid, checksummed metrics objects after official settlement for ALPHA, BLZ, and REN, containing one or two rows with zero OI. R031 then confirmed missing recent archive/REST observations for all five symbols, but neither report had joined contract epochs to executable candle evidence.

## Impact on replay validity

- `scripts/research/crypto_exhaustive_consensus.py` selects `volume`, `quote_volume`, and `trade_count`, but does not use them to gate signal bars or executable paths. It passes all historical OHLC rows into the resampler and barrier evaluator. Thus any result from this script that includes these tails is not validated against tradable observations.
- `chart_predictor/resample.py` requires a complete timestamp bucket, not a complete bucket of traded bars. It sums zero trade/volume rows and carries their constant OHLC into aggregated candles. A complete bucket can therefore still be synthetic/non-executable.
- `chart_predictor/setup_backtest.py` also loads `trades` and `v` without explicit zero-trade gating in the inspected path. Its present universe is a recent top-volume list and may not include these five delisted contracts; this audit does not claim those contracts actually enter its current sample. Its historical candle execution semantics still need an explicit validity policy before results are generalized.
- This audit changes no earlier report or result. It invalidates the assumption that timestamp completeness/checksum validity alone proves executable-price validity; it does not establish that any strategy's numerical result changes, which requires a fresh, frozen replay.

## Decision and next controlled test

- Mark affected all-history strategy rankings as **provisional / not admissible for selection** until replays exclude or explicitly invalidate post-epoch observations.
- Reconstruct contract epochs from official futures listing/delisting notices and observed trade activity; retain unknown boundaries as unknown. Never infer zero OI or tradability from absent files or constant-price rows.
- Define execution validity before rerunning: entry must occur on a traded executable bar; a no-trade interval inside the outcome horizon must not be treated as a filled barrier or a valid timeout mark. Preserve gaps; do not interpolate. Record omitted/invalid events and coverage by symbol, timeframe, and epoch.
- Rerun the frozen candidate set and report paired old/new event counts, target-first rate with Wilson interval, timeout/direction accuracy, costs, and all symbols/periods lost to data validity. Do not retune rules during this diagnostic rerun.
- No strategy performance was computed in R032. Crypto acceptance remains target-first ≥80% on at least 200 non-overlapping OOS events; deadline-close direction accuracy is separate. Stock/ETF backtests remain NO-GO pending licensed point-in-time total-return data and usage-rights confirmation.

## Reproducibility

Raw daily ZIPs, publisher checksum files, and `probe.json` are preserved outside Git under `/private/tmp/r032-contract-epoch-probe/`. Local SQLite was queried read-only. The exact per-file hashes, row counts, and pre/post sample statistics are in the raw probe record; no source database or strategy code was modified.
