# Daily NAS backup - independent review 3 (2026-11-05)

Review-only. No source, test, script, plist, launchd job, container or NAS data was modified. All experiments used synthetic trees and command stubs under the session scratchpad (`.../scratchpad/exp`, harness `h.py`, `e1.py`..`e8.py`, wrapper stubs in `w/`). The only real-system actions were read-only: `launchctl list/print`, reading NAS manifests, `df`, and a momentary non-blocking `flock` on the real archive lock (no holder).

## Verdicts

| Decision | Verdict | Basis |
|---|---|---|
| (a) Install daily plist (deletion OFF) after unloading old jobs | **YES**, with the checklist corrections in F5 | Deletion cannot occur: plist has `DAILY_NAS_ENABLE_DELETE=0`, the wrapper passes `--no-delete`. Filled plist passes `plutil -lint`. Wrapper/mount-deadline behavior verified with stubs. |
| (b) Manual `--enable-delete --only-day <old day>` trial | **YES, supervised, one day**, without `--max-files` | All Review2 data-loss races reproduce as fixed (E1, E2a/b/e, E3a/b/f, E6, E8). Residual windows are narrow and need a live-fd writer on a closed day (F1). Failure modes seen are fail-closed. |
| (c) Unattended deletion after a successful trial | **NOT YET (conditional)** | No known data-loss path without a concurrent writer, but fix F1 (ctime/fd check), F2 (uncaught `EOFError`/`zlib.error`) and F3/F4 (status classification) first; they are small. Disk is 88% used, so do not leave deletion off for long (F6). |
| (d) Blockers | None for (a) or (b). For (c): F1-F4 should be fixed or explicitly accepted. | See below. |

## Review2 claims: verification

| Claim | Result | Evidence |
|---|---|---|
| 1 CRITICAL: full re-hash before each unlink and again on tombstone | **Fixed** | E1: same-length in-place rewrite with mtime restored during a 1.2s idle wait: rc 1, file kept, no tombstone, no audit record. E2a: rewrite between pre-rename hash and rename: tombstone hash catches it, file restored (rc 1). E2b/E2e: append before rename: restored. E3a/E3b/E3f: NAS gz replaced by same-size random bytes, or by a valid gzip of different plaintext, before or after rename: nothing deleted, local file back. |
| 2 HIGH: recovery never clobbers | **Fixed** | E8a: source recreated after rename, hashes OK: new file untouched, tombstone unlinked. E8b: source recreated and NAS swapped: new file preserved, old data kept as `.deleting-N.late-<ns>`. Recovery uses `os.link` (exclusive). |
| 3 deferred runs exit 10; success marker only for complete runs | **Fixed with caveats** (F3, F4) | Wrapper stubs: archive 10 gives wrapper rc 10 and only `last_partial.archive`; archive 0 gives all three success markers; archive 2 gives wrapper rc 1. |
| 4 absolute 3h NAS retry deadline | **Fixed** | `NAS_RETRY_WINDOW_SECONDS=8` with a mount stub that sleeps 100s: wrapper exits rc 1 after 7s, no orphan processes. `open` stub that hangs, window 7: exits after 6s, no orphans. Mount timeouts are clamped to remaining time. |
| 5 doc rollout order | **Mostly fixed**, see F5 | Labels and file names are correct, but gaps remain. |

## Filesystem map (hardlink question)

- LOCAL source tree is on APFS (`/System/Volumes/Data`). Tombstone `rename`, `link` (restore), `unlink`, `stat` and local hashing all touch only APFS. Hard links work there, so the restore path works in production.
- smbfs is touched only for: gz `.part` write, `os.link(part, final)` (falls back to O_EXCL + `os.replace` on `ENOTSUP`/`EOPNOTSUPP`/`EXDEV`), manifest and `deleted.jsonl` appends, and NAS reads/decompression.
- Simulated link-unsupported local FS (E4a): when the tombstone hash mismatched and restore could not use `os.link`, the tombstone survived (`t.jsonl.deleting-PID`), was logged (`could not restore tombstone`), `--report` returned rc 1 and listed `orphan_tombstones` and `dangling_intents`, and later runs kept failing closed. When links became available again (E4a4) the next run restored the file and wrote an `abort` record. No data loss. The smbfs link fallback was not tested live (it would need a write to the NAS).

## Findings (NEW or UNFIXED), severity ranked

