# US equity/ETF source candidate: Sharadar — 2026-11-20

## Finding

Sharadar is a materially more accessible US daily-data candidate than the CRSP route previously identified: its official materials describe active and delisted stock and fund OHLCV histories from December 1997, corporate-action tables, and historical S&P 500 constituent changes. Its posted personal-use Prices tier is $9/month for five years or $39/month for full history (annual prices $99 and $299). This is a source candidate, not a cleared data gate: the personal-use license creates restrictions that may conflict with publishing data-evaluation conclusions or making the research output available to others.

## Coverage and field claims from the vendor

- Stock prices: active and delisted US stocks, 21,000 tickers, EOD OHLCV, history from December 1997. Vendor describes unadjusted, split-adjusted, and split/dividend/spinoff-adjusted variants; its documentation warns that full OHLCV for some adjustment variants requires imputation. [Prices overview](https://sharadar.com/prices), [stock-price table](https://sharadar.com/docs/stocks)
- Fund prices: active and delisted US-listed funds, 10,000 tickers, including ETFs, CEFs, ETNs, and ETDs, with OHLCV and the same adjustment caveat. [Fund-price table](https://sharadar.com/docs/funds)
- Corporate actions: the vendor says the table covers splits, dividends, spinoffs, ADR-ratio changes, listing/delisting dates and reasons, acquisitions, and ticker changes from 1998. [Corporate-actions table](https://sharadar.com/docs/actions)
- Index universe: its S&P 500 table records additions/removals and effective dates plus quarterly historical constituent snapshots from 1998. This is useful for an S&P 500 strategy universe, not a complete point-in-time US stock or ETF universe. [S&P 500 constituents](https://sharadar.com/docs/sp500)
- The vendor advertises a no-sign-up sample endpoint for AAPL and a public Google Sheet for AAPL/SPY. This review did **not** receive or store sample rows; direct API access from the shell failed DNS resolution, while the browser cannot open the API endpoint. Sample schema/quality therefore remains unverified in this environment. [Sample page](https://sharadar.com/sample), [authentication/sample instructions](https://sharadar.com/docs/auth)

## Published price and license boundary

The currently published personal-use tier lists Prices at $9/month or $99/year for five years; $19/month or $199/year for ten years; and $39/month or $299/year for full history. The Prices plan includes descriptions, tickers, actions, S&P 500 constituents, stocks, funds, and price metrics. No account, purchase, or paid download was made. [Subscription prices and tables](https://sharadar.com/subscribe)

The posted Personal Use License is restricted to a natural person acting individually. It excludes professional, institutional, organizational, and on-behalf-of-others use; it prohibits sharing the service/data and says evaluation conclusions about data usability or fitness may not be disclosed externally without prior written approval. It permits retaining derived backtests/results only when they do not contain or reproduce the source data. Those terms mean suitability depends on the user's exact research and repository-sharing setup; do not put source rows, caches, or redistributable tables in GitHub, and do not publish a vendor fitness evaluation without written permission. [Personal Use License](https://sharadar.com/terms)

## Decision and next gate

1. **Do not purchase or create an account under the current authorization.** The user approved sample/quote lookup, not a subscription.
2. If pursuing a permitted free sample, inspect only the vendor's explicitly provided AAPL/SPY sample and record field/schema facts privately; this current environment could not retrieve the API response.
3. Before using paid data, establish that the personal-use terms cover the intended self-directed strategy research and determine whether the GitHub repository/report access is private and limited to the user. If any other person can access data or evaluation conclusions, obtain written permission or a different license first.
4. A sample or subscription still must verify ETF inactive/delisted history, ID stability/ticker recycling, adjustment arithmetic, timestamp conventions, and portfolio-universe construction. The published S&P 500 history cannot stand in for the complete ETF universe.
5. Until the scope and sample are verified, US strategy performance remains `NOT_EVALUABLE`; no strategy test was run with Sharadar data.

This document records provider claims and the current access/rights gate. It is not a recommendation to buy the data and does not establish that the dataset is complete or unbiased for every intended universe.
