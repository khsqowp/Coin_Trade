# Independent review 2: archive_to_nas (2026-11-05)

Scope: re-review of `trading/scripts/archive_to_nas.py` (443 lines), `trading/tests/test_archive_to_nas.py`, `trading/docs/archive_to_nas_install.md`, the launchd plist template, and the 2026-11-04 report. Review only: no edits to the script or tests, no real upload or delete, no commit, launchd untouched. Experiments used synthetic trees in the scratchpad (`scratchpad/x/exp.py`, `neg.py`) that import the real module.

## Verdict

**(a) Install launchd with `--no-delete` now: YES, with two conditions.**
- Run the first `launchctl kickstart` by hand and read both logs to confirm TCC (Full Disk Access or Desktop and Network Volumes) is granted to `/opt/anaconda3/bin/python3`. This could not be tested without loading launchd.
- Know that the legacy job `com.orchestration.tick-archive-weekly` is still loaded and its next run is due about 2026-11-07 19:32 KST. It will `rm -rf` closed UTC day folders (H1). That is independent of the new job. The new job does not make it worse, and data stays safe because the legacy job verifies its own gz hash before it deletes. Unloading its tick part first is still better.

**(b) Use `--enable-delete`: NO, not yet.** H1 is still open, and this review found new problems that bite on the first real deletion:
- N1: the two real, already-uploaded files crash the delete path after the unlink (confirmed).
- N2: a lost or truncated manifest lets a late-recreated file overwrite the only gz copy (confirmed data loss in a synthetic run).
- N3: `--max-files` is silently ignored, so the staged "delete one day first" rollout cannot be done.

Deletion cannot happen by accident. See "Delete gate" below.

## Test results

- `/opt/anaconda3/bin/python3 -m pytest tests -q` from `trading/`: **133 passed** (2.8 s). The archive test file has 21 tests.
- `plutil -lint` on a filled copy of the plist (`scratchpad/filled.plist`): **OK**. Arguments are `--no-delete --max-minutes 40 --throttle-mbps 10`, `StartInterval` 3600, Nice 10, LowPriorityIO. No `ThrottleInterval` or `ExitTimeOut`, which is cosmetic.
- Real dry-run: `--dry-run --report --state-dir <scratch>` returned rc 0. 1376 pending (45.03 GB), 2 uploaded and verified, 0 deletable, NAS free 522 GB.
- `_mount_check` run directly on the real mount (not through the test stub). The real tree, `/Volumes/HDD2TB` and `Trade/tick-archive` passed. All five negative cases failed closed:
  - a local directory used as the mount
  - dest outside the mount
  - dest equal to the mount
  - a missing dest
  - mount `/`
- The tests stub `MOUNT_CHECK` in the fixture, so the production mount logic has no automated test (see test gaps).

## Delete gate: confirmed

- The only call path to `_safe_delete` is line 434. It is reached only after this chain:
  1. `args.enable_delete and not args.no_delete and not args.dry_run` (line 425)
  2. age >= keep-days and local grace >= 24h (line 426)
  3. the latest manifest upload record matches the exact upload_id, sha256, size and `mtime_ns` (lines 428-429)
  4. a second full `_verify` (line 430). It runs this run, after the earlier `_verify` at 415. It re-reads the whole gz, re-hashes it, decompresses it, re-hashes the source, and compares size and `mtime_ns` before and after.
  5. `_mount_check`, then in `_safe_delete` the mount check again, the size/mtime/inode stat, the rename, the post-rename stat, and one more mount check.
- Experiment (`gate`): with the grace elapsed and the file 18 days old, these invocations all left the file in place: `--report`, `--dry-run --enable-delete`, `--no-delete --enable-delete`, and no flags. Only `--enable-delete` alone deleted.
- Removing `--no-delete` from the plist does not enable deletion. The same-size-garbage NAS gz still blocks deletion (test `corrupted_nas_copy_blocks_deletion`; also reasoned from the code).
- Caveat: abbreviated flags are accepted by argparse (`--enable` works as `--enable-delete`). That is deliberate by the operator, so it is not a risk.
- Residual path: none found that deletes without `--enable-delete` or without a fresh verification.

