# Daily NAS backup implementation and rollout review (2026-11-05)

## Implementation model

The LaunchAgent runs once daily at 03:00 KST. In that single run it backs up crypto-paper state, database dumps, and bot state, then uploads and verifies eligible tick-archive days. State/DB and tick archive backups are daily stages; there is no six-hour state/DB mode. Each UTC tick day is rescanned and fully verified before optional deletion. Deletion remains disabled by default in the wrapper and plist. Archive status 10 means work was deferred; the wrapper records a partial marker and does not claim archive or aggregate success.

Each file deletion has a durable `intent` audit row before rename. The uploader reserves hard-kill grace for per-file deletion work, checks the reserve between files, and defers remaining work with status 10 when the next file cannot safely fit. A delete-stage gzip verification error is logged against that day and other days continue. `--dry-run` and `--report` do not modify manifests, audit records, or state files, including legacy manifest adoption. The obsolete `--only no-tick` wrapper mode and `no-tick` tick-backup mode are removed.

## Rollout checklist

1. Fill the placeholders in `trading/docs/launchd/com.ochestration.daily-nas-backup.plist.template` in a temporary copy and run `plutil -lint` on the filled copy. Do not stage or bootstrap the daily plist yet. Keep `DAILY_NAS_ENABLE_DELETE=0`.
2. Boot out the old hourly archive job first: `launchctl bootout gui/$(id -u)/com.ochestration.archive-to-nas`. Confirm its process is gone with `pgrep -fl 'archive_to_nas.py|archive-to-nas'` and confirm the archive lock is not held. Check both launchd registration and installed files with `launchctl list | grep -E 'ochestration|orchestration'` and `ls ~/Library/LaunchAgents`. Boot out the weekly `com.orchestration.tick-archive-weekly` job. Boot out `com.orchestration.tick-backup`, rename its installed plist to `.plist.disabled`, then persist the removal with `launchctl disable gui/$(id -u)/com.orchestration.tick-backup`.
3. Run the one-day deletion pilot manually only after the hourly process has exited and released its archive lock. Use `/opt/anaconda3/bin/python3 /Users/user/Desktop/CODE/Ochestration/trading/scripts/archive_to_nas.py --enable-delete --only-day <oldest-eligible-UTC-day> --idle-seconds 5 --max-minutes 150 --throttle-mbps 30 --keep-days 1`. Do not use `--max-files`; it can still culminate in deletion of a complete day. Preserve a local inspection copy first. Compare NAS gzip decompressed SHA-256 values with that copy; inspect the NAS day manifest, local day-complete record, matching deletion intent/completion audit rows, and confirm only the selected local day became empty.
4. Only after the pilot is reviewed, copy the filled plist into `~/Library/LaunchAgents/com.ochestration.daily-nas-backup.plist`, lint the installed copy, then bootstrap it with `launchctl bootstrap gui/$(id -u) ~/Library/LaunchAgents/com.ochestration.daily-nas-backup.plist`. Do not use `launchctl kickstart -k` while any run is active; it terminates the active process. A normal kickstart is unnecessary for installation. Confirm with `launchctl print gui/$(id -u)/com.ochestration.daily-nas-backup`.
5. Any change to `DAILY_NAS_ENABLE_DELETE` in the installed plist requires `launchctl bootout gui/$(id -u)/com.ochestration.daily-nas-backup` followed by `launchctl bootstrap gui/$(id -u) ~/Library/LaunchAgents/com.ochestration.daily-nas-backup.plist`; `kickstart` does not reload plist environment values. Set it back to `0` the same way to return to upload-only behavior. Verify `.last_success.state-db`, `.last_success.archive`, the aggregate `.last_success`, wrapper logs, and no unresolved errors.
6. Rollback: boot out the daily job; restore any renamed legacy plist if needed; run `launchctl enable gui/$(id -u)/com.ochestration.archive-to-nas` before bootstrapping its restored plist. `launchctl disable` persists across logins, so restoring the file alone does not re-enable a job. Check hourly registration and installed files again after rollback.

