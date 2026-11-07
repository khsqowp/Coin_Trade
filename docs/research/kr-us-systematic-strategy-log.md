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


## 2026-11-07 — Alpha Vantage terms wording correction

The earlier Alpha Vantage note that described private research/testing as clearly within non-commercial personal use is too definite and is superseded here. The official Terms of Service currently state that commercial use includes a purpose “that goes beyond personal usage including investment analysis, research, testing, monitoring, and any other activities that are individual in nature.” The wording does not clearly resolve whether a private individual's backtest is affirmatively covered as personal use or treated as commercial. No affirmative provider confirmation for storing raw history or publicizing strategy-derived outputs was found.

Decision remains `UNRESOLVED / DO NOT USE FOR PERFORMANCE TESTING WITHOUT CLEARER TERMS`. This corrects the prior interpretation; it does not mean the provider definitively prohibits private research. No provider was contacted, no account/key was created, and no data was fetched.

Primary source: https://www.alphavantage.co/terms_of_service/


## 2026-11-07 — Nasdaq WIKI EOD public-domain archive check

- Nasdaq's WIKI Prices page is currently indexed as describing daily EOD prices, dividends and splits for 3,000+ US tickers from January 1996, with the dataset “released into the public domain.”
- The same record says community support ended 2018-04-11 and explicitly recommends against using it for investment or analysis. Direct page fetch returned 404 in this review; official docs say API use/data export requires login, and the free-data path requires a free account.
- Current Nasdaq general terms describe access under an Order Form/internal-business-use license and incorporate third-party data terms. The relationship between those terms and the WIKI public-domain statement was not resolved. No account, acceptance, or download was performed.
- No official evidence was found that the 3,000+ tickers are point-in-time constituents or that delisted names and their final returns are complete. The dataset therefore does not meet the frozen PIT/full-universe/OOS gate.
- A lawfully obtained pre-2018 archive might only support a separate, explicitly historical exploratory study after a fresh preregistration; it cannot validate contemporary strategy performance, and no such archive is currently available in this workspace.

Decision: `DATA_BLOCKED — PUBLIC-DOMAIN LABEL EXISTS, BUT ACCESS/TERMS APPLICATION, PIT COMPLETENESS, AND DATA AVAILABILITY ARE UNRESOLVED`.

Primary-source records:
- WIKI Prices: https://data.nasdaq.com/databases/WIKIP
- Nasdaq Data Link terms: https://data.nasdaq.com/terms
- Free-data sign-up/access description: https://next-qc.cdn.data.nasdaq.com/sign-up
- Nasdaq Data Link client docs: https://github.com/Nasdaq/data-link-python/blob/main/FOR_DEVELOPERS.md


## 2026-11-07 — Additional public-source feasibility round

### Newly checked US sources

- **MarketParquet** advertises a free sample/free account tier and a full daily archive to 2000 with delisted names. Its own license page says internal research/backtesting and derived, non-reconstructable performance results are permitted, but the license is granted only **on payment for an archive**. Its free-tier guide explicitly says those files carry **no license** and are a sample for trying the service. The free tier also requires a free account/API key for the full recent-year window. No account was created, no key was requested, and no file was downloaded. Since this round is limited to free data, it is not eligible. The paid archive is a possible future US source only if separately authorized; its docs say prices are split-adjusted but dividends are excluded, the vendor disclaims accuracy warranties, and PIT membership/calendar/corporate-action completeness still requires independent verification. Sources: https://marketparquet.com/pricing, https://marketparquet.com/license, https://marketparquet.com/guides/free-historical-stock-data, https://marketparquet.com/documentation.
- **Wiki Prices / Quandl WIKI** is surfaced by a third-party ML4T provider wrapper as a 3,199-stock, 15.4-million-row local Parquet archive covering 1962–2018 and including delisted companies. That wrapper is not the data origin or a license grant. The exact dataset license, source-vintage/PIT coverage, delisting terminal-return treatment, and a lawfully reusable no-account archive were not verified. No archive was downloaded. It does not pass the current gate; it could only be reconsidered for a separately preregistered historical-only study if primary-source rights and provenance are established.
- **Stock-Data GitHub project** describes a universe/event archive derived from SEC and Nasdaq symbol-directory snapshots, but the repository is not itself an authoritative price feed. Its claim does not repair gaps in historical OHLC, security identity, action-adjusted execution prices, or source rights. No data was downloaded.

