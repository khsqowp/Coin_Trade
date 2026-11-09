# Daily NAS backup - independent re-review 4 (2026-11-05)

Review-only. No source, test, script, plist, launchd job, container or NAS data was modified or written. Experiments used synthetic trees and stubs under the session scratchpad (`.../scratchpad/r4`: `h.py` harness, `e1.py`..`e8.py`, wrapper stubs in `w/`). Real-system actions were read-only: `launchctl list`, `ls ~/Library/LaunchAgents`, `df`, reading two NAS manifests and `plutil -lint` on temp copies.

## Verdicts

| Decision | Verdict | Basis |
|---|---|---|
| (a) Install daily plist (deletion OFF) now | **YES**, after unloading the old jobs, with the doc corrections in N4 (do not `kickstart -k` before the pilot, do not enable the optional 6h job) | Plist has `DAILY_NAS_ENABLE_DELETE=0`; wrapper passes `--no-delete` (verified with a stub: args are `--no-delete ...`, and `--enable-delete` only when the env is `1`). Filled plist passes `plutil -lint`. |
| (b) Supervised `--enable-delete --only-day <old day>` trial | **YES**, one day, no `--max-files` | F1 stat/ctime check and all earlier races reproduce as fixed (E1). Failure modes seen are fail-closed and self-recover (E4). |
| (c) Unattended deletion after a clean trial | **CONDITIONAL / not yet**. No data-loss path found other than the acknowledged millisecond writer window. Fix N1 (one line) and N3 (do not start a day's deletion near the deadline) first, or explicitly accept them. | See N1, N3. Disk is 88% used (51 GB free, 44 GB backlog), so do not delay the trial. |
| (d) Blockers | None for (a) or (b). For (c): none that cause data loss; N1 and N3 are recommended pre-conditions. | |

## Test and lint results

- `cd trading && /opt/anaconda3/bin/python3 -m pytest tests -q`: **208 passed** (18 s). No pandas_ta/numba problem in this sandbox.
- `bash -n scripts/daily_nas_backup.sh` and `scripts/backup-tick-archive-to-nas.sh`: OK.
- `plutil -lint`: filled daily plist OK. There is no 6-hourly template file in `trading/docs/launchd/` (only archive-to-nas, daily-nas-backup, docker-watchdog templates). The 6h example in the doc is an XML fragment (no `<plist><dict>` envelope, no log paths); I wrapped it in an envelope and it lints OK.

## F1-F9 status (verified in code and by experiment)

| # | Result | Evidence |
|---|---|---|
| F1 | **Fixed in code** (residual ms window acknowledged) | `_safe_delete` lines 410-424: tombstone opened once, fstat before/after hash on the same fd, `_stat_identity` = (size, mtime_ns, ctime_ns, inode), compared fd vs path, and again after `_mount_check` right before `unlink`. Experiment E1 mutated the tombstone through a pre-opened fd inside the post-hash `_mount_check` window: append, same-length in-place rewrite, rewrite plus `utime` restore, and a ctime-only `chmod`. All four: rc 1, source restored with the changed bytes, no tombstone left, only an `intent` audit row (reconciled with `abort` by the next run). Unmodified control: rc 0, `intent`+`complete`. A write after the last stat and before the `unlink` syscall cannot be closed in userspace. The day-level idle check (lines 826-832) still compares only size/mtime/inode, not ctime; harmless because the full hash and the tombstone check follow. |
| F2 | **PARTIALLY fixed** (see N1) | Per-file `_verify` (line 756) and day-level `_verify` (line 794) handle `EOFError`/`BadGzipFile`/`zlib.error`; `_safe_delete` callers catch them (line 847). Experiment E2 (truncate, bit-flip, garbage, empty gz; corrupted before the run, between day verify and delete-stage verify, and during the idle wait): all handled except the delete-stage `_verify` at line 821 with a truncated gz (EOFError), which crashes the run (N1). Nothing was ever deleted in any case. |
| F3 | **Fixed** | E3 with a monotonic offset pushing past the deadline: after the first deletion, during the second file's pre-delete hash, just before the delete-stage verify, and during the idle sleep. All: rc 10, no tombstones, every started day fully deleted with matching intent/complete counts (3/3), untouched days intact (stage-verify case: no deletion at all, audit 0/0). Deterministic. `_safe_delete` now receives `deadline=None`, so the `TimeoutError` at line 419 is dead code. |
| F4 | **Fixed** | Wrapper stubs: tick fail + archive 10 gives rc 1 (markers: `last_partial.archive` only, no success markers); tick ok + archive 10 gives rc 10; archive 0 gives rc 0 and all three markers; archive 2 gives rc 1; tick fail + archive 0 gives rc 1 (archive marker only). Stale `last_success.no-tick`, `.archive`, `last_partial.archive` and aggregate are all cleared at start (line 52). |
| F5 | **Mostly fixed**, doc issues remain (N4) | Labels `com.ochestration.archive-to-nas` and `com.orchestration.tick-backup` match `launchctl list`; plist names match `ls ~/Library/LaunchAgents` (`com.ochestration.archive-to-nas.plist`, `com.orchestration.tick-backup.plist`; the weekly one is already `.plist.disabled`). Hourly removal now persists (bootout, rename to `.disabled`, `launchctl disable`). Stage/lint/bootstrap/kickstart/print commands for the daily plist are exact and use absolute paths. Pilot command uses the absolute script path and works from any cwd. |
| F6 | **UNFIXED (operational), documented** | Throttle still applies to local hash passes (`_verify`, `_file_hash`). With deletion off each run re-verifies the whole backlog; 44 GB local, 51 GB free (88%), growth 2-4 GB/day. Do the trial promptly. The currently loaded hourly job already exits 10 (deferred) per `launchctl list`. |
| F7 | **Fixed** (but see N5) | Legacy manifest records without `upload_id`: second run adopted them (gz count stayed 2, no duplicate upload), then deletion completed normally. Legacy record plus truncated gz: no crash, re-uploaded as `ticks.jsonl.<hash8>.gz`. Real NAS manifests (10/18, 10/19) are mixed legacy/new. |
| F8 | **Fixed** | E7: source plus same-inode `.deleting-N` hard link self-heals (tombstone removed, source kept, rc 0). An unrelated `.late-1` file with different content is retained with a stable name (no further renaming), rc 1 alert each run until the operator removes it. By design. |
| F9 | **Fixed** | `with_timeout` with grace 0 and 2: both return 124, no orphan processes. Side effect: any child killed by SIGKILL (for example OOM) is reported as 124. Harmless. |

## Full-suite abort fix (`cleanups` in outermost `finally`)

Correct and production-neutral.
- Watchers are created at lines 521-529 and `cleanups.append(...)` happens at line 530 with nothing that can return in between, so there is no window where a watcher exists unregistered. Returns before line 521 (state dir, lock open, lock contention) occur before any watcher exists.
- Experiment E5 ran `main` in-process through source-missing, mount-unavailable, deadline-at-start, preflight failure, bad `--only-day`, insufficient space, `--report`, `--dry-run`, normal run, mount lost mid-run, and lock contention. Thread inventory after each call: zero leaked watcher threads in all 11 cases. A `SystemExit` raised mid-delete also unwinds through the finally blocks (E4).
- Production behavior is unchanged: the io-timeout watchdog is still created before the hard-kill thread, and the hard-kill thread still calls `os._exit(3)` at `deadline + grace`. E6 in a subprocess with a stuck `_scan`: hard-kill path (0.6 s deadline, 1 s grace) exits 3 after about 1-2 s; the watchdog path (`--io-timeout 1`) exits 3 after about 1 s.
- Nit: `cleanups` run before `lock.close()`, which is correct order (watchers stop, then the lock is released).

## Findings (NEW or UNFIXED), severity ranked

### N1 MEDIUM-LOW (NEW, incomplete F2) - truncated NAS gz still crashes the run at the delete-stage verify
`archive_to_nas.py` line 821 calls `_verify(...)` inside `try` whose handler at line 838 is `except (BackupError, OSError)`. `gzip.BadGzipFile` is an `OSError`, but truncated deflate data raises `EOFError` and corrupt deflate raises `zlib.error`, which escape.
- E2 (stage, truncate): traceback, rc 1, nothing deleted, remaining UTC days not processed, status file left at "processing", no per-file ALERT. Local data intact (no rename had happened).
- Reachable only if the NAS gz is damaged in the seconds between the day-level verify and the delete-stage verify, so rare, and fail-closed.
- Fix: `except (BackupError, OSError, EOFError, zlib.error)` at line 838, and add a test. The report text "No traceback should escape" is currently inaccurate for this one spot.

### N2 LOW-MEDIUM (NEW) - `--dry-run` writes to the NAS manifest
Legacy adoption (lines 698-714) calls `_json_append(manifest, upload)` with no `readonly`/`dry_run` guard. E8: a `--dry-run` over a legacy manifest grew it from 2 to 3 lines. `--report` returns earlier and is safe. The appended record is correct (verified hashes), but the doc claims `--dry-run` is read-only. The real NAS day manifests for 2026-10-18 and 2026-10-19 contain legacy records, so any dry-run against them will write. Guard with `not args.dry_run`.

### N3 MEDIUM-LOW (NEW) - a day's deletion can outlast the hard-kill grace
Once a day's delete set starts, it ignores the deadline (by design, F3). Each file performs a full local hash plus NAS decompress-hash before rename, then another local hash after rename; the local hashes honor the 30 MB/s throttle. A 3-4 GB day therefore needs roughly 4-5 minutes, while the grace after the 150-minute deadline is 300 s and the wrapper timeout (9300 s) equals deadline plus grace. A day that starts deleting just before the deadline can be cut off by `os._exit(3)` or the wrapper's kill. Outcome is fail-closed and recoverable (tested with a simulated abort mid-transaction: tombstone restored on the next run, then a normal delete worked, E4), but it produces rc 1 alerts and a dangling intent for that night. Mitigation: skip starting a day's deletion when less than about 10 minutes of budget remains (defer, rc 10), or do not throttle the pre/post-delete hashes.

### N4 MEDIUM-LOW (NEW, doc) - rollout order and command details
1. Step 2 says to bootstrap the daily job before step 3 (the pilot), and the appended section then runs `launchctl kickstart -k`. That immediately starts a long upload-only run, so the pilot would collide on the archive flock (exit 2). Worse, `kickstart -k` kills a running instance. Recommended order: stage and lint, cut over the old jobs, run the pilot, then bootstrap the daily job and do not kickstart (or kickstart without `-k`).
2. Staging and bootstrap commands appear only in the appended section at the bottom, while the numbered steps say "do not bootstrap yet" without pointing there. Staging the plist into `~/Library/LaunchAgents` also means it loads at next login even if the cutover was not done.
3. There is no confirmation command for the hourly job removal. Add `launchctl list | grep -E 'ochestration|orchestration'` and `ls ~/Library/LaunchAgents` after the bootout/rename/disable steps.
4. Step 4 and the report say "restart that user job" after editing `DAILY_NAS_ENABLE_DELETE`. launchd re-reads the plist only after `launchctl bootout` followed by `bootstrap`; `kickstart` does not. State that explicitly.
5. Rollback does not mention `launchctl enable gui/$(id -u)/com.ochestration.archive-to-nas`; bootstrapping the restored plist fails while the label is disabled.
6. Optional 6h job (see N6).

### N5 LOW - pilot day selection and first-run side effects
Legacy adoption (F7) appends `upload` records to the NAS manifest on first contact, even with `--no-delete`. Expect manifest growth on 10/18 and 10/19 during the first runs. This is correct behavior, but it makes the pilot's "inspect the NAS day manifest" step noisier.

### N6 MEDIUM-LOW (NEW) - `--only no-tick` interacts badly with markers and the lock
- Line 52 clears all markers before the mode is parsed, so a `--only no-tick` run deletes `last_success.archive` and the aggregate marker, then line 118 writes the aggregate `last_success` and logs "DAILY NAS BACKUP SUCCESS" even though no archive step ran (E-wrapper: stale archive and aggregate markers removed, aggregate marker re-created). If the optional 6h job is enabled, any monitor on these markers is wrong most of the time.
- It shares the same wrapper lock. If it is running at 03:00, the daily run exits 2 (lock unavailable) and that night's archive is skipped. A `StartInterval` timer is relative to load time, so overlap is possible.
- Recommendation: do not enable the optional 6h job, or make no-tick mode neither clear nor write the archive/aggregate markers and use a separate lock.

### N7 LOW - cosmetic or benign
- When the deadline passes during the last day's transaction, `deferred_days += max(1, remaining)` makes the run exit 10 although nothing is left; the next run is clean.
- Dead code: `deletion_deferred` is never set, and the `TimeoutError` branch at line 419 is unreachable with `deadline=None`.
- A ctime-only change on the tombstone (for example `chmod` or an xattr write by another tool) is treated as a modification and the file is retained (fail-closed, retried next run).
- Residual: bytes written through an already-open descriptor in the few milliseconds between the final stat comparison and `unlink` are still lost (acknowledged; needs a live writer on a day closed for 6 h or more).

## Crash and recovery (synthetic)
- Abort after rename: tombstone and `intent` remain; the next run restores the file byte-for-byte and the following `--enable-delete` run deletes normally (E4).
- Delete-stage truncated gz: crash before any rename; no local change (N1).
- Hard link tombstone left by a crashed restore: self-heals (F8).

## Residual real-system checks left to the operator
Not testable here: SMB hard-link fallback on the NAS, TCC/Desktop access of `/bin/bash` running the new wrapper under launchd (the existing `com.orchestration.tick-backup` job runs the same way from the same Desktop path with last exit 0, which is encouraging), and a real deletion pilot.
