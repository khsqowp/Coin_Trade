# KR/US Systematic Strategy Research Log

This is the cumulative decision log for the KR/US equity strategy search. Add every materially distinct candidate and its evidence here before creating another report, so failed or blocked ideas are not unknowingly repeated. This log is separate from the live crypto trading system and does not authorize live orders.

## 2026-11-07 — Data feasibility and first candidate gate

### Outcome

No KR/US price-performance backtest was run in this round. No strategy is currently validated, rejected on performance, or eligible for deployment. The current bottleneck is admissible historical price data and its licensing/PIT properties, not proof that no strategy can work.

### Candidate register

| ID | Market / hypothesis | Data and rule status | Result | Decision |
|---|---|---|---|---|
| `A-US-TFF-Emini-LeveragedFunds-Z156-SPY-20261107` | US broad-market regime signal from CFTC TFF leveraged-money positioning in E-mini S&P 500 futures, standardized with a 156-week window, mapped to SPY | Rule was frozen before performance testing; preregistration SHA-256: `515e7094…afc3c40`. Eleven official CFTC TFF archives were downloaded and ZIP-integrity checked. Exact contract label had 246 weekly observations from 2022-02-08 to 2026-10-20; the frozen warmup leaves 90 signal observations. Price history, trading calendar, and execution-cost inputs were not available under a verified admissible source. | No returns, benchmark comparison, IS/OOS metrics, DSR/PSR, or multiple-testing result were computed. | `DATA_BLOCKED`; do not call this a performance failure or a successful strategy. Do not merge the similarly named legacy contract series into this frozen rule. |

### Independent review and corrections

- Independent review found a row-count discrepancy in the initial CFTC data note: the legacy-alias count was reported as 494, while the independent count was 526 for 2012-01-10 through 2022-02-01, plus 290 earlier rows. Keep the exact frozen contract label separate; correct the source report before relying on the alias count.
- The preregistration's empty-window pass criterion is ambiguous. Resolve it in a dated addendum before any future performance run; do not silently reinterpret it after seeing results.
- CFTC data integrity checks establish archive readability and row-level properties only. They do not establish a profitable signal.

### Data-source gate

- **KRX:** Official API catalog exposes daily KOSPI/KOSDAQ stocks, indices, and ETFs from 2010-01-04, but access requires registration/API key and applicable terms. Delisted-security coverage, point-in-time membership, corporate-action adjustment, and historical revisions were not established. No credentials or API key were stored in this repository.
- **US prices:** No source was verified in this round that simultaneously provides the required historical executable prices, delisted/PIT coverage, and sufficiently clear rights for automated research and derived backtest results. Stooq returned an HTML challenge rather than usable CSV; Yahoo automated collection is not permitted by its stated terms and historical downloads require a paid tier; FRED's S&P 500 series is price-only and does not solve the coverage/rights requirements. Other inspected alternatives also have unresolved licensing or instrument mismatch.
- **SSGA:** Public NAV/distribution files were identified, but they do not supply the full historical daily OHLC dataset needed for the intended execution test; copying/derivative-use rights were not verified.
- **Conclusion:** Data is a blocking prerequisite. Do not substitute a different ETF, price-only index, current constituent list, or unverified public download and present it as a valid PIT backtest.

### Distinct untested ideas (not results)

These are candidate families only; none has been backtested or shown to have an edge. Before implementation, check the existing Coin_Trade and house research catalogues for overlap and freeze a precise rule.

1. **US insider accumulation:** SEC Form 4 open-market purchases clustered by issuer and time window. Define transaction codes, ownership role, reporting delay, cluster threshold, tradability and delisting treatment.
2. **KR disclosed ownership increases:** OpenDART ownership-change disclosures, with publication-time lag and event deduplication. Availability, survivorship, and licensed data use remain to be checked.
3. **KR short-balance pressure:** KRX reported short-sale balance changes as a lagged contrarian/covering signal. Exact API, publication timing, PIT completeness and terms remain unverified.
4. **KR buyback execution:** Actual treasury-share acquisition progress versus announced plan, using only information observable at each decision date. Disclosure timestamps, completion/cancellation handling and terms remain unverified.

