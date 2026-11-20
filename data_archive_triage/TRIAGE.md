# Data/research archive triage (read-only analysis, 2026-11-20)

Nothing was deleted or moved. Sizes are apparent bytes (sum of file sizes). "tracked?" = git ls-files. Excluded by request: inbox/, trading/scratchpad/, trading/strategy_archive, trading/data_tick/ and trading-tick-archive (other agent).

Recommendation meanings: **KEEP** = must preserve, small, archived+moved by apply.sh; **COMPRESS-AND-MOVE** = worth preserving compactly outside repo; **DISCARD** = regenerable/superseded, deletion only with extra `--allow-discard`; **KEEP-IN-PLACE** = leave in repo (code/in use), not in allowlist.

## Table

| path | size | files | mtime range | class | tracked? | recommendation | reason |
|---|---:|---:|---|---|---|---|---|
| `backups/momentum_rotation_state.*` | 2.5 MB | 2 | 2026-10-11..2026-10-11 | REAL-MONEY RECORD | no (ignored) | KEEP | Live mainnet momentum bot state snapshots (2026-10-11): 573-row trade_log, 522 entry_log, 6298 equity_history points since 2026-09-02 (start equity 70.97 USDT). Not regenerable. Newer copy lives on linuxserver, but these are the only Mac-side copies. |
| `backups/momentum_*.inspect.*.json` | 27.6 KB | 2 | 2026-10-11..2026-10-11 | REAL-MONEY RECORD | no (ignored) | KEEP | docker inspect of live momentum containers (config/env at 2026-10-11); tiny, context for the state snapshots. |
| `backups/docker-compose.trading.yml.*` | 21.9 KB | 2 | 2026-10-11..2026-10-11 | REAL-MONEY RECORD (config) | no (ignored) | KEEP | Compose snapshot of the live trading stack on 2026-10-11; tiny, documents bot parameters used for the live history. |
| `backups/pre-flyway-manual-backup-20260919-161545.sql` | 50.7 MB | 1 | 2026-09-19..2026-09-19 | OTHER (app DB dump, non-investment) | no (ignored) | COMPRESS-AND-MOVE | Manual MySQL dump before Flyway adoption (2026-09-19). Orchestration app DB (notes, tasks, webhooks...), no trading tables. Oldest pre-migration state; keep one cheap copy. |
| `backups/orchestration-2026-11-11_030000.sql.gz` | 25.1 MB | 1 | 2026-11-11..2026-11-11 | OTHER (app DB dump, non-investment) | no (ignored) | COMPRESS-AND-MOVE | Latest daily dump of the app DB on Mac. Keep newest only. |
| `backups/orchestration-2026-11-0[3-9]_030000.sql.gz` | 141.4 MB | 6 | 2026-11-03..2026-11-09 | OTHER (app DB dump) | no (ignored) | DISCARD | Older daily dumps (Nov 3-9). Superseded; NAS daily backup 03:00 KST also holds them (verify on NAS before deleting). |
| `backups/orchestration-2026-11-10_030000.sql.gz` | 24.9 MB | 1 | 2026-11-10..2026-11-10 | OTHER (app DB dump) | no (ignored) | DISCARD | Superseded by the 11-11 dump. |
| `trading-crypto-paper-state` | 994.3 KB | 2 | 2026-10-18..2026-11-11 | FORWARD PAPER STATE (not regenerable) | no (ignored) | COMPRESS-AND-MOVE | Crypto paper-strategy engine state (6 symbols x 20 strategies; ledgers, equity) last updated 2026-11-11 + older 2-symbol file (2026-10-18). Paper, not real money, but forward-time results cannot be re-run. Gitignored. Mac copy is a stopped rollback copy; confirm linuxserver holds the live one. |
| `trading/shadow_predictor/runtime [excl: .gitkeep]` | 8.6 MB | 6 | 2026-10-22..2026-11-11 | FORWARD SHADOW PREDICTIONS (not regenerable) | no (ignored) | COMPRESS-AND-MOVE | Kronos shadow-predictor outputs: shadow_predictions.json (2.8MB) + rotated logs (Oct 22 - Nov 11). Forward-time forecasts cannot be recreated. NOTE durable sqlite spool is outside repo (~/Library/Application Support/CoinTradeShadowArchive) - already safe. Code in trading/shadow_predictor stays. |
| `trading/docs/round*-results-*.json` | 82.4 MB | 15 | 2026-10-13..2026-10-13 | REGENERABLE OUTPUT (backtest results) | yes (all 15) | COMPRESS-AND-MOVE | 15 round3-16 strategy-screen result JSONs (2026-10-06..08). Re-runnable from strategy_archive + cached prices, but expensive; summaries live in 전략-백테스트-종합.md. 86MB tracked (also in git history). Sibling round*.log/.txt files (tiny) not covered here. |
| `trading/docs/research/*.md` | 444.7 KB | 33 | 2026-10-11..2026-11-13 | DOCS | yes (all 33) | KEEP | Top-level research conclusions/PREREG/addenda/data-source audits (KR/US OHLC source audits, AW design/results). Cheap, high value. |
| `trading/docs/research/*.json` | 11.4 MB | 17 | 2026-10-11..2026-10-13 | REGENERABLE OUTPUT (small results) | yes (all 17) | COMPRESS-AND-MOVE | Top-level result JSONs (risk, regime, cadence, map_*, final_*): backtest outputs, ~10MB. |
| `trading/docs/research/*.diff` | 7.1 KB | 2 | 2026-10-11..2026-10-11 | DOCS (patches) | yes (all 2) | COMPRESS-AND-MOVE | Compose patch diffs, tiny. |
| `trading/docs/research/lev_loop [excl: B/out,R2A/out,R2B/data,R2C/data,*.pkl,C/results.json,*.npz]` | 3.0 MB | 165 | 2026-10-30..2026-11-08 | DOCS + scripts + small results | yes (all 165) | COMPRESS-AND-MOVE | Leverage-loop research: prereg/amendments, py scripts, reports, frontier tables (crypto leverage/liquidation study). Heavy pkl/npz/results excluded (see DISCARD). |
| `trading/docs/research/lev_loop/R2B/data` | 9.5 MB | 7 | 2026-10-31..2026-10-31 | RAW DATA (refetchable) | no (ignored) | COMPRESS-AND-MOVE | 1m crypto klines for 6 crash days (2022-05-11 ... 2025-10-10) + days.json. Public data.binance.vision; refetchable but cheap to keep (10MB). Gitignored. |
| `trading/docs/research/lev_loop/R2C/data [excl: new_panel_2020_2021.npz]` | 8.2 MB | 4 | 2026-10-31..2026-10-31 | RAW DATA (refetchable, PIT-built) | no (ignored) | COMPRESS-AND-MOVE | Binance USDT-M daily panel (daily_1d.csv.gz), point-in-time monthly universe membership incl. delisted (pit_membership.csv.gz), symbol lists. Source data.binance.vision; PIT membership was costly to build. Gitignored. |
| `trading/docs/research/lev_loop/B/out` | 659.0 MB | 207 | 2026-10-31..2026-10-31 | REGENERABLE OUTPUT (pkl sim caches) | no (ignored) | DISCARD | 54+ simulation pkl files (T0/T1/T2 x IS/OOS/FULL per config), 675MB, gitignored. Regenerable via lev_loop/B scripts; frontier.md/analysis.json keep the conclusions. |
| `trading/docs/research/lev_loop/A/*.pkl` | 137.7 MB | 5 | 2026-10-30..2026-10-30 | REGENERABLE OUTPUT (pkl) | no (ignored) | DISCARD | res_FULL/IS/OOS + sensitivity pkl, 141MB, gitignored; analysis2.json/out retained in COMPRESS entry. |
| `trading/docs/research/lev_loop/R2A/out` | 2.8 MB | 4 | 2026-10-31..2026-10-31 | REGENERABLE OUTPUT (pkl) | no (ignored) | DISCARD | stage pkl, 3MB, gitignored. |
| `trading/docs/research/lev_loop/C/results.json` | 11.8 MB | 1 | 2026-10-30..2026-10-30 | REGENERABLE OUTPUT | no (ignored) | DISCARD | 12MB sim result dump, gitignored by name; analysis.out kept. |
| `trading/docs/research/lev_loop/C/results_r.npz` | 6.8 MB | 1 | 2026-10-30..2026-10-30 | REGENERABLE OUTPUT | no (ignored) | DISCARD | 7MB npz, gitignored. |
| `trading/docs/research/lev_loop/R2C/results_arrays.npz` | 236.3 KB | 1 | 2026-10-31..2026-10-31 | REGENERABLE OUTPUT | no (ignored) | DISCARD | npz result arrays, gitignored. |
| `trading/docs/research/aw2 [excl: raw,raw/*]` | 16.6 MB | 43 | 2026-11-13..2026-11-13 | DOCS + ledger | yes (all 43) | COMPRESS-AND-MOVE | All-weather v2 KR/US search: AW2_LOG.md, ledger.jsonl (12MB, full trial ledger), wf/ walk-forward results, stock_cache_first_dates.csv. Conclusion-level artifacts. |
| `trading/docs/research/aw2/raw` | 672.7 MB | 5671 | 2026-11-13..2026-11-13 | REGENERABLE OUTPUT (per-trial backtest curves) | no (ignored) | DISCARD | 5711 JSON, 699MB, gitignored. NOT raw market data despite the name: each file is one trial result (curve_dates, equity curve, metrics). Regenerable from ledger params + price cache. No prices/fundamentals inside. |
| `trading/docs/research/aw1` | 17.1 MB | 2 | 2026-11-12..2026-11-12 | REGENERABLE OUTPUT | no (ignored) | COMPRESS-AND-MOVE | All-weather v1 KR/US result JSONs, 17MB, gitignored (so not in git history). Superseded by aw2 but only copy; cheap. |
| `trading/docs/research/equity_transfer_2026-10 [excl: full_runs]` | 627.2 KB | 30 | 2026-10-13..2026-10-16 | DOCS + summary results | yes (all 30) | COMPRESS-AND-MOVE | Oct 13-16 equity-transfer of crypto strategies to KR/US stocks: ~25 report md, kr/us.json, logs, strategy_scope_audit. 17MB. |
| `trading/docs/research/equity_transfer_2026-10/full_runs` | 686.1 MB | 295 | 2026-10-14..2026-10-16 | REGENERABLE OUTPUT (per-case result csv.gz) | yes (all 295) | DISCARD | 295 files, 703MB, TRACKED (recoverable via git history even after deletion; deleting does not shrink .git). Daily-case result tables derived from .kis-cache OHLCV. equity_peer_pairs*.json inside are results too. |
| `trading/docs/research/rebal_loop [excl: B/*.npz,B/.nbc]` | 11.3 MB | 57 | 2026-11-01..2026-11-01 | DOCS + scripts + small results | yes (all 57) | COMPRESS-AND-MOVE | Rebalance-loop study (A/B/C, debate): prereg, py, reports, grid.json, summaries. 11MB tracked. |
| `trading/docs/research/rebal_loop/B/streams.npz` | 220.7 MB | 1 | 2026-11-01..2026-11-01 | REGENERABLE OUTPUT | no (ignored) | DISCARD | 226MB npz of simulated streams, gitignored. |
| `trading/docs/research/rebal_loop/B/rs_final_panel.npz` | 20.6 MB | 1 | 2026-11-01..2026-11-01 | REGENERABLE OUTPUT | no (ignored) | DISCARD | 21MB npz derived panel, gitignored. |
| `trading/docs/research/rebal_loop/B/.nbc` | 1.0 MB | 5 | 2026-11-01..2026-11-01 | REGENERABLE OUTPUT (cache) | no (ignored) | DISCARD | numba/cache dir, 1MB, gitignored. |
| `trading/docs/research/sl_loop` | 31.9 MB | 24 | 2026-11-13..2026-11-14 | DOCS + scripts + results | yes (all 24) | COMPRESS-AND-MOVE | Stop-loss study (2026-11-13/14): prereg, report, results*.json (24MB), ledger.jsonl. Conclusion "no stop helps; keep 4x" is already in memory; results modest value. |
| `trading/docs/research/tp_loop` | 570.0 KB | 30 | 2026-10-30..2026-11-08 | DOCS + scripts + small results | yes (all 30) | COMPRESS-AND-MOVE | Take-profit loop (A/B/C/review), 0.6MB. |
| `trading/docs/research/jev_intraday` | 81.7 KB | 4 | 2026-10-16..2026-10-16 | DOCS | yes (all 4) | COMPRESS-AND-MOVE | Intraday feasibility notes (US/KR, crypto), 4 files. |
| `trading/data/aw_events.csv` | 13.3 KB | - | 2026-11-12 | INPUT TABLE (KR/US event calendar, hand/script generated) | yes | KEEP-IN-PLACE | Used by trading/app/aw_run.py. 13KB. |
| `trading/shadow_predictor/{*.py,Dockerfile,README.md,compose,...}` | 40.9 KB | - | 2026-10-19..11-11 | CODE | yes | KEEP-IN-PLACE | Sidecar source; only runtime/ is data. |

