# R036 — Public US panel audit

Date: 2026-11-17  
Status: source-readiness audit; **not a strategy performance trial**

## Question

Does the public `Johnbrick123/sp500-data` release provide a legally usable, reproducible daily US stock/ETF panel with adequate point-in-time membership, inactive-security, delisting, and corporate-action handling for portfolio strategy testing?

## Frozen scope

- Inspect public GitHub repository metadata, README, release metadata, workflow, and relevant data-building scripts.
- Do not download release data assets, execute candidate code, create an account/API key, contact a provider, or purchase data.
- Do not calculate strategy outcomes.

## Decision rule

Proceed to data acquisition only if source rights, reproducible lineage, actual schema, historical universe, inactive security/delisting handling, ETF scope, and corporate actions are all supportable. Otherwise classify as `NO-GO` and record which gates remain open.

## Sources inspected

- Repository metadata: https://api.github.com/repos/Johnbrick123/sp500-data
- README: https://github.com/Johnbrick123/sp500-data/blob/main/README.md
- Release metadata: https://api.github.com/repos/Johnbrick123/sp500-data/releases/tags/data
- Workflow: https://github.com/Johnbrick123/sp500-data/blob/main/.github/workflows/update.yml
- Build scripts: `build_universe.py`, `bridge_membership.py`, and `fetch_prices.py` on the public `main` branch.
