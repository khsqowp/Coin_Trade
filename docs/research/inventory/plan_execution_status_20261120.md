# Coin_Trade research/data plan execution status

Snapshot date: 2026-11-20. This is a factual status ledger for the approved
10-phase plan. “Complete” means the phase's defined work and gate were handled;
it does not mean a profitable strategy was found.

## Phase status

| Phase | Status | Evidence / disposition |
|---|---|---|
| 0 — repository and work state | Complete | Canonical Coin_Trade root `/Users/user/CODE/Coin_Trade`, branch `main`; current metadata snapshot records 26 registered worktrees. Existing worktrees and raw data remain untouched. |
| 1 — data and artifact inventory | Complete | Metadata file manifest plus registry/worktree snapshots; market/data quality and source limitations in `data_quality_findings_20261120.md`. Latest listed snapshot is linked from `README.md`. |
| 2 — preserve/cleanup decision | Complete as a decision | No data or worktree deletion/move was performed or approved. Candidate removal is not proven safe; retain originals. |
| 3 — common evaluation rules | Complete | `comparable_evaluation_protocol_v1.md` fixes separate KR/US/crypto metrics, audited legacy base/stress assumptions, and promotion gates. These are scenario assumptions, not account-specific actual fills. |
| 4 — existing strategy mapping | Complete for available registry | Registry reconciliation and 107 append-only rows map prior studies. Historical incomparable, exposed, blocked, and non-evaluable results remain labeled; no missing result was inferred. |
| 5 — evaluation pipeline | Complete for the new comparable runners | Run-contract validator, common KR/US NAV runner, robustness runner, and tests are present. Legacy runners are not all wired to the contract; the contract's structural validity is not market-data validation. |
| 6 — comparable existing-candidate evaluation | Complete for the declared batches | Fixed USD-M 1h M2 batch: 76 cells, sealed best 38.46% (10/26), 23 non-overlap signals, zero 80% cells. KR/US v1 and inverse-excluded v2 each have 16 cells. No stock momentum variant passes the 30% MDD cap; full results are in the linked reports. |
| 7 — robustness/red-team | Complete for the fixed stock candidate family; crypto promotion not triggered | 36 stock parameter-neighborhood cells; 7 non-overlapping 6-month pseudo-OOS folds / 14 cost rows; 1,000 daily-return permutations and 1,000 20-session block-bootstrap paths for each of 12 stock cells. Independent recomputation of the 6 aggregate walk-forward cells and all 12 resampling cells matched. These are not untouched OOS or trade-level permutations. No stock cell clears the hard gates, so no candidate is promoted. |
| 8 — limited new strategy search | **Existing exploratory candidates rejected; later source screens produced no eligible candidate** | Independent read-only KR/US reviewer found no materially distinct cache-testable equity candidate. The four-source scout and four-role panel found no immediately eligible candidate; OI lead remains timing-ineligible. Prior-hour return contrarian screen: H1 M1 51.39%, gross +0.603 bp, net -9.396/-29.396 bp; H4 M1 50.50%, gross -1.119 bp, net -11.109/-31.109 bp. Cross-asset proxy uses BTC/ETH/XRP/LTC one-hour equal-weight leader return, fades it on 32 targets, H1/H4. Final v4 has 1,118,560 event rows; M1 49.87–51.62%; H1 base/stress opportunity net -8.95/-28.95 bp development, -10.18/-30.18 bp exposed validation, -9.93/-29.93 bp prior-exposed evaluation; H4 -11.38/-31.38, -9.67/-29.67, -13.03/-33.03 bp. Funding endpoint-exclusive base results are also negative (-8.96 to -13.04 bp). Coverage is 99.994–100%; market-wide non-overlap counts are 1,271–16,998, not independent events. Non-circular synchronized 7-day bootstrap intervals remain below zero. M2 was not measured. All dates were previously exposed; no core qualifies. Four-role final panel voted 4/4 to reject this fixed proxy for M2 progression, while limiting the conclusion to the proxy. Round F reviewed tick-jump clustering: no jump strategy advanced to M2 scoring; hourly proxy cannot reproduce tick jump timing and hourly data do not resolve intrabar barrier order. One positive-leader relative-return mechanism remains a forward-only, unregistered lead; no scoring or data download occurred. v2's H4 block length was 28 days and lacked coverage, and v3 used circular block joins; all are preserved as superseded. Canonical artifacts: `runs/cross_asset_seesaw_screen_20261120_v4/`; frozen rule: `PREREG_CROSS_ASSET_SEESAW_SCREEN_20261120.md`. Round F record: `phase8_source_rounds_20261120.md`.
| 9 — combination/portfolio | **Not run: prerequisite absent** | The protocol allows only individually validated core strategies into a combined portfolio. Current validated-core count is zero. Combining rejected or exposed exploratory candidates would be an invalid portfolio claim. |
| 10 — final record/backup | Complete for this continuation | Prior batch commit `7bbe07cb72dba8cbf941202b2467c58ad97d9a71` remains on `origin/main`. Cross-asset correction commit `07fd2b5059825a9af3b4253aac95ca233faa0a42` is pushed to `origin/research/bat-harmonic-validation-20261120`; `git ls-remote` matched, and v2/v3/v4 ledgers are tracked by LFS (v2/v3 identical; v4 includes endpoint sensitivity). Changed-scope tests: 20 pass, all 1,118,560 v4 ledger rows, 4,212 source hashes, source-manifest digest, code digest, and `git diff --check` were verified. This snapshot update is included in a follow-on documentation commit on the same branch. No Oracle deployment or orders are in scope. |

