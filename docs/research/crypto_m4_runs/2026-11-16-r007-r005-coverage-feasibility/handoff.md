# R007 handoff

- R005's per-timeframe 10% coverage gate conflicts with its rule suppressing events for 20T bars.
- Arithmetic audit only; it reads no market data and computes zero performance cells.
- The one-hour public BTC/ETH feed pilot remains pipeline-integrity material only, not signal evidence.
- Next: finish bounded capture; verify its manifest and hashes; replay raw → compact → windows twice and compare hashes. This can establish software/data integrity only.
- Before any predictive scoring, draft a new pre-label event-overlap/coverage protocol with effective-sample and block-bootstrap rules, plus all unresolved R005 data, cost, model, and timestamp gates. Do not reopen exposed historical result segments.