### F1 MEDIUM (UNFIXED, acknowledged) - bytes changed after the final hash can still be unlinked
`archive_to_nas.py` `_safe_delete` (about lines 398-401). After the tombstone hash there is `_mount_check` and then `tomb.unlink()`, with no stat re-check.
- E2c: a writer with an already-open descriptor appended after the tombstone hash. Result: tombstone unlinked, `complete` audit written, appended bytes lost.
- E2d: same-length in-place rewrite in that window: also deleted.
The window is milliseconds and needs a live-fd writer on a day closed for 6h+, so it is unlikely. Cheap hardening: open the tombstone once, `fstat` before and after hashing, and compare `st_size`, `st_mtime_ns` and `st_ctime_ns`, immediately before `unlink`. ctime cannot be restored from userspace, so it also defeats the utime-restore trick. Use the same ctime comparison at the idle-check stage (about lines 774-786).

### F2 MEDIUM (NEW) - `EOFError` / `zlib.error` from a corrupt or truncated NAS gz crash the whole run
`main` catches `(BackupError, OSError, TimeoutError)` around `_verify` and `_safe_delete` (about lines 775-792 and 799-801). `gzip.BadGzipFile` is an `OSError` and is caught, but truncated or corrupt deflate data raises `EOFError`/`zlib.error`.
- E3c/E3d/E3e: the run died with a traceback (exit 1). Fail-closed: the tombstone was restored (the generic `except Exception` in `_safe_delete`) and a dangling `intent` was left, which the next run reconciles.
- Impact: remaining days are not processed, the status file stays "processing", and no per-file ALERT line is emitted. Add `EOFError, zlib.error` to both except tuples.

### F3 MEDIUM (NEW) - deadline during a day's deletion set is reported as failure (exit 1), not deferral (exit 10)
E7b: the deadline passed during the second file's pre-rename hash. `TimeoutError` is caught at line 799 and counted as a failure with an ALERT. Result: rc 1, one file deleted (complete audit), one retained, later day deferred. At 150 minutes this happens whenever a large backlog day is mid-delete. Treat `TimeoutError` with `time.monotonic() >= deadline` as deferred (`deferred_days += 1`). Safe either way (no loss), but the "10 means no operation failure" contract is violated.
E7a (deadline between days) behaves correctly: rc 10, day 1 fully uploaded, verified, day-complete written and deleted; days 2-3 untouched.

### F4 MEDIUM (NEW) - wrapper status aggregation can mask a failure
`daily_nas_backup.sh` lines 93 and 104: if no-tick fails (`status=1`) and the archive then exits 10, `status=10` overwrites it (stub run agg1: wrapper rc 10 "PARTIAL" even though DB/state backup failed). The `ALERT no-tick backup failed` line is still logged and no success marker is written, but the exit code and the "PARTIAL" summary hide the failure. Use `(( status == 0 )) && status=10`, or take the max failure. Also the start-of-run `rm -f` (line 52) does not clear `daily_nas_backup.last_success.no-tick`, so a stale no-tick marker survives a failing day.

Exit code table: Python 0 complete; 1 failure(s) or uncaught exception; 2 setup/mount/lock/space/bad `--only-day`; 3 watchdog or hard-kill (`os._exit`); 10 deferred only. Wrapper: 0 all complete; 1 any failure (archive rc 1, 2, 3, 124, 137 all map to 1; mount unavailable gives 1); 2 wrapper lock unavailable; 10 archive deferred (subject to F4 masking). `$?` in the `else` branch is the archive rc (verified).

### F5 MEDIUM (doc/rollout) - checklist gaps
Verified correct: labels `com.ochestration.archive-to-nas` (loaded, idle, spelled "ochestration") and `com.orchestration.tick-backup` (loaded, spelled "orchestration"); both plist file names exist in `~/Library/LaunchAgents`; the flock one-liner runs and prints `archive flock released`; lock path and state dir match the wrapper; `pgrep -af` works on macOS (`-a` is accepted).
Problems:
1. `launchctl bootout` of `com.ochestration.archive-to-nas` is not persistent. The plist stays in `~/Library/LaunchAgents`, so it reloads at next login/reboot and runs hourly again (flock prevents overlap, but it contradicts the cutover). Rename it to `.disabled` as done for `tick-backup`, or add `launchctl disable gui/$(id -u)/com.ochestration.archive-to-nas`.
2. No command to stage or bootstrap the daily plist is given. Needed: `sed` fill into `~/Library/LaunchAgents/com.ochestration.daily-nas-backup.plist`, `plutil -lint`, then `launchctl bootstrap gui/$(id -u) <that file>` (and `launchctl print gui/$(id -u)/com.ochestration.daily-nas-backup` to confirm).
3. The pilot command uses the relative path `trading/scripts/archive_to_nas.py`, so it only works from the repo root; say so or use an absolute path.
4. Disabling `com.orchestration.tick-backup` (runs `state-db-only` every 4h) reduces DB/bot-state backup to once a day via the wrapper's `no-tick` step. State this as an intentional change.
5. Doc and report claim the full pytest is blocked by equity collection errors. In this environment collection succeeded, but the session aborts (rc 3) in `tests/test_docker_watchdog.py` (out of scope; several tests fail and one terminates pytest). With that file ignored: 190 passed. `test_archive_to_nas.py` (65) and `test_daily_nas_backup.py` (11) pass.

