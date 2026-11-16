# Round 5 continuation — cross-market research status (2026-11-17)

## Decision snapshot

No strategy passes the user-fixed objective yet: KR strategies `0`, US strategies `0`, qualified crypto signals `0`. This is a source/eligibility continuation, not a strategy-performance test. No stock/ETF or crypto outcome labels were calculated in this continuation.

## Four-role review

| Role | Finding | Decision |
|---|---|---|
| Korea researcher | KR-02 KOSPI 200 reconstitution is mechanically distinct from ordinary price/volume signals, but its current status is conditional only. PIT constituent notices, inactive/delisted names, and price history are not established. KRX's public index-product and API catalog descriptions are the next source documents to inspect. | No backtest or promotion. |
| US researcher | None of the five conditional US candidates is data-ready. The CRSP stock database description does not resolve ETF coverage or license/price; the WRDS demo has only four monthly tickers for one year. | No backtest or promotion. |
| Crypto researcher | The strongest distinct mechanism proposed was liquidation-cascade price impact and absorption. Price bars cannot identify liquidation-driven flow or order-book depth, so this is not a coded candidate on the current OHLCV panel. | No registration or performance test; first verify whether permitted historical sources cover liquidation events and depth. |
| Red team | Require a pre-fixed target/label, split boundary, purge, trial count, costs and coverage; reject any OOS segment used for tuning, any cost proxy passed off as observed, and any mechanism requiring absent flow/depth inputs. | Keep all confirmation gates closed. |

Two of the four delegated agents initially lacked direct checkout access. After that, the KR and US reviewers received the exact charter, conditional-candidate dispositions and source-gate findings; the crypto researcher received the fixed signal contract and prior rejection summary. Their conclusions are independent role reviews of those supplied records, not independent full-repository audits. The red-team result supplied a falsification checklist but could not inspect repository/data metadata. Do not overstate this round's independence.

## New crypto archive evidence

- Read-only aggregation of the local `archive_manifest` found **37 symbols** with full 1-minute monthly archives in all **70 months** from 2021-01 through 2026-10. Each calendar month has **51–84** full-month symbol archives. This supersedes the 2026-11-16 claim that the long-history archive lacked a synchronized 20-symbol price panel.
- The 37-symbol finding is conditional on the seed cohort selected from archive availability. No dated contract-status map proves the historical eligible universe; survivorship remains. Other panel gaps and eight quarantined archives remain, including **577,125 unclassified missing-minute slots across 38 symbols**.
- Official Binance public-data helper documentation lists USD-M/COIN-M `markPriceKlines`, `indexPriceKlines`, and `premiumPriceKlines` historical downloads from 2020. HTTP HEAD confirmed sample BTCUSDT monthly files exist for the tested dates; bodies and per-symbol coverage were not downloaded or audited. A sample BTCUSDT 2021-01 `aggTrades` archive is **917,138,866 B**, so broad trade-level expansion requires explicit disk/time scoping.
- The Vision daily `metrics` family contains 5-minute open-interest, top-trader/account long-short ratios, and taker-volume ratio fields. Four BTCUSDT/ETHUSDT archives for 2026-06-24/25 and matching aggTrades archives passed publisher checksum checks. Rebuilt raw taker buy/sell volume ratios matched the corresponding metrics bin at the same `create_time` on all four symbol-days (288 points/day; median relative error 0.020–0.032%); ±5-minute shifts had 29.9–34.4% median relative error. This does not support a blanket taker-flow timestamp shift at the reported 2026-06-25 boundary, but it says nothing conclusive about other fields. Separately, on 2026-11-01, all 288 Vision OI values for BTCUSDT and ETHUSDT matched the official OI REST observation timestamped `create_time + 5m` exactly; same-time maximum relative errors were 0.8377% and 0.6305%. Treat Vision OI as available five minutes after its displayed label for now; validate additional dates before using it. The endpoint itself exposes only the latest month.
- **R026 follow-up supersedes the single-day OI check:** across 2026-10-31, 2026-11-01, and 2026-11-02, BTCUSDT and ETHUSDT each had 288 unique, complete metrics timestamps/day; all 1,728 OI values matched the public REST OI observation at `create_time + 5m` exactly. Same-time maximum relative errors ranged 0.326–0.845%. This validates alignment for three recent dates only, across two publication paths from the same exchange. For the June taker-ratio sample, per-day median relative error was 0.020–0.032% against the same labeled raw-trade interval, but 11–16 of 288 bins/day exceeded 1% error and largest errors were 7.7–17.0%. The interval must close before use, so the conservative availability time is label +5m. Other metrics columns and broader history remain unverified. R026 includes a read-only validator and checked aggregate results; it is not a strategy test.
- The guessed `fundingRate` monthly URL returned 404, which is not evidence that all historical funding archive routes are absent. The next source task is to verify exact public archive paths and coverage for funding and auxiliary price series, then independently validate checksums, timestamps, gaps, and symbol/date overlap before strategy registration.

