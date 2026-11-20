# docs/research — start here

The 2026-11-20 source inventory, data-quality gates, run contract, and first
fixed USD-M M2 re-evaluation are recorded under
[`inventory/`](inventory/README.md). The run disposition is documented in
[`inventory/usdm_1h_setup_m2_results_20261120.md`](inventory/usdm_1h_setup_m2_results_20261120.md).
The fixed common-panel stock momentum replay is separately reported in
[`inventory/stock_common_momentum_results_20261120.md`](inventory/stock_common_momentum_results_20261120.md);
it is exploratory only because the cache is exposed and not point-in-time.
The bounded funding-tail reversal trial is documented in
[`inventory/runs/funding_tail_reversal_20261120_v3/report.md`](inventory/runs/funding_tail_reversal_20261120_v3/report.md);
it was rejected and its evaluation dates were already exposed by prior research.

This directory accumulated ~100 one-off result files from two separate
sprints (2026-11-07 "oracle" equity-factor work, 2026-11-15 "agent loop"
equity+coin work) with no central index. If you are looking for "did we
already test X", **do not grep this directory by hand** — read
[`INDEX.md`](INDEX.md) first.

## The registry

[`registry.jsonl`](registry.jsonl) is the append-only source of truth: one
line per tested hypothesis (coin or stock), with its scope, headline
result, verdict, and a pointer to the full write-up. `INDEX.md` is a
generated view of it — never edit `INDEX.md` by hand, it is overwritten.

To log a new experiment or rebuild the index, see the usage docstring in
[`../../scripts/research/registry.py`](../../scripts/research/registry.py):

```bash
python3 scripts/research/registry.py list                  # browse
python3 scripts/research/registry.py list --verdict REJECT
python3 scripts/research/registry.py show 42                # full row
python3 scripts/research/registry.py rebuild-index           # after hand-editing jsonl
```

Any new backtest/probe script should call `log_experiment(...)` from that
module right after it has a result, instead of leaving a report file for
someone to find later by accident.

## Where the long-form write-ups live

- `docs/chart_predictor/rounds.md` — coin chart_predictor P4-P9 series (26
  rule-based setups, all against the 1/5/30/60m target-first hit-rate bar).
- `docs/research/agent_strategy_research_rounds_20261115.md` — the
  2026-11-15 sprint's own Round 1-7 (KR/US equity momentum + factor probes,
  coin signal/boundary diagnostics).
- `docs/research/strategy_research_round4_20261115.md` — an umbrella doc
  that actually covers Rounds 4 through 11 of that same sprint (misleading
  filename; every `round4_*`/`round5_*`/.../`round9_*` registry row below
  Round 7 points here unless noted otherwise).
- `docs/research/crypto_round10_liquidity_sweep_preregistration_20261115.md`,
  `docs/research/crypto_round11_streak_results_20261115.md`,
  `docs/research/equity_kr_compression_breakout_results_20261115.md` — three
  rounds that got their own dedicated files instead of the umbrella doc.
- `docs/research/kr-us-systematic-strategy-log.md` — the 2026-11-07 sprint's
  first pass, blocked entirely on data rights/point-in-time coverage before
  any strategy could be scored (0/2 valid).
- `docs/archive/salvage_2026-11-15/oracle_server/isolated_research/kr_us_loop_v1/`
  — the 2026-11-07 sprint's later generations (Gen02 through Gen18), moved
  to archive after three independent reviewers agreed no new hypothesis was
  left to try (`FEASIBILITY_BLOCKED`). `Gen17-low_skew-toy`'s 7/21-symbol
  "passing" low-skewness factor is the one historical result worth knowing
  about: it numerically cleared the CAGR/MDD/Sharpe bar, but only on a toy
  universe, and the 2026-11-18 `Round4` re-test on the full 92-symbol cache
  shows it does not survive.
