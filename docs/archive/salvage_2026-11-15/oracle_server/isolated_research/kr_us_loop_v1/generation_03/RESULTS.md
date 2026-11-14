# Generation 03 — OHLC/volatility candidates

Run: `GEN03-20261106T094011-28550` · 2026-11-06 UTC  
Preregristration: `PREREG.md`  
Ledger: `attempts_GEN03-20261106T094011-28550.jsonl` · Curves: `equity_curves_GEN03-20261106T094011-28550.csv.gz`  
Manifest: `manifest_GEN03-20261106T094011-28550.json`

## Outcome

Ten candidate-market attempts were planned. Ledger integrity is true: 10 starts, 5 completions, 5 failures, 10 unique terminal IDs. All five US screens completed; all five KR attempts failed the pre-execution raw OHLC integrity gate. No candidate qualified as valid.

Annualized net CAGR (%). US SPY: 5.22 IS / 14.84 later. Later is previously inspected and contaminated, not independent confirmation.

| Candidate | US IS | US later | US later MDD | Decisions (IS/later) |
|---|---:|---:|---:|---:|
| FRAMA16_SLOPE5 | 1.60 | 12.14 | -24.14 | 192 / 119 |
| VORTEX14_SMA100 | 2.69 | 9.72 | -26.10 | 192 / 119 |
| ICHIMOKU_CURRENT_CLOUD | 4.46 | 8.87 | -33.50 | 192 / 119 |
| DCTC_GAP_INTRADAY63 | 5.91 | 11.53 | -34.91 | 192 / 119 |
| VOL_COMPRESSION_RELEASE55 | 10.27 | 11.10 | -40.68 | 192 / 119 |

The compression-release breakout led this small fixed screen in US IS CAGR, but returned 11.10% in the contaminated later period versus SPY 14.84%, with -40.68% maximum drawdown. It is not a pass. No threshold or formula was tuned after observing these figures.

## Korean attempts and integrity stop

All five KR rows have status `FAILED` at `market_setup_or_benchmark`; no KR strategy calculation was run. The preflight read all 3,236 parquet files and found 28 traded rows with invalid OHLC, including `008080` with volume-positive rows where close/low are zero. The shared inferred split-repair routine is already known to transform this source into zero closes and infinite/NaN volumes, so the runner blocks before calling that loader. The five failures are preserved individually in the ledger. Do not infer KR performance from Gen01/Gen02 KR records either; those runs used the defective loader.

## Method verification and limits

- Independent pre-run code review found and required fixes for KR gating, FRAMA warm-up/signals, Ichimoku cloud exit parity, and missing-OHLC handling. After fixes, independent review cleared the runner and synthetic tests passed.
- Strict simulator rejects a held security without a valid open/close mark and rejects a new entry without a complete executable bar. US candidates completed under this stricter policy; the ledger is the source for exact attempts and metrics.
- Synthetic tests passed for all five feature paths, long-only/unlevered weights, next-open simulation, randomized future-price perturbation invariance, month-end-only state, FRAMA persistent-trend signal and post-gap recovery, and fail-closed missing-price behavior.
- US remains exploratory: the later partition was previously inspected, only 688 of about 1,209 PIT tickers have local prices, and prior global trial count is unknown. No DSR/PSR or multiple-testing correction is claimed.
- These US results add five local strategy tests to an incomplete historical search. A high IS result or a good-looking drawdown is not evidence of a durable edge.
