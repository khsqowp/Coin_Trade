# Read-only market-data and research inventory findings

Snapshot date: 2026-11-20. This is an inventory/data-quality pass, not a strategy result or a deletion authorization. The metadata scanner did not open candle databases, move data, or calculate file hashes. The separate stock-cache check streamed the two CSV panels to validate timestamps, OHLC bounds, and zero-volume rows; it did not modify them.

## Repository and worktree state

- `/Users/user/Desktop/CODE/trading_bot` is not a Git repository. Coin_Trade is `/Users/user/CODE/Coin_Trade`, branch `main`, HEAD `069cbc6`, clean before this task's new files.
- Ochestration's repository root is `/Users/user/CODE/Ochestration`; `trading/scratchpad/` is untracked user work. The NAS target `/Volumes/HDD2TB/Trade` is not mounted, so no archive is certified for deletion.
- The two Git roots report 26 registered worktrees: 5 locked and 2 marked prunable. Their contents were not removed. Coin_Trade `.claude/worktrees` occupies about 29 GiB; the lock/prunable indicators require manual review before any cleanup.
- Current high-volume artifacts include Coin_Trade `chart_predictor/data` (~12 GiB), Ochestration's tick archive (~37 GiB), `trading/.rs_cache` (~2.5 GiB), and untracked `trading/scratchpad` (~1.9 GiB). Size does not establish that any is disposable.

## Preservation and cleanup decision

No file or directory is approved for deletion in this pass.

| Location | Classification | Reason for preserving / next proof required |
|---|---|---|
| Coin_Trade `chart_predictor/data` (~12 GiB; includes multi-GB SQLite DBs) | Research input, derived cache, run outputs; mixed and currently in use by the research package | Database contents were not opened for this inventory. Confirm writer/process state, DB references, reproducibility, run IDs, and verified backup before any cleanup proposal. |
| Ochestration `trading-tick-archive` (~37 GiB) | Raw tick logs | Archive is not current through 2026-11-20; NAS is unmounted; process-wide scan was permission-limited. Confirm collection quiescence and NAS checksum/manifest before considering archival cleanup. |
| Ochestration `trading/.rs_cache` (~2.5 GiB) | Cache | Rebuildability and active consumers have not been proven. Keep until code references and runtime usage are checked. |
| Ochestration `trading/scratchpad` (~1.9 GiB, untracked) | User work / mixed scratch outputs | Explicitly untracked, no ownership or reference proof for deletion. Preserve unchanged. |
| Coin_Trade `.claude/worktrees` (~29 GiB; 26 registered worktrees across both roots, 5 locked, 2 marked prunable) | Git worktrees and likely generated work | `prunable` is only Git metadata, not authorization. Check each branch, dirty state, lock owner, unique commits, and open work before cleanup; no worktree was removed. |
| Two initial inventory snapshots | Generated reports | A deletion attempt was rejected by the approval gate. Both snapshots remain; the older snapshot is explicitly preliminary. No workaround was used. |

Cleanup classification is therefore “preserve / needs evidence,” not “safe to
delete.” Any later deletion requires a separate candidate-by-candidate review
and explicit approval, plus a verified restorable copy for user data.

## Market and artifact inventory

The initial snapshot's 97-entry Coin_Trade experiment registry mapped to 49 crypto and 48 stock studies; that was the count at the time of the original inventory, not the current count. After the append-only stock replay rows and final documentation refresh, the latest snapshot `market_artifacts_20261120T040453Z.csv` records 11,334 entries, 102 registry rows, and 26 registered worktrees. Its paired registry crosswalk is `research_registry_20261120T040453Z.csv`. The labels remain conservative metadata hints, not a verified strategy leaderboard. Older inventory snapshots are retained; no source artifacts were deleted.

The tick archive contains 1,209 JSONL files (~39.9 decimal GB): 343 each for `crypto_perp`, `crypto_spot`, and `crypto_funding`; 148 `kr`; 32 `opening-scan-kr`. The dated directory range is 2026-10-18 through 2026-11-11. No US tick file was found in this archive scan. November data is not confirmed to be current; no file was deleted, and the absent NAS mount prevents backup verification.

The local USD-M research inputs at `/private/tmp/cointrade-50_50-data` are outside Git and must be preserved. Metadata audit files report 6,911 valid archives, 919 missing monthly archives, 113/113 recovered mark-price gaps, zero unresolved mark gaps, and nine funding interval metadata changes/disagreements. A fresh metadata-only continuity calculation requiring complete `klines_1h`, `mark_price_1h`, and `funding` archives, zero intra-month gaps, and no per-archive funding-interval inconsistency finds a 39-month clean run (2023-03–2026-05) for 36 symbols and at least 36 clean months for 37 symbols; per-symbol spans are recorded in [`usdm_archive_coverage_20261120.json`](usdm_archive_coverage_20261120.json). The separate raw ZIP audit verifies SHA-256 for all 6,911 archive files (0 missing, 0 mismatches), then checks 1,404 symbol-months over the common 36-symbol cohort: 0 missing/malformed, 0 incomplete hourly series, 0 in-window kline/mark timestamp mismatches, and 0 funding interval failures. Two extra mark-price rows occur before the corresponding symbol's first tradable kline and are explicitly outside that kline window. Result: [`usdm_archive_sha256_20261120.json`](usdm_archive_sha256_20261120.json) and [`usdm_timestamp_alignment_20261120.json`](usdm_timestamp_alignment_20261120.json). This proves byte identity against the provided audit and hour/funding alignment for this cohort, not price correctness, execution realism, source licensing, or point-in-time universe integrity. Inputs are 1-hour only, so they cannot validate 1m–30m strategy horizons. No archive ZIP was modified.

