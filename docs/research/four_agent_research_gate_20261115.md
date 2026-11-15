# Four-agent research gate — 2026-11-15

Status: independent review only. Four agents reviewed existing research and data limitations. They ran no backtests, parameter grids, or edits. This report records the decision about what is worth testing next; it does not claim a new strategy result.

## Decision

Do not run another historical performance sweep on the currently exposed price sets. For KR and US equities, first establish a point-in-time universe and defensible corporate-action/delisting data. For crypto, the current strategy evidence does not support an 80% signal claim; one fixed macro-to-micro candidate is worth retaining, but its cost model and append-only prospective evaluation must be frozen before scoring new outcomes. A separate implementation-parity check is justified only if the team elects to continue relying on the stored SuperTrend-derived studies; those studies are not evidence for the user-attached liquidity-sweep Pine script.

## Agent findings

### Korea — no new price-strategy candidate

The prior 20-session failed-breakdown study produced 5,355 events across 64 current-cohort stocks, with mean net return −0.315% at base assumed costs and −0.515% at stress costs. The 069500-relative block interval included zero. The 069500 volatility-compression breakout produced only 50 completed trades and failed its minimum-sample gate; base CAGR was approximately flat and stress CAGR negative. The corrective stress-day reversal diagnostic also failed its prewritten numeric gate, and was post-hoc after an earlier invalid run.

The research checkout has reports and scripts but no source KR price panel. The historical panel described in prior reports consisted of present-day survivors; it does not establish delisted names, historical constituent membership, or adjusted corporate-action histories. Repeating or slightly modifying the existing reversal and breakout rules on that panel would be low-information reuse, not independent confirmation.

**Next gate:** document whether KRX historical data products can provide licensed daily prices for inactive/delisted names, dates of index membership, and corporate-action adjustments together. The KRX interface lists delisted-issue information and delisted-issue price history, but this review did not establish the history depth, downloadable coverage, API availability, or reuse terms needed for a complete point-in-time backtest. No purchase or account action is authorized by this review.

### United States — no new price-strategy candidate

The archived stock-loop ledger records 207 cumulative trials and no new survivor; its one Stage-3 survivor, US-18-T100, lost significance/strength under a fixed 2014-era universe check. US momentum, downside-beta, trend gating, ETF rotation, volatility breakout, and several event/cross-asset ideas have already been covered. The most attractive local headline results are vulnerable to current-constituent survivorship, short or regime-concentrated samples, concentration, and cost assumptions.

CRSP documents monthly security histories, distributions, delisting data, and inactive securities; this is a plausible research-grade source, but access is licensed and no subscription or spend was initiated. A current S&P 500 list plus adjusted prices does not reconstruct historical membership or delisted returns.

**Next gate:** establish a point-in-time, inactive-security-inclusive stock/ETF dataset with corporate-action provenance, and define portfolio drawdown/risk constraints before testing another strategy. No additional backtest is justified on the present survivor-only panels.

### Crypto — retain one candidate, do not claim an edge

The available local `candles.sqlite` was independently queried read-only during this turn: 17,142,161 one-minute rows, 100 symbols, earliest open 2026-07-16 18:10 UTC, latest open 2026-11-14 00:28 UTC. Prior reports state these observations and adjacent post-cutoff data were exposed without a sealed-access ledger; therefore no segment is a defensible untouched holdout.

Existing results continue to reject broad strategy families rather than establish an 80% system: the corrected multi-timeframe probe's best adequately sampled base-cost cell had 38.89% net-positive exits (n=324), mean net return −0.0411%, and only 0.082% raw signal incidence; all adequately sampled stress-cost cells had negative mean net return. The BTC-leads/alt-lags candidate returned 28.05%/31.41% target-first at 10/20-minute horizons and 0.4106% coverage, with negative mean net R. These are historical development figures, not independent future performance.

The single candidate to retain is the existing draft in `crypto_pine_macro_to_micro_audit_20261115.md`: completed BTC 4-hour HH+HL/LH+LL regime first; then an individual coin's 5-minute close-back-inside sweep; a later, distinct 5-minute MSS confirmation; next-bar-open entry; sweep extreme as stop; fixed 2R target; 10-bar (50-minute) expiry. This is structurally aligned to macro-first, micro-entry and has a fixed target horizon. It is not yet an executable preregistration: point-in-time eligible symbol cohort, tick/fee schedule, slippage and funding treatment, exact calendar/data alignment, and the prospective ledger/access controls still need to be fixed. Do not tune this candidate after a first outcome run.