These ideas must not be described as strategies that “work” until preregistered, independently reproduced, cost-adjusted, evaluated OOS, and passed the agreed data-integrity and multiple-testing gates.

### Evidence artifacts

The following artifacts remain in the isolated Oracle research workspace; only their identifiers and hashes are recorded here, not market-data files or credentials:

- Agent A CFTC data gate: `/home/opc/isolated_research/kr_us_loop_v1/round_20261107/agent_a_us_macro/DATA_GATE.md`
- Agent B CFTC independent review: `/home/opc/isolated_research/kr_us_loop_v1/round_20261107/agent_b_factor_rotation/REVIEW_agent_a_cftc_prereg_20261107.md` — SHA-256 `5892d68a07a6128ae8bb797264923121b3166846fb8e49d70d89ddc791adf4f9`
- Agent B ETF data feasibility: `/home/opc/isolated_research/kr_us_loop_v1/round_20261107/agent_b_factor_rotation/FEASIBILITY_public_etf_alternatives_20261107.md` — SHA-256 `9adf0950aeb1e2997a3462046397eb02ae2ff63505df97183616477d965fcf54`
- Agent A SSGA gate: `/home/opc/isolated_research/kr_us_loop_v1/round_20261107/agent_a_us_macro/SSGA_DATA_GATE.md` — SHA-256 `701b4748ce1c0535d011eb840ea28256ec64b99c9d8bfdb0c2d835d705404056`
- Agent C KRX index/ETF data review: `/home/opc/isolated_research/kr_us_loop_v1/round_20261107/agent_c_kr_data/agent_c_index_etf_data.md` — SHA-256 `85a17f595c4568c8c20a37625e5f90c2eb3388701029a954430df12f48d1cd19`
- Agent C distinct-candidate catalogue: `/home/opc/isolated_research/kr_us_loop_v1/round_20261107/agent_c_kr_data/agent_c_distinct_candidates_20261107.md` — SHA-256 `0ba8446876530ae6d57dcfe0f7b920cd594cb9a3814c70b28b341ced3bfb51b7`
- Agent C price-data rights audit: `/home/opc/isolated_research/kr_us_loop_v1/round_20261107/agent_c_kr_data/agent_c_price_data_source_audit_20261107.md` — SHA-256 `d1f813930e5e6b7110c75e90ea8435e63d4eeeba7869f168d7f9aebc73636dea`

### Next admissible step

1. Obtain a permitted historical price-data route with explicit enough use rights and required PIT/delisted/corporate-action coverage, or document that a named dataset does not meet those gates.
2. If using KRX, the owner must complete account/password/verification and any required terms directly, then place the API key only in the isolated server-side `.env`; never commit it or paste it into chat.
3. Correct the CFTC alias row-count note and preregistration ambiguity via dated addenda.
4. Only then preregister a bounded next generation, calculate the true cumulative trial count from the supplied trial databases, and run performance tests.

## Ongoing logging rules

For every future candidate, record a stable ID, market, hypothesis, exact signal/entry/exit/position rules, data source and vintage, preregistration hash/time, trial-count basis, fees/slippage, IS/OOS dates, benchmark, metrics, independent reproduction status, and final gate decision. Keep blocked, failed, and duplicate candidates in the log. Never change a frozen rule after seeing OOS results without a dated addendum; never call a data-blocked idea an unsuccessful performance test.


## 2026-11-07 — Public-data countercheck

### Correction to the scope of the data conclusion

The earlier wording must not be read as “no free market-data endpoint exists.” A red-team search found additional endpoints and free/personal-use tiers. The supported conclusion is narrower: no source was established in this review that clears the complete price-data, use-rights, PIT/corporate-action and survivorship gates for the frozen KR/US equity backtests. The candidates below are recorded so they are not rediscovered as new strategies.

