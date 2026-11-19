# Four-agent research reassessment and next data gate — 2026-11-19

## Scope

Four independent, read-only reviews were run across (1) crypto micro-OHLC, (2) crypto derivatives/flow data, (3) Korean stocks and ETFs, and (4) US stocks and ETFs. No strategy outcome labels were opened, no performance backtest was run, no external account or inquiry was created, and no market-data files were acquired in this round. This record does not amend any frozen preregistration.

## Decisions by domain

| Track | Evidence-based result | Current disposition |
|---|---|---|
| Crypto micro-OHLC | The existing micro ledger already covers next-candle direction, close location, expansion/compression, body dominance, sweep/reclaim, and 3m–15m replications. Its 22 primary M2 outcome cells did not meet the 80% target-first gate. Review found no supported, untested OHLC-only mechanism. | Do not add another candle-shape combination or retune exposed results. The current historical series cannot serve as independent OOS. |
| Crypto derivatives/flow | OI shock → unwind is potentially distinct from the prior funding/countertrend (R021), BTC shock/range break (R023), and order-book replenishment (R005/H3) families. OI content coverage, point-in-time contract epochs, availability timing, costs, a frozen rule, and an untouched OOS boundary are unresolved. R030 found 20/740 requested symbol-days absent and five checksummed but structurally incomplete archives; R031's exact `create_time + 5m` match covers 32 symbols on three recent dates and does not measure first-publication latency. | Candidate for data-readiness and novelty work only; no strategy registration or signal score yet. |
| Korea stocks/ETFs | Existing daily candidates and results do not establish the fixed return/risk/OOS gates. KIS/KRX data rights for local + personal-server copying, PIT listings/delistings, distributions/corporate actions, and reproducible vintage remain unverified. Intraday data is not required for daily/swing testing. | No result rerun. Resolve data rights and source semantics before any new test. |
| US stocks/ETFs | Prior US-01–52 and ETF/VIX research does not establish net CAGR ≥20%, MDD ≤30%, Sharpe ≥1, and ≥200 OOS round trips. Current-member/survivor universe, delisted coverage, corporate-action treatment, data-use rights, and source vintage remain unresolved. | No result rerun. Build the data-provenance gate from existing records; do not score the survivor cache again. |

The exact review evidence is in the existing [micro-candle ledger](crypto_microtrial_ledger_2026-11-19.md), [cross-market inventory](cross-market-strategy-inventory-2026-11-19.md), and the R026/R030/R031 OI records. Counts are not added across different units (outcome cells, symbol-days, events, and portfolio trades).

## Newly verified source path for microstructure research

Binance's official public-data README distinguishes USD-M `trades` archives from `aggTrades`: `trades` records are identified as originating from `/fapi/v1/trades` and contain individual trade ID, price, quantity, quote quantity, timestamp, and buyer-maker flag. The official helper documentation says trade archives can be requested by market type, symbols, and dates from 2020 onward. The same README documents daily/monthly archive publication and per-file SHA-256 sidecars. These statements establish a documented source path, **not** the existence, completeness, or exact reconstruction quality of any particular archive.

The existing fixed-sample `aggTrades` audit does not certify exact minute reconstruction: its 80 symbol-days had 4,317 base-volume mismatches, 6,845 underlying-trade-count estimate mismatches, and 31 unresolved daily volume totals. Therefore do not use that `aggTrades` sample as a validated minute-flow panel. A fixed `trades`-to-native-kline integrity audit is the next admissible source test before any event-sequence feature is considered.

Proposed audit boundary (not yet run): reuse the already frozen 20-symbol × four-date 80 symbol-day sample; verify archive/checksum presence and SHA-256, row schema, UTC-day bounds, ID ordering/duplicates/gaps, all 1,440 minute slots, and minute OHLCV/taker-volume/trade-count reconstruction against native USD-M 1m klines. Order same-timestamp prints by trade ID. Keep missing or defective files in the denominator; do not impute or replace them. Passing would establish only this tested data-integrity scope, not a predictive edge. Before opening outcome labels, an independent novelty review must show that a proposed within-minute sequencing feature is structurally different from prior taker-flow studies and R005.

## Data-use boundary

The current Binance Vision Dataset Terms state that permitted use includes purely personal, non-production historical backtesting, while prohibiting live proprietary execution and compensated third-party signal distribution. Derivative work redistributed from these datasets is subject to attribution and CC BY-NC-SA 4.0. The terms were last updated 2026-08-26; recheck them before any new acquisition or publication. This project may not use Vision history for real-time/manual signal delivery. Do not commit raw archives; before publishing data-derived results, preserve the required attribution/license and confirm repository compatibility.

## Next bounded actions

1. Independently approve the fixed raw-`trades` archive integrity protocol; no performance metrics in this gate.
2. If the source gate passes, perform a separate novelty review of one within-minute event-sequence hypothesis against all prior taker-flow and order-book work. Register the exact rule before reading its target/stop path.
3. If the source gate fails, do not rescue it by relabeling `aggTrades`; evaluate the distinct OI data-readiness track, still without outcomes, or report the remaining source blocker.
4. For KR/US, proceed only with rights/PIT/corporate-action evidence; do not contact data providers or open accounts under this round.

No candidate has passed the user's performance gates. This round advances the research by narrowing the next source test; it does not claim a winning strategy.

## External primary sources

- Binance Public Data README: <https://github.com/binance/binance-public-data/blob/master/README.md>
- Binance Public Data helper README: <https://github.com/binance/binance-public-data/blob/master/python/README.md>
- Binance Vision Dataset Terms: <https://github.com/binance/binance-public-data/blob/master/TERMS_AND_CONDITIONS.md>

Data-derived findings in this document are attributed to Binance Vision and licensed under CC BY-NC-SA 4.0. This file-level license does not relicense unrelated repository code.