**Next gate:** freeze the complete rule and evaluation contract, establish an append-only per-signal/outcome ledger plus access audit before new results are inspected, and only then begin prospective collection. Final success still requires M4 target-first precision ≥80%, ≥10% coverage, ≥200 non-overlapping events over ≥20 symbols, uncertainty lower bound above matched baselines, and positive cost-adjusted expectancy. If no candidate has enough pre-outcome development data to calibrate M4 confidence, report that gap instead of inventing a threshold.

### Pine and implementation integrity — a distinct diagnostic

The user-attached Pine liquidity-sweep source was already audited in `crypto_pine_macro_to_micro_audit_20261115.md`: it lacks a genuine completed-HTF regime, can process sweep and MSS on the same bar, can score pre-entry movement from the entry bar, resolves TP before SL, and has no setup/trade expiry. Its defaults have poor reward:risk and likely repeat entry alerts. It must not be performance-tested as written.

The fourth reviewer independently found a separate mismatch in the repository's stored SuperTrend studies: the Python direction implementation does not reproduce the stored Everget Pine recursive trailing stop/wick behavior, and the Pine default ATR 22 differs from the P7-D ATR 14. P7-D's cells all failed their gate and did not open a holdout. Therefore those studies are not valid Pine parity evidence. A deterministic Python-vs-Pine parity check on fixed fixtures and real OHLC is a meaningful implementation test if those studies remain in scope; it is not a strategy-performance test and would not validate the attached liquidity-sweep source.

## Evidence map

- Crypto prior-study synthesis: `agent_strategy_research_rounds_20261115.md`.
- Multi-timeframe development outcomes: `long_history_taker_multitf_corrected_20261115.md` and `round5_mtf_dev_results_20261115.md`.
- BTC lead/alt lag: `crypto_btc_lead_alt_lag_results_20261115.md` and `crypto_btc_lead_alt_lag_preregistration_20261115.md`.
- Attached Pine audit and candidate draft: `crypto_pine_macro_to_micro_audit_20261115.md`.
- KR failed-breakdown and compression outcomes/protocols: `equity_kr_failed_breakdown_results_20261115.md`, `equity_kr_compression_breakout_results_20261115.md`, and their preregistrations.
- US study limitations and prior exploratory data: `equity_us_downside_beta_results_20261115.md`, `equity_round9_cross_sectional_20261115.csv`, and archived `docs/archive/salvage_2026-11-15/linuxserver_research/linuxserver_research/stock_loop/results/US_FINAL.md`.

## External data-source check (read-only)

