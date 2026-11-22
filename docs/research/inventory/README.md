# Market research inventory

This directory contains generated, read-only inventories of research and market data.
Source files remain in their original locations. No inventory command deletes, moves,
or edits source data.

Each inventory is a dated snapshot. The latest complete run is
`market_artifacts_20261120T044737Z.csv` with paired summary
`market_artifacts_20261120T044737Z.md`, worktree list
`git_worktrees_20261120T044737Z.csv`, and 105-row registry crosswalk
`research_registry_20261120T044737Z.csv`. It records 11,398 entries and 26
registered worktrees. Paths, sizes, Git tracking status, and any
date hints derived from paths describe the observed state at generation time.
The scanner does not calculate content hashes, and its snapshot does not prove
that a data source is licensed, point-in-time complete, or safe to delete.

Generate a fresh snapshot from the Coin_Trade root with:

```bash
PYTHONDONTWRITEBYTECODE=1 python3 scripts/research/inventory_market_artifacts.py \
  --out-dir docs/research/inventory
```

The script writes a file-level CSV, an experiment-registry CSV, a worktree CSV,
and an aggregate Markdown report. Very large untracked trees are aggregated rather
than enumerated. It deliberately does not hash data files because they may be large
or actively written; use a separate quiescence and preservation check before any
content-level deduplication or deletion decision.

The Phase 8 Round J source scan and its one fixed development-only lead-lag
screen are recorded in `phase8_source_round_j_20261120.md` and
`runs/lead_lag_1h_m2_round_k_20261120_v2/report.md`. The earlier incomplete
reporting attempt is retained with an explicit superseded status.

Rounds L and M are read-only source reviews. Their candidate exclusions and
source links are recorded in `phase8_source_round_l_20261120.md` and
`phase8_source_round_m_20261120.md`; neither round generated a performance
score.

Supplementary correction: [`phase8_data_correction_20261121.md`](phase8_data_correction_20261121.md)
records the later NAS spot/perpetual minute-archive discovery and its read-only
timestamp-grid audit. It supersedes only the earlier statement that the checked
`/private/tmp` panel had no spot OHLCV; it does not change any strategy score or
Core/OOS decision.

Round O's four-role HOLD decision on cross-cryptocurrency return prediction is
recorded in
[`phase8_source_round_o_cross_crypto_predictability_panel_20261121.md`](phase8_source_round_o_cross_crypto_predictability_panel_20261121.md).
It did not score outcomes or approve an M2 candidate.

The read-only `um_bookDepth` schema and official daily-to-monthly parity audit
is recorded in
[`phase8_bookdepth_archive_audit_20261121.md`](phase8_bookdepth_archive_audit_20261121.md).
It found only BTC/ETH coverage plus confirmed stale-band and incomplete-day
samples; no strategy score was run.

The full 2024-09..2026-10 Binance minute-archive timestamp-grid audit is
recorded in `phase8_full_minute_archive_timestamp_audit_20261121.md`. It
isolates a 32-symbol aligned spot/perpetual cohort, a shared missing mark-price
day, and unresolved funding timestamp semantics. No strategy was scored. The
rerunnable audit and its per-file JSON output are
`scripts/research/audit_crypto_minute_archive.py` and
`crypto_minute_archive_timestamp_audit_20261121.json`; the current full-union
status is FAIL due to documented gaps and partial listings.
The `--sha256` run is stored as
`crypto_minute_archive_sha256_audit_20261121.json`; all 3,580 present files
were stable during their individual hash reads. These local hashes are
reproducibility fingerprints, not publisher checksums.
The corrected `--ohlc-values` audit is stored as
`crypto_minute_archive_ohlc_audit_20261121.json`; it checks finite positive
OHLC values, high/low envelopes, nonnegative volume/count fields, and close
time alignment. It found zero value-invariant violations across the checked
price rows; overall status remains FAIL because of known timestamp gaps,
partial files, and funding anomalies. Four-lane source scouting and the
adversarial panel disposition are recorded in
`phase8_source_round_p_4lane_panel_20261121.md`.

Round Q repeated a bounded four-lane source search after the rejected Round N
minute diagnostic and convened a Blue/Red/Data-Methods/Judge panel. Both
stages returned zero eligible candidates; no outcomes were scored. The record
is `phase8_source_round_q_4lane_panel_20261121.md` and registry entry #119.

Round R screened adaptive selective prediction, polynomial autoregression,
microstructure, Pine, public-community, and GitHub leads. No source-defined M2
candidate qualified; the ML-to-M2 adaptation received no-preregistration/no-
test from the Judge. The review and next specification gate are in
`phase8_source_round_r_ml_selective_m2_panel_20261121.md`; registry #120.

Round S's fresh four-role panel cleared one frozen adaptive-selective M2
historical diagnostic only. The 32-symbol, 92-day run emitted 426,337 signals;
target-first M2 was 49.42%, with negative mean net return at both fixed cost
proxies. The candidate is rejected, Core remains zero, and Phase 9 was not
run. Approval and result records are
`phase8_round_s_adaptive_m2_prereg_approval_20261121.md` and
`phase8_round_s_adaptive_m2_historical_diagnostic_20261121.md`; registry #121.

The 2026-11-22 four-agent cross-market candidate round defines two KR, two US,
and two crypto order-block research slots, with red-team exclusions and
data/OOS gates recorded in
[`strategy_search_round_20261122.md`](strategy_search_round_20261122.md).
These are hypotheses, not passing strategies: no backtest ran, NAS paths were
not mounted in the current environment, and the validated count remains zero.
One US slot is an existing ETF volatility-rotation candidate, not a new
strategy family; the low-skew alternative was excluded after a prior stress-cost
failure.

Follow-up correction: local staged data was subsequently found under
`/Users/user/CODE/trading_data`, although the NAS mount remained absent. The
read-only crypto archive audit and the resulting blocked equity gates are in
`strategy_search_round_20261122.md`. The frozen spot/perpetual OB historical
development screen ran once and was rejected: candidate M2 target-first was
31.3869% across 16,749 issued signals and fee-proxy mean return was negative.
The report and compressed ledgers are in
`CRYPTO_OB_SAMEBAR_DEV_RESULT_20261122.md` and its linked run directory. This
does not qualify as OOS or profitability validation.