### KR near-miss reconfirmation

- The public aikstockdata history page states that its open data is non-commercial use only and that KRX/FSC-origin price series inherit Gonggongnuri Type 4 (attribution, non-commercial, no derivatives); it also states that only currently included names are published, delisted symbols are removed, and prices are unadjusted for splits/dividends. Its recent history endpoint is useful for current-name inspection, not a free PIT backtest panel. No price values were downloaded or read. Source: https://aikstockdata.com/downloads/history.
- The FSC listed-stock-information API is metadata, not a price history. The official portal states Type 4 reuse terms. Source: https://www.data.go.kr/en/data/15094775/openapi.do.

### Cycle disposition

No price file was acquired and no KR/US strategy performance test ran. No candidate is performance-rejected, and no strategy passes. This round adds one **paid-only potential US source** and closes the free tier as non-licensed; it does not change the performance evidence. Continue searching for admissible free sources and retain all prior preregistrations unchanged.


### Independent 3-agent review of the new source leads

- **US source audit (Agent A):** Wiki Prices Parquet's repository wrapper does not prove the data-file license or PIT completeness. MarketParquet's free sample is explicitly unlicensed; paid archive is a possible future source, not acquired or approved. No file download, parsing, or backtest. Report SHA-256: `4860999c8723cf6e0a468313912d9eec55a63e22e0979f31575cba6dd6df0c35` (`trading/docs/research/us_candidate_rights_audit_20261107.md`).
- **KR source audit (Agent B):** PyKRX adjusted prices route to Naver; source policy does not establish permission for automated collection. FinanceDataReader's code license is not its upstream data license. Public KRX/Naver GitHub mirrors have no verified data reuse grant or PIT guarantee. Issuer ETF UI shows market close and NAV but not reuse rights or complete delisted/PIT coverage. No download, API key, account, or price-value inspection. Report SHA-256: `3489fcfeb4ff5b58278ce67fdcc119bca2cc6f6da761792300b24702bff5ea48` (`trading/docs/research/kr_public_daily_sources_audit_20261107.md`).
- **Independent red-team (Agent C):** Wiki WIKI start-year claims conflict (Nasdaq search index says Jan 1996; secondary mirrors/wrappers say 1962), official access/license details remain unresolved, and its use for investment/analysis is discouraged. Stock-Data is a point-in-time directory/action project, not a complete OHLC feed. aikstockdata is current-names-only and unadjusted. Report SHA-256: `33baeb1bd5f1b2e58c791c5408fad3faa08a1374f096553e2ccb2a12eff33a08` (`/private/tmp/agent_c_candidate_redteam_wiki_marketparquet_stockdata_aik_20261107.md`).

**Disposition:** no new source meets the free-data gate. MarketParquet is a documented paid internal-research option at `$79` one-time, but was not purchased or downloaded; no authorization to incur cost was inferred. This source audit is not evidence that strategy edges do not exist. No performance test was run and the two-strategy success condition remains unmet.


## 2026-11-07 — US free/paid API and archive alternatives

### Additional source checks

