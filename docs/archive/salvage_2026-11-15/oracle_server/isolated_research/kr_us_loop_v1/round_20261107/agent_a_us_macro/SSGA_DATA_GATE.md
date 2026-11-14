# SSGA SPY Data-Source Gate — Metadata and Schema Only

- Checked: 2026-11-07 04:08 UTC
- Scope: official State Street/SSGA SPY NAV history, product-data workbook, and historical-distribution workbook. This is a source-feasibility audit only.
- Frozen CFTC candidate: unchanged and remains `DATA_BLOCKED`.
- Numeric performance/data cells: not decoded, printed, persisted, or backtested. The three public XLSX payloads were fetched into memory only; the parser inspected workbook structure and string labels in the first 30 rows to locate header rows, then emitted only workbook metadata, header labels, and SHA-256 hashes. It did not emit or interpret any data-row cell values.

## Finding

SSGA exposes a no-login, no-API-key SPY NAV-history XLSX with a daily `Date, NAV, Shares Outstanding, Total Net Assets` schema, plus a separate distributions XLSX with ex-date, record date, payable date, dividend and short/long-term capital-gain fields. This is a daily NAV/accounting series, not executable exchange OHLC. The product-data workbook is a point-in-time fund snapshot: it includes fields such as closing price, day high/low, and NAV, but has no dated OHLC time series schema.

The download endpoint is technically public and returned HTTP 200 without credentials. This does **not** establish a license for private backtesting/reuse. The official fund page says the whole or any part may not be reproduced, copied, transmitted, or disclosed to third parties without SSGA's express written consent. No express permission for private research/backtesting was found in the inspected official page text. Therefore, do not use the workbook values for a performance test until reuse rights are clarified. SSGA also labels the page as intended for U.S. investors.

## Official endpoints, metadata, and schema

1. SPY product page: <https://www.ssga.com/us/en/intermediary/etfs/state-street-spdr-sp-500-etf-trust-spy>
   - The page exposes “Most Recent NAV / NAV History” and “Download Product Data” links (web inspection: lines 173 and 303–322).
   - NAV link: <https://www.ssga.com/library-content/products/fund-data/etfs/us/navhist-us-en-spy.xlsx>
   - `GET` returned 200, XLSX MIME type, 278,814 bytes; `Last-Modified: Fri, 06 Nov 2026 05:58:34 GMT` on HEAD.
   - In-memory workbook SHA-256: `7aa8414e1cc8ab09f1fe20c321f5c87493c81b32936154f80db40b350286a683`.
   - Sheet: `navhist`; header row fields: `Date`, `NAV`, `Shares Outstanding`, `Total Net Assets`.
   - The source is explicitly labelled “NAV History”; daily frequency is independently corroborated by the workbook's date-row structure only insofar as the official artifact is a NAV-history file. Exact first/last dates and gaps were deliberately not inspected.
   - No OHLC, exchange close, intraday price, or distribution column appears in the observed header schema.

2. Product data endpoint: <https://www.ssga.com/library-content/products/fund-data/etfs/us/spdr-product-data-us-en.xlsx>
   - The official page calls it “Download Product Data” (web inspection: lines 318–322).
   - `GET` returned 200, XLSX MIME type, 96,813 bytes.
   - In-memory workbook SHA-256: `cb596f3f321bf1c743a2c7f7d9cd7f31ad585f85c211303422a1b05fb0af1fd5`.
   - Sheet: `Sheet1`; header row has `As of**`, `Ticker`, `Name`, identifiers, `Closing Price`, `Day High`, `Day Low`, `NAV`, `Shares Outstanding`, `Total Net Assets`, and `Total Returns` period/measurement fields, among other current product descriptors.
   - This is a current product-finder snapshot, not a historical daily price file: there is one as-of field, not a date-indexed OHLC history.

3. Historical distributions page: <https://www.ssga.com/us/en/individual/resources/documents/etf-dividend-distributions>
   - The page links “SPDR Historical Distributions XLSX” and defines ex-date, record date, and payable date (web inspection: lines 31–52).
   - Workbook: <https://www.ssga.com/library-content/products/fund-data/etfs/us/spdr-etf-historical-distributions.xlsx>
   - `GET` returned 200, XLSX MIME type, 584,557 bytes.
   - In-memory workbook SHA-256: `4add18439e505ba6c114bea5d352ac68b1ea5420bc99abdf2e21500dd6f1faa2`.
   - Sheet: `dividend`; header row fields: `FUND NAME`, `TICKER`, `CUSIP`, `EX-DATE`, `RECORD DATE`, `PAYABLE DATE`, `DIVIDEND ($)`, `SHORT TERM CAPITAL GAIN ($)`, `LONG TERM CAPITAL GAIN ($)`, `FREQUENCY`.
   - No NAV, market price, or total-return series is present in this distribution schema. Exact distribution date span was not inspected.

## Access and terms assessment

- Authentication/API key/payment: none required for the observed direct HTTPS GETs; all three returned HTTP 200 from the Oracle host. This establishes technical downloadability only.
- No bot challenge, login wall, or access-control bypass was used.
- The SSGA page footer states: “The whole or any part of this work may not be reproduced, copied or transmitted or any of its contents disclosed to third parties without SSGA’s express written consent.” It does not explicitly grant private-research/backtest rights. Treat data-use permission as unresolved; do not infer permission from public access.
- The SPY product page states it is intended for U.S. investors and that ETFs can trade above/below NAV. It also says total-return figures assume distributions/capital gains are reinvested at NAV and actual returns may differ.

## Decision for strategy research

- The official NAV-history file is a candidate input for a *separate, explicitly non-executable NAV-series exploratory study*, but it cannot satisfy the frozen candidate's market-price/OHLC/executable-price gate and must never be substituted into that candidate.
- A NAV-only exploration could measure signals on daily fund NAV returns and use the distributions file for cash-distribution accounting, clearly labelling the result as fund-NAV research rather than tradable SPY backtest evidence. NAV is calculated by the fund, while ETF shares trade on an exchange at market prices; assuming fills at NAV would be an execution-model assumption, not demonstrated execution.
- Do not preregister or open values for that new exploration until (a) SSGA data-use permission is clarified, and (b) a separate preregistration explicitly distinguishes NAV observations from executable market prices, specifies how signals map to next available tradable prices (or states that no tradability claim is made), and defines date-span/missing-row gates.
- The frozen CFTC candidate remains untouched. No strategy performance test was run: 0 new candidate backtests, 0 performance value cells read.

## Reproducibility record

- Official page links were inspected with the web tool; direct XLSX metadata/schema probes ran over SSH using Python stdlib `urllib`, `zipfile`, and `xml.etree`; no remote files were written.
- The single HEAD probe on the SPY NAV-history endpoint returned HTTP 200 and the metadata listed above.
- The schema probe fetched the three workbook payloads in memory. It printed HTTP status/content type/size/SHA-256, sheet names, and header labels only. No numeric data-row values, date values, or performance values were decoded or printed.
- No backtest, strategy test, or trade simulation was run.
