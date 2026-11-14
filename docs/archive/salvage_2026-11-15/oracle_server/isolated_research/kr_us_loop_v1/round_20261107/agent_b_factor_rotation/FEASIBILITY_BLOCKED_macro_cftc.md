# US Macro Candidate Feasibility — CFTC Positioning

Date: 2026-11-07
Status: `FEASIBILITY_BLOCKED`
Agent: B

## Candidate concept

A distinct, not-yet-tested candidate is a weekly E-mini S&P 500 futures positioning signal from the CFTC Traders in Financial Futures (TFF) report. The report measures Tuesday positions and is normally published Friday at 3:30 p.m. Eastern. A valid simulation must not act on the Tuesday observation before the actual publication time; signals would become available only after the recorded Friday release and orders would be placed at the next eligible NYSE Arca session. Holiday-related release delays must use the actual release calendar, not a fixed Friday assumption.

This is only a candidate definition, not a frozen rule or preregistration. No threshold was selected, no performance values were read or computed, and no backtest was run.

## Source and timing evidence

- CFTC COT report descriptions and release timing: <https://www.cftc.gov/MarketReports/CommitmentsofTraders/AbouttheCOTReports/index.htm>
- CFTC release schedule: <https://www.cftc.gov/MarketReports/CommitmentsofTraders/ReleaseSchedule/index.htm>
- CFTC public reporting FAQ/API: <https://publicreporting.cftc.gov/stories/s/Public-Reporting-FAQ/inwp-fmhz/>
- Federal Data Catalog entry identifies COT as a public federal data asset: <https://catalog.data.gov/dataset/commitments-of-traders>
- CFTC historical special announcements document at least one historical COT correction/republication (VIX reports in 2009): <https://www.cftc.gov/MarketReports/CommitmentsofTraders/HistoricalSpecialAnnouncements/index.htm>

The public source is free and needs no API token according to CFTC's FAQ. However, current historical tables alone do not prove the exact value available at every historical publication: the correction notice means the research must establish access to as-published weekly vintages or otherwise isolate corrected dates before passing point-in-time validation.

## Matched asset / benchmark feasibility

- SSGA's official SPY page describes SPY as an S&P 500 tracker, gives inception date 1993-01-22, and explains dividend-reinvested performance: <https://www.ssga.com/us/en/institutional/etfs/state-street-spdr-s-p-500-etf-trust-spy>
- FRED's daily `SP500` series is explicitly a price index and excludes dividends; it is not an admissible total-return benchmark by itself: <https://fred.stlouisfed.org/series/SP500>
- NYSE's Arca closing-price product specification states that historical Arca closing-price files begin 2008-12-01 and are available via NYSE FTP subject to entitlements; this is not established as a free unrestricted history: <https://www.nyse.com/publicdocs/nyse/data/TAQ_Closing_Prices_Client_Spec_v1.2.pdf>
- SSGA's published NAV history is not an exchange-traded execution price. A NAV-based signal/return series would not establish fills at executable prices, even if distributions were reinvested.
- Yahoo Finance exposes a public SPY history page with adjusted-close values, but the research has not established redistribution/use rights, stable vintage behavior, or a sufficiently authoritative source: <https://finance.yahoo.com/quote/SPY/history/?p=SPY>
- NYSE's accessible annual calendars are year-specific; a complete historical NYSE Arca session calendar including exceptional closures has not been established for the proposed test horizon.

## Gate result

Do not preregister or backtest yet. The signal source is promising and public, but the matched return path is not validated: no free, authoritative, executable SPY price history with distributions/corporate-action provenance and full historical Arca session calendar has been confirmed. In addition, CFTC as-published historical vintages need verification because the agency documents historical correction(s).

Required to reopen the gate:

1. A free data source with explicit usable rights for daily SPY executable prices, distributions/splits, and stable historical-vintage provenance.
2. A complete authoritative session-calendar source (or validated calendar reconstruction with documented exceptional closures) for the exact test horizon.
3. CFTC release-time/as-published vintage evidence for each historical signal, including holiday delays and corrections.
4. After those pass: choose one exact signal formula and execution rule, preregister/hash it, freeze OOS windows and costs, then run only the registered test.

## Actions and test count

- Public source research only; no dataset downloaded.
- No remote pipeline/service access and no secrets/API keys used.
- No market performance values inspected or calculated.
- Backtests executed: 0.
- Candidate-specific preregistration: none.
