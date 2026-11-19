# Equity data source follow-up — 2026-11-20

## Decision

The current public-source review narrows, but does not clear, the stock/ETF data gate. CRSP is the strongest identified US candidate for survivor-aware daily research. KRX exposes a public delisted-stock price-history screen, but that screen is not permission to automate collection or reuse the data in a research product. No strategy backtest was run and no sample, quote, account, or paid data was obtained.

## Korea — KRX

- The official **delisted-stock price trend** screen exposes date, ticker/name, market/security type, close/change/return, open/high/low, volume, value, market cap, delisting date, and delisting reason. KRX warns that the displayed market data may be delayed or erroneous. This establishes that a public UI can show historical delisted-stock observations; it does not establish a complete, downloadable, adjusted total-return history or a licensed research dataset. [Delisted-stock price trend](https://data.krx.co.kr/contents/MDC/STAT/issue/MDCSTAT239.jsp)
- The separate **delisted-stock status** screen exposes listing date, delisting date/reason, market, security type, and other final-status fields. This is useful for building a delisting roster only if its history, exportability, and reuse terms are confirmed. [Delisted-stock status](https://data.krx.co.kr/contents/MDC/STAT/issue/MDCSTAT238.jsp)
- KRX Data Marketplace terms prohibit unauthorized automated collection and copying, redistribution, transmission, or public communication; market-data products are governed by separate purchase/use terms. Therefore, do not scrape the public UI as a substitute for an authorized bulk feed. [KRX site terms](https://data.krx.co.kr/contents/MDC/INFO/informationController/MDCINFO003.cmd)
- The reviewed public pages did not provide a usable sample file or a public quote for a complete stock+ETF point-in-time package. A product-level sample/quote and permitted research use remain unresolved.

## United States — CRSP

- CRSP's current US Stock Databases page describes daily/monthly data for more than 32,000 active and inactive US securities, permanent PERMNO/PERMCO identifiers, corporate actions, delisting information, returns with and without dividends, and index series including the S&P 500. This is a strong technical fit for survivorship-aware daily equity research. Exact ETF coverage and point-in-time ETF membership still need confirmation. [CRSP US Stock Databases](https://www.crsp.org/research__trashed/crsp-us-stock-databases/)
- CRSP states that product materials migrated to Morningstar Indexes on 2026-06-30. The public page exposes subscription-information routes but no current price. [CRSP product page](https://www.crsp.org/research/crsp-us-stock-databases-2025-layout/)
- CRSP's public sample guide says promotional SAS/ASCII samples are available by request to `subscriptions@crsp.org`; this guide is from 2023, so present availability and the current workflow must be reconfirmed against the migrated product page. The guide is a request route, not a sample already received. [CRSP sample guide](https://www.crsp.org/wp-content/uploads/2023/09/CRSP_Sample_Data_and_Software_Guide.pdf)
- No subscription quote, sample, account, contact, or paid data was obtained in this review.

## Effect on the research plan

1. Keep KR and US strategy performance at `NOT_EVALUABLE` for point-in-time, all-regime research until a lawful, reproducible historical package and its terms are confirmed.
2. For US, the next diligence target is CRSP sample plus a quote for daily active/inactive stocks **and ETFs**, including survivorship, delisting, corporate-action/total-return, constituent-history, risk-free-rate, and personal research-use terms.
3. For KR, request KRX's official data-product sample and quote covering listed and delisted stocks plus ETFs, point-in-time universe membership, adjusted total returns/corporate actions, index benchmarks, and automated internal-research use. Do not automate the public UI.
4. After data arrives, verify only a small manifest/sample first: fields, IDs, date coverage, delisting/corporate-action cases, ETF constituents, and license terms. Preregister a candidate only after those checks; keep validation/sealed periods closed.

This source review does not authorize account creation, a purchase, scraping, or a performance claim. It supports data-source selection only.
