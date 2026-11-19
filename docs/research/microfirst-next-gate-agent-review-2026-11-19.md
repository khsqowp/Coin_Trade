# Micro-first next-gate independent review — 2026-11-19

**Disposition: no new performance trial is justified from the current evidence.** Four independent agents reviewed the next admissible stage: a crypto candidate review, crypto red-team, Korea stock/ETF data-and-candidate review, and US stock/ETF data-and-candidate review. No market rows, candle values, trade outcomes, or result JSON were used in this review round; no data was downloaded and no backtest ran.

## Crypto

- The candidate reviewer found no justified new 1-minute OHLC hypothesis after the registered Phase 0–8 sequence and the existing taker-flow, order-book, funding, and cross-asset candidate families. The recommendation is source/field/time/integrity feasibility for event-level `trades`/`aggTrades`, not an invented candle blend.
- The red-team rejected using the exposed 1-minute Phase 0–8 history to tune a new 80% M2 rule. Any eventual claim must freeze one candidate and all barriers before a fresh, chronological OOS interval; count all emitted signals in M2; keep timeout as failure; require ≥200 non-overlapping OOS signals and the frozen symbol/family gates; and use executable entry, costs, dependency-aware inference, and multiplicity control.
- The local 1-minute database is development-only and gapped; the 20-symbol event capture lasted 120 seconds and had no signals/orders or injected reconnect. Its file hash was verified against its manifest, but it is not a strategy test or recovery test. The NAS destination was not mounted during the local check. Full metadata is in [`crypto-microdata-readiness-2026-11-19.md`](crypto-microdata-readiness-2026-11-19.md).
- Binance Vision's current terms permit personal non-production historical backtesting, not the project's live/manual alert use. Preserve the user's historical-only approval; a future live/manual signal source must be independently eligible. The official format/terms are linked from the readiness record.

## Korea and United States

- Korea: no nonduplicative strategy candidate was advanced. The pending weekly top-two ETF momentum proposal uses the same 126-session momentum family as the already examined top-three ETF rotation. KRX public material did not establish a complete point-in-time/delisted universe, total-return corporate-action treatment, or local/Linux retention rights. No account, API key, sample request, purchase, or backtest was initiated.
- United States: no nonduplicative candidate was advanced. A 12–1 common-stock momentum proposal overlaps the existing momentum exploration; the public Databento sample does not establish delisted/PIT completeness or permission for persistent local-plus-Linux copies. No account, API key, sample request, purchase, or backtest was initiated.
- Both equity-market performance tracks remain gated on licensed daily histories with point-in-time membership, inactive securities, splits/distributions, source lineage, and permitted storage. Their already frozen performance goals remain net CAGR ≥20%, MDD ≤30%, Sharpe ≥1.0, and ≥200 closed OOS round trips per market.

## Updated next admissible work

1. The metadata-only screen is now complete: all 20 frozen USD-M contracts have a published 2026-10 `aggTrades` archive, totaling 2,040,955,218 compressed bytes (1.90 GiB). No body was downloaded; 18/20 contracts already have that month in the local 1m development panel. Detailed evidence is in [`crypto-microdata-readiness-2026-11-19.md`](crypto-microdata-readiness-2026-11-19.md).
2. A separate two-agent literature/novelty review of event-level mechanisms is pending. Download only if that review identifies a distinct candidate, the OOS protocol is preregistered, and storage rights/cap/destination pass. Do not use Binance Vision-derived signals for live/manual output.
3. If no distinct candidate survives, do not expand the exposed OHLC grid or download multi-gigabyte archives merely to generate more tests. Reserve future eligible data for chronological OOS, after an archive destination and capture cap are verified.
4. Do not retune old thresholds or relabel the fixed-expiry selective-prediction paper as target-first evidence.
