# Crypto micro-candle trial ledger — 2026-11-19

## Scope and counting rule

This is an index of the documented micro-candle sequence (Phase 0–8), its adjacent feasibility screens, the micro-magnitude diagnostic, and the interrupted divergence WFA. It is **not** a count of every crypto strategy ever explored in this repository: older indicator, funding, cross-sectional, MTF, and order-book studies remain in their own trial records. Counts below distinguish predictor diagnostics, feasibility-only candidates, and M2 outcome cells; they must not be summed as if they were independent strategies or observations. All historical crypto samples listed here are already exposed development data.

The wider crypto/KR/US strategy-family inventory and current data gates are in [`cross-market-strategy-inventory-2026-11-19.md`](cross-market-strategy-inventory-2026-11-19.md).

## Phase ledger

| Record | Smallest registered question | Evaluation scope / count | Recorded result | Status |
|---|---|---|---|---|
| Phase 0 | Next completed 1m close: persistence, reversal, per-symbol majority, fixed SHA random | 6 symbols; 777,594 labels; direction diagnostic | Best simple rule was reversal at 47.983% 3-class accuracy; per-symbol majority 48.166%. No entry, barriers, costs, or M2. | Diagnostic only; no trading edge shown. |
| Phase 1 | Two adjacent candle directions agree → predict next 1m direction | 6 symbols; 777,594 labels; 1 fixed rule | 23.012% 3-class accuracy versus 48.166% training-majority; rejected. | Exploratory, post-hoc, not M2. |
| Round screen A | Three-bar impulse/pullback/confirmation breakout | 6 symbols; 277,170 events / 18,345,578 eligible anchors (1.5108%) | Below 10% coverage and overlaps prior R021 pullback/re-entry family; no future outcomes queried. | Rejected at feasibility. |
| Phase 2 | Expansion followed by compression; expansion-bar direction | 6 symbols; 614,904 events / 18,345,380 eligible anchors (3.3518%) | Below 10% frozen coverage; no target/stop paths or M2 queried. | Rejected at feasibility. |
| Phase 3 | Large-body impulse followed by inside candle with opposite-side close acceptance | 100 recorded symbols; 181,512 events / 17,139,961 scheduled anchors (1.0590%); cooldown count 156,809 | Below 10% coverage; no forward path/outcome rows read. Collection provenance and coin-only contract membership also remain unverified. | Rejected at feasibility. |
| Phase 4 | 1m close-location upper/lower 20%; next-open entry; 1 ATR stop and target | 86 archived symbols; 2 primary M2 cells (10m, 20m) | All-issued M2 47.9772% / 49.3788%; resolved-only sensitivity 47.9772% / 49.3789%; unresolved 54 / 109 of 75.35M / 75.35M issued. Base mean net R −1.489 / −1.490. Five chronological folds, but exposed development data. | Both primary cells rejected before Monte Carlo/plateau; denominator clarification in [`Phase 4 addendum`](micro-candle-phase4-m2-denominator-addendum-2026-11-19.md). |
| Phase 5 | 1m body/range ≥0.80; follow body direction; 1 ATR stop/target | 100 recorded symbols; 2 M2 cells (10m, 20m) | M2 47.64% / 49.22%; base mean net R −4.268 / −2.925. | Both rejected; no parameter rescue. |
| Phase 6 | 1m two-bar sweep/reclaim; next-open entry; sweep-extreme stop and 1R target | 100 recorded symbols; 2 M2 cells (10m, 20m) | M2 46.13% / 47.33%; base mean net R −1.426 / −1.426; raw coverage 3.894%. | Both rejected; below 80% M2 and negative net R. |
| Phase 7 | Fixed Phase 5/6 patterns aggregated to 3m and 5m | 2 rules × 2 timeframes × 2 horizons = 8 M2 cells | All cells M2 46.45–49.50%; base mean net R negative (−2.302 to −0.676). | All 8 rejected. |
| Phase 8 | Same fixed patterns aggregated to 10m and 15m | 2 rules × 2 timeframes × 2 horizons = 8 M2 cells | All cells M2 46.93–48.64%; base mean net R negative (−0.892 to −0.394). | All 8 rejected. |
| Magnitude diagnostic | Forecast next 1m absolute return using previous absolute return vs frozen per-symbol training median | 86 symbols; 9,719,850 forecast rows; one hypothesis, initial invalid run plus corrected replay | Corrected exposed-development replay: equal-symbol relative MAE improvement −1.3008%; 95% interval −2.6533% to +0.2660%; 14/75 eligible symbols improved. | `STOP_MAGNITUDE_BRANCH`; not directional, not a strategy, not M2. |
| Divergence WFA | RSI/MACD divergence with higher-timeframe context | 86 symbols planned; training stopped after 17 symbols, partway through BTC | No aggregate training/OOS/WFA/Monte Carlo/plateau output was persisted. | Interrupted; no backtest result. Also out of order for the current no-macro micro-first gate. |

The numbered M2 phases contain **22 primary rule×timeframe×horizon outcome cells** (Phase 4: 2; Phase 5: 2; Phase 6: 2; Phase 7: 8; Phase 8: 8). This count excludes any sensitivity-only cells unless a persisted result explicitly records them, and excludes feasibility screens and diagnostics. None of the 22 primary cells met the 80% target-first gate. Phase 7–8 cells are scale replications of the same two candle rules, not 16 distinct mechanisms.

## Independent agent round — 2026-11-19