## Status of prior findings

| Finding | Status | Evidence and notes |
|---|---|---|
| H1 legacy job deletes ticks | **OPEN** (as stated) | Plist loaded: `runs = 2`, last exit 1. Its log shows `mkdir /Volumes/HDD2TB: Permission denied` on 10-24 and 10-31, so it never ran while the NAS was mounted. The NAS is mounted now. The next run, about 11-07, will archive and delete for real. |
| H2 plist deletes by default | **FIXED** | The template has `--no-delete --max-minutes 40 --throttle-mbps 10`, and the script needs `--enable-delete`. A test pins this. |
| M1 TOCTOU on unlink | **MOSTLY FIXED** | Rename to `<name>.deleting-<pid>`, post-rename stat of size, mtime and inode, rollback on mismatch. `deleted.jsonl` is written after the unlink. Residuals: T1-T4 below, and N1. |
| M2 late append stuck | **FIXED** | A changed source gets a new upload record with name `<f>.<hash8>.gz`. The old gz is kept (test `late_append_creates_versioned_copy_and_keeps_old`). Residual: N2. |
| M3 grace from mutable manifest | **FIXED** | Grace is a local file keyed by path and upload_id. Garbage, empty, non-numeric, or an out-of-range value (before `uploaded_at`, or in the future) resets grace to now (experiment `gracebad`). The forged-epoch tests pass. The legacy no-upload_id match is still accepted (see N1). |
| M4 invalid on transient errors | **FIXED** | `invalid` is written only for EOFError, BadGzipFile, zlib.error, or a definite mismatch. OSError and TimeoutError defer. Residuals: L-items below. |
| M5 mount identity | **FIXED** | Checks are ismount, dest strictly under mount, dest is a directory, and `st_dev(dest) == st_dev(mount) != st_dev(source)`. They run before each file and each upload, and three times around the delete. Negative cases verified on the real function. A stale mount that still reports mounted cannot yield a false verification, because `_verify` has to read the real gz bytes. |
| M6 hung SMB | **PARTIAL** | The watchdog works (`os._exit(3)` after `--io-timeout`, default 300 s). Residuals: T3, L3. |
| M7 TCC and interpreter | **DOCUMENTED, UNVERIFIED** | The interpreter was changed to the pinned anaconda python. The TCC grant is a manual step and was not exercised under launchd. |
| L1 partial manifest line | **FIXED** | Healed on append (test present). |
| L2 `disk_usage` unguarded | **FIXED** | Returns rc 2. |
| L3 `.part` leftovers | **FIXED** (mostly) | `finally` unlinks the part. A sweep removes `.part` older than 24 h, only in day dirs the run visits. |
| L4 symlinks | **FIXED** | Skipped in scan and re-checked per file. |
| L5-L8 | Unchanged or accepted | The `ts` timezone assumption, the 2 h heuristic, no NAS scrub, no cross-host lock. |

## New findings

### HIGH

None independent of the open H1. N1 and N2 are the nearest and each blocks deletion.

### MEDIUM

**N1. The two real existing upload records have no `upload_id`, and the delete path crashes after the unlink.**
- Reproduced (experiment `legacy`): upload, strip `upload_id` from the manifest records, then run `--enable-delete` after the grace period. Result: `KeyError('upload_id')`, the source file is deleted, `deleted.jsonl` is not written, and the run aborts with a traceback.
- Cause:
  - `_verified` matches `None == None`, so records without an ID are treated as verified.
  - `_safe_delete` (line 301) indexes `upload["upload_id"]` after `tomb.unlink()`.
  - The invalid path (line 417) indexes it as well.
- Real exposure: `2026/10/18/03/crypto_funding.jsonl` and `crypto_perp.jsonl` on the NAS manifest were written by the earlier script version and have no `upload_id`. They are the first deletable files, being 18 days old. Data is not lost, because the gz was just verified, but the audit trail is lost and the run dies mid-batch.
- Related: line 394 compares `r.get("upload_id") == old.get("upload_id")`, so with `None` on both sides any ID-less `invalid` record would match.
- Fix:
  - Treat an upload without `upload_id` as unverified and force a fresh upload, or backfill a synthetic ID.
  - In `_safe_delete`, use `.get`, and write `deleted.jsonl` robustly.
  - Move the `deleted.jsonl` write into a `finally`-safe block that cannot abort the loop.

