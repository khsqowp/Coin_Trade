# Next research round: data gates before another strategy test

Date: 2026-11-20  
Decision: no new performance backtest in this pass. The goal remains maximum after-cost compounded wealth across market regimes. Crypto target-first M2 >=80% remains a separate signal-quality gate and cannot replace positive expectancy or portfolio growth.

## Independent role reviews

Four read-only reviews were performed: Korea equities, US equities/ETFs, a new crypto hypothesis, and crypto red-team.

| Area | Finding | Decision |
|---|---|---|
| KR stocks/ETFs | No verified PIT membership/delist/merger history, adjusted-price/corporate-action provenance, or sourced trading costs. Current cohort studies are not a valid replacement. | `NOT_EVALUABLE`; do not register another performance test yet. |
| US stocks/ETFs | Cached universe is survivor/current-cohort based; PIT constituents, delisted products, corporate-action provenance, usage rights, and common benchmark/cash contract are not established. | `NOT_EVALUABLE`; resolve the dataset contract first. |
| Crypto candidate | Funding/OI crowding reversal is distinct, but aligned funding+OI coverage and publication-time semantics are not established. Funding alone was already included in prior 45-symbol research (Trials 78/81); the six-symbol minute DB has no funding fields. | Do not preregister a new funding-only variant. Require a distinct mechanism and resolve the joint-data gate before another funding+OI candidate. |
| Crypto red-team | Trial 100 is correctly rejected. Six-current-survivor results and price-only six-symbol inputs are insufficient for broad futures claims. Cross-sectional momentum and a funding-reversal overlay have already had broad 45-symbol screens (Trials 78/81); their OOS has already been inspected. | No parameter retry or OOS reuse as fresh validation. Require a point-in-time universe and cost inputs before another candidate run. |

## Data-use boundary

Binance Vision's current published terms permit algorithmic historical backtesting for purely personal, non-production research, but prohibit using its datasets for live proprietary trading execution and commercial signal services. Therefore:

- Vision-derived data may be used only for historical non-production research under the applicable terms and required attribution/share-alike conditions.
- Do not use Vision-derived features, trained outputs, or historical signals to drive the user's live/manual trading signals unless Binance provides a separately applicable written permission or an independent data source with appropriate rights is used.
- Keep research/backtest data and future live/manual signal data on separate, provenance-tracked paths.

Four archive months were checksum-verified and parsed in memory during this audit, and a paginated historical S3 key inventory was performed; see `coin_candle_data_inventory_2026-11-20.md`. Separately, `alpha.md` and `map_api.md` record prior 45-symbol funding research, including funding coverage and already-viewed OOS results. The six-symbol minute SQLite inventory and that broader hourly research cache are different datasets; the latter raw `/tmp/.rs_alpha_cache` was absent in this audit environment, so its recorded results were not independently rerun.

The official archive documentation describes historical market-data archives and checksums. Community issue records document unresolved timestamp/provenance ambiguities in USD-M historical metrics; those metrics are not eligible as causal features until their effective-time semantics are independently established. Funding-rate availability in public archives is not by itself proof of complete point-in-time coverage, correct symbol identity, or suitable live-signal rights.

## Next actions and gates

1. KR and US: identify a legally usable source that includes point-in-time membership, delisted/merged instruments, corporate actions/total returns, timestamped data availability, benchmark/cash rates, and auditable cost assumptions. No purchase/account creation is authorized by this record.
2. Crypto: audit archive-level coverage, symbol lifetimes, checksum lineage, funding timestamps, and metrics availability semantics for a predefined development window only. Do not open the sealed window. If metrics timestamp semantics remain unresolved, exclude OI metrics rather than applying an assumed shift.
3. Only after these gates pass, preregister one mechanism-distinct crypto test and/or market-specific equity test. Freeze universe, timing, execution, costs, benchmark, M2 denominator, and failure gates before outcomes are computed.
4. Every candidate is judged first by after-cost compounded wealth and benchmark-relative results across regimes; MDD and uncertainty remain hard risk evidence. For crypto, also require target-first M2 >=80%, non-overlap OOS N>=200, >=20 eligible symbols, and >=10% signal coverage as already frozen in the round plan.

## Follow-up source review (four independent agents)

- **KR:** Official KRX screens expose delisted-security fields and the catalog includes stock/ETF price products, but complete PIT price history, merger/corporate-action cashflows, adjusted total returns, fees, and research rights are not proven. Formal KR stock/ETF performance testing remains `NOT_EVALUABLE` on the current data contract.
- **US:** CRSP is the strongest candidate for inactive securities/permanent IDs/corporate actions; Sharadar and Nasdaq Daily List/Zacks are possible supporting sources. Neither public product descriptions nor the existing 92-name survivor cache prove PIT membership, ETF completeness, revision vintages, or usage rights. Formal US performance testing remains `NOT_EVALUABLE`.
- **Crypto:** The long-history local `chart_predictor` files contain six symbols; the repaired 1m file is continuous through 2026-06-30, but it has no funding/OI fields and cannot meet the 20-symbol breadth gate. Separate 45-symbol hourly/funding research is recorded in `alpha.md` and `map_api.md`, with OOS already inspected and a survivor-universe limitation; its raw temporary cache was absent in this audit environment. A separate short-history 100-symbol candle file is mentioned in the independent inventory review; its COIN-only composition and relationship to the historical PIT universe remain unverified. Do not combine these into a purported unbiased universe.
- **Official derivatives API limits:** Binance funding history has a documented paginated endpoint (up to 1,000 records per response), but this review did not fetch or prove complete per-symbol history; check applicable data-use terms before using REST history. OI statistics are documented only for the latest month, at 5m-or-coarser periods, with period-end timestamps and possible omitted intervals. This does not meet the multi-year OI history need. Keep OI out of historical features unless an appropriate licensed historical source is verified.
- **Red-team:** no new development performance test is justified by the six-symbol history alone. Trials 78 and 81 already screen broad cross-sectional momentum and a funding-reversal overlay; Trials 98-100 screen candle-pressure, BTC-to-alt lag-flow, and 28/5 market timing. Another parameter/label variant would add selection bias, not new evidence. The sealed 2024+ interval for Trials 99/100 remains closed; the distinct OOS windows reported for Trials 78/81 were already examined and are not fresh confirmation.

## Evidence and limitations

- Official provider comparison and prioritized source-acquisition gates: `docs/research/market_data_vendor_gate_2026-11-20.md`.
- Direct local candle inventory and its strict scope caveat: `docs/research/coin_candle_data_inventory_2026-11-20.md`.
- Repository records: `docs/research/research_round_2026-11-20.md`, trials 78 and 98-100, `docs/kr-us-equity-trader/SPEC.md`, and `docs/chart_predictor/SPEC.md`.
- Four agents examined the above repository records and data inventories without editing files or computing strategy performance. Their findings are documented in the current Codex run; this note records the integrated decision, not an independent data audit.
- Binance Vision terms: https://github.com/binance/binance-public-data/blob/master/TERMS_AND_CONDITIONS.md
- Binance Public Data archive structure/checksum documentation: https://github.com/binance/binance-public-data/blob/master/README.md
- USD-M metrics timestamp/provenance uncertainty: https://github.com/binance/binance-public-data/issues/491 and https://github.com/binance/binance-public-data/issues/509

No new strategy performance numbers were calculated. No validation/sealed data were opened. No source database was modified.