- **OHLC.io Free** advertises EOD OHLCV, price adjustment choices, `as_of` knowledge cutoffs and stable instrument IDs. Its published Free plan is limited to seven fixed names (AAPL, NVDA, JNJ, PEP, MSFT, SPY, QQQ), five years, a free API account/key, and personal use; it is not the full US universe. Provider documentation describes prior-known corrections, but its ticker/security-master caveat means those API features do not prove a complete historical S&P membership/delist universe. No account or key was created; no data were called or downloaded. It is not eligible for the current broad-market objective. Sources: https://ohlc.io/pricing, https://ohlc.io/data/historical-stock-prices, https://ohlc.io/about, https://ohlc.io/terms.
- **HistoricalData.net** advertises US daily OHLCV from October 2003, active and delisted tickers, raw plus split/dividend adjusted values, and a data license allowing research/backtests after purchase. Its stock archive is priced at `$199`; its free sample is six months from July–December 2022 across TSLA, KO, SPY and TWTR, which the vendor says is for evaluating file formats/workflow. That window and symbol set cannot establish strategy OOS efficacy or full S&P PIT membership; complete delisted-vintage/terminal-settlement behavior remains unverified. No sample or archive was downloaded, no account was created, and no purchase was made. Sources: https://historicaldata.net/about.html, https://historicaldata.net/samples.html, https://historicaldata.net/terms.html, https://historicaldata.net/faq.html.
- Independent red-team corroborated that neither provider currently supplies a free source satisfying the full strategy gate. Agent C report SHA-256: `bf8e429aa69f209f7a3de20f718edb1ac5f116be6f440f66abb59a84ada45b7a` (`/private/tmp/agent_c_source_redteam_20261107.md`). Agent A detailed source audit SHA-256: `c7721685f4f72f0df0ff97e1249a21a00a86c7660ec2ecacdf5111e4392bf190` (`trading/docs/research/us_ohlc_historicaldata_net_audit_20261107.md`). Agent B's further KR search found no qualifying source; report SHA-256: `90f32eeb1004431b2cca1d61a0860b5e7d2cc905b52ebaabaeecd4864ed4f29c` (`trading/docs/research/kr_public_daily_sources_audit_20261107.md`).

### Disposition

No full-gate data source was acquired. No preregistration was changed and no performance backtest ran. The two-strategy success condition remains unmet. A free sample may support file-format/pipeline evaluation only where the provider explicitly permits it; it is not a substitute for the registered full-universe, cost-adjusted OOS tests. Paid sources remain unpurchased and require separate authorization; this project has not been changed into a paid-data task.


## 2026-11-07 — Academic/public repository sweep (four-agent round)

### Newly checked US evidence

- **HF Data Library** advertises CC BY 4.0, but its own terms page restricts the data to academic/educational research and says it must not be used to build or operate trading strategies. Its stated source is IEX HIST, the universe is a fixed ~1,253-ticker panel, and coverage begins 2022-03-07; these facts also fail the consolidated S&P PIT/OOS requirement. No account/key or data was obtained. Sources: https://hfdatalibrary.com/, https://hfdatalibrary.com/pages/terms, https://hfdatalibrary.com/pages/docs.
- **CRSP / CRSPMI and NYSE TAQ** are the closest official-quality reference paths found for active/inactive securities, long historical returns, corporate actions and/or constituents, but they are institutional/licensed products rather than freely accessible public datasets. No institutional credentials or paid access were assumed. CRSPMI's precise S&P membership entitlement would also need contract-level verification.
- **Ken French Data Library and SEC EDGAR** are not daily individual-stock OHLC feeds: French supplies factor/portfolio returns; SEC supplies filings/XBRL. Neither substitutes for executable stock prices.
- The public Zenodo/Mendeley candidate surfaced in search is a 16-stock Yahoo-derived adjusted-price panel for 2022–2024, not a delisted/PIT universe or raw executable OHLC source. Other academic prediction datasets explicitly apply a continuous-listing filter, which preserves survivorship bias. None changes the US data gate.
- Detailed Agent A audit SHA-256: `c8067a988c2e8bdb3c3de9a8e4a8d6408c4adc04d423765889f8e048dcf757aa` (`trading/docs/research/us_free_pit_ohlc_sources_audit_20261107.md`).

### Newly checked KR evidence

- A broader academic/public-repository pass found KRX OHLCV in a paper replication package, a Naver-scraped OHLCV study, an academic purchased-KRX 1-minute sample, a public delisted-ticker metadata list, and a KRX index-indicator catalog. The replication package's MIT code license does not grant rights to underlying KRX bars; the Naver scrape does not establish source reuse permission; the purchased research sample is not a free PIT universe; a delisted-ticker list is not a price panel; and Inofin's index-indicator feed is not individual-stock OHLC, with its license field blank. The KRX/FSC API remains gated by application/key and its listed-stock price data has KOGL Type 4 terms. No price file/value was downloaded or read.
- Detailed Agent B audit SHA-256: `be1abd4431fbb7dd774760cd715e203f8ad9424a929ed69e770ce45d7f697d05` (`trading/docs/research/kr_public_daily_sources_audit_20261107.md`).