**N2. An existing gz is overwritten without a manifest guard (data loss when the manifest is lost).**
- Reproduced (experiment `manifestloss`):
  1. Upload `ticks.jsonl` ("ORIGINAL-DATA").
  2. Delete it locally via the normal gate.
  3. Remove the NAS manifest (truncation, restore from an older copy, or a human edit).
  4. A late writer recreates `ticks.jsonl` with 5 bytes.
  5. Next run: `old is None`, so the name is the unversioned `ticks.jsonl.gz`. `os.replace` overwrites the only copy, and the gz now contains only `late`.
- Versioning (the M2 fix) depends entirely on the manifest. The manifest sits on SMB and is editable by any client.
- Fix: before `os.replace`, if the target gz exists and is not backed by a matching upload record for this exact content, use the versioned name (or refuse). Use `os.link` or `O_EXCL` semantics so an existing gz is never replaced.

**N3. `--max-files` is accepted but ignored.**
- Line 316 defines it and no other line reads it (`grep max_files`).
- Real run: `--dry-run --max-files 3` printed 1374 `PLAN` lines.
- The earlier real smoke test used `--max-files 2`, so this is a regression from an earlier version.
- Impact: a staged rollout (delete one old day first) cannot be done. No data risk by itself. Implement it or remove the flag.

**N4. `--dry-run` without `--report` mutates the NAS manifest and the state directory.**
- Reproduced (experiment `dry`): after tampering with a gz, `--dry-run` appended an `invalid` record to the NAS `manifest.jsonl`. `--dry-run` also creates `grace/*.json`. Lines 417-424 are not guarded by `args.dry_run`.
- `--report` also writes grace files (line 371), which silently starts the grace clock.
- The design promise "dry-run writes nothing" holds only for not-yet-uploaded files.
- Fix: guard the manifest and grace writes with `not args.dry_run and not args.report`.

### LOW

**T1. Residual open-descriptor window in the tombstone logic.**
- A writer that opened the old inode before the rename and writes after `tomb.stat()` (line 286) and before `tomb.unlink()` (line 296) loses that write. The window includes the second `_mount_check` at line 295, which is several SMB stats, so tens of milliseconds, and up to the watchdog timeout if the NAS hangs.
- The writer in `app/tick_archive.py` opens, writes, fsyncs and closes per batch, so the window is tiny and only a writer stalled between open and write can hit it.
- Path-based opens after the rename correctly create a fresh file at the original path (no loss).
- The writer holds `flock` on `ARCHIVE_DIR/.append.lock` for each batch. Taking that same flock around rename, verify and unlink would close the window, if the lock is honored across the Docker bind mount. That could not be tested here.
- Cheaper alternative: open the tombstone for reading before the unlink, then after the unlink `fstat` the descriptor. If the size or mtime changed, write the content back to the original path.
- Move the second `_mount_check` out of the window.

**T2. `os.rename(tomb, src)` can overwrite a file the writer created in between.**
- Lines 288-293 and 298-299 check `src.exists()` and then rename. If the writer creates `src` in that gap, POSIX rename silently replaces the newer file.
- It is rarely reachable: it only happens on the failure path, and the window is microseconds.
- Fix: restore with `os.link(tomb, src)` and then unlink the tombstone. `link` fails with EEXIST instead of replacing.

**T3. Orphan tombstones.**
- A crash between rename and unlink (SIGTERM, SIGKILL, a watchdog `os._exit(3)`, or any `BaseException`; the handler catches only `Exception`) leaves `<name>.deleting-<pid>` locally.
- Nothing scans for it (the scan matches `*.jsonl` only). No data is lost, because the gz was verified. But it is never cleaned up or alerted on, and it keeps the hour directory from being pruned.
- `.late-<ns>` files (a changed tombstone with the original path re-created) hold the late-appended bytes. They are retained locally but never uploaded or listed anywhere except one ERROR log line, and the legacy job's `rm -rf` will remove them.
- Fix: sweep and upload `*.deleting-*` and `*.late-*` (or at least report them in `--report`).