Four separate reviews were completed: crypto candidate novelty, crypto red-team, US equity data/strategy readiness, and Korea equity data/strategy readiness. Both crypto reviewers independently found **no admissible new single-candle OHLC hypothesis** after Phase 0–8; neither ran market outcomes. The US and Korea reviewers found **no presently valid equity performance test** under the frozen per-market criteria (net CAGR ≥20%, MDD ≤30%, Sharpe ≥1, OOS ≥200 closed round trips), because the current caches do not prove data-use rights, point-in-time/delisted universe, corporate-action treatment, source lineage, and costs. No paid access, account, sample request, data download, or backtest was performed.

## Current disposition and next admissible work

- Do not repeat or retune exposed OHLC patterns, reuse the Q1 development interval as independent OOS, or resume the interrupted divergence WFA under a new run identity.
- The corrected magnitude branch is closed. Its metrics are exposed historical diagnostics and do not establish a directional trading edge.
- For KR/US, first resolve permitted daily data, PIT universe, adjustment, cost, and lineage gates before preregistering any return test. A single broad-market ETF would reduce universe complexity but still needs valid distribution-adjusted history and enough frozen OOS trades.
- For crypto, market prediction work can resume only with a genuinely distinct information source/mechanism and a declared sequence that preserves the requested micro-first order. Existing L2 captures are integrity pilots, not strategy labels; R005 remains blocked by its coverage/overlap contract and uncompleted capture/execution gates. Do not call it an 80% candidate.
- The unfinished RSI/MACD divergence WFA was interrupted before aggregate results and is superseded by the one-candle-first sequence; its proposed R020 calibration also lacks an implementation-grounded mixed-null truth generator and measured end-to-end runtime. Keep its archived design review for audit only; do not reopen that WFA or its market labels under the old identity.
- The quarter-hour taker-order-imbalance paper was independently re-reviewed. Its input is order imbalance (not open interest); its first-10-second signal's 4-hour horizon is 1,440× the signal interval, outside the requested 10–20× band, and local evidence supports no 20-symbol historical window. It is not a current candidate and no raw trade archive was downloaded. See `crypto-quarter-hour-order-flow-research-2026-11-19.md`.
- The 2026 selective-prediction paper is a methodology reference, not a passed strategy: its fixed-expiry BTC/ETH event-contract estimand, 55.56% stylized break-even, two-symbol universe, and unpublished implementation do not establish the project's ≥80% target-first M2 or ≥20-symbol OOS gates. Do not fit adaptive thresholds to the exposed Phase 0–8 outcomes. See `crypto-selective-prediction-paper-review-2026-11-19.md`.
- Current data readiness is development-only: the local 1m DB has 86 symbols but only 67 complete 70-month histories, and the 20-symbol live capture covers 120 seconds with no signals/orders or injected reconnect. The expected NAS path is not mounted, so do not start an unbounded local accumulation or claim fresh OOS. See `crypto-microdata-readiness-2026-11-19.md`.
- Four independent follow-up reviews found no justified new crypto 1m OHLC trial, no nonduplicative KR/US equity candidate on the current unlicensed/incomplete panels, and no admissible fresh OOS event panel. The next step is metadata-only Binance Vision `aggTrades` coverage/size feasibility; see `microfirst-next-gate-agent-review-2026-11-19.md`.
- The metadata-only 2026-10 USD-M `aggTrades` screen now confirms HTTP 200 for the frozen 20-symbol cohort at 2,040,955,218 compressed bytes total; no data body was downloaded. Eighteen cohort symbols already have that month in the local 1m development panel, so it is not an untouched full-cohort OOS month. Do not download until a distinct candidate is registered and storage/destination gates pass. See `crypto-microdata-readiness-2026-11-19.md`.
- The next recordable task is to reconcile trial registration/status across the broader strategy catalog before any new hypothesis is opened. This ledger deliberately does not claim the whole repository's historical trial count is complete.
- The Coinbase/Binance fixing-window price-discovery screen was not opened as a performance trial: papers describe venue leadership/activity, not the required 10–20-minute target-first forecast; a BTC-only sketch cannot meet the ≥20-symbol gate. No vendor data was acquired. See `crypto-cross-venue-price-discovery-screen-2026-11-19.md`.

## Source records

- `docs/research/micro-candle-research-round-2026-11-18.md`
- `docs/research/micro-candle-phase0-results-2026-11-18.md` and `docs/research/micro-candle-phase1-exploratory-2026-11-18.md`
- `docs/research/micro-candle-phase2-prereg-2026-11-18.md` and `docs/research/micro-candle-phase3-prereg-2026-11-18.md` with `micro-candle-phase3-frequency-2026-11-18.json`
- `docs/research/micro-candle-phase4-m2-decision-2026-11-18.md`
- `docs/research/micro-candle-phase4-m2-denominator-addendum-2026-11-19.md`
- `docs/research/micro-candle-phase5-marubozu-m2-results-2026-11-18.md`
- `docs/research/micro-candle-phase6-sweep-reclaim-m2-results-2026-11-18.md`
- `docs/research/micro-candle-phase7-multiscale-m2-results-2026-11-18.md`
- `docs/research/micro-candle-phase8-10m-15m-m2-results-2026-11-18.md`
- `docs/research/micro-magnitude-phase1-corrected-rerun-2026-11-19.md`
- `docs/research/micro-first-gate-audit-2026-11-19.md` and `docs/research/micro-candle-next-stage-screen-2026-11-19.md`
- `docs/research/crypto-r020-divergence-calibration-design-2026-11-19.md` and `docs/research/crypto-quarter-hour-order-flow-research-2026-11-19.md`
- `docs/research/crypto_m4_runs/2026-11-18-crypto-divergence-wfa-v1/INTERRUPTED.md`
- Equity gates/data status: `docs/kr-us-equity-trader/SPEC.md`, `docs/research/equity_market_data_catalog_audit_2026-11-19.md`, and `docs/research/equity-market-data-acquisition-options-2026-11-19.md`.
