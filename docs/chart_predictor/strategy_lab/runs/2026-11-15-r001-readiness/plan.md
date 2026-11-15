# R001 — Strategy-lab readiness gate

Status: `blocked_data_gate` — preflight only; zero strategy-performance cells run.

## Question

Can the repository's existing data support a fair, cost-adjusted portfolio Buy-and-Hold comparison for the requested search for two robust strategies?

## Existing evidence and non-duplication

- The study objective is portfolio net CAGR and risk versus matched Buy-and-Hold; it is not the M4 ≥80% selective signal-accuracy target in `docs/chart_predictor/SPEC.md`.
- P5–P9 are intraday setup experiments on the July–October 2026, volume-ranked futures universe. Their signal/trade results do not establish account-level portfolio performance versus Buy-and-Hold. They will not be repeated as this study.
- The MACD(12,26) zero-cross + RSI(14)>50 long experiment is already recorded in `artifacts/macd_zero_rsi_20261115/` and preregistered in `docs/research/macd_zero_rsi_backtest_prereg_20261115.md`. In its first 70% development segment it had 537 signals/trades per exit rule; all five exits had negative mean net R and PF below 1. No exit qualified, so its conditional later segment was not opened. This is not a new strategy-lab result and will not be retested here.

## Data under review

1. `chart_predictor/data/vision_dev_repaired.sqlite` (external local ignored input; read-only): 19,790,858 1-minute rows, six symbols (BNB, BTC, DOGE, ETH, SOL, XRP), roughly 2020-01 through 2026-06. The 2026-11-15 audit reports no missing minutes within observed spans, duplicate keys, off-grid timestamps, invalid OHLCV, or nulls. Its published fingerprint `2b421901d3777f6127c90772b090341b3947046c71d4e15e45ccf00e557c438a` covers schema and per-symbol coverage metadata, not all candle content.
2. The six names are current survivors, not a point-in-time investable universe. Long-history portfolio comparisons on this set are exposed to survivorship/selection bias.
3. This database is USDⓈ-M perpetual OHLCV; the audited schema does not include payable funding cashflows. Funding is a material holding cost and cannot be represented as measured from these rows. Slippage, spread, and market impact also require explicit assumptions or quote/trade data.
4. `chart_predictor/data/candles.sqlite` contains 100 symbols over observed spans in July–November 2026. It is too short for the requested long-horizon robustness and does not supply historical point-in-time universe membership.
5. Current worktree lacks these ignored database files; the metadata above comes from the dated audit in the source checkout, not a fresh content-level verification in this worktree. No database was opened or performance metrics calculated for this run.

## Frozen analysis choices

- No returns, strategy metrics, grid, or candidate selection are calculated in R001.
- Do not access a sealed segment until a strategy study has a preregistered universe, exact half-open dates, fee/slippage/funding model, capital and cash rules, rebalance/execution rules, development/validation/sealed boundaries, full parameter grid, metric definitions, multiplicity correction, and decision thresholds.
- Existing files and prior trial records are read-only evidence. Do not overwrite or relabel them.
- No public data were downloaded in R001. Any follow-up acquisition first records source terms, exact symbols/fields/window, purpose, expected size, hashes, and separate destination.

## Gate decision

The repaired futures dataset is suitable for descriptive, explicitly survivor-biased OHLC research, but it is **not sufficient for a qualifying net portfolio-vs-Buy-and-Hold result**: funding is absent, the universe is not point-in-time, and the content fingerprint is incomplete. A spot dataset would remove perpetual funding from the accounting but would not resolve delistings or point-in-time universe construction on its own. Therefore no parameter grid is preregistered against this inadequate input and no performance test was run.

## Next-step requirements

Before any grid is run:

1. Choose and document either (a) a point-in-time spot universe with a delisted-symbol history, or (b) a point-in-time perpetual universe plus a complete funding-settlement series; avoid mixing these instrument types in one baseline.
2. Verify raw content hashes, exact coverage, listing/delisting dates, missing bars, and all schema fields. Store new data separately from existing databases.
3. Set comparable B&H treatment: same universe/period/capital, cash and delisting handling, rebalance timing, fee/slippage assumptions, and no leverage in the headline comparison. State any exposure difference.
4. Design distinct hypotheses from the existing 239-configuration catalog and P5–P9 catalog; reject nominal renamings or small boundary edits. Freeze one complete coarse grid per study before calculating any strategy result.
5. Run smoke checks only for code/schema correctness. Then execute the full preregistered grid once, retain every cell, and keep the sealed period untouched until one final candidate evaluation.

## Public-source investigation (read-only, 2026-11-15)

- Binance Vision documents downloadable daily/monthly public archives and spot klines sourced from its public kline endpoint; its README says all symbols are supported and provides per-archive checksums. This makes a separate spot snapshot technically plausible, but does not by itself prove a complete delisted-symbol point-in-time universe. See [Binance Public Data README](https://github.com/binance/binance-public-data/blob/master/README.md).
- Binance's published Vision dataset terms state that the data and derived data are CC BY-NC-SA 4.0, restrict use to enumerated non-commercial uses (including purely personal, non-production historical backtesting), and prohibit live proprietary execution, commercial order generation, and compensated third-party signal distribution. Any future data acquisition and output handling must remain within those terms or use a separately licensed source. See [Binance Vision Dataset Terms](https://github.com/binance/binance-public-data/blob/master/TERMS_AND_CONDITIONS.md).
- Binance USDⓈ-M developer docs expose a public funding-rate-history endpoint. This confirms a possible official source, not that the currently audited DB includes funding or that the public endpoint/archive provides a complete payable-settlement history for every delisted contract. That completeness must be demonstrated before using perps for qualifying results. See [USDⓈ-M Futures market-data documentation](https://developers.binance.com/docs/derivatives/usds-margined-futures/market-data/rest-api/Get-Funding-Rate-History).
- No data were downloaded, and the terms were not interpreted as legal advice. Source scope and licensing remain a data-acquisition gate.

## Validation checklist

- [x] Prior tests checked before proposing a repeat.
- [x] Strategy-lab metric separated from M4 signal accuracy.
- [x] Existing-data limitations and provenance qualification documented.
- [x] No strategy metrics calculated before an adequate preregistration/data gate.
- [x] No ignored data or credentials read, changed, or added to Git.
- [ ] Suitable point-in-time data and cost inputs acquired and audited.
- [ ] Full strategy grid preregistered and executed.
- [ ] Independent accounting/falsification and sealed evaluation completed.

R001 is complete as a readiness audit only. The overall objective remains in progress (0/2 qualifying strategies).