### Independent red-team disposition

- Agent C found no counterexample that passes all gates. The closest Korean path remains the KRX Open API, but public documentation does not settle delisted coverage in daily bars, adjustment/corporate-action handling, or whether the intended local PIT backtest/archive use is permitted; account/key/terms acceptance were not attempted. Its report SHA-256: `8063659b16c1408d9e36a1c3701c351954c59ef7a9fb3371234c62d6125a9a61` (`/private/tmp/agent_c_counterexample_audit_20261107.md`).

### Cycle disposition

No new source passed. No strategy preregistration was altered, no market-price data was acquired, and no performance backtest ran. This records additional source failures, not evidence of absent strategy edge. Continue with the full KR/US scope and unchanged two-strategy OOS success criterion; do not substitute academic-only data, factor returns, current-survivor panels, or index-only statistics for PIT execution prices.


## 2026-11-07 — Index-constituent fallback opened

### Scope decision

The earlier data-access blockage is not a strategy-search termination. A separate restricted-universe research path is now open for S&P 500 and KODEX 100/200 member stocks, as well as a separately labeled single-index-ETF path. This does not alter or replace the existing full-universe preregistrations.

### Official-source checks

- KRX Open API's public service list documents daily KOSPI/KOSDAQ stock prices, index prices, and ETF trading data from 2010-01-04. The published service list does not establish historical KODEX 100/200 membership snapshots or constituent effective dates.
- KRX's index information product explicitly describes constituent files (including constituents, index shares, prices, weights and float ratios) and corporate-action/change files. Access, licensing, cost, historical coverage, and permitted research transformations still require confirmation.
- The FSC/KOGL Type 4 KRX ETF quote catalog states attribution, non-commercial use, no-derivatives, and restrictions on third-party redistribution. It is not treated as permission to build transformed strategy signals until the exact data use right is resolved.
- S&P DJI says SPICE is subscription-based and lists S&P 500 constituent data from 1964. Its data licensing page describes subscriptions for index, constituent, and corporate-action data. No free personal entitlement was verified.

Primary sources:
- KRX Open API service list: https://openapi.krx.co.kr/contents/OPP/INFO/service/OPPINFO004.cmd
- KRX index information products: https://openapi.krx.co.kr/contents/OPP/DATA/OPPDATA005.jsp
- FSC/KOGL KRX ETF quote catalog: https://www.data.go.kr/data/15094806/openapi.do
- S&P SPICE coverage/access: https://www.spglobal.com/spdji/en/landing/topic/spice/
- S&P data licensing: https://www.spglobal.com/spdji/en/about-us/data-index-licensing/

### Red-team gate

Applying today's constituents backward creates survivorship and constituent-lookahead bias. Such a run may be retained as `SURVIVOR-COHORT / exploratory only`, but it cannot count as an OOS pass or one of the two target strategies. Valid routes are (1) historical point-in-time membership plus price/corporate-action/delisting outcomes, (2) a hash-frozen present-day cohort evaluated prospectively from its freeze date, or (3) one index ETF treated as a single instrument, with distributions, fees, tracking error, and termination risk accounted for. These are distinct research claims.

### Execution status

- No account, API key, paid subscription, terms acceptance, or server access was attempted.
- No market-price values were downloaded or backtested in this update.
- Strategy performance passes: 0. This is an active fallback research track, not project closure.
- Local plan: `trading/docs/research/kr_us_index_universe_research_plan_20261107.md`.


### Independent three-agent review results