## Stock cache quality gate

`.kis-cache-local` is Git-ignored and contains 92 KR and 92 US daily CSVs.

| Cache | Rows scanned | Start-date range across symbols | End-date range across symbols | Zero-volume rows | OHLC bound violations |
|---|---:|---|---|---:|---:|
| KR | 326,225 | 2010-05-28 to 2023-01-05 | 2026-08-28 to 2026-11-12 | 457 | 0 |
| US | 339,303 | 2010-01-27 to 2021-07-29 | 2026-11-12 | 123 | 62 |

The US violations are 35 opens above the recorded high, 26 opens below the recorded low, and one close below the low. They cluster on 2021-05-05 (36 rows) and 2023-06-05 (22 rows), with additional rows on 2017-07-03 and 2018-11-15. This differs from the older 2026-11-07 audit's 35 Open violations; use this fresh scan as the current snapshot, and investigate the field-level adjustment/source behavior before using intraday fills or OHLC-bar stops. Zero volume and ending-date gaps also require symbol/date-level disposition.

Fresh per-file intersection check: requiring all 92 symbol files to have a
present, internally valid OHLC row yields 889 common KR sessions
(2023-01-05–2026-08-28) and 1,207 common US sessions (2021-07-29–2026-11-12).
Requiring positive volume as well reduces those to 832 KR sessions
(2023-01-05–2026-08-06) and 1,187 US sessions (2021-07-29–2026-11-12).
These are data-availability intersections only, not approved OOS periods; the
92-symbol current-survivor cohort and corporate-action gaps still invalidate a
validated historical claim. The KR all-symbol common window ends earlier than
the newest individual CSV because at least one file is stale.

Existing research documentation says these are current-survivor cohorts, not point-in-time membership, and that corporate-action provenance is not fully established. Therefore historical stock results may be used for exploratory comparison, but cannot be promoted as validated OOS evidence until the universe and price-history limitations are addressed.

The 2026-11-20 common-panel momentum replay is now documented in v1 and
inverse-excluded v2 reports. V1 retains the original 92-file cache including
KR `114800` and US `SH`; v2 excludes only those issuer-confirmed inverse ETFs
and uses 91 symbols per market. Both results are exploratory and fail the MDD
gate; see `stock_common_momentum_results_20261120.md` and
`stock_common_momentum_results_20261120_v2.md`. No source cache was changed.

## Transaction-cost source audit

- Existing KR/US portfolio research uses different assumptions across experiments. The comparable trend-gate runner uses KR base fee 6.5 bp/side + 5 bp/side slippage + 20 bp sell tax on taxable stock holdings; KR stress fee 11.5 bp/side with the same slippage/tax. US base is 8 bp fee + 10 bp slippage/side; stress is 36 bp fee + 25 bp slippage/side. These are historical scenario assumptions, not the user's account-specific fill costs.
- The Korea Investment Securities public guide says online domestic commission can vary by account/management branch and promotions; it lists stock sale tax separately. The KRX ETF guide states securities transaction tax is not charged to ETFs. Do not infer that every ETF has identical tax treatment for every other tax category.
- Binance's current official futures FAQ states fees vary with maker/taker and VIP tier; it gives an illustrative regular-user USDⓈ-M taker rate of 0.05% per side and maker 0.02%, while directing users to the current account fee table. The old crypto probes use 0.10% base / 0.30% stress round-trip cost and omit funding, spread, and slippage. The 10 bp base matches two 5 bp taker fees only as an illustrative assumption, not verified for this account.
- The local Ochestration `.rs_cache/funding` directory is empty. The separate temp archive has audited historical funding data, but coverage is incomplete. Tick records inspected by schema contain executed trade price/quantity and timestamps, not bid/ask depth; they cannot by themselves estimate quoted spread or order-book slippage.

For the first comparable research batch, retain the existing base/stress scenarios as named legacy assumptions, preserve KR tax separately, add observed funding where the symbol/time coverage passes validation, and keep results explicitly exploratory wherever account fee, spread, or slippage inputs remain unverified. Do not call the legacy scenarios “realistic fills” or approve a candidate solely on them.

Official fee/tax references reviewed:

- [Binance Futures fee structure FAQ](https://www.binance.com/en/support/faq/detail/360033544231)
- [Korea Investment Securities online-trading fees and tax guide](https://securities.koreainvestment.com/main/customer/guide/_static/TF04ae010000.jsp)
- [Korea Investment Securities overseas-market fee guide](https://securities.koreainvestment.com/main/bond/research/_static/TF03ca050000.jsp)
- [KRX ETF trading/tax information](https://global.krx.co.kr/contents/GLB/06/0605/0605010103/GLB0605010103.jsp)

## Next gate

1. Reconcile the 62 current US OHLC violations with the older 35-row audit and verify the source/adjustment mode without rewriting the cache.
2. Crypto archive byte identity and hour/funding timestamp alignment are now verified for the selected 36-symbol, 39-month cohort. The remaining 919 archive gaps and 9 funding interval metadata disagreements outside that cohort remain exclusions, not repaired data.
3. The first cost specification is frozen as named legacy base/stress scenarios in `comparable_evaluation_protocol_v1.md`. Account-specific fees and measured slippage remain unknown, so no candidate can receive final acceptance from those proxies alone.
4. Establish a defensible point-in-time stock universe or keep all current-cache stock results exploratory.
5. Only after those checks, map existing strategy outputs onto the common per-market periods and evaluate candidates under the fixed gates.
