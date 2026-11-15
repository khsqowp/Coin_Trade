# R003 — Data-source options across KR, US, and crypto

Status: `source_gate_partial`; no price data acquired or read, and zero performance cells.

## Objective

Advance the active research program without rerunning exposed survivor-cohort grids: identify whether any no-purchase path can lawfully and technically support (a) KR/US cash stock and ETF strategy research, and (b) prospective USDT-perpetual directional signal evaluation for the user's manual decisions.

Targets remain separate: KR/US exploratory CAGR near 20% is not guaranteed and no max-drawdown limit has been set; crypto's requested >=80% selective target-first signal quality has not been demonstrated. Neither result can be inferred from this source audit.

## Method and boundaries

- Four independent research agents reviewed KR data, US data, crypto historical/prospective data, and an adversarial cross-track design, respectively. Their responses were evidence-linked but were not independent reproductions of local files or raw datasets.
- The lead reviewer independently checked KRX's official service list and terms, CRSP product information, NYSE Daily TAQ documentation/pricing, Nasdaq legal terms, Binance Vision terms, and Binance USDⓈ-M stream documentation.
- No account/API key was created; no contract was accepted; no provider was contacted; no data were downloaded; no price row/database was opened; no strategy or performance test was run; no paid product was purchased; no public comment was posted.
- Distinguish source existence, technical endpoint capability, legal/use permission, point-in-time coverage, actual data quality, and strategy performance. Passing one does not imply the others.

## Findings

### Korea