### Phase 8 continuation: OI metrics data gate

The four-source review's OI-stop-hunt lead remains unscored. A preregistered 268-file sample across the 36-symbol cohort passed checksums and structural 5-minute-grid checks; two nulls occurred in the taker-ratio field, not OI. A separate BTCUSDT 2026-11-19 archive/REST comparison matched both OI fields exactly at the same timestamp for 288 rows; the preregistered +5-minute timing screen failed. Current files for 2026-06-24/25 have start-of-day labels, conflicting with public Issue #491's earlier observations. Historical observation time and first-availability remain unresolved, so OI is still ineligible for strategy scoring. See `usdm_metrics_sample_audit_20261120.md`; no raw samples were added to Git.

### Phase 8 continuation: source panel and UTC calendar candidate

This continuation supersedes the Phase 8 table row's wording that the prior
cross-asset screen was the final screen. Four-source scouting (SNS,
TradingView/Pine, public communities, GitHub) found no directly eligible
recipe. A four-role panel approved one fixed UTC weekday-hour candidate for a
single exploratory M2 run after data gates. The run independently checked
3,024 monthly ZIP hashes and 36 daily mark-price recovery overlays; it excluded
IMXUSDT for one funding interval inconsistency. M2 was 37.36% (14,724/39,410),
below the 80% gate and frozen short baseline 37.70%; coverage was 38.50% across
35 symbols. Modeled base/stress net means were -11.424/-31.424 bp, and fees-only
means were also negative. The final panel rejected this fixed rule; no retuning
or Phase 9 combination follows. The 2026-06..09 data are source-audited, not
sealed or live-forward evidence. Funding notional basis and six period-end
exits limit precision of the modeled funding mean. See
`phase8_calendar_candidate_panel_20261120.md` and
`runs/weekday_hour_m2_20261120/report.md`.

## Robustness result in one view

- The 36 lookback/cadence/gate/cost cells had **0/36** meet the simultaneous
  numeric CAGR, MDD, and Sharpe thresholds; every cell exceeded MDD 30%.
- The combined pseudo-OOS US daily-top-10 path had CAGR 35.7% / MDD 33.7% /
  Sharpe 1.381 at base cost and CAGR 18.5% / MDD 36.9% / Sharpe 0.844 at
  stress cost. Its 286 closed-position records are not proven independent.
- The best-looking pseudo-OOS numbers are exposed-history diagnostics and
  cannot turn the input into an untouched test set. Raw round-trip counts do
  not override data defects or drawdown failure.
- Across the path simulations, worst-cell p95 MDD was 53.7%/60.9% under daily
  return permutation and 59.6%/70.4% under block bootstrap for KR/US,
  respectively. These resample daily portfolio returns, not individual trades.

## Remaining evidence needed to resume strategy validation

1. Point-in-time KR/US security membership including delisted/merged symbols,
   with licensed historical prices and verified corporate-action semantics.
2. For minute-scale crypto signal claims, causal minute-or-finer OHLCV and
   execution/funding inputs with source and coverage validation. The local
   exchange archive evaluated in Phase 6 is 1-hour only.
3. Account-specific fee/tax schedules and measured spread/slippage if results
   are to support an account-level execution claim.