- **KR index data (Agent A):** The official KRX composition screen has a date field, but the supported historical range and automated-download rights are unverified. KRX describes historical membership/weight and index-change files as a data product; its documented purchase path includes registration/login, payment, and purpose review. The free API's stock/ETF daily-price list does not itself establish membership history, adjusted OHLC, delisted coverage, or private-backtest transformation rights. KODEX 100 ETF 237350 began trading on 2016-01-27, so that ETF cannot stand in for earlier index history. Report: `trading/docs/research/kr_kodex_100_200_data_audit_20261107.md`, SHA-256 `2d20bbec0a1cea1b1e3bf5cae92fcefb6e147ac80b3860698ee7a59d5f0239a2`.
- **US index data (Agent B):** S&P's official material provides the current roster and dated changes, while SPICE offers S&P 500 constituent history from 1964 as a subscription service. A complete free PIT constituent file was not found. Public announcement reconstruction completeness and reuse rights remain unresolved. FRED's free S&P 500 series is not constituent OHLC or total-return price data. No account, API key, subscription, or download.
- **Independent red-team (Agent C):** Retrospective current-member testing is survivor-conditioned exploratory analysis only; it cannot pass an OOS strategy gate. Viable valid routes are historical PIT membership/actions/prices/delist outcomes, a cohort frozen today and evaluated prospectively, or a single ETF treated as one instrument with distributions/costs/tracking error/termination risk. Report: `/private/tmp/agent_c_constituent_scope_review_20261107.md`, SHA-256 `85f4509086b193234f40aa803d0eea05d44e0f9221ed88f697a066b69fa20cdf`.

These independent checks reinforce the data-access limitation but do not end strategy research. Next, compare the existing local daily-price cache with the current S&P/KODEX member sets for a strictly labeled survivor-cohort exploratory run, while separately preserving the historical PIT and prospective tracks. Do not count survivor-cohort metrics toward the two valid strategy target. Do not fetch/derive/publish performance values until the local cache provenance and permitted use are reviewed.

## 2026-11-07 — Gen14 close/HLC trend screen preregistration and data gates

- Frozen exploratory screen: `trading/docs/research/PREREG_survivor_closeonly_gen14_20261107.md`, SHA-256 `1524185587405bde943c3b947701a3e4bcf3bf15378b2bca7cdf7ca7236e3893`.
- Execution clarification v1: `ADDENDUM_survivor_closeonly_gen14_v1_20261107.md`, SHA-256 `eda5028211d69b55faf28522989bdb39baff5ce8f592b1fa064eb13874416248`; v2: `ADDENDUM_survivor_closeonly_gen14_v2_20261107.md`, SHA-256 `7bf48257b3b4a8aaed2af371b1c45fd29cb8d9f42b45b48e717df3eaec437768`.
- Frozen input: 7 current US top-cohort names (K=2) and 21 current KODEX 200 top-holdings/cache intersections (K=5); `.kis-cache` manifest SHA-256 `395e3acc608493164700e2fcdfebebe9bca541bfa6e952a3cebdb15ab81a85b4`. This is not PIT index membership.
- Three fixed candidate variations: adaptive KAMA trend (C1), Vortex trend state (C2), and volatility-scaled medium-term momentum above SMA200 (C3). All use monthly close signals and next-union-date close fills; no parameter sweep.
- The earlier 35 US OHLC invariant violations are confined to `Open` on 2021-05-05 (22 rows) and 2023-06-05 (13 rows); Gen14 does not use `Open`. The exact KIS domestic endpoint used locally documents `FID_ORG_ADJ_PRC=0` as adjusted and `1` as raw; a different KIS endpoint uses the opposite mapping, so endpoint semantics must not be transferred between APIs.
- Independent prereg/data/red-team review found and resolved manifest serialization, missing-bar execution, B&H sizing/fees, and terminal liquidation ambiguities before performance values were calculated.
- Performance is now being run independently by three implementations over the complete US/KR × base/stress × IS/OOS matrix. Results remain pending. No candidate counts as a valid strategy because the input cohort is current/survivor-selected and data vintage/rights are not established.

## 2026-11-07 — Gen14 independent close-only candidate results

### Registration and data boundary

