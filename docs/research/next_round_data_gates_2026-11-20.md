# Next research round: data gates before another strategy test

Date: 2026-11-20  
Decision: no new performance backtest in this pass. The goal remains maximum after-cost compounded wealth across market regimes. Crypto target-first M2 >=80% remains a separate signal-quality gate and cannot replace positive expectancy or portfolio growth.

## Independent role reviews

Four read-only reviews were performed: Korea equities, US equities/ETFs, a new crypto hypothesis, and crypto red-team.

| Area | Finding | Decision |
|---|---|---|
| KR stocks/ETFs | No verified PIT membership/delist/merger history, adjusted-price/corporate-action provenance, or sourced trading costs. Current cohort studies are not a valid replacement. | `NOT_EVALUABLE`; do not register another performance test yet. |
| US stocks/ETFs | Cached universe is survivor/current-cohort based; PIT constituents, delisted products, corporate-action provenance, usage rights, and common benchmark/cash contract are not established. | `NOT_EVALUABLE`; resolve the dataset contract first. |
| Crypto candidate | Funding/OI crowding reversal is a distinct possible mechanism, but no verified aligned historical funding+OI coverage or publication-time semantics were established in this checkout. | Do not preregister or calculate candidate performance until the data gate passes. |
| Crypto red-team | Trial 100 is correctly rejected. Six-current-survivor universe and missing funding make it insufficient for futures profitability claims. Cross-sectional momentum has already had a broad 45-symbol screen (trial 78); repeating it under a new label is not a new strategy. | No parameter retry. Require point-in-time universe and cost inputs before another candidate run. |

## Data-use boundary

Binance Vision's current published terms permit algorithmic historical backtesting for purely personal, non-production research, but prohibit using its datasets for live proprietary trading execution and commercial signal services. Therefore:

- Vision-derived data may be used only for historical non-production research under the applicable terms and required attribution/share-alike conditions.
- Do not use Vision-derived features, trained outputs, or historical signals to drive the user's live/manual trading signals unless Binance provides a separately applicable written permission or an independent data source with appropriate rights is used.
- Keep research/backtest data and future live/manual signal data on separate, provenance-tracked paths.

The official archive documentation describes historical market-data archives and checksums. Community issue records document unresolved timestamp/provenance ambiguities in USD-M historical metrics; those metrics are not eligible as causal features until their effective-time semantics are independently established. Funding-rate availability in public archives is not by itself proof of complete point-in-time coverage, correct symbol identity, or suitable live-signal rights.

## Next actions and gates

1. KR and US: identify a legally usable source that includes point-in-time membership, delisted/merged instruments, corporate actions/total returns, timestamped data availability, benchmark/cash rates, and auditable cost assumptions. No purchase/account creation is authorized by this record.
2. Crypto: audit archive-level coverage, symbol lifetimes, checksum lineage, funding timestamps, and metrics availability semantics for a predefined development window only. Do not open the sealed window. If metrics timestamp semantics remain unresolved, exclude OI metrics rather than applying an assumed shift.
3. Only after these gates pass, preregister one mechanism-distinct crypto test and/or market-specific equity test. Freeze universe, timing, execution, costs, benchmark, M2 denominator, and failure gates before outcomes are computed.
4. Every candidate is judged first by after-cost compounded wealth and benchmark-relative results across regimes; MDD and uncertainty remain hard risk evidence. For crypto, also require target-first M2 >=80%, non-overlap OOS N>=200, >=20 eligible symbols, and >=10% signal coverage as already frozen in the round plan.

## Evidence and limitations

- Repository records: `docs/research/research_round_2026-11-20.md`, trials 78 and 98-100, `docs/kr-us-equity-trader/SPEC.md`, and `docs/chart_predictor/SPEC.md`.
- Four agents examined the above repository records and data inventories without editing files or computing strategy performance. Their findings are documented in the current Codex run; this note records the integrated decision, not an independent data audit.
- Binance Vision terms: https://github.com/binance/binance-public-data/blob/master/TERMS_AND_CONDITIONS.md
- Binance Public Data archive structure/checksum documentation: https://github.com/binance/binance-public-data/blob/master/README.md
- USD-M metrics timestamp/provenance uncertainty: https://github.com/binance/binance-public-data/issues/491 and https://github.com/binance/binance-public-data/issues/509

No new strategy performance numbers were calculated. No validation/sealed data were opened. No source database was modified.
