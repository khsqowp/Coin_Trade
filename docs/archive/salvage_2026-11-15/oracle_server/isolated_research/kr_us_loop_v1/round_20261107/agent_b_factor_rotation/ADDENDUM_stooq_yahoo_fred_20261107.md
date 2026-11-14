# Addendum — Stooq, Yahoo Finance, and FRED total-return search

Date: 2026-11-07
Scope: source feasibility only; no performance calculations, registration, or backtest.

## Stooq

- Endpoint tested with a header-only request: `curl -L -I --max-time 15 'https://stooq.com/q/d/l/?s=spy.us&i=d'`.
- HTTP returned `200 OK`, but response type was `text/html; charset=utf-8`, with `Cache-Control: no-store`, `X-Robots-Tag: noindex, nofollow`, and a restrictive CSP. It was not a CSV response. The site's pages also present a JavaScript browser-verification challenge in the web reader. No challenge was solved or bypassed, and no OHLC values were downloaded or viewed.
- Stooq-specific public CSV downloads are thus not operationally available to this non-interactive research process at the check time. A manual human download might be possible, but is not a reproducible unattended source path and was not attempted.
- Stooq's first-party terms/data-adjustment documentation could not be retrieved because the site presents the verification page. Secondary descriptions claim free data is for personal use only, commercial use prohibited, redistribution requires Stooq's consent, and the bulk download lacks a documented split/dividend methodology. Because these claims could not be verified against accessible first-party text, treat use rights and adjustment semantics as **unverified**, not as established facts. References found: <https://stockmarketstack.com/tools/stooq> and <https://financialliterature.com/data/stooq/>.
- Consequently Stooq cannot presently serve as a validated SPY execution series or total-return benchmark. Missing evidence includes a successful permitted CSV delivery, primary-source rights, documented raw/adjusted field definitions, dividend/distribution schedule, and a stable as-of/vintage policy. Even if a manually downloaded history later becomes available, adjusted history alone would not provide contemporaneous executable prices.

## Yahoo Finance (distinct from Stooq)

- Yahoo's official help says adjusted close reflects applicable splits and dividend distributions, with split and dividend multipliers using CRSP standards: <https://help.yahoo.com/kb/SLN28256.html>.
- Yahoo's official download help says offline CSV download is available with Yahoo Finance Gold, and that instrument availability is subject to licensing restrictions: <https://help.yahoo.com/kb/finance/certain-amounts-sln2311.html>. Therefore the webpage does not offer an unrestricted free official CSV download route.
- Yahoo Terms prohibit collecting data from its Services using automated means without express prior permission: <https://legal.yahoo.com/us/en/yahoo/terms/otos/index.html?ncid=mbr_idnedulnk00000001>. Do not use yfinance/unofficial endpoints for this project absent explicit permission.
- `Adj Close` is a dividend/split-adjusted analytical series, not an execution price. The official help describes the applicable adjustment factors but does not supply an as-published vintage archive. Later distributions can change the backward adjustment factor; thus downloaded current adjusted history is not a contemporaneous price snapshot. Yahoo's separately listed Close can help with historical price analysis, but this audit did not establish lawful free automated acquisition, full dividend-event provenance, or a sufficient vintage method.

## FRED official series search

- The official FRED stock-market-index category contains a Nasdaq US 500 Large Cap Total Return Index series, but not an S&P 500 total-return series in the catalog page reviewed: <https://fred.stlouisfed.org/categories/32255>.
- The Nasdaq series is `NASDAQNQUS500LCT`, with daily observations shown from 2016-01-11 in the category listing; FRED identifies Nasdaq as the source and marks it copyrighted/pre-approval required: <https://fred.stlouisfed.org/series/NASDAQNQUS500LCT>.
- The direct FRED series path `https://fred.stlouisfed.org/series/SP500TR` returned HTTP 404 in the page fetch. The existing official `SP500` series is explicitly a price index excluding dividends and limited to a rolling 10 years of daily history: <https://fred.stlouisfed.org/series/SP500>.
- Finding: no official FRED S&P 500 total-return series was identified. Nasdaq's 500 Large Cap Total Return series is not the S&P 500 and its own licensing/history constraints make it an invalid substitute for the specified benchmark.

## Gate disposition

The original `FEASIBILITY_BLOCKED` status remains. Stooq's actual HTTP response and its unverified rights/adjustment policy do not clear the asset or benchmark gate. Yahoo is not an unrestricted free automated route under Yahoo's official terms, and its adjusted close is neither an executable price nor a vintage-stable point-in-time price archive. FRED's daily S&P 500 is price-only; the TR series found is Nasdaq rather than S&P.

Source-only test counts: 1 Stooq HTTP HEAD request; 0 data rows downloaded/read; 0 performance values calculated; 0 backtests; 0 preregistrations.
