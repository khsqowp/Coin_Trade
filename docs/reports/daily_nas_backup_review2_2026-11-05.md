# Daily NAS backup - independent review 2 (2026-11-05)

## Scope and verdict summary

Review-only. No source, test, script, plist, launchd job, NAS archive, container, or Docker state was edited. The only repository file created by this review is this report. Experiments used temporary synthetic trees and command stubs under `/private/tmp`.

| Decision | Verdict | Basis |
|---|---|---|
| (a) Install the daily plist with deletion OFF | **YES, as a staged/offline install only; do not activate before cutover.** | Template has `DAILY_NAS_ENABLE_DELETE=0`, wrapper defaults to `--no-delete`, and filled plist passed `plutil -lint`. The wrapper will still fail its archive step if the old hourly job holds the Python `flock`; the current hourly plist file exists, so verify the process is gone and lock is released before starting the daily agent. |
| (b) Run manual `--enable-delete --only-day` pilot | **NO, not with the current deletion implementation.** | A same-size/same-mtime local rewrite during the idle interval was deleted although NAS still held the old bytes. Fix the pre-unlink re-hash race first. |
| (c) Enable unattended deletion after pilot | **NO, until all blockers below are fixed and independently re-reviewed.** | The reproduced data-loss race also applies to unattended deletes; interrupted-tombstone recovery has a separate overwrite race. |
| (d) Blockers | **Two data-loss races; misleading deferred-success status; incomplete cutover checklist.** | Details and reproducible synthetic evidence follow. |

## Severity-ranked findings

### CRITICAL — local content can change after the last hash and still be deleted

**Location:** `trading/scripts/archive_to_nas.py:741-768`, especially `:749-768`.

The source and decompressed NAS payload are freshly hashed before the idle wait (`:745`). After the wait, the whole delete set is checked only by `(size, mtime_ns, inode)` (`:751-755`); `_safe_delete` repeats the same metadata-only check (`:346-348`, `:357-358`) before unlink. A writer that changes bytes while preserving these metadata values passes every check. This does not meet the requested fresh content re-hash immediately before each unlink.

**Synthetic reproduction:** uploaded `ORIGINAL` to a temporary NAS tree, then replaced the local file with same-length `REPLACED` during the idle callback and restored its original nanosecond mtime. The run returned 0, deleted the local source, and left `ORIGINAL` as the NAS payload. No real archive was touched.

**Fix:** immediately before each individual tombstone rename/unlink, re-hash the local source and decompress/re-hash the referenced NAS gzip against the manifest; fail closed on any mismatch. Preserve the per-file mount and inode checks as additional guards. Add a regression case for same-size content replacement with restored mtime during idle.

### HIGH — tombstone recovery can overwrite a concurrently recreated source

**Location:** `trading/scripts/archive_to_nas.py:526-531` and `:542-547`.

Both recovery paths test `not original.exists()` / `not src.exists()` and then call `os.rename(tomb, original)` / `os.rename(tombs[0], src)`. On macOS/POSIX, rename replaces an existing regular destination. If the writer recreates the original path after the existence check but before rename, recovery replaces the new writer file with the older tombstone.

**Synthetic reproduction:** intercepted the recovery rename and created new source contents after the code's absence check. `os.rename` replaced those contents with the tombstone contents. The run returned 0. The test used a local temporary tree only.

**Fix:** restore without replacement, for example using an exclusive hard-link/create operation and unlinking the tombstone only after the destination is secured. If the original path already exists, retain the tombstone under a distinct late name and alert; never overwrite the path. Test both recovery sites with an injected concurrent source creation.

### MEDIUM — deferred archive work returns success and writes the archive success marker

**Location:** `trading/scripts/archive_to_nas.py:700-703`, `:723-725`, `:757-760`, `:780-782`; `scripts/daily_nas_backup.sh:84-86`.

Deadline exhaustion increments `deferred_days` and leaves work pending but does not increment `failures`; `main()` therefore returns 0. The wrapper interprets that as full archive success and writes `daily_nas_backup.last_success.archive`. A deadline reached before a selected `--only-day` deletion can consequently look successful to automation even though the day remains local. The report logs `deferred_days`, but the marker and exit code contradict that state.