## Summary: bytes per recommendation

| recommendation | bytes | human |
|---|---:|---|
| KEEP | 3176696 | 3.0 MB |
| COMPRESS-AND-MOVE | 291626968 | 278.1 MB |
| DISCARD | 2711329691 | 2.5 GB |
| KEEP-IN-PLACE | 55542 | 54.2 KB |

Counts of table rows: KEEP 4, COMPRESS-AND-MOVE 17, DISCARD 13, KEEP-IN-PLACE 2.

## Findings that matter

**Real-money records (must keep)**
- `backups/momentum_rotation_state.20261011T063143Z.json` and `...063842Z.json`: `mode: live`, log line "[LIVE:mainnet] ... equity 70.97 USDT, 2x", trade_log 573, entry_log 522, equity_history 6298 points (2026-09-02 onward). Only real-money history inside the audited scope. Matching inspect JSON and compose snapshot are KEEP too.
- No TRX swing or funding-arb live trade/fill history exists in the audited scope. Those records must live elsewhere: linuxserver docker volumes (`ochestration_trading_paper_state` etc.), `trading-tick-archive`, `.rs_cache`, or trading/forward_test. Verify those separately before any cleanup there. `trading/docs/research` contains only backtests/papers, no live fills.
- Backups SQL dumps are the Spring app DB (tables like notepad, work_tasks, webhook_*; no trading tables), so they are not investment data.