- KRX Data Marketplace currently exposes menus for delisted issues and delisted-issue price history. This alone does not prove adequate historical depth or that a complete historical index constituent panel is freely downloadable: [KRX delisted-issue price history](https://data.krx.co.kr/contents/MDC/STAT/issue/MDCSTAT239.jsp), [KRX Data Marketplace data purchase guidance](https://openapi.krx.co.kr/contents/OPP/DATA/OPPDATA001.jsp).
- WRDS describes CRSP monthly US stock data as including historical identifier/name information, price/volume histories, delisting data, distributions and inactive securities. Access is a data-vendor/subscription path, not a free local input: [WRDS CRSP monthly-stock description](https://wrds-www.wharton.upenn.edu/demo/crsp/form/), [CRSP US Stock Databases](https://www.crsp.org/research/crsp-us-stock-databases-2025-layout/).

## Research integrity and next round

No strategy-result grid was launched because the four-agent evidence says an additional score on exposed/survivor data would not answer the decisive questions. This is not a claim that all strategies are impossible. It is a sequencing decision: improve dataset validity and evaluation controls before generating another headline return or accuracy figure. The next high-information research round should be implementation/data readiness (not parameter optimization): (1) choose one canonical Pine implementation only if relevant; (2) freeze the crypto candidate and ledger; (3) determine legal and technical availability of inactive/PIT KR and US panels; (4) start prospective collection only after those contracts are fixed. No Oracle access, deployment, external order path, or data purchase occurred.

## Post-gate update — fixed sweep/MSS probe and four-agent review

The user's additional instruction is to prohibit low-value testing and require agents to analyze prior evidence before recommending further work. The decision-value review and 2026-11-15 read-only local KR/US CSV inventory are recorded in [`research_decision_value_gate_20261115.md`](research_decision_value_gate_20261115.md). No strategy test was added in response.

The single sequential BTC 4h / coin 5m sweep→MSS candidate was subsequently preregistered and run once as a development-only rejection screen; this does not turn the exposed interval into validation. Across 100 current-cohort symbols and 23,823 scored events (2026-07-17 through 2026-10-09 exclusive), target-first was 13.38%, coverage 1.7688%, and mean net R was -0.294 under the assumed 0.10% fee-only cost (-0.910 under 0.30%). Eleven events were unscorable. The detailed preregistration, raw event ledger and report are in `crypto_macro_mtf_sweep_preregistration_20261115.md` and `crypto_macro_mtf_sweep_results_20261115.{md,json}`. Causal synthetic checks passed, but they do not cure the exposed development period, current-cohort bias, or omitted execution costs.

The matched 5m momentum comparator was structurally non-discriminating, not merely coincidentally similar: the long MSS close must exceed the previous four bars' maximum high, which is at least the prior close; the short condition symmetrically forces a lower close than the prior close. Thus comparator direction is necessarily the candidate direction on every emitted event. The exact outcome identity is expected and cannot show incremental value from the macro/sweep filters. The low target-first rate and negative fee-only expectancy still reject this fixed candidate; do not tune it or reopen this interval.

Four independent reviewers (two cash-equity, two crypto) then reviewed the prior evidence and this run without running tests or editing research. All four advise against another historical strategy sweep on current data. For KR/US, the immediate blocker remains a licensed, point-in-time security universe including inactive/delisted names and verified corporate-action/total-return histories; intraday data is separately absent. For crypto, neither the latest candidate nor prior MTF confidence slices satisfy the frozen M4 gate. The appropriate next work is data/evaluation readiness, not another signal permutation: acquire/verify the necessary equity panel before strategy tests; for crypto, require a genuinely prospective append-only signal ledger, usable and causally defined signal/calibration scheme, and realistic costs before any decisive evaluation. No such input or forward result was established in this review.

The existing Kronos shadow sidecar is not a hidden high-confidence trade-signal system: `shadow_predictor/core.py` emits 1- and 5-minute close forecasts and scores close MAE/no-change MAE/direction; it does not produce entry, invalidation/stop, target, first-touch outcome, or calibrated M4 success probability. Its present operation or forecast score cannot be used as evidence that the user's chart-entry objective is being met (`shadow_predictor/README.md`, “Evaluation semantics”; `shadow_predictor/core.py`, `process_snapshot` and `score_summary`).

This update supersedes the earlier statement above that the sweep/MSS candidate was untested. It does not authorize data purchases, network collection, server work, or trading.

## Official KR/US data-source readiness follow-up

A read-only check of official KRX and CRSP product pages found plausible data paths, but did not clear the purchase/data gate. KRX publicly describes delisted-issue metadata and a separate delisted-price-history screen, and sells index data products containing close/next-day constituents and corporate-action/index-membership changes; it does not establish from the public product descriptions that a complete all-listed-stock/ETF daily point-in-time panel with distributions is available in one bundle. CRSP advertises daily/monthly market data and corporate actions for 32,000+ active/inactive securities, with permanent identifiers; its CIZ schema includes ETF security subtypes, active/trading status and delisting/distribution fields. Access is subscription-based and no quote, sample, account, purchase, or local data availability was verified.

The detailed scope and acceptance checklist are in [`equity_data_source_readiness_20261115.md`](equity_data_source_readiness_20261115.md). Therefore the immediate KR/US blocker is narrower than “no data source exists”: candidate products exist, but full coverage, sample joins, rights, price, and locally usable files remain unverified. The next work requiring new authority is provider/account/quote or purchase activity; it was not performed. Maximum acceptable drawdown also remains undefined and must be fixed before choosing an autonomous portfolio objective.

## Follow-up research synthesis — L2 liquidity resilience

After the user's instruction to stop low-value tests, four read-only agents independently revisited the prior evidence by crypto/Pine/KR/US scope. No strategy sweep was run. The one differentiated crypto research question is whether L2 depth recovery/resilience after one-sided trade-flow shocks adds target-first price information beyond completed-BTC-regime + price-only and signed-flow baselines. It cannot be answered from the exposed candle-only cache. A current Binance public-data pilot would first have to reconstruct depth correctly, record sequence gaps/reconnects, and preserve an append-only stream ledger. The all-market liquidation stream is sampled (at most the latest event per symbol per 1,000 ms), so it is not a complete liquidation count. This is a new data/instrumentation gate, not evidence of a strategy edge. Full literature, stream constraints, and preregistration requirements: [`crypto_l2_resilience_research_gate_20261115.md`](crypto_l2_resilience_research_gate_20261115.md).