| Source | Documented capability | Unresolved gate | Status |
|---|---|---|---|
| Polygon/Massive US | Daily OHLCV, split adjustment, date-specific ticker status/delisted-date fields; free tier described as two years | Published market-data terms restrict non-display use and investment-strategy/derived-work creation absent a separate license; no dividend adjustment; two years do not cover frozen long-history tests | `FAIL — rights/coverage` |
| Alpha Vantage | Official docs describe raw daily OHLCV (25+ years), adjusted OHLCV with split/dividend events (premium), US listing-status lookup including delisted status, and 25 free requests/day for most datasets | The terms allow personal non-commercial use and include private individual investment analysis/research/testing in that scope, but do not expressly settle storing/using provider data for derived backtest series; complete delisted price/event history and revision-vintage guarantees were not established. Adjusted daily data is marked premium. No account, key, or data request was made. | `LEAD — rights/PIT/data completeness not cleared`; do not treat as a pass or performance result |
| Financial Modeling Prep | EOD OHLCV, adjusted-price endpoints, some delisted-company coverage and a free request tier | Terms restrict downloading/copying/derivative works absent permission; provider documents incomplete delisted coverage | `FAIL — rights/coverage` |
| FSC/KRX | Daily stock and ETF/ETN/ELW OHLCV APIs exist | Published KOGL Type 4/no-modification and third-party rights; PIT, delisting returns, distributions, and revisions remain unproven | `FAIL/UNKNOWN — rights/PIT` |
| FRED `SP500` / Ken French Data Library | Public daily index or aggregate portfolio/factor series | Not executable OHLCV/total-return ETF data for the frozen test; third-party rights and full signal-derived use are not established | `FAIL for current execution gate` |

### Alpha Vantage interpretation note

The primary-source Terms of Service distinguish personal, non-commercial use from activities beyond private individual investment analysis/research/testing. This is not a basis to claim that personal backtesting is categorically forbidden. Conversely, the reviewed terms do not explicitly grant a data-specific right to download, retain, transform, and store strategy-derived return series, and the historical adjusted endpoint is marked Premium. Treat the source as an unresolved lead pending an allowed data route and verification of the relevant dataset terms; do not report it as definitively prohibited or permitted.

### Primary-source register

- Alpha Vantage API documentation: https://www.alphavantage.co/documentation/
- Alpha Vantage support/API request limits: https://www.alphavantage.co/support/
- Alpha Vantage Terms of Service: https://www.alphavantage.co/terms_of_service/
- Alpha Vantage market-data policies: https://www.alphavantage.co/realtime_data_policy/
- Polygon/Massive market-data terms: https://polygon.io/terms/market_data_terms.pdf
- Financial Modeling Prep Terms: https://site.financialmodelingprep.com/developer/docs/terms-of-service
- FSC/KRX ETF daily quote API: https://www.data.go.kr/data/15094806/openapi.do
- FSC/KRX stock daily quote API: https://www.data.go.kr/data/15094808/openapi.do

### Countercheck evidence

Red-team report: `/private/tmp/agent_c_source_audit_countercheck_20261107.md`, SHA-256 `49e6bae662bb5aac9edc774d329897081c533682f263cea9835a8d4df807c058`. This report checked source documentation and terms, not price values; it did not download data, create accounts, request keys, or accept terms.


## 2026-11-07 — Source-license and KR PIT follow-up

### US daily-source follow-up

- **Cboe DataShop EOD:** Cboe documents daily US equity/ETF OHLCV and VWAP from 2010, but its standard license bars strategy creation/validation without a separate written agreement. This is not a qualifying free route for the current research gate. PIT ticker lifecycle and full adjusted-price/distribution coverage were not established.
- **Alpha Vantage demo check:** An unauthenticated/public `apikey=demo` request for SPY full daily data returned a key-registration instruction, not a time series. No key was created and no price values were downloaded.
- **Alpha Vantage ToS wording correction:** One agent report characterized personal research/testing as commercial use. The official Section 2(i) wording instead describes commercial use as going beyond investment analysis, research, testing, monitoring, and activities private and individual in nature. Therefore this review does **not** classify private individual research as categorically forbidden. The remaining issue is narrower: the reviewed terms do not expressly settle retaining provider data or persisting backtest-derived series, and documentation does not establish complete delisted security prices/event vintages. Adjusted daily OHLCV is marked Premium; the free tier is limited to 25 requests/day for most datasets. Current decision stays `LEAD / UNRESOLVED`, not an asserted terms violation and not a data-gate pass.
- **Agent A follow-up:** `/private/tmp/US_DAILY_DATA_SOURCE_FOLLOWUP.md`; it records the Cboe review and demo response. Its Alpha Vantage interpretation is superseded by the primary-terms reread above; preserve the discrepancy rather than repeating it as fact.