4. A preregistered hypothesis materially distinct from the recorded strategy
   families, followed by the same comparable pipeline and untouched future
   evidence. Until then, no Core designation and no Phase 9 mix.

## Reproduction anchors

- Stock core results: `stock_common_momentum_results_20261120_v2.md`.
- Robustness preregistration: `PREREG_STOCK_MOMENTUM_ROBUSTNESS_20261120.md`.
- Canonical stock robustness run: `runs/stock_momentum_robustness_20261120_v5/`.
- Crypto M2 results: `usdm_1h_setup_m2_results_20261120.md`.
- Crypto funding-tail exploratory result: `runs/funding_tail_reversal_20261120_v3/report.md` and its event ledger; the two invalid earlier attempts are retained with explicit status markers.
- Additional source-inspired crypto screen: `runs/hourly_return_reversal_screen_20261120/report.md`; frozen H1/H4 prior-hour contrarian rule rejected after base/stress costs. It does not measure M2 and all periods were previously exposed.
- Final source inventory: see the snapshot names in this directory's `README.md`.

### Phase 8 continuation: four-source panel and basis follow-up

Four independent scouts screened public SNS, TradingView/Pine, communities, and
GitHub/skills. The only conditional lead was a BTC 1h negative-funding + RSI
30 up-cross with ATR trailing exit. Four reviewers (Blue, Red, Data/Methods,
Judge) unanimously rejected it for the frozen M2 pipeline: it has no fixed TP
or expiry, is BTC-only, and source-reported trades are not a local independent
ledger. A second four-source screen on perp/spot basis convergence found no
eligible M2 candidate: published examples lack exits, rely on BTC/ETH or a
two-leg spread, or lack verified source/license/universe evidence. The local
historical input root contains perp klines, mark-price klines, and funding but
no spot OHLCV. No scoring or data download occurred. Full source-by-source
findings and the debate are in
`phase8_source_rounds_20261120.md`. The prior OI timing audit already ran but
did not establish historical first availability. Do not repeat it without new
authoritative evidence. Validated-core count is still zero; Phase 9 remains
blocked.

### Phase 8 continuation: 1m/3m source screen and debate

Four source scouts (SNS/research, TradingView/Pine, communities, GitHub/skills)
found zero eligible strategies for scoring. The closest novel lead was a
published 15-minute-boundary/10-second direction effect, but its reported
direction accuracy is not M2 target-first success; its reported gross mean is
below cited taker cost, it provides no TP/SL/expiry rule, and local data are
hourly. The positioning/OI lead remains ineligible because historical first
availability and a stable complete rule are unproven. Pine/community/GitHub
leads were incomplete, overlapping, or framework-only. A second four-role
panel (Blue, Red, Data/Methods, Judge) unanimously held all candidates from
scoring. A further four-researcher, local-data-constrained hypothesis round
also produced zero defensible, source-grounded candidates. This is a bounded
search, not proof all public strategies or all custom hypotheses were
exhausted. Do not repeat OI provenance work without new authoritative
evidence. Next: require a distinct, complete preregisterable mechanism and
confirm data availability before acquisition; use exposed history only for
development, then test prospectively without tuning. Core count remains zero;
Phase 9 remains blocked. Details and source links are in
`phase8_source_rounds_20261120.md`.

### Phase 8 continuation: Round E source follow-up and panel

Four roles reviewed the 2023 BTC candle-boundary paper, the 2026 hourly
BTC/ETH session-momentum/reversal paper, and whether Binance OI timing is now
resolvable. The candle-boundary mechanism duplicates an already exposed local
probe (registry row 23) and the source portfolio simulation does not define
target-first barriers. The session paper searched 300 cutoff/strategy
combinations, reports no significant SPA superiority, and has no M2
boundaries; its BTC result does not hold up in the chronological evaluation.
A custom 12-hour session-sign M2 adaptation was judged conceptually distinct
by Blue only, while Red, Data/Methods, and Judge did not advance it. No new
strategy was scored.

Official Binance USDⓈ-M documentation confirms historical OI statistics are
period-end timestamped, latest-month-only via REST, and may omit no-trade
periods. This does not establish the first time an archived OI value was
available; prior archive/REST offset results conflict. No additional OI audit
or scoring is warranted from this documentation alone. OI remains ineligible,
Core count remains zero, and Phase 9 is not run. Detailed record:
`phase8_source_rounds_20261120.md`, Round E.