**Fix:** give deferred/incomplete work a distinct nonzero or explicitly partial exit status, and have the wrapper write a completion marker only when no selected work remains. Keep a separate healthy-run marker if deferral is an expected operational outcome. Add deadline-boundary tests covering the wrapper marker and manual pilot result.

### MEDIUM — documented three-hour NAS retry window is not a three-hour upper bound

**Location:** `scripts/daily_nas_backup.sh:53-70`; `trading/docs/archive_to_nas_install.md:21`.

There are up to 18 ten-minute sleeps after the initial mount attempt, and each `ensure_mounted` call can itself spend up to 30 seconds on the initial mount probe, up to 90 seconds requesting each of two hosts, and five 30-second probes per host. Thus the worst-case run can exceed the stated three-hour retry window substantially (up to roughly 5.6 hours from these limits). The retry count is finite, but its wall-clock bound does not match the documentation.

**Fix:** enforce an absolute three-hour monotonic deadline across mount requests, probes, and sleeps, passing remaining time to each operation; report the actual bound in the install guide. Add a stubbed test that measures total elapsed virtual time at the failure boundary.

### MEDIUM — rollout checklist permits the four-hourly state backup to remain enabled

**Location:** `trading/docs/archive_to_nas_install.md:17-20`.

Step 2 says the four-hourly `com.orchestration.tick-backup` job “may remain.” The requested cutover requires disabling it when the daily job is installed. The weekly job is already present under a `.plist.disabled` filename in `~/Library/LaunchAgents`; the four-hourly plist is still present as an enabled-name `.plist`. This review did not change launchd. `launchctl list` returned no matching labels; a separate process listing was blocked by the environment, so current process/lock ownership could not be independently confirmed.

**Fix:** make the checklist require disabling/unloading the four-hourly job as part of cutover, while recording whether it is intentionally retained only before daily activation. Explicitly distinguish staging the daily plist from bootstrapping it. Keep the old hourly uploader unload-and-lock-release check before the daily agent starts.

## Requested checks and experimental results