### Korea daily-source follow-up

Agent B's KR source audit found no free source documented to jointly allow automated collection and derived backtesting while providing full-universe PIT, delisted returns, corporate actions, and historical vintages.

- EODHD was identified as a paid near-miss whose individual personal noncommercial terms appear to allow backtesting and retaining derived results, but its free tier covers only one year of EOD data. The audit did not establish complete delisted history, point-in-time universe, or revision vintages; historical updates overwrite prior values. Not used because this task is limited to free data and the PIT gate remains open.
- Twelve Data's terms may permit individual derived analysis, but KRX third-party licensing, free access and full delisted/vintage coverage were not cleared.
- KIS API and its backtester are oriented to the user's own account/assets and do not establish a historical delisted PIT universe.
- Stooq terms could not be verified through its JavaScript challenge; Yahoo automated collection remains outside the verified permission scope.
- No data values were requested or inspected, no account/key action occurred, and no performance test ran.

KR report: `/home/opc/isolated_research/kr_us_loop_v1/round_20261107/agent_b_factor_rotation/KR_daily_legal_data_gate_audit_20261107.md`, SHA-256 `6b6d7419a083eb9e0922eb636f04e700568767c2e322471b9f6efe23342b207f`.

Cboe sources:
- EOD product description: https://datashop.cboe.com/equity-eod-summary
- Standard license: https://datashop.cboe.com/documents/Cboe_LiveVol_DataShop_License_Agreement.pdf


## 2026-11-07 — Tiingo EOD near-miss for a fixed US ETF test

Official Tiingo documentation adds a potentially useful route for a narrowly scoped US ETF test:

- The Individual Starter plan is listed at $0/month, with 30+ years of historical price coverage, up to 500 unique symbols/month, 1,000 requests/day and 1 GB/month. It labels the license “Internal Use Only” and defines this as personal use that may not be displayed or shared.
- The EOD endpoint documents raw and adjusted daily OHLCV, dividend cash and split fields. Its adjustment method incorporates both splits and dividends. The provider says prices may be corrected through 8 PM Eastern and updates prices as corrections arrive.
- The supported-ticker list reflects current coverage/reservations; the reviewed documentation does not establish a complete point-in-time universe, delisted-price coverage, or frozen historical vintages. This makes the free tier unsuitable for the frozen all-stock US PIT test as currently documented.
- A pre-specified long-lived ETF such as SPY could avoid constituent survivorship and could be evaluated as an ETF-only regime strategy, but this is a narrower claim than the existing all-stock KR/US objective. Do not substitute it into a frozen all-stock preregistration or label it a full-market result.
- API use requires an account/token. No Tiingo variable was present in this workspace's `.env`/ `.env.example` name-only check. No account was created, no terms were accepted, no token was requested, and no API values/backtest were obtained. This does not establish whether a token exists in another environment.

Decision: `POTENTIAL US ETF-ONLY LEAD; DATA ACCESS AND PUBLIC-DERIVED-RESULTS RIGHTS UNRESOLVED; NOT A FULL-GATE PASS`.

Primary sources:
- Pricing and plan limits: https://www.tiingo.com/pricing
- EOD price fields/adjustment and correction behavior: https://www.tiingo.com/documentation/end-of-day
- API use and internal-use restrictions: https://www.tiingo.com/documentation/

This lead may be revisited only if a permitted token/data route is already available; do not create an account or accept terms on the user's behalf. Keep the final research scope intact.
