# Round 2 — data readiness and next admissible work

Date: 2026-11-16 (Asia/Seoul)
Status: official-source/document audit complete; no vendor contact, account, purchase, market-data download, database read, backtest, or deployment. This is a source-eligibility decision, not a strategy result.

## Decision

**Do not run performance tests for Round 1 candidates yet.** The controlling limitation is data eligibility, not the number of strategy combinations. Proceed with a one-time rule clarification for the 13 conditionally retained stock/ETF candidates, source manifests, and a prospective crypto signal-capture design. No conditional candidate becomes approved merely by being clarified.

Round 1 red-team row tally was 0 pass, 16 reject, and 14 conditional; chief scope review additionally rejects US-10 because listed options are outside the user-fixed US/KR stocks-and-ETFs-only scope. Final candidate disposition is therefore **0 pass, 17 reject, 13 conditional**. Round 1 performance trials and valid OOS events remain **0**.

## User-fixed evaluation contract

| Market | Primary pass condition | Additional unresolved contract fields |
|---|---|---|
| Korea stocks/ETFs | CAGR >=20%, MDD <=30%, annualized Sharpe >=1.0, >=200 OOS closed trades | PIT universe, adjusted prices/actions, ETF distributions, benchmark, fee/tax/slippage, position sizing and overlap rules |
| US stocks/ETFs | CAGR >=20%, MDD <=30%, annualized Sharpe >=1.0, >=200 OOS closed trades | Same categories as Korea; US-specific costs and benchmark must be separately frozen |
| Crypto USDT perpetual manual signals | OOS TP-first precision >=80%, >=200 non-overlapping OOS signal events per claim; deadline-close directional accuracy reported separately | 10x and 20x timeframe-bar horizons reported separately; the MTF SPEC's 20+ symbol, coverage, confidence-interval, expectancy, and non-domination diagnostics remain additional checks where applicable |

No unified cross-market portfolio is evaluated. The older Round 5 readiness note says the equity maximum-drawdown policy was undefined; that statement is superseded by the user-confirmed 30% Round 0 limit. Benchmark and trading-cost assumptions remain open.

## KR stocks and ETFs

### Source facts

- KRX's public catalogue lists daily KOSPI/KOSDAQ stock and ETF trading data from 2010-01-04. This confirms a published historical date range, not completeness of point-in-time active/inactive universes or delisted outcomes. [KRX Open API service catalogue](https://openapi.krx.co.kr/contents/OPP/INFO/service/OPPINFO004.cmd)
- KRX Open API terms require agreement and an API authentication-key application; a key may be declined, is valid for one year subject to renewal, and has a stated maximum of 10,000 requests/day. The terms prohibit providing KRX data to third parties. These conditions are separate from KRX's real-time market-data distribution products. [KRX Open API terms](https://openapi.krx.co.kr/contents/OPP/INFO/OPPINFO005.jsp), [KRX distribution products](https://openapi.krx.co.kr/contents/OPP/DATA/OPPDATA002.jsp)
- KRX's real-time product catalogue lists executions, quotes, program trading, short-sale and investor data for relevant products; it does not establish a free historical tick archive. [KRX distribution products](https://openapi.krx.co.kr/contents/OPP/DATA/OPPDATA002.jsp)

### Readiness decision

The KRX catalogue is a plausible place to validate daily price fields, but it does not yet qualify the backtest panel. Required checks still include whether historical inactive/delisted securities are queryable over their full lifetimes, historical security-master snapshots, correction/vintage timestamps, corporate-action and distribution fields, rights for private derived research, benchmark total returns, and dated fee/tax/slippage schedules. Auction-imbalance and iNAV strategies additionally need historical timestamps and executable quote data; daily bars cannot stand in for these.

Do not apply for a key or buy a KRX data-distribution product as part of this round. The next safe step is a metadata/terms checklist from official documentation, followed by a separately authorized sample or key request if the checklist finds a plausible complete path.

## US stocks and ETFs

### Source facts

