# Round 6 — return objective, candidate triage, and data gate — 2026-11-19

## Governing objective

The sole economic objective is to maximize compounded net portfolio returns across market regimes. Gross return, hit rate, target-first accuracy, or a single favorable regime is not success by itself. The already frozen thresholds remain hard admission gates, not substitute objectives:

- KR and US cash stocks/ETFs: net portfolio CAGR ≥20%, maximum drawdown ≤30%, annualized Sharpe ≥1, and at least 200 closed out-of-sample round trips per market.
- Crypto discretionary long/short signals: all-issued target-first M2 ≥80%; separately report deadline-direction accuracy; also require outcome-blind non-overlap OOS N≥200 across ≥20 symbols, coverage ≥10%, dependence/multiple-testing-adjusted superiority to both registered signal baselines, and positive cost-adjusted expectancy.
- Report compounded net returns, drawdowns, and results by preregistered regime separately. Do not promote a strategy from M2 or accuracy alone. No objective promises profit in every future regime.

## Independent candidate triage

Four read-only reviews were completed: KR, US, crypto candidate selection, and an independent crypto red team. They used tracked records, did not inspect untracked M4 panels, did not query/download market data, and changed no source files.

| Market | Candidate / decision | Why it is distinct | Current admissibility |
|---|---|---|---|
| Korea | **KR-02: official KOSPI 200 additions**; retain as a conditional research lead, not a winner. Use the registered event timestamp/version, permanent security ID, next-session close entry, registered −8% stop, and exit at five sessions after effective inclusion or 20 sessions after announcement, whichever comes first. | Index inclusion is an event catalyst rather than another price-momentum screen. Similar limit-up continuation is already negative and must not be relabeled as a new mechanism. | No valid performance test: point-in-time announcement/correction history, inactive securities, price/corporate-action history, costs, and independent OOS events are not established. |
| US | **US-06: non-leveraged equity/sector ETF net creation persistence**; retain as an untested registered lead, not a winner. Five-session net creations divided by prior 20-session mean AUM ≥2%, with underlying index return ≥0; enter next regular-session open after both inputs are public. Exit at 20 sessions, next open after creations/AUM ≤−1%, or 2-ATR trailing stop, whichever occurs first. | Uses ETF share creation/redemption and NAV flows, not another price-momentum or candle rule. | No valid performance test: point-in-time shares/NAV/AUM and publication times, delisted ETF universe, distributions, benchmark linkage, and candidate-specific costs are missing or not rights-cleared. |
| Crypto | **R005 liquidity replenishment**; **NO-GO as the next performance strategy and no-go for calling it the best candidate.** Keep only as an engineering/data-readiness hypothesis pending a micro-first rule review. | The book-replenishment mechanism differs from raw taker imbalance, but the current registered implementation still has unresolved frequency, minimum-history, calibration, execution, and regime-ordering issues. | No performance cells exist. The one-hour BTC/ETH replay is pipeline evidence, not strategy OOS. No signal rate, full executable bid/ask path, depth-qualified fills, funding-adjusted return, or 20-symbol × N≥200 evidence is established. A second crypto review rejected promotion. |

These are priority candidates for resolving data gates, not estimates of which will earn the most. No candidate has demonstrated the frozen profit objective. The latest strategy inventory remains the controlling summary; its heterogeneous historical counts must not be summed into a fabricated “all strategies” total.

## Data-source finding that changes the next decision

The current Tardis.dev Terms of Service, last modified 2026-10-28, provide a plausible lawful-storage route for private internal research: clauses 9.1 and Schedule 1 permit access, storage/copying on Customer Systems, creation of derived data, and necessary mirrored backups; clause 9.5 allows private AI/ML models for Customer Users. Clause 9.3 limits making derived data available to non-Customer Users, including a separate allowance for aggregates at intervals of at least 10 minutes. Clause 23 imposes additional prohibitions on Coinbase data, including AI/ML uses. Tardis documentation says its historical instrument set includes delisted, expired, or renamed instruments and warns that exchanges may reuse symbol IDs.

This does **not** yet authorize a Tardis sample or API call: accessing even sample/trial data constitutes acceptance of its licence, and exchange-specific rights may add restrictions. The previously size-checked free sample is metadata-only, predates the current candidate freeze, and is not a forward prospective panel; it could qualify as a sealed historical holdout only if its outcome body and overlapping outcomes remain unopened until the rule and data lineage are frozen. No account, trial, purchase, sample download, or data call was made. Binance Vision remains limited to personal, non-production historical backtesting under the user's previously approved scope; it must not be used as the live/manual signal source for this project. The HDD2TB mount and `/Volumes/HDD2TB/Trade` were absent on this check, so the requested duplicate local+server/archive plan is not ready for a long capture.

Primary references: [Tardis Terms, current version](https://docs.tardis.dev/legal/terms-of-service) (clauses 9, 23 and Schedule 1); [Tardis historical-data coverage](https://docs.tardis.dev/faq/data); [Binance Vision Dataset Terms](https://github.com/binance/binance-public-data/blob/master/TERMS_AND_CONDITIONS.md).

## Next actions and stop conditions

1. **Do not run another exposed-history sweep.** It cannot create independent OOS, and the tested price-only/taker-flow families have already failed or lacked positive cost evidence.
2. Resolve the user's authority to accept Tardis terms and use Binance futures sample/trial data, including whether an individual Customer System may include the user's private Linux server and whether private high-frequency derived signals may be sent only to the user's own Telegram. Do not accept terms, create an account, or download before that decision and exchange-rights review.
3. Restore and verify the archive destination, size/retention cap, and local+server parity before prospective recording. A short sample must first pass clock provenance, reconnect gap accounting, source integrity, and deterministic feed-to-executable-price replay; do not label recorder validation as strategy performance.
4. Freeze a materially distinct **micro-first** crypto rule before any outcomes are read. If R005 cannot satisfy that ordering and the data/coverage/cost gates without retrospective threshold changes, reject it and select a separate preregistered event hypothesis. Only then collect/score a sealed chronological OOS panel.
5. Keep KR-02 and US-06 at source/rights/universe-readiness stage. A paid purchase, vendor account/trial, or provider inquiry was not authorized by this review. Do not substitute current-member caches or present constituents as PIT OOS.

No backtest, forecast, return result, strategy approval, data download, account action, or external system change occurred in this round. The next required user decision is whether to authorize access to Tardis sample/trial data under its current terms; until then all performance testing remains gated.