- **Per-day sequencing:** candidates are grouped oldest UTC day first (`archive_to_nas.py:609-616`); each day is uploaded, re-scanned, re-hashed, then considered for deletion before advancing (`:699-739`). A day with zero matching candidates is not generated as a group; a day whose files disappear before the barrier has `day_ok=False` and does not delete. A late file observed by the barrier prevents that day from completing. A file arriving after the barrier is not deleted because it was not in the verified set, but it can make the just-written completion record stale until a later run.
- **Late append and NAS corruption:** the existing synthetic test for a local append during idle fails closed. I also truncated the synthetic NAS gzip during idle; it returned 1 and retained the local source. These checks do not close the same-size/same-mtime rewrite gap above.
- **Versioning and keep-days:** changed-source uploads use versioned remote names; verification binds the latest manifest upload to the current file. Deletion uses `day < current_UTC_date - keep_days`; with `keep-days=1`, yesterday remains. At 2026-11-06 03:00 KST (2026-11-05 18:00 UTC), 2026-11-04 is the newest eligible day and is retained; at 2026-11-07 03:00 KST (2026-11-06 18:00 UTC), 2026-11-04 becomes deletable. The UTC close-margin scan includes 2026-11-04 at 06:00 UTC on Nov 5, not at 05:59 UTC.
- **`--only-day`, `--max-files`, and exit status:** `--only-day` filters candidates before day grouping; invalid input returns 2. `--max-files` truncates candidates before day grouping, while the completeness barrier re-scans the entire selected day. A capped run with missing/unuploaded members fails the barrier; a capped run whose other members already have valid uploads can still reverify and delete the entire complete day. Therefore `--max-files` is not a per-file deletion cap. The install guide correctly says not to use it for the pilot.
- **Mount loss/deadline:** mount checks occur before uploads and before each file deletion. The between-day deadline defers remaining days, but currently exits 0 as described in MEDIUM finding 3. The existing tests cover preflight mount failure and deadline stops; the requested mid-day mount-loss and between-day marker/exit interplay are not fully covered by the repository tests.
- **Tick script:** `all`, `tick-only`, and missing mode are rejected before tick deletion; `no-tick` and `state-db-only` are dispatched separately. `rg` found no tick-archive `rm -rf`, `find -delete`, or directory move in the helper. Remaining removals target the wrapper lock, temporary staging, the previous state snapshot after successful replacement, or log rotation. The helper sets `/opt/homebrew/bin` in `PATH`; the daily plist itself has no explicit `PATH` key. The helper's group-timeout pattern terminated a synthetic child process in a direct Perl process-group experiment.
- **Staged state snapshot:** `docker cp` output and rsync are staged before moving the prior snapshot aside. A staging rsync failure occurs before the old snapshot is moved. If the staged move itself fails, restore is attempted and the previous snapshot remains under its `.previous.*` name if restore cannot complete; that restore failure is logged only indirectly and is not tested. The code does not delete the `.previous.*` directory on a failed stage move.
- **Wrapper lock and old uploader:** dead stale wrapper locks are reclaimed only after the configured age threshold; a live process identified as `daily_nas_backup.sh` is never stolen. If the old hourly uploader holds the Python archive `flock`, the archive command exits 2 and the wrapper records archive failure; the no-tick state backup has already run. This is safe against concurrent archive deletion but is an unsuccessful daily run. Verify the old PID has exited and the archive flock is free before starting the daily agent.
- **Deletion switch and success aggregation:** absent `DAILY_NAS_ENABLE_DELETE`, wrapper passes `--no-delete`; exactly `1` selects `--enable-delete`. Tick backup failure sets wrapper status 1 and skips archive execution; archive failure prevents aggregate `last_success`; per-step markers are separate. The remaining deferred-success mismatch is the MEDIUM finding above.
- **Shell modes and tests:** shell syntax checks passed for both requested scripts. The 69 targeted archive/wrapper tests passed. The requested full `cd trading && /opt/anaconda3/bin/python3 -m pytest tests -q` command failed during collection in seven unrelated equity tests because installed `pandas_ta`/Numba raises `RuntimeError: cannot cache function 'fibonacci': no locator available`; no NAS tests failed in that run.
- **Plist:** a placeholder-filled copy passed `plutil -lint`. The daily template defaults deletion to `0`. No explicit Homebrew `PATH` appears in the plist, but the tick helper exports Homebrew before invoking Docker; the wrapper's configured Python, Perl, mount, and date/stat paths are absolute or available from launchd's system path.
- **Real-tree read-only report:** `/Volumes/HDD2TB` was mounted. `archive_to_nas.py --dry-run --report` returned a report with 1,322 pending files / 43,024,668,714 bytes, 103 uploaded and verified candidates / 3,318,451,821 bytes, and 17 eligible UTC days from 2026-10-18 through 2026-11-03. NAS and state-tree metadata digests matched before and after. The local source-tree digest changed while the check ran (1,863 entries both times); a process-list query was denied, so the change cannot be attributed conclusively and may reflect the live tick writer. The report path itself is read-only in code; no NAS/state-tree mutation was observed.
- **Workspace state:** the reviewed uploader, tests, plist, docs, and wrapper remain untracked in the current Git worktree, alongside unrelated user changes. No commit was made, as instructed.

## Required blockers before deletion approval

1. Re-hash both local and decompressed NAS bytes after the idle wait immediately before each individual unlink; reject same-metadata content changes.
2. Make tombstone restoration no-clobber at both recovery sites and retain/alert on collisions.
3. Make deferred work distinguishable from completed success in archive exit status and wrapper markers.
4. Correct rollout order: stage with deletion off; unload the old hourly uploader and verify its process/flock is gone; confirm weekly remains disabled; disable the four-hourly state backup for daily activation; then start daily upload-only mode. Run the complete one-day manual pilot only after blockers 1-2 are fixed, with a preserved pre-run local copy and the documented NAS/local/audit checks.
5. Bound the NAS retry loop by its advertised absolute wall-clock limit and update the guide.
