# Agent A — US CFTC positioning filter (single-candidate preregistration)

Status: frozen for data-source feasibility checks only. No CFTC observations or market-price values have been downloaded or inspected at the time of this registration. No performance run is authorized by this document.

Frozen date: 2026-11-07 (Asia/Seoul)
Candidate ID: `A-US-TFF-Emini-LeveragedFunds-Z156-SPY-20261107`

## Hypothesis and non-duplication boundary

Test whether the weekly net positioning of leveraged funds in CME E-mini S&P 500 futures contains useful broad-market risk-on/risk-off information for SPY exposure. This is a derivatives-positioning input, not an OHLC trend indicator, price-volume anomaly, FOMC event overlay, stock-ranking factor, or candidate copied from an existing crypto bot.

The local Gen01–Gen13 review found no CFTC COT position-signal candidate. Gen12 macro is a proposed FOMC event overlay; Gen12 volatility is a downside-semivariance exposure rule; Gen13 custom trend is a DMI/Choppiness price-state rule. This candidate is economically related to broad risk-state filters, so it is a dependent hypothesis for multiple-testing purposes, not an independent discovery. The duplicate audit is bounded to the currently available Gen01–13 registrations and source catalog; unrecorded historical experiments remain unknown.

## Frozen market, source, and observation timing

- Trade instrument: SPY, long or cash only, unlevered. No futures orders, short positions, constituent selection, or alternative ETF.
- Signal source: CFTC Traders in Financial Futures (TFF), Futures Only historical reports, exact market name `E-MINI S&P 500 - CHICAGO MERCANTILE EXCHANGE`.
- Signal field: `x_t = (Lev_Money_Positions_Long_All - Lev_Money_Positions_Short_All) / Open_Interest_All`.
- Report `Report_Date_as_MM_DD_YYYY` is the Tuesday position snapshot. A report becomes eligible only at the first NYSE Arca session open on or after `Report_Date + 8 calendar days`. This fixed lag is deliberately conservative relative to the CFTC's usual Friday 3:30 p.m. ET publication and its stated one-to-two-day federal-holiday delays. Never use the report date itself as the publication date or trade on a same-day assumption.
- At each eligible open, compute `z_t = (x_t - mean(x[t-156:t-1])) / sample_sd(x[t-156:t-1])` from exactly the 156 preceding report observations, excluding the current observation. If any of those observations is missing, duplicated, non-finite, or has nonpositive open interest, no signal is available and the attempt fails closed; no interpolation or shortened lookback.
- Target is 100% SPY if `z_t > 0`; otherwise target 0% cash. Between eligible report updates, hold the previous target. Equality is cash. First exposure is permitted only after a complete 156-report history.
- Signal is applied at the eligible session open; it cannot earn the return interval ending at that open. If report date plus eight days falls on a holiday/weekend, use the next session open. The exact historical session dates must come from an authoritative NYSE Arca calendar.
- Data cutoff: CFTC report date no later than 2026-10-20. This avoids relying on the newest weekly report near the research cutoff and gives the latest included report at least eight calendar days of publication lag. No post-cutoff observations may enter any calculation.

## Price, calendar, execution, and cost gates

- Required executable price input: official NYSE Arca SPY daily open/close history with distribution/split adjustment provenance adequate to compute total returns and a complete, authoritative NYSE Arca session calendar covering the full price interval. A free source must provide reuse terms that permit this private research.
- A FRED S&P 500 index close series, ETF NAV, synthetic weekday calendar, Yahoo/Stooq mirror, or current NYSE holiday page alone is not an executable-price/calendar substitute for this test.
- Execute at the first eligible session open after the fixed report lag. Mark the prior target through the prior open-to-current-open interval before changing exposure. Charge 10 basis points per absolute change in SPY notional; cash earns zero. Benchmark is SPY buy-and-hold on identical eligible curve intervals, with identical 10 bp entry and terminal liquidation charges.
- Reject the attempt as `DATA_BLOCKED` before performance values are opened if official free price/calendar data, corporate-action treatment, source terms, or exact date coverage cannot be established. No paid data, account registration, subscription, or key is authorized.

## Fixed periods and evaluation

- Signal lookback: fixed 156 prior weekly CFTC reports; no optimization.
- Price performance sample: first executable signal after the 156-report warm-up through the last session corresponding to the frozen CFTC cutoff.
- Descriptive chronological windows: full eligible sample; 2009-06-15 through 2016-12-30; 2017-01-03 through 2020-12-31; 2021-01-04 through the cutoff. Use each window only when it contains eligible observations; do not move boundaries to improve results.
- These historical partitions are exploratory and not project-wide untouched OOS because the wider daily market history has already been examined in other generations. Only observations after the freeze date can be called prospective OOS; a qualifying claim requires at least 52 prospective weeks and cannot be made in this attempt.
- Report gross/net CAGR, annualized Sharpe (252), maximum drawdown, exposure, turnover, fees, and matched SPY benchmark on identical dates. One frozen candidate, one performance attempt maximum. No alternate report family, contract, category, threshold, lookback, lag, market, or sample window after seeing any result.
- Descriptive candidate pass requires net CAGR and net Sharpe both exceed matched SPY buy-and-hold in every fixed historical window, with no worse maximum drawdown in every window. Even a pass is an exploratory lead only; it does not satisfy prospective OOS or investment suitability.
- Global historical independent trial count is unresolved. Record this candidate as one new dependent hypothesis and do not claim DSR/PSR/BH significance from a guessed N.

## Termination and artifacts

One run only if all source, calendar, date coverage, point-in-time, corporate-action, execution, and independent-review gates pass. Any failed gate ends this attempt as `DATA_BLOCKED` or `FAILED` before performance. Preserve source files, terms, timestamps, hashes, preflight logs, and reason. Never change the registered rule after data inspection; a genuinely new rule requires a separate dated preregistration and counts as another dependent trial.

## Official source references reviewed before freeze

- CFTC COT overview, report timing, historical data, and static-publication statement: https://www.cftc.gov/MarketReports/CommitmentsofTraders/index.htm
- CFTC TFF historical compressed files: https://www.cftc.gov/MarketReports/CommitmentsofTraders/HistoricalCompressed/index.htm
- CFTC TFF variable names, including the exact leveraged-money and open-interest columns: https://www.cftc.gov/MarketReports/CommitmentsofTraders/HistoricalViewable/cotvariablestfm.html
- CFTC release schedule: https://www.cftc.gov/MarketReports/CommitmentsofTraders/ReleaseSchedule/index.htm
- CFTC public-domain and reuse acknowledgement policy: https://www.cftc.gov/WebPolicy/index.htm
- NYSE historical data and pricing/coverage: https://www.nyse.com/market-data/historical
- NYSE Arca holiday/session schedules: https://www.nyse.com/trade/hours-calendars

These source pages establish source identity and stated availability, not that the market-data gates have passed or that the candidate has an edge.
