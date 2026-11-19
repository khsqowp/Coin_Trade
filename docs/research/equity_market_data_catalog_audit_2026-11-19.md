# KR/US equity data catalog check — 2026-11-19

## Scope

Read current public official product/catalog pages only. No account creation, API key request, data download, vendor contact, quote request, or market-price/outcome access was performed. This is a current public-catalog check, not legal advice or proof of an individual license.

## Korea — KRX / ETF

- The KRX OPEN API service list documents daily stock and ETF transaction data beginning 2010-01-04. It does not list intraday or 1-minute stock/ETF candles.
- KRX's market-data distribution page says individuals may view real-time/delayed (20-minute or end-of-day) data through brokers and vendors for reference. Use beyond simple reference, including program development, requires a separate agreement. Professional market-data subscription is routed through Koscom and requires KRX approval and contract.
- The public catalog does not establish a downloadable, historical, licensed 1-minute OHLCV feed or its price. The appearance of intraday data on broker screens is not evidence of research/backtest rights.
- A KR single-ETF intraday VWAP-reversion hypothesis remains only a research idea; it cannot be tested until data resolution, history, entitlement, ETF distributions/corporate actions, and execution costs are verified.

## United States — CRSP / Morningstar Indexes

- Current CRSP US Stock Databases documentation specifies daily and monthly stock data, corporate actions, active and inactive securities, delisting information, and permanent identifiers. It does not specify intraday stock/ETF candles.
- CRSPMI Intraday is explicitly second-by-second and end-of-day **index** levels, not per-security equity or ETF bars. It does not meet this project's tradable-universe need.
- Current product pages expose a subscription-information request, not a public price quote. The reviewed public pages do not grant this project a license.
- The publicly indexed CRSP sample guide is dated 2019 and describes promotional samples for internal preview/evaluation; its sample stock universe is 25 issues and its example history ends in 2019. It is not an adequate basis for a current out-of-sample strategy backtest or a license claim.

## Additional US candidate — public S&P 500 + ETF GitHub snapshot

- The dataset author's README claims point-in-time S&P 500 membership from 1970, member prices plus selected ETFs, and daily bars through the current date. It reports 1,895 tickers, 1,742 ever-members, and a 235 MB Parquet file. These are author claims; the files were not downloaded or independently verified.
- Lineage is mixed: the README says 1970–1995 relies on CRSP; 1996 onward is checked against CRSP and other sources; 2019–present membership is reconstructed from a Wikipedia change log. It identifies 17 recycled tickers to exclude, incomplete independent checks for recent NYSE dividends and 12 acquired firms, and different ETF start dates.
- The repository page and README expose no explicit data license. “Free”, public access, and a public release do not establish permission to copy, retain, or redistribute underlying third-party market data. The latest immutable release visible in the repository is dated 2026-11-03, but its exact file hash/data cutoff was not checked.
- **Decision: conditional discovery lead only; no download or backtest.** First establish explicit research/retention rights, then freeze the release and verify its hash, PIT membership, ETF life dates, corporate actions, and stated exclusions. Any later test would be limited to the documented S&P 500 member universe and ETFs, not described as the whole US equity market.

## Decision

Both equity domains remain at **data-readiness / no performance backtest**. Do not use the local daily caches as intraday data. Do not infer research rights from public chart access or a sample-data file. A future strategy study requires written terms covering internal algorithmic research/backtesting, interval/history, PIT/delisted universe, corporate actions, storage/derived results, and costs. User-authorized sample/quote lookup does not authorize account creation, purchase, or an external inquiry.

## Official sources checked

- KRX OPEN API service list: https://openapi.krx.co.kr/contents/OPP/INFO/service/OPPINFO004.cmd
- KRX data receipt and use-contract process: https://openapi.krx.co.kr/contents/OPP/DATA/OPPDATA003.jsp
- KRX distribution products: https://openapi.krx.co.kr/contents/OPP/DATA/OPPDATA002.jsp
- CRSP US Stock Databases (current product description): https://indexes.morningstar.com/research-data-products/crsp-us-stock-databases
- CRSPMI Intraday (index product): https://www.crsp.org/research/crspmi-intraday/
- CRSP sample-data guide (legacy 2019 guide): https://www.crsp.org/wp-content/uploads/2023/09/CRSP_Sample_Data_and_Software_Guide.pdf
- Candidate repository README: https://github.com/Johnbrick123/sp500-data
- Candidate immutable releases: https://github.com/Johnbrick123/sp500-data/releases