- NYSE describes Daily TAQ as historical all-market trades and quotes for US equity instruments, including NBBO, master files, and administrative messages, available from 1993-present. Its page links sample data and a purchase path. A sample or product description does not prove free bulk rights or complete PIT security-master/delisting coverage. [NYSE Daily TAQ](https://www.nyse.com/data-products/catalog/daily-taq/)
- CRSP's product description advertises daily and monthly data, corporate actions, and more than 32,000 active and inactive US securities. CRSP10 documentation describes ten years of monthly history including active and inactive securities, distributions, delists, and identifier/name history. This is a strong potential research panel but a licensed product, not a free confirmed source. [CRSP US Stock Databases](https://www.crsp.org/research/crsp-us-stock-databases-2025-layout/), [CRSP10 guide](https://www.crsp.org/wp-content/uploads/2023/08/CRSP10-User-Guide.pdf)
- CRSP's sample guide says Stock & Index samples are available for internal evaluation and describes a 25-security sample. It directs users to request samples/web demos through CRSP subscriptions. No inquiry or sample request was made in this audit. [CRSP Sample Data and Software Guide](https://www.crsp.org/wp-content/uploads/2023/09/CRSP_Sample_Data_and_Software_Guide.pdf)
- NYSE Group's Market Event Feed offers event/corporate-action historical data and samples for its stated scope. It does not by itself establish all-market corporate actions or ETF distributions. [NYSE Market Event Feed](https://www.nyse.com/market-data/corporate-actions/market-event-feed)
- SEC Form N-PORT datasets include registered-fund holdings, including some ETFs; they are not a complete ETF price/distribution total-return series. [SEC Form N-PORT datasets](https://www.sec.gov/data-research/sec-markets-data/form-n-port-data-sets)

### Readiness decision

CRSP is the most promising research-quality path identified for point-in-time active/inactive securities and corporate-action/delisting fields, but its quoted coverage claims still need sample inspection, target instrument mapping (including ETFs), price/return definitions, missing-delisting treatment, subscription terms, and cost. NYSE TAQ samples can validate intraday schema but cannot replace daily delisting-aware total-return histories. Public SEC and exchange fragments do not compose into a proven full-history panel without a completeness audit.

No sample was downloaded, no vendor contacted, and no account or subscription created. A permitted next step is a documented sample/quote inquiry only; a purchase or account creation is not authorized by this note.

## Crypto USDT perpetuals

### Feasible bar construction

- Official USDⓈ-M Kline endpoints document public OHLCV bars and supported intervals including 1m, 3m, 5m, 15m, 30m, 1h and 4h. Binance's documentation also exposes higher intervals in the same endpoint specification. The user's 10m bar is not a listed standard interval in the shown endpoint set; construct it from exactly ten contiguous UTC-aligned 1m bars and discard incomplete groups. [USDⓈ-M market-data API](https://developers.binance.com/en/docs/catalog/core-trading-derivatives-trading-usd-s-m-futures/api/rest-api/market-data)
- Binance Public Data provides delayed daily/monthly archives; the repository says daily files become available the next day. Historical archives therefore support offline backtests, not real-time inputs. USD-M archive rows include Klines, trades and aggregate trades. [Binance Public Data repository](https://github.com/binance/binance-public-data)
- USDⓈ-M funding-rate history is available from `/fapi/v1/fundingRate`, with `fundingTime`, rate and associated mark price fields where available; the documented response limit is 1,000 and it consumes IP-based request weight. Existing runs must preserve blank mark values and account for coverage gaps rather than silently inventing a mark. [Funding history endpoint](https://developers.binance.com/en/docs/catalog/core-trading-derivatives-trading-usd-s-m-futures/api/rest-api/market-data)
- Binance Vision's published terms describe personal, non-production historical backtesting within the stated noncommercial scope, extend the terms to derived data, and restrict live proprietary execution and compensated signal distribution. This is a summary of the provider's published terms, not legal advice or a determination that a particular use is authorized. Vision-derived research is not approved as the user's current manual-trading feed. [Binance Vision terms](https://github.com/binance/binance-public-data/blob/master/TERMS_AND_CONDITIONS.md)

### Readiness and technical boundary

R024 documents 19.79 million historical 1m rows across six current symbols, which does not satisfy the existing 20-symbol MTF diagnostics or provide a point-in-time contract universe. The recent 100-symbol panel is short, price-only, and exposed to development. Round 5 MTF and the fixed MACD/RSI experiment are development/validation exploration, not a clean prospective OOS result. No historical complete bookTicker/depth archive with fillable spread is established by these records.

Round 0's 80% target-first goal cannot be established by selecting a favorable historical cell. The next admissible crypto data work is a new prospective development stream with fixed eligible symbols, point-in-time listing/termination history, exchange event time plus local monotonic receive time, closed-bar state, trade quantities/maker side, mark/index/premium, funding, and sequence-safe L2 where claimed features require it. Store every reconnect, gap, stale interval and missing field. Do not label an observation OOS until an independent access boundary is frozen. This round does not start the stream: the earlier Gate 0 pilot authorized consideration of a separate capture proposal, not an ongoing capture or server deployment.

The requested hierarchy should be explicit in any future protocol: daily/4h regime; 1h/30m structure; 15m/10m transition; 5m/3m/1m trigger and path. Each signal timeframe must be tested at its own 10x and 20x bar horizons. Entry uses the next executable price after a confirmed candle; same-minute target/stop ambiguity is stop-first; timeout is not a target-first hit. Report coverage, per-symbol/timeframe/side precision, cluster-aware uncertainty, net R after fee/funding/spread/slippage, and baselines alongside the user's primary precision. No multi-timeframe candidate is approved by this structural specification alone.

Do not admit premium/funding dislocation normalization as a new candidate family at this stage. Existing `orb_funding_session`, R021 funding re-entry, and premium/basis proposals overlap materially; R021 was already rejected after its fixed 10/20-bar study. A future proposal would need a demonstrably distinct mechanism and a catalog-level duplicate check before registration. Repackaging or renaming the existing family is not a new trial.

## Four-agent round result and next bounded work

Four roles completed this round: KR source gate, US source gate, crypto bar/cost/OOS gate, and independent chief/red-team audit. Two source agents initially could not see the checkout, but later work was recovered using the correct `/private/tmp/cointrade-round5-ready` path for the US and crypto audits; the KR source findings were independently cross-checked in this main checkout and against KRX primary sources. The chief agent also independently confirmed the Round 1 row tally and the difference between the old MDD note and the user-fixed 30%.

Next work, without opening sealed/exposed OOS or running performance tests:

1. The single permitted correction and rule review are complete: 4 of 13 corrected stock/ETF candidates were rejected, 9 remain conditional, and 0 pass. The rejected four cannot be revised again. The nine still require data and cost gates before any trial; see [`round2_rule_review_20261116.md`](round2_rule_review_20261116.md).
2. Build a source-field manifest for KRX/US sample paths: source, rights, timestamp/vintage, PIT/inactive universe, action/distribution, return definition, identifier crosswalk, costs, and explicit missingness. No purchases or accounts.
3. Write a prospective crypto multi-timeframe capture proposal and access boundary; writing the proposal is not approval to start collection or deploy. Collection requires a separate approval after storage allocation, rotation, NAS failure handling, and no-secret/no-order constraints are documented. No strategy scoring until a fresh cohort exists.
4. Reconcile the existing local branch's 70-commit divergence before commit/push. Its configured `origin` currently resolves to a local path, not GitHub; no push is authorized by this data audit.

## Method and provenance

Repository facts above were checked in `/private/tmp/cointrade-round5-ready`; volatile DB row counts and database contents were not re-read in this note. Official KRX, CRSP, NYSE, SEC, and Binance documentation was browsed on 2026-11-16. The three domain/source agents and the independent chief returned read-only findings; their sources are linked inline. No market values, account credentials, or sealed OOS rows were queried. This file records evidence and next gates only; it contains no strategy-performance metrics generated by Round 2.