**T4. Versioned-name collisions.**
- The name is `<file>.<hash8>.gz`. Equal content with a changed mtime yields the same name, and `os.replace` rewrites byte-identical content, which is harmless. Different content colliding on 8 hex digits is about 2^-32 per pair (negligible).
- Only the latest upload record authorizes deletion, so older versions are never deleted by mistake.
- The collision caveat that matters is N2.

**L1. Grace and retention depend on the wall clock.**
- A large forward clock jump satisfies both the 24 h grace and the 7-day rule. Experiment: a 3-day-old file was deleted after a +5 day clock jump.
- A backward jump or a bad value resets grace, which is the safe direction.
- Verification still runs and the NAS copy exists, so no data is lost, but the retention window is not protected.
- Mitigation: reject a `now` that is earlier than the newest manifest `uploaded_at`, or one more than a day past the last run time.

**L2. Watchdog side effects.**
- `os._exit(3)` skips `finally`. It leaves `.part` on the NAS (swept after 24 h, only in visited day dirs) and the lock file (the flock is released at process exit).
- If the process is stuck in uninterruptible SMB I/O, `os._exit` may not take effect until the syscall returns.
- A preflight failure returns without stopping the watcher thread. It is a daemon, so this only matters in long test sessions.
- There is no heartbeat during `fsync`, `_scan`, or manifest reads. A single `fsync` of a large `.part` taking more than 300 s would kill the run (unlikely at 10 MB/s).
- A very low `--throttle-mbps` (below about 0.004) would exceed the 300 s window per chunk.

**L3. `--max-minutes` behaviour.**
- A TimeoutError during an upload counts as a failure, so the run returns rc 1 instead of 0.
- The second `_verify` at line 430 has no `try`. A TimeoutError or OSError there ends the run with a traceback (rc 1), with no deletion.
- Both are safe but noisy.
- Throttling: the effective NAS transfer is about throttle / 3, because each file is read three times (pre-hash, copy, source re-hash), all throttled. The NAS-side gz reads are unthrottled. At 10 MB/s a 40-minute run handles about 8 GB, so the 45 GB backlog takes about 6 hourly runs. The largest file (428 MB) fits easily.

**L4. Failure after the unlink is not handled.**
- Any OSError from the `deleted.jsonl` append or the rmdir pruning after the unlink escapes as a traceback (only `BackupError` is caught at line 435). The local file is already gone, but the gz was verified.

**L5. Test gaps.**
- The production `_mount_check` has no test (the fixture stubs it). The real negative cases above were exercised only by hand.
- Missing tests:
  - legacy records without `upload_id` (N1)
  - manifest loss followed by a re-created file (N2)
  - `--max-files` (N3)
  - a dry-run on an already-uploaded file (N4)
  - an orphan tombstone or `.late` file, or a crash between rename and unlink
  - a rename-back overwrite
  - the watchdog killing a real run
  - `--max-minutes` expiry
  - `--report` output fields
  - the plist's argument list beyond string matching
- `test_tombstone_race_keeps_appended_original` patches `Path.stat`, which is a reasonable race injection. The remaining gap is a write after the post-rename stat.

**L6. Operational.**
- Neither log rotates, and INFO lines go to the `.error.log`.
- The label `com.ochestration.*` differs from the existing `com.orchestration.*` jobs, which is easy to confuse. Both are cosmetic.

## Recommended next steps

1. Install the plist with `--no-delete` and check the first kickstart logs for TCC and permission errors.
2. Unload (or strip the tick portion of) `com.orchestration.tick-archive-weekly` before about 11-07 (H1).
3. Fix N1, N2, N3 and N4, and add tests for them.
4. Consider the T1 and T2 hardening: hold the writer's `.append.lock`, or use `fstat` after the unlink; restore with `os.link`.
5. Run `--no-delete` for a few days, spot-check a few gz files against the local sources by hand, then enable `--enable-delete` on a single old day using a working `--max-files` or `--keep-days`.