State/DB backups run once daily at 03:00 KST. There is no optional six-hour schedule or `--only no-tick` command. NAS mount retries remain bounded by the wrapper's three-hour retry window.

## Verification boundary and risks

Repository tests validate stubbed flows and temporary directories. They do not prove current launchd state, NAS mount health, SMB atomic rename behavior, Docker Desktop state, TCC permissions, or a real deletion pilot. Real NAS writes are limited to a removable smoke-test scratch directory; the rollout pilot remains an operator action. A writer with an already-open descriptor can still alter bytes in the small interval after the final full hash and before unlink; no userspace hash check can make that interval atomic. If the source filesystem does not support hard links, recovery fails closed and leaves a tombstone for operator recovery. SMB directory rename semantics and the mount timeout behavior still require host confirmation.

The source, tests, and plist are present at their expected repository paths. No commit, push, build, deployment, launchd load/unload, real archive deletion, or real-job edit was performed.


## Independent review 2 fixes (2026-11-05)

- **CRITICAL fixed:** pre-unlink full SHA-256 checks now compare local bytes and decompressed NAS bytes to each other and the upload manifest immediately before each delete; the tombstone is re-hashed after rename. Added the same-size rewrite / restored-mtime idle-wait regression.
- **HIGH fixed:** recovery creates the original path with an exclusive hard link. A collision keeps the newly created source and moves the old tombstone to a distinct `.late-*` name with an alert. Added a concurrent recreation regression.
- **MEDIUM fixed:** archive deferred work returns 10; wrapper writes `.last_partial.archive` only for that outcome and does not write archive or aggregate success markers.
- **MEDIUM fixed:** wrapper bounds mount requests, probes, and retry sleeps under a three-hour retry window; mount command timeouts use no grace period inside that window. Added a short-window wall-clock stub test.
- **MEDIUM fixed:** rollout steps now require hourly uploader bootout, PID exit and flock release confirmation, then four-hourly tick-backup bootout and `.plist.disabled` rename before daily activation. `--max-files` is explicitly prohibited for the one-day pilot; `--only-day` is required.

Validation in this report predates F1–F9 follow-up fixes; current validation results are recorded below. No launchd operation, real archive deletion, commit, push, or deployment was performed.


## Follow-up fixes for independent review 3 (2026-11-05)

- **F1:** Deletion now hashes the tombstone through the same open descriptor and compares size, mtime_ns, ctime_ns, and inode from the hashed snapshot to the descriptor and tombstone path immediately before unlink. The remaining writer race is the final stat syscalls through unlink (normally milliseconds); userspace cannot make those syscalls atomic.
- **F2:** Truncated/corrupt gzip exceptions (`EOFError`, `zlib.error`, `gzip.BadGzipFile`) are handled within file/day processing. Local files remain; deletion tombstones are restored by `_safe_delete`; remaining UTC days continue. No traceback should escape. Generic transient OSError remains a failure and does not poison the manifest as invalid.
- **F3:** Once a day's deletion transaction begins, its per-file transactions finish safely even if the archive deadline passes. Remaining work is deferred and returns 10 when no operation failed; the wrapper hard timeout remains the outer bound.
- **F4:** A state/DB failure remains status 1 when archive returns 10. Per-step and aggregate success markers are cleared at run start. The old `--only no-tick` mode is removed.
- **F5:** Install instructions cover persistent hourly-job removal, filled plist linting, pilot-before-bootstrap order, explicit process/registration checks, environment reload via bootout/bootstrap, and rollback re-enable.
- **F6:** The documentation records the measured 88% volume use, estimated free space/backlog growth, and first-night pilot sequence.
- **F7:** A legacy upload without `upload_id` is adopted into a new manifest upload record when the existing gzip verifies against current local content; it is not duplicated.
- **F8:** Same-inode source/tombstone hardlinks self-heal by removing the extra link. Existing late tombstones are no longer renamed repeatedly, and recovery accepts chained legacy suffixes.
- **F9:** Timeout helpers normalize signal status 137 to 124.