- Registration: `PREREG_survivor_closeonly_gen14_20261107.md`, SHA-256 `1524185587405bde943c3b947701a3e4bcf3bf15378b2bca7cdf7ca7236e3893`; addenda v1 `eda5028211d69b55faf28522989bdb39baff5ce8f592b1fa064eb13874416248`, v2 `7bf48257b3b4a8aaed2af371b1c45fd29cb8d9f42b45b48e717df3eaec437768`.
- Input manifest SHA-256: `395e3acc608493164700e2fcdfebebe9bca541bfa6e952a3cebdb15ab81a85b4`. It is a 7-name current US cohort and 21-name current KR KODEX 200 holdings/cache intersection, not historical PIT constituents. The run is exploratory and cannot count as a valid index strategy.
- OOS spans US 962 sessions (2023-01-03–2026-11-02) and KR 934 sessions (2023-01-02–2026-11-02). Benchmark is equal-weight buy-and-hold on the same fixed cohort. Candidate rules were preregistered: C1 KAMA adaptive trend, C2 Vortex + SMA100, C3 risk-adjusted 126-day momentum above SMA200.

### Corrected independent reproduction

Agents A and B independently reproduced 16 OOS daily NAV paths across benchmark/candidates, both markets, and base/stress costs. Root compared all dates and daily NAVs; maximum absolute difference was 1.24e-14 versus the frozen 1e-10 tolerance. Fill counts, turnover and costs matched. Two 12-decimal hashes differed at a floating-point rounding boundary; hashes are not claimed identical for those cells.

Agent C's first KR-stress run used a wrong sell-cost parameter (0.00345 instead of the registered 0.00295). Its first-pass KR stress metrics and hashes are discarded. C corrected and reran; corrected stress curves matched Agent A. Only corrected A/B values are used.

| Market | Candidate | Base CAGR / Sharpe / MDD | Stress CAGR / Sharpe / MDD |
|---|---|---|---|
| US | C1 KAMA | 36.57% / 1.346 / -16.49% | 32.97% / 1.241 / -17.21% |
| US | C2 Vortex + SMA100 | 27.24% / 1.074 / -30.50% | 23.63% / 0.959 / -31.33% |
| US | C3 risk-adjusted MOM126 + SMA200 | 26.39% / 1.009 / -29.29% | 21.13% / 0.847 / -31.20% |
| KR | C1 KAMA | 19.19% / 0.669 / -55.80% | 18.53% / 0.654 / -55.89% |
| KR | C2 Vortex + SMA100 | 37.42% / 1.012 / -50.92% | 36.69% / 0.999 / -50.92% |
| KR | C3 risk-adjusted MOM126 + SMA200 | 12.23% / 0.509 / -45.21% | 11.36% / 0.487 / -45.37% |

Same-cohort B&H: US base 50.78% CAGR / 1.543 Sharpe / -30.61% MDD; stress 50.56% / 1.538 / -30.61%. KR base 49.14% / 1.269 / -48.44%; stress 49.10% / 1.268 / -48.44%.

### Decision

The frozen gate requires beating same-cohort B&H on CAGR and Sharpe without worse MDD under both cost cases. **0/6 candidate-market combinations passed; 0/12 candidate-cost cells passed.** Gen14 found no valid strategy and does not change the target of two valid strategies. No post-result data exclusions were made. Cache vintage/request provenance remains absent, and 21 >20% close-to-close changes were observed (several KR names on 2026-07-31); cache-only evidence cannot classify their cause.

Next generation must test materially distinct families, preregister rules/accounting before reading performance, retain exploratory labels on these current cohorts, and continue the separate PIT data work.

## 2026-11-07 — Gen15 conditional panic-reversal preregistration

