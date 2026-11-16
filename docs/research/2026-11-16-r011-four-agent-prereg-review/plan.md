# R011 — Four-agent preregistration and next-step review

Status: `design_review_only`; no market outcomes, performance metrics, or new data were inspected for this review.

## Objective

Use four independent roles to select non-duplicative next research actions for (1) US stocks/ETFs, (2) Korean stocks/ETFs, (3) crypto multi-timeframe manual-trading signals, and (4) adversarial study prioritization. This review is not a strategy performance experiment and does not count toward either two-strategy target.

## Prior evidence considered

- Equity source-readiness audit dated 2026-11-15: current 184-file KIS cache lacks verified per-file provenance, point-in-time universe/delisted coverage and complete corporate-action/total-return semantics. KRX/CRSP paths are not yet rights- and sample-qualified.
- R004 MACD-zero-cross plus RSI(14)>50: all 48 validation cells failed to beat matched buy-and-hold on net CAGR; final holdout remained unopened. This family is not rerun under a new name.
- R005 liquidity-replenishment: its current 20T refractory rule conflicts with the frozen >=10% coverage gate; do not score outcomes under that contract.
- R007: documents the coverage feasibility conflict; no strategy performance was computed.
- R008: synchronized time-block inference is a design proposal, not a frozen protocol or performance result.
- R010: one-hour BTC/ETH ingestion/replay integrity evidence only; reconnect recovery was not observed and no predictions/performance were evaluated.

## Roles and bounded questions

1. US equity: propose one mechanism distinct from momentum, downside-beta and MACD, with data/PIT gates and falsification.
2. KR equity: propose one distinct mechanism and specify rights, provenance, PIT, delisting, costs and execution gates.
3. Crypto MTF: specify valid target/stop/time-limit accuracy estimand, coverage, overlap and dependence-aware uncertainty.
4. Independent auditor: identify the highest-value action without exposed-data retuning or unverified data rights.

## Acceptance and stop rules

- Do not claim any strategy edge, accuracy, expected return, or market readiness from design proposals.
- Do not run a backtest until its data-use rights, immutable data identity, time coverage and preregistered outcome definition are accepted.
- Keep stock/ETF B&H portfolio performance distinct from crypto signal hit-rate; neither substitutes for the other.
- Crypto 80% success requires a preregistered accuracy estimand, >=10% frozen coverage, and a dependence-adjusted lower confidence bound >=80%, plus sufficient effective sample. Target-vs-stop same-bar ties resolve adversely; timeout outcomes are reported separately and cannot silently become wins.
- Equity tests require a date-valid universe including inactive/delisted assets, verified adjustment/return treatment, realistic costs and untouched chronological evaluation.
- No final holdout access or parameter changes are authorized by this review.

## Expected work

Four bounded written reviews; zero strategy cells. Persist each proposal, disagreements, and the single next action before any performance computation.