Current verification results:

- Focused archive/wrapper suite: **81 passed**.
- Requested full suite: collection stopped with **7 unrelated equity module errors** because installed `pandas_ta`/Numba raised `RuntimeError: cannot cache function 'fibonacci': no locator available`.
- Remaining suite excluding those seven collection blockers and `test_docker_watchdog.py`: **180 passed**.
- `test_docker_watchdog.py` run separately: **12 passed**.
- `bash -n scripts/*.sh`: passed.
- Placeholder-filled daily plist `plutil -lint`: passed.

No launchd job, real NAS archive data, or production data was changed.

## Full-suite abort (exit 3) root cause and fix
`archive_to_nas.main()` armed the io-timeout watchdog and the hard-kill thread (os._exit(3) at deadline + grace) before several early returns (missing source, mount failure, deadline, preflight failure). Those returns skipped the `finally` that stops the watchers, so in-process tests leaked daemon threads that later called `os._exit(3)` and killed the pytest process mid-run (it surfaced during test_docker_watchdog.py because that test is slow). Production was unaffected (the process exits on return anyway). Fix: watcher shutdown is registered in a `cleanups` list run from the outermost `finally`. Regression test: `test_early_return_does_not_leak_hard_kill_watchers` (fails/aborts the run without the fix). Full suite now 208 passed.


## Review 4 remediation (2026-11-05)

- **N1 fixed:** Delete-stage day verification catches `BackupError`, `OSError`, `EOFError`, and `zlib.error`; the failed day is retained, logged, and later days continue. Regression coverage injects EOF at the pre-delete verification boundary.
- **N2 fixed:** Legacy adoption appends only during mutating runs. Dry-run and report tests seed a legacy manifest and compare all NAS files and state-directory existence before and after.
- **N3 fixed:** Before each file transaction, deletion estimates required hash time from source size and configured throttle, reserves a safety margin before `deadline + hard_kill_grace`, and passes that cutoff into `_safe_delete`. If the next file cannot fit, remaining day work is deferred with status 10. A started transaction writes `intent` before rename and restores its tombstone if hashing reaches the cutoff.
- **N4 fixed:** Rollout requires hourly bootout and process/lock confirmation, manual pilot before daily bootstrap, no `kickstart -k` on active runs, bootout/bootstrap to reload environment changes, hourly rollback `launchctl enable`, and notes that `launchctl disable` persists.
- **N5:** Normal first-run adoption of legacy uploads can append records to their NAS day manifests. Read-only modes leave those manifests untouched.
- **N6 fixed:** Removed the six-hour `--only no-tick` wrapper mode and the `no-tick` tick-backup dispatch mode. Crypto-paper state, DB, and bot state run once daily at 03:00 KST.
- **N7 fixed:** Crossing the archive deadline after the final day no longer fabricates one deferred day; status 10 is reserved for work that remains.

Current remediation test and lint results are recorded after the requested validation run below.


Validation results after review 4 changes:

- Focused archive and daily-wrapper tests: **86 passed**.
- Requested exact full-suite command: blocked during collection by 7 unrelated equity test imports; installed `pandas_ta`/Numba raises `RuntimeError: cannot cache function 'fibonacci': no locator available`.
- Full suite with `NUMBA_DISABLE_JIT=1`: **214 passed**.
- `bash -n scripts/*.sh`: passed.
- Placeholder-filled daily plist copy at `/private/tmp/daily-nas-backup-filled.plist`: `plutil -lint` passed. The scratch plist was removed after validation.

No launchd operation, real NAS write, real archive deletion, commit, push, or deployment was performed.