- Frozen preregistration: `trading/docs/research/PREREG_conditional_panic_reversal_gen15_20261107.md`, SHA-256 `8b2d1026a3cf764b5f9436ea10dc548e9a0319fbf30f153f9d802dd7d86eadb7`.
- Frozen 28-file input manifest SHA-256: `395e3acc608493164700e2fcdfebebe9bca541bfa6e952a3cebdb15ab81a85b4`; US 7-name cohort/K=2 and KR 21-name current KODEX 200 holdings/cache intersection/K=5. This is a survivor cohort, not historical PIT index membership, and any return test is exploratory only.
- Candidate classification: a conditional short-horizon reversal variant, related to catalogued cross-sectional reversal, RSI2 and rebound studies. It is not presented as an independent novel strategy family, and is subject to accumulated reversal-family selection burden.
- Fixed hypothesis: equal-weight cohort market proxy falls at least 2 times the preceding 247-session population volatility times sqrt(5), while the individual security has a negative 5-session return, close-location value (CLV) at least 0.60, and volume at least 2 times the median of the previous 20 observed bars. Rank by CLV; enter at next union-session close, hold through five subsequent valid security closes, exit at the fifth. No parameter grid or post-result tuning.
- Frozen accounting includes market coverage ≥80%, missing-data and no-fill semantics, K slots, terminal exits, same-cohort buy-and-hold, and explicit base/stress costs. Per-date NAV is fixed before the buy batch; each slot all-in spend is NAV/K, with gross buy amount reduced by the one-way fee so fees do not cause systematic initial under-allocation. On non-terminal missing-bar dates, NAV alone may use last actual close; no signal/fill/holding observation is synthesized. Terminal liquidation requires a valid terminal-date close. At execution, after due exits, ranked candidates are tried until K slots are filled or the candidate list ends; canceled missing-price or cash-limited orders do not block the next rank. The same-cohort B&H baseline matches Gen14 delayed-start rules: fixed per-name gross G, reserve the all-in slot budget in cash when start close is unavailable, buy only at the first actual valid close, or leave cash if none occurs. US one-way costs: 0.08%/0.36%. KR: base buy 0.065% / sell 0.245%; stress buy 0.115% / sell 0.295%.
- Three independent agents are implementing separately and running synthetic accounting/prefix/future-mutation tests only. No actual price performance has been opened or computed for Gen15 yet. Performance is authorized only after the independent implementations pass prereg gates.
- The Oracle cumulative trial databases are not available locally. Oracle access will not be retried. Global cumulative N is unknown, so no DSR/PSR/Bonferroni/BH significance will be claimed. A current-cohort screen, even if numerically promising, cannot count toward the two valid strategies until PIT data, source rights, adjustment/vintage, and cumulative multiple-testing gates are resolved.
- Separate event-driven candidates logged for future feasibility: US SEC Form 4 clustered buying (public filing source but PIT CIK/security map and price universe unresolved), and as-filed EPS/SUE drift (SEC possible for US; OpenDART key/account gate unresolved for KR). Neither has had a price-performance test.

## 2026-11-07 — Gen15 data gate (blocked before performance)

- The frozen preregistration SHA-256 is `8b2d1026a3cf764b5f9436ea10dc548e9a0319fbf30f153f9d802dd7d86eadb7`; the 28-file local input manifest reproduced as `395e3acc608493164700e2fcdfebebe9bca541bfa6e952a3cebdb15ab81a85b4`.
- A read-only schema/field-quality scan covered 58,796 rows. Dates were sorted and unique; positive finite OHLC values and OHLC relationships passed. Three KR files contained 30 rows with zero volume: 005930 (3 rows, 2018-04-30–2018-05-03), 017670 (24 rows, 2021-10-26–2021-11-26), and 035420 (3 rows, 2018-10-08–2018-10-11).
- The frozen Gen15 data gate requires valid volume and explicitly blocks on input-field quality failure. Disposition: `DATA_BLOCKED` before performance. No IS/OOS returns, signal-performance comparison, or candidate metrics were computed. No row was corrected, dropped, or silently reinterpreted. The candidate is neither performance-rejected nor passed.
- Independent synthetic-only implementation checks passed: A 15/15, B 24/24, C 24/24. These validate mechanics only, not market performance. The three runners embed the frozen preregistration SHA.
- Next action: continue no-cost data-source feasibility research and prepare a materially distinct, preregistered close-only hypothesis only if its input and adjustment rules pass a separate data gate. The 0/2 valid-strategy count does not change.


## 2026-11-07 — Gen16 preregistration and input gate (status only)

