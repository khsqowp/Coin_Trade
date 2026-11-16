# R020 — KRX and CRSP sample/quote source audit

Date: 2026-11-16
Status: public source-access audit; **not a strategy performance trial**

## Question

What can be established from official public sources about obtaining historical daily stock/ETF data, sample files, and prices from KRX and CRSP for a future backtest? Is there enough public information to select and budget a point-in-time dataset without creating accounts, buying data, or contacting a vendor?

## Frozen scope

- KRX official Data Marketplace, OPEN API documentation, and official stock/ETF data product pages.
- CRSP official US Stock Database and official sample-data documentation.
- Public pages and documents only. No login, account creation, API-key request, download of licensed sample data, purchase, vendor message, or disclosure of user identity/contact information.
- Capture coverage claims, sample access method, public pricing availability, and unresolved ETF/universe/delisting/license terms.
- Calculate no strategy metrics and access no market observations.

## Decision rule

- Treat a coverage or pricing statement as established only if stated by an official source.
- A gated detail is `not publicly verified`, not “unavailable” or “free.”
- Do not proceed to an equity performance backtest until the intended dataset, historical universe including inactive securities, corporate-action treatment, ETF coverage, cost/license terms, and reproducible sample are documented.

## Official references

- KRX data purchase guide: https://openapi.krx.co.kr/contents/OPP/DATA/OPPDATA001.jsp
- KRX OPEN API usage guide: https://openapi.krx.co.kr/contents/OPP/INFO/OPPINFO003.jsp
- KRX service catalogue: https://openapi.krx.co.kr/contents/OPP/INFO/service/OPPINFO004.cmd
- CRSP US Stock Databases: https://www.crsp.org/research__trashed/crsp-us-stock-databases/
- CRSP Sample Data and Software Guide: https://www.crsp.org/wp-content/uploads/2023/09/CRSP_Sample_Data_and_Software_Guide.pdf
