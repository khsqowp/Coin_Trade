# R037 — MarketParquet free-sample audit

Date: 2026-11-17  
Status: public source and license-scope audit; **not a strategy performance trial**

## Question

Can the MarketParquet free sample serve as an authorized, sufficiently complete and economically valid US stock/ETF panel for the Round 0 portfolio gates?

## Frozen scope

- Inspect public official pricing, terms, license, documentation, methodology, and sample pages.
- No account/API-key creation, purchase, provider contact, full archive download, candidate code execution, or strategy return calculation.
- A one-byte/range metadata probe may be attempted only to establish public sample file size; do not retain market data.

## Decision rule

Classify separately: (1) whether a no-account sample is explicitly offered, (2) whether its usage rights are unambiguous, (3) whether it has adequate date depth and field semantics for the fixed US equity portfolio objective, and (4) whether point-in-time universe, delisting, corporate-action, and quality claims are independently verifiable. No strategy metrics unless each required gate is cleared and a plan is preregistered.

## Sources inspected

- https://marketparquet.com/pricing
- https://marketparquet.com/terms
- https://marketparquet.com/license
- https://marketparquet.com/documentation
- https://marketparquet.com/guides/free-historical-stock-data
- https://marketparquet.com/data-quality