- Frozen preregistration: `trading/docs/research/PREREG_calendar_closeonly_gen16_20261107.md`; SHA-256 `d43cb7cb869e19ad138b7a099583b2b288527572b3f2b6857447a92e6b0954ab`.
- Two fixed close-only calendar hypotheses: (C1) first observed union-session close entry, fourth observed same-month session exit, with a causal next-month-first-session exit if the month changes before a fourth session; (C2) exact five-year same-calendar-month cross-sectional score, OOS-only, full ranked fallback, and next-month-first-session exit. No parameter grid.
- Three independent prereg readers identified issues in earlier drafts; the final revision resolved the stated timing/accounting ambiguities. This is specification review only; synthetic and independent implementation gates remain pending.
- The local close-only input gate verified the frozen 28-file manifest `395e3acc608493164700e2fcdfebebe9bca541bfa6e952a3cebdb15ab81a85b4` and 58,796 rows for timestamp/close structure only. No returns, signals, benchmark performance, or derived performance figures were calculated.
- Price-source rights, adjustment/vintage, corporate-action provenance, and PIT membership remain unresolved. If the exploratory screen proceeds, this repository will retain method/status/hashes only until those rights are verified; no derived performance numbers or pass/fail results are published here. No strategy count changes.

## 2026-11-07 — Gen16 close-only calendar screen execution (status and provenance only)

- Final frozen preregistration SHA-256: `1d85c35f9696ee3c982f62027f96599aeed7f3d3d3e99dc8efbabf250a350342`. This supersedes the earlier draft hash `d43cb7cb869e19ad138b7a099583b2b288527572b3f2b6857447a92e6b0954ab` listed in the initial Gen16 status entry.
- Frozen 28-file input manifest verified as `395e3acc608493164700e2fcdfebebe9bca541bfa6e952a3cebdb15ab81a85b4`.
- Three synthetic-only independent implementations passed their frozen tests: A 31/31, B 29/29, C 16/16. A/B independently executed the frozen local screen and reconciled 20 candidate/market/segment/cost cells; daily NAV maximum absolute difference was `6.22e-15`, with fills, shares, notionals, fees and cash matching within `1e-10`.
- The local exploratory run is complete. Detailed metrics and candidate screen disposition are retained only in the local research log because price-source rights, adjusted-price vintage/corporate-action provenance, and PIT membership remain unresolved. This entry deliberately does not publish derived performance figures or pass/fail outcomes, and does not change the count of valid strategies.
- CAGR day-count basis (365.2425 versus 365.25) was not specified in the frozen text. This does not affect paired terminal-NAV ordering, but the basis must be explicitly frozen before the next generation's performance output.
- No Oracle server was accessed, no live orders were placed, and no Ochestration commit or push was made.


## 2026-11-07 — Gen17 low-skew factor (method/status only)

- Preregistration SHA-256: `ecd75ddbae7b59813bbc4837aba2f58d139adb8ec117c89087d07e7334e6cc58`.
- Input-manifest SHA-256: `395e3acc608493164700e2fcdfebebe9bca541bfa6e952a3cebdb15ab81a85b4`.
- Candidate: fixed 63-return, bias-corrected Fisher–Pearson G1 cross-sectional low-skew rank, fixed K, 21-union-session schedule, frozen base/stress costs. It is a known factor variant on the current survivor cohort and reused OOS window, not a newly validated independent strategy.
- Three synthetic independent implementations passed their test suites (A 29/29, B 39/39, C 14/14). Actual overlap diagnostics agreed across A/B/C on all preregistered dates.
- A local exploratory market screen has been recorded. Numerical results are intentionally not reproduced here: price-data use rights, adjustment/vintage, point-in-time membership and cumulative trial-count gates are unresolved, and the required full per-date independent reconciliation was completed after metric exposure. Accordingly no valid-strategy pass, significance claim, or strategy count increase is recorded.
- Disposition: exploratory only; **valid strategy count remains 0/2**. Do not tune this frozen candidate post-result. The detailed local evidence remains in the Ochestration workspace; this repository records method/status/hashes only until the data-use and validation gates are cleared.