- Official KRX OPEN API lists daily KOSPI/KOSDAQ index series, daily stock trading information, and ETF daily trading information beginning 2010-01-04. It is a plausible route for daily single-instrument or current/universe exploratory work, but the service-list page does not by itself prove complete historical listing/delisting coverage, adjusted-price vintage, ETF composition history, or survivorship-free PIT membership. See [KRX API service list](https://openapi.krx.co.kr/contents/OPP/INFO/service/OPPINFO004.cmd).
- API use requires agreement, login/account, key application, and service application/approval. Official terms limit API service use to non-commercial purposes, prohibit providing supplied data to third parties, and do not warrant accuracy/completeness or continued availability. The user has not authorized registration, agreement acceptance, or key handling. See [KRX API terms](https://openapi.krx.co.kr/contents/OPP/INFO/OPPINFO002.jsp) and [usage steps](https://openapi.krx.co.kr/contents/OPP/INFO/OPPINFO003.jsp).
- KRX states that an individual's use of price information beyond simple reference, including other purposes, may require a separate contract. Thus, the API's non-commercial clause is not treated as a blanket approval for every backtest/storage purpose. See [KRX data-receipt guidance](https://openapi.krx.co.kr/contents/OPP/DATA/OPPDATA003.jsp).
- One agent located KRX date-filtered index constituent and delisted-security screens plus data.go.kr and Open DART adjuncts. Those may support a coverage audit, but page existence is not proof of a complete historical PIT archive or permission for bulk retrieval. This lead was not independently tested and no screen/API was queried.

### United States

- Nasdaq's public historical page is not a demonstrated bulk-data license. Its current legal terms prohibit using any process, automated or manual, to capture data/content from Nasdaq services. The public page therefore is not an authorized substitute for an OHLC history acquisition path. See [Nasdaq historical data](https://www.nasdaq.com/market-activity/quotes/historical) and [Nasdaq legal terms](https://www.nasdaq.com/legal).
- CRSP describes daily/monthly data for active and inactive securities, corporate actions, permanent identifiers, delisting information, and survivor-bias-free history. It is a subscription product; this audit did not establish user's access, cost, or point-in-time release-vintage guarantees. See [CRSP US Stock Databases](https://www.crsp.org/research/crsp-us-stock-databases/).
- NYSE Daily TAQ describes consolidated trades/quotes for CTA/UTP participating U.S. equity markets, with history from 1993. NYSE publishes commercial prices and license-based access. TAQ can support trade-derived bars but does not, by itself, establish total-return adjustment, corporate-action treatment, or index PIT membership. See [Daily TAQ](https://www.nyse.com/data-products/catalog/daily-taq), [TAQ client specification](https://www.nyse.com/publicdocs/nyse/data/Daily_TAQ_Client_Spec_v3.3b.pdf), and [current historical pricing](https://www.nyse.com/publicdocs/nyse/data/NYSE_Historical_Market_Data_Pricing.pdf).
- SEC EDGAR is an event/filing source, not daily OHLCV. It can supplement a future event study but cannot replace price, corporate-action, or universe inputs.

### Crypto

- Binance Vision's official dataset terms permit specified non-commercial uses including purely personal, non-production historical backtesting, and prohibit live proprietary trading execution, automated commercial order generation, and compensated third-party signal distribution. The terms do not expressly settle the user's narrower scenario—private/manual decisions using Vision-derived analysis—so this report makes no legal conclusion and does not treat the use as cleared. See [Binance Vision terms](https://github.com/binance/binance-public-data/blob/master/TERMS_AND_CONDITIONS.md).
- Binance USDⓈ-M has official public market REST and WebSocket interfaces. The official futures WebSocket docs state that a connection is limited to 24 hours, with ping/heartbeat, incoming-message, and stream-count limits; reconnecting and gap reconciliation must therefore be implemented and measured. A stream endpoint's existence does not establish complete historical coverage or the user's rights for downstream use. See [USDⓈ-M WebSocket market streams](https://developers.binance.com/en/docs/products/derivatives-trading-usds-futures/websocket-market-streams/Connect).
- The official funding-history endpoint is a technical source candidate, not evidence of complete payable funding across all historical/delisted contracts. See [USDⓈ-M funding history](https://developers.binance.com/docs/derivatives/usds-margined-futures/market-data/rest-api/Get-Funding-Rate-History).
- Agents listed Bybit and OKX as possible public-data alternatives, but did not establish applicable data-use rights, complete delisted-contract coverage, or complete funding history. These remain unverified leads; do not substitute venue data or run a new test from them yet.
- The user-facing 80% signal goal also needs an immutable target-first contract: signal anchor and closed-bar rule, horizon by timeframe, stop/target construction, abstention/coverage, overlapping-signal resolution, fees/funding/slippage, sample size, confidence interval, multiplicity correction, and one-time sealed decision. A provider or model consensus cannot replace this contract.

## Four-agent synthesis and limitations

- KR researcher: free official routes may aid exploratory work; no unauthenticated unrestricted source was shown to supply a complete PIT universe, delisted-price history, adjustment provenance, and clear internal-use rights together. KRX source work still requires independent empirical coverage/license checks.
- US researcher: no demonstrated free/no-account route met PIT, delisting/corporate-action, and internal research-right requirements. CRSP/TAQ are plausible paid/licensed routes; no provider was contacted and no quote was obtained.
- Crypto researcher: no alternative exchange source was shown to meet all license, PIT universe, delisted history, funding completeness, and intended manual-use requirements. A live public stream could support future observation only after applicable terms and a frozen signal protocol are cleared.
- Adversarial reviewer: current survival-cohort results and exposed historical grids cannot substantiate 20% CAGR or 80% accuracy. It recommended preserving old files, stopping further tuning on them, and using a genuinely new forward period only after data rights and the evaluation contract are resolved.
- Agent reports are recommendations, not legal advice or proofs of data completeness. Findings explicitly marked as agent leads are not promoted to verified facts.

## Decision and next gate

No historical performance work is authorized by this audit. The active strategy goal remains unmet. The next lawful/actionable step is not another parameter test: it is to resolve the source/use path for each market and freeze its quality criteria. KRX's authenticated API is a possible non-commercial route if the user independently elects to register/accept terms; U.S. broad PIT OHLC likely needs licensed data or a narrower single-ETF claim; crypto can consider a prospective shadow period only after the live-data use scope and signal contract are resolved. No one should create accounts, accept terms, spend money, or contact vendors without separate authorization.
