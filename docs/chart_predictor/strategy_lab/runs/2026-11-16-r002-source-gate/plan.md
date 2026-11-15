# R002 — Source, license, and point-in-time data gate

Status: `blocked_data_gate` — source-feasibility audit only; zero strategy-performance cells.

## Question

Can a documented, suitably licensed historical source provide enough point-in-time universe, price, and (for perpetuals) payable funding data to support the strategy-lab objective: two portfolio strategies outperforming matched Buy-and-Hold after costs and risk controls?

This portfolio objective is distinct from the chart-prediction M4 selective-signal target of at least 80% target-first accuracy. This run does not assess either strategy performance or signal accuracy.

## Frozen scope and method

- Review the existing R001 readiness gate and prior trial records; inspect official source documentation and terms already researched for this round.
- Audit source capabilities, known gaps, licensing constraints, and the minimum evidence needed before acquisition.
- Do not download data, open price databases, calculate returns, define a parameter grid, place orders, contact providers, post public comments, or accept terms on the user's behalf.
- Preserve existing datasets and prior run artifacts. Record no strategy metrics because no strategy tests are run.
- Treat four-agent opinions as dossier-based research suggestions, not independent reproductions of raw files, data, or calculations.

## Prior-state evidence

R001 (`2026-11-15-r001-readiness`) found zero qualifying results and blocked performance testing because the audited long-history source was a six-current-symbol USDⓈ-M perpetual cohort, lacked funding cashflows and point-in-time universe membership, and had a metadata-coverage fingerprint rather than a full candle-content hash. The separate 100-symbol cache was only July–November 2026. R001's dataset inventory came from a dated audit in the source checkout; this temporary checkout did not freshly open the ignored database files.

The prior strategy catalog also matters. The proposed four-agent mean-reversion notion—failed range expansion followed by a close back inside and reversal—overlaps the already tested volume-climax/failure-close work in `docs/research/agent_strategy_research_rounds_20261115.md` and the prior sweep-close-back-inside rule in `docs/research/crypto_round10_liquidity_sweep_preregistration_20261115.md`. It is therefore rejected as a nominal simplification, not admitted as a distinct untested candidate. No repeat is run.

## Source findings

1. Binance Public Data's official repository provides downloadable archive files and checksum sidecars. A checksum can establish that a downloaded file matches its sidecar; it does not establish complete historical coverage or a point-in-time investable universe. The repository's helper behavior based on current exchange metadata does not alone establish a full delisted/renamed symbol manifest. See [official Binance Public Data README](https://github.com/binance/binance-public-data/blob/master/README.md).
2. The official Binance Vision terms dated 2026-08-26 state CC BY-NC-SA 4.0 conditions and enumerate permitted use, including purely personal, non-production historical backtesting, while restricting live proprietary execution, commercial automated order generation, and compensated third-party signals. The terms also apply to derived data. Whether private/manual live trading informed by Vision-derived analysis is permitted is not resolved here; no legal conclusion is made. Use requiring a different scope needs separate licensing clarification before acquisition or use. See [official Binance Vision terms](https://github.com/binance/binance-public-data/blob/master/TERMS_AND_CONDITIONS.md).
3. Binance's official USDⓈ-M funding-history API documents `/fapi/v1/fundingRate`, inclusive time bounds, a maximum page size of 1000, funding records with timestamps/rates/mark prices, and regular/special rate types. This establishes an endpoint, not the completeness of payable settlement history across historical and delisted contracts. Completeness must be measured against expected settlement windows and contract lifetimes. See [official funding-history documentation](https://developers.binance.com/docs/derivatives/usds-margined-futures/market-data/rest-api/Get-Funding-Rate-History).
4. Open issues in Binance's public-data repository raise questions about delisted-symbol manifests, funding coverage, and archive/API reconciliation. These are user-reported issue discussions, not official Binance answers or proof of a definitive gap. Their existence reinforces the need to verify coverage empirically and obtain authoritative clarification where necessary: [issue #479](https://github.com/binance/binance-public-data/issues/479), [issue #481](https://github.com/binance/binance-public-data/issues/481), [issue #517](https://github.com/binance/binance-public-data/issues/517), and [issue #475](https://github.com/binance/binance-public-data/issues/475).
5. Public market-data access and downloadable archives do not resolve source-use rights, delisted instruments, point-in-time membership, complete funding cashflows, canonical price reconciliation, or realistic execution costs. Those are independent gates.

## Four-role research round

Four agents received the prior-evidence dossier and were asked to propose or reject a genuinely novel, testable strategy direction while respecting the source gate. They did not independently inspect repository files or raw data in this checkout, so their conclusions are advisory rather than reproductions.

- Trend/momentum: no admissible distinct candidate; prior P5–P9 and MACD-zero/RSI-50 evidence plus data limitations prevent a defensible new test.
- Mean reversion: suggested a failed-range-expansion/close-back-inside idea conditionally, explicitly untested. Local prior-art review found material overlap with the volume-climax failure-close and liquidity-sweep close-back-inside experiments; proposal rejected as non-distinct.
- Cross-sectional/regime: no admissible candidate without point-in-time membership and complete instrument/cost records.
- Independent adversarial reviewer: no candidate passed; flagged unresolved terms interpretation for any use of Vision-derived analysis to inform private live trades. This remains a question for authoritative licensing clarification, not legal advice.

## Pre-acquisition evidence required

Before another strategy-performance run, select one instrument class and source path, then establish all of the following in a separate frozen input manifest:

1. Exact terms and permitted purpose for acquisition, derivative storage, analysis, and intended output/use.
2. Point-in-time listing, delisting, renaming, and eligibility history; no present-day survivor universe substituted for the historical universe.
3. Exact symbol/field/date coverage, expected versus observed bars, duplicate/off-grid/null/invalid records, and reconciliation against an independent canonical source where available.
4. Full raw-content hashes, per-file source checksums, schema/version, acquisition timestamp, and immutable destination separate from existing databases.
5. For perpetuals, expected funding settlements for every contract lifetime and observed rate/mark records reconciled across pagination, special-rate changes, delistings, and missing intervals. If this cannot be proven, use a spot design and still resolve PIT membership.
6. Frozen matched Buy-and-Hold treatment and realistic fee, spread, slippage, market-impact, cash, delisting, rebalance, and exposure rules before any metric calculation.

Do not pay a provider, create accounts, send inquiries, post comments, download a bulk dataset, or accept terms without separate user authorization. No public comments were posted in this run.

## Acceptance and stop rule

Proceed to preregistered strategy performance only when the input manifest proves the source/use gate, PIT universe, price continuity/content identity, and applicable instrument cashflows/cost model. If any mandatory item remains unknown, stop at the data gate, save the exact gap, and do not spend compute on parameter searches over exposed or inadequate data.