**Stock data (US/KR/aw2)**
- Nothing in the audited scope is raw per-stock price data. `aw2/raw/*.json` (5711 files, 699MB) are per-trial backtest result curves (curve_dates, equity, metrics), named "raw" but regenerable. `aw2/stock_cache_first_dates.csv` only lists first-bar dates per symbol (KR/US cache status).
- The real stock OHLCV sits outside scope: `.kis-cache` (40MB, KIS API daily OHLCV, 118 files: US 54 and KR 64, 2018-01-02..2026-10; re-downloadable from KIS only with credentials, history limits apply) and `trading/.rs_cache` (2.6GB, bot cache, "regenerable" per .gitignore). `research/kr_us_loop_v1/data_mirror` is referenced in .gitignore but does not exist locally. Recommend the user decide on `.kis-cache` separately; it is the nearest thing to non-trivial stock raw data (the audit docs `us_*_sources_audit`, `kr_*_sources_audit` show free PIT sources were found inadequate, so re-sourcing may not reproduce it).
- Crypto raw data in scope: `lev_loop/R2B/data` (1m klines for 6 crash days) and `lev_loop/R2C/data` (daily USDT-M panel + PIT membership incl. delisted), both from public data.binance.vision, so refetchable; archived only for convenience.

**Git note**: ~720MB of the DISCARD bytes (`equity_transfer .../full_runs`) plus round*/sl_loop/etc are tracked; removing the working-tree copy does not shrink `.git`, and shows as deletions in git status. Ignored DISCARD items (~1.9GB: lev_loop B/out and A pkl, aw2/raw, rebal_loop npz) are gone for good when deleted but are regenerable from tracked scripts (some require the price caches above).

