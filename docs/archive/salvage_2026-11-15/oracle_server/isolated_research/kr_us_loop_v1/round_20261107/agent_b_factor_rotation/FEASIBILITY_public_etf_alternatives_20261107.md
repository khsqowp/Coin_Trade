# Public Issuer/Exchange ETF Price-Series Feasibility — US alternatives

Date: 2026-11-07
Status: `NO_QUALIFYING_SOURCE_FOUND`
Scope: source/terms/calendar metadata only. No historical price rows or performance values accessed or computed; no preregistration/backtest.

## Strongest near-match: Vanguard Total Stock Market ETF (VTI)

- Vanguard says its ETF profile Price tab provides historical daily closing market price and NAV: <https://investor.vanguard.com/investor-resources-education/etfs/what-is-an-etf?msockid=2c1b875f5df96f992fbf91d65ca86ebd>.
- Vanguard Advisors' VTI page exposes “Export historical price data” and distinguishes secondary-market market price from NAV. Its page identifies price data as FactSet-provided and delayed: <https://advisors.vanguard.com/investments/products/vti/vanguard-total-stock-market-etf>.
- Vanguard's general site terms explicitly allow a limited license to view/store/bookmark/download content solely for personal, informational, noncommercial use, but also bar copying, modifying, or creating derivative works from reports/data/content without written permission: <https://investor.vanguard.com/terms-conditions?lang=en>. Therefore the terms do **not clearly authorize** transforming downloaded values into a backtest time series/derived performance record. The displayed market data is also third-party licensed (FactSet), so the website grant alone does not establish that rights from the data provider extend to this use.
- VTI is an investable US total-market ETF, but it is not the S&P 500. Vanguard's current product page says it seeks to track the Morningstar US Total Market Index and gives inception 2001-05-24: <https://advisors.vanguard.com/investments/products/vti/vanguard-total-stock-market-etf>. The exact downloadable daily file start/end coverage was not available in readable page metadata; the current benchmark description alone does not verify historical benchmark lineage. The daily price/NAV history is not itself dividend-reinvested total return; distributions are separate and need dated event records plus documented reinvestment convention.
- Verdict: a plausible *separately scoped instrument* if the project permits a broad-market ETF instead of S&P 500. It is not currently admissible for this test because use of the published series for derived backtest calculations is not clearly licensed, full downloadable coverage was not verified, and dated distribution/vintage and full calendar details remain unverified.

## Invesco QQQ (QQQ): rejected

- Invesco's ETF page has a Price History control and published market-price/NAV descriptions, but no accessible public historical CSV/file was verified: <https://www.invesco.com/us/en/financial-products/etfs/invesco-qqq-trust-series-1.html>.
- Invesco terms provide website material only for personal noncommercial or internal use, but prohibit downloads outside browser caching, automated repeated access, data-mining/robots, and derivative use without prior permission: <https://www.invesco.com/us/en/resources/terms-of-use.html>.
- Published market-price and NAV performance shown on the site is not a downloadable daily OHLC + distribution dataset. QQQ is Nasdaq-100 exposure, not S&P 500. No usable source route passes the stated requirements.

## Other apparent routes

- FRED `NASDAQNQUS500LCT` is a Nasdaq 500 Large Cap total-return index, not S&P 500; it is copyrighted/pre-approval required and the listed history starts 2016-01-11: <https://fred.stlouisfed.org/series/NASDAQNQUS500LCT>.
- FRED's official daily `SP500` is a price-only S&P 500 series; the page states it excludes dividends and has only a rolling 10-year daily history: <https://fred.stlouisfed.org/series/SP500>.
- NYSE/NYSE Arca closing prices have an official historical product but access is by entitlement, not verified free and unrestricted: <https://www.nyse.com/publicdocs/nyse/data/TAQ_Closing_Prices_Client_Spec_v1.2.pdf>.
- Stooq SPY endpoint returned a browser-verification HTML page rather than CSV in the prior source audit. Its terms and adjustment treatment were not verifiable from accessible primary-source text. No bypass attempted.

## Conclusion / reopening requirements

No issuer/exchange route was found that simultaneously proves: (1) public daily executable prices; (2) distribution/split events sufficient for total-return P&L; (3) a clearly compatible personal noncommercial backtest license including derived calculations; (4) full dated coverage and revision/vintage behavior; and (5) a defensible US trading-session calendar.

VTI is the closest non-S&P candidate by instrument and issuer-published history. It should not advance to preregistration until Vanguard/FactSet terms clearly permit private derived backtest use and the daily export's exact coverage, event series, and vintage semantics are verified. It must be registered as US total-market ETF research, never described as S&P 500.

Counts: 0 dataset downloads; 0 price rows viewed; 0 performance values calculated; 0 backtests; 0 preregistrations.