- `docs/research/PREREG_*_gen14_*`/`gen15`/`gen16`/`PREREG_opening_gap_acceptance_screen`/
  `PREREG_survivor_cohort_screen` + their `ADDENDUM_*` files — frozen specs for
  the 2026-11-07 sprint's later equity screens; registry phases
  `gen14_survivor_closeonly`, `gen15_panic_reversal`, `gen16_calendar_closeonly`,
  `gen_opening_gap_screen`, `survivor_cohort_screen_us`,
  `survivor_cohort_screen_kr_mom12`. `docs/archive/.../kr_us_loop_v1/
  ORACLE_KR_US_LOOP_LOG_2026-11-07.md` has the narrative results for these same
  frozen specs (no generation_14/15/16 folders exist in the archive — the
  PREREG files here are the only copy of the frozen spec text).
- `docs/research/strategy_catalog.md` — a 2026-10-13 read-only meta-audit of
  the coin Round1-16 CAGR/Sharpe series; mostly re-describes rounds already
  in `legacy-cagr-rounds-1-16`, but surfaces two specific held-back
  candidates with their own registry rows: `donchian70_hysteresis` and
  `dual_thrust_longshort`.
- `docs/research/stocks_kr.md` / `stocks_us.md` — the coin momentum-rotation
  strategy ported to KR/US daily equities (registry phases
  `rs_kr_momentum_grid`, `rs_us_momentum_grid`); winner-dependent, not a
  clean pass.
- `docs/research/alpha.md` — a 5,953-combination crypto perpetual
  cross-sectional signal screen (registry phase
  `perp-futures-cross-sectional-alpha-screen`): the simple 14-day return
  rank baseline beats every challenger OOS.
- `docs/research/audit.md` — an independent red-team re-check of the
  momentum-rotation-live headline numbers reported elsewhere in this
  directory (registry phase `momentum-rotation-live-audit-correction`):
  the commonly-quoted "+28.9%" is one favorable cost/offset combination, not
  the live rule's realistic performance (~18-21% at realistic cost). Read
  this before trusting any single-number headline for that strategy.
- `docs/research/regime.md` (phase `regime-overlay-design-c-crash-reversal-trend-switch`,
  `VALIDATION_REQUIRED` — survivorship-biased crash-reversal sleeve, not a
  clean pass) and `docs/research/map_api.md` (phase
  `funding-reverse-overlay`, `REJECT` — loses to the live rule out of
  sample) — two overlay ideas on top of the live momentum-rotation
  strategy, evaluated and triaged.
- `docs/research/kr_kodex_100_200_data_audit_20261107.md`,
  `kr_public_daily_sources_audit_20261107.md`,
  `kr_us_index_universe_research_plan_20261107.md`,
  `us_candidate_rights_audit_20261107.md`,
  `us_free_pit_ohlc_sources_audit_20261107.md`,
  `us_ohlc_historicaldata_net_audit_20261107.md` — data-rights/PIT-coverage
  audits, not strategy results. Conclusions (no free KR/US source clears
  licensing + point-in-time + delisted-name coverage) are still the reason
  this project relies on the 92-symbol survivor CSV caches, and remain
  unrebutted as of 2026-11-18.
- `docs/research/cadence.md`, `risk.md`, `profit_protection.md`,
  `map_offline.md`, `final_integration.md` + their accompanying large JSON
  grids, `compose_patch.diff` / `compose_patch_profit_lock.diff`,
  `alphaxiv_openresearch_assessment.md`, and the `lev_loop/`, `rebal_loop/`,
  `tp_loop/`, `jev_intraday/` subdirectories — confirmed **not** hypothesis
  tests: they are operational/risk-engineering tuning (rebalance cadence,
  drawdown kill-switch ladder, profit-lock overlay, leverage/exposure
  sizing, a Docker Compose patch) for the already-deployed momentum-rotation
  strategy, so they don't fit this registry's pass/fail schema and are not
  logged as rows. `compose_patch.diff`'s comments claim a 2026-10-11 live
  parameter change (LEVERAGE=4, DEPLOY_PCT=0.5 → 2.0x gross, TOP_K=8,
  REBALANCE=3d, BTC-crash-flat overlay) — **this could not be verified
  locally** (the actual `docker-compose.trading.yml` lives on the remote
  trading server, not in this repo); treat it as an unverified claim about
  live config, not a confirmed fact, until checked against the server.