## Proposed layout outside the repo

```
~/CODE/trading_data/
  live_records/            # KEEP: momentum bot state, inspect, compose snapshots
  paper_state/             # crypto paper state, shadow predictor runtime
  db_backups/              # latest app DB dump + pre-flyway dump
  research/
    top_level/  rounds/  lev_loop/  aw1/  aw2/  equity_transfer/  rebal_loop/  sl_loop/  tp_loop/  jev_intraday/
  MANIFEST (per-archive .sha256 beside each .tar.zst)
```
Each archive is `NN_<path>.tar.zst` + `NN_<path>.sha256` (sha256 of every source file, relative to repo root) + `.tar.zst.sha256`. Restore: `zstd -dc X.tar.zst | tar -xf - -C /Users/user/CODE/Ochestration`. Suggest also copying `~/CODE/trading_data` to NAS.

## How to use apply.sh

1. Edit `trading/data_archive_triage/allowlist.txt` (`ACTION|path-or-glob|excludes|dest-subdir`; comment out `#` anything you want left alone, flip ACTION as you decide).
2. Dry run: `trading/data_archive_triage/apply.sh` (lists files/bytes per line, changes nothing).
3. `apply.sh --execute` archives KEEP/COMPRESS lines, verifies (zstd -t, extract and re-hash every file, count check, source re-hash) and only then removes those files (no `rm -r`; empty dirs pruned).
4. `--allow-discard` is required in addition to delete DISCARD lines (these are not archived).
Requires `zstd` (`brew install zstd`). Not executed by this triage. It refuses trading/data_tick, trading-tick-archive, inbox, scratchpad, strategy_archive.
Run order tip: do archive first (`--execute`), review, then a separate `--execute --allow-discard`.