## What changed and what did not

| Gate | Before this continuation | Current evidence | Status |
|---|---|---|---|
| Crypto synchronized price history ≥20 symbols | R024 had found no suitable panel | 37 seed symbols have complete monthly 1m archive counts in all 70 months | Structural OHLCV gate now possible, not PIT-universe pass |
| Contract point-in-time listing/termination status | Missing | Still no dated status map | NO-GO |
| Funding, spread, slippage, executable mark/price path | Incomplete | Official auxiliary series identified; no full data audit, funding route unresolved | NO-GO for cost/expectancy confirmation |
| Sealed, untouched evaluation boundary | Uncertified; incident-implicated material excluded | No new independent boundary established | NO-GO for confirmatory OOS |
| KR/US licensed PIT stock+ETF data | Missing | KRX/CRSP public descriptions narrowed; account, access, price, rights, ETF and PIT details remain unresolved | NO-GO |
| Strategy performance | Existing rejected/exploratory results only | No new outcome metrics in this continuation | 0 qualified strategies/signals |

## Fixed criteria retained

- KR and US stock/ETF books are evaluated separately: CAGR ≥20%, MDD ≤30%, annualized Sharpe ≥1.0, and at least 200 OOS closed trades per claim after registered costs.
- Crypto primary criterion remains TP-before-stop/deadline target-first precision ≥80%, with at least 200 non-overlapping OOS events per claim. Deadline-close direction accuracy remains a separate secondary report. Each timeframe retains separate 10× and 20× bar-horizon claims.
- Historical Binance Vision data is for personal non-production backtesting only; no Vision-derived manual/live signal or trade is authorized.

## Next bounded work

1. Extend the timestamp and missing/duplicate checks to the remaining metrics fields and older dates; the REST cross-check only covers three recent OI dates. Then verify and, if eligible within the agreed historical-use scope, ingest checksum-verified mark/index/premium 1m archives and the exact historical funding source for the fixed 37-symbol structural cohort. Record unavailable files without filling or proxying them.
2. Establish a dated contract-status map and an independent evaluation-access boundary. If either cannot be established for the chosen sample, classify all performance results as exploratory and do not claim OOS qualification.
3. Have the three domain researchers produce novel candidate sets only after comparing the full registered catalog and one-time rejection limits. The red team must adjudicate duplicates before any strategy outcome is opened.

## Sources and run records

- Binance archive types: [official helper README](https://github.com/binance/binance-public-data/blob/master/python/README.md); archive schemas/checksums: [official public-data README](https://github.com/binance/binance-public-data/blob/master/README.md).
- KRX and CRSP access findings: [`round5_source_access_audit_20261116.md`](round5_source_access_audit_20261116.md).
- Crypto archive quality and limitations: [`round5_crypto_source_feasibility_20261116.md`](round5_crypto_source_feasibility_20261116.md).
- Fixed objectives and history: [`round0_master_charter_20261116.md`](round0_master_charter_20261116.md), [`round2_data_readiness_20261116.md`](round2_data_readiness_20261116.md).
- Vision timing audit: [`R026 decision`](../chart_predictor/strategy_lab/runs/2026-11-17-r026-vision-metrics-timing/decision.md), [`R026 aggregate results`](../chart_predictor/strategy_lab/runs/2026-11-17-r026-vision-metrics-timing/results.json).