### F6 MEDIUM (operational) - deletion OFF means every run re-verifies the whole backlog, and the disk is 88% full
Each run fully hashes (throttled to 30 MB/s, local reads included) and decompresses every local closed day twice (file verify and day-level verify), oldest first. Backlog is about 44 GB locally (2026-10-18 to 11-04) and grows 2-4 GB/day, with only about 51 GB free on the Data volume (88% used). Estimated 1 hour per run now, increasing about 3-4 minutes per day, so the 150-minute budget is hit in roughly 3-4 weeks and the newest days would then starve (exit 10 forever). The disk fills in about 2-3 weeks. Do not run with deletion off for long; plan the trial promptly. Consider not applying the throttle to local-only hash passes.

### F7 LOW (NEW) - old-model NAS manifests have no `upload_id`
NAS manifests for 2026-10-18 and 2026-10-19 contain `upload`/`verified` records without `upload_id`. The new code treats them as not uploaded, so the first run re-uploads each file as `<name>.<hash8>.gz` next to the existing `.gz`. This is a duplicate-space cost (two days), not a correctness problem, and `_latest_upload` then uses the new record. If the trial day is 10/18 or 10/19, expect this.

### F8 LOW (NEW) - stuck tombstone states need operator action
- E6d: a crash between `link` and `tomb.unlink()` in restore leaves two hard links to the same inode. The next run renames the tombstone to `.late-*` (original exists), and every run afterwards reports it and blocks that day's completion (rc 1). Comparing `os.path.samefile` and simply unlinking the tombstone would self-heal.
- E8b: with a `.late` file still present and a dangling intent, each run renames it again (`.deleting-N.late-A.late-B`), which no longer matches the recovery regex, so names grow and the alert persists. No data loss.
- Link restore has no non-link fallback (E4a), fail-closed by design.

### F9 LOW - cosmetic
With `TIMEOUT_GRACE_SECONDS=0` the perl timeout helper kills its own process group, so a timed-out command reports `Killed: 9` and exit 137 instead of 124. Behavior is still correct (deadline enforced, no orphans).

## Crash and recovery matrix (all synthetic)

| Scenario | Outcome |
|---|---|
| Crash after rename (BaseException, no restore) | Tombstone and `intent` remain, `--report` rc 1. Next run restores the file and writes `abort`. A later `--enable-delete` run deletes normally (E6a). |
| Crash after unlink, before `complete` | `intent` only. Next run verifies the NAS copy (gz size/hash, payload size/hash) and writes `complete` (E6b). |
| Same, but NAS gz corrupted afterwards | No `complete` written, rc 1 persists, loud (E6c). Local data is already gone in that case (it requires NAS corruption after the final hash). |
| Reader holding the tombstoned inode | A reader keeps its descriptor (POSIX), no effect. A writer's bytes are caught if written before the tombstone hash completes (E2b); lost if after (F1). |

## Wrapper pipeline order (verified)
mount (bounded) -> no-tick backup (2h cap) -> `archive_to_nas.py` (155 min cap; the Python hard-kill is at 150 min + 300 s). Python order per UTC day, oldest first: deadline check -> per-file upload/verify -> deadline check -> rescan -> per-file `_verify` -> artifact checks -> `day_complete` -> (delete only if enabled and day older than keep-days) full verify of the set -> idle wait -> stat check -> per-file: hash local + NAS, intent, rename, tomb stat, tomb hash + NAS, mount check, unlink, complete. The deadline is honored between days and inside hashing (see F3 for classification).

## Test and lint results
- `bash -n` on `scripts/daily_nas_backup.sh` and `scripts/backup-tick-archive-to-nas.sh`: OK.
- Filled plist copy: `plutil -lint` OK.
- `cd trading && python3 -m pytest tests -q`: aborts at `test_docker_watchdog.py` (ignored per task). With it ignored: 190 passed. Targeted NAS files: 76 passed.