- `docs/research/equity_transfer_2026-10/` — a much bigger 2026-10-14 port of
  the coin side's entire 98-strategy-family offline registry onto KR/US
  daily equities (separate from, and larger than, `stocks_kr.md`/
  `stocks_us.md`'s 2026-10-13 momentum-grid-only port). All REJECT except
  four post-hoc-selected `VALIDATION_REQUIRED` cells (registry phases
  `equity_transfer_mach7_portfolio`, `round12_13_account_policy_transfer`,
  `round13_extension_account_policy_transfer`,
  `round14_prereg_portfolio_transfer` — each has a best-of-grid cell that
  numerically clears the stock bar but is a post-hoc pick out of
  44-106 settings, not independent evidence). The former
  `equity_transfer_round3_10_12_13_14_16_bundle` `NOT_EVALUABLE` row (left
  as-is per registry convention) is now superseded in substance by six
  per-round rows (`round3_account_policy_transfer`,
  `round10_regime_meta_transfer`, `round12_13_account_policy_transfer`,
  `round13_extension_account_policy_transfer`,
  `round14_prereg_portfolio_transfer`, `round16_liquidation_proxy_transfer`),
  all read individually 2026-11-18. No cell beats the stock bar on
  anything but a cherry-picked single config.
  **`full_runs/` inside this directory is 687MB across 295 gzipped CSVs and
  is committed to git** (not gitignored) — very likely the single biggest
  contributor to this repo's `.git` size (~592MB as of 2026-11-18). The
  headline numbers are already captured in the registry and in
  `FULL_TRANSFER_REPORT.md`, but the user explicitly decided (2026-11-18)
  to keep the raw per-trial CSVs as-is rather than rewrite git history to
  remove them ("그것 마저도 데이터야" — raw trial data is data too). **Do
  not propose deleting or history-rewriting `full_runs/` again** unless the
  user reopens this.

## Conventions

The 2026-11-20 read-only inventory and current data-quality blockers are in
[`inventory/data_quality_findings_20261120.md`](inventory/data_quality_findings_20261120.md).
The frozen first-pass market comparison rules are in
[`inventory/comparable_evaluation_protocol_v1.md`](inventory/comparable_evaluation_protocol_v1.md),
and current registry mapping limitations are in
[`inventory/registry_reconciliation_20261120.md`](inventory/registry_reconciliation_20261120.md).
The 2026-11-20 exploratory common-panel stock momentum replays are recorded in
[`inventory/stock_common_momentum_results_20261120.md`](inventory/stock_common_momentum_results_20261120.md)
(original 92-file sensitivity) and
[`inventory/stock_common_momentum_results_20261120_v2.md`](inventory/stock_common_momentum_results_20261120_v2.md)
(91-symbol inverse-excluded core cohort). Neither is valid OOS evidence.
The full phase-by-phase disposition, including the single distinct Phase 8
candidate tested and why no unvalidated Phase 9 mix was run, is in
[`inventory/plan_execution_status_20261120.md`](inventory/plan_execution_status_20261120.md).
The fixed-candidate robustness diagnostic is in
[`inventory/runs/stock_momentum_robustness_20261120_v5/report.md`](inventory/runs/stock_momentum_robustness_20261120_v5/report.md).
Regenerate metadata snapshots with `scripts/research/inventory_market_artifacts.py`;
the command does not inspect data contents, hash files, or alter source artifacts.

- Never retroactively edit a past registry row's `verdict` or
  `headline_metric` after you've seen a later, better result — append a new
  row instead (e.g. `Gen17-low_skew-toy` stays `VALIDATION_REQUIRED`;
  `Round4` is the separate row that supersedes it with `REJECT`). The
  registry is a lab notebook, not a leaderboard.
- `bar` should name the pre-registered pass/fail threshold that was active
  *at the time*, not today's threshold, if they differ.
- One row per named round/phase as it appears in the long-form doc, not one
  row per grid cell — the long-form doc is still the place for full detail.
