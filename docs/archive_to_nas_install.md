# Daily tick archive backup

The daily wrapper starts at 03:00 KST and retries an unavailable NAS inside an absolute three-hour wall-clock window. The deadline includes `mount` probes, `open` mount requests, probe sleeps, and ten-minute retry sleeps; mount commands are killed at their remaining deadline without an added termination grace period. The archive tree uses UTC folders (`YYYY/MM/DD/HH`), so 03:00 KST is 18:00 UTC on the previous UTC date. Eligibility requires the UTC day to have ended plus `--close-margin-hours` (default 6). The run processes each eligible local day oldest first: upload and verify the day, rescan and verify completeness, then delete that day's files only when explicitly enabled. The 150-minute archive budget defers remaining work with exit status 10; status 10 means partial/deferred with no operation failure. Exit 1 means a failure, and exit 0 means the selected work completed.

Example: a run at 2026-11-06 03:00 KST is 2026-11-05 18:00 UTC. UTC day 2026-11-04 ended at 2026-11-05 00:00 UTC, and its six-hour margin ended at 06:00 UTC, so 2026-11-04 is the newest eligible day. UTC day 2026-11-05 has not ended and is not eligible. `--report` lists the selected UTC days and hour buckets explicitly. The UTC current day and previous UTC day are retained locally by `--keep-days 1`.

## Per-day safety barrier

For each eligible UTC day, the uploader uploads and verifies its files, then rescans the local day to include files created during upload. It requires matching local file counts and byte totals, a matching current local SHA-256 and size for every verified NAS gzip, and no `.part`, `.deleting-*`, or `.late-*` artifacts. Immediately before each source rename and again on the tombstoned file after rename, it freshly hashes full local content and decompressed NAS gzip and compares both to the upload manifest. Metadata checks remain an additional guard. A successful day writes `day_complete` with day, count, bytes, and sorted SHA-256-list digest to the NAS day manifest and local state directory. Any failure retains local data, emits an `ALERT` line, and exits nonzero. Tombstone recovery uses exclusive hard-link creation; if the source path reappears, the new source is preserved and the tombstone remains under a unique `.late-*` name with an alert.

Deletion requires `--enable-delete`; `--no-delete` overrides it. The wrapper and plist default to no deletion. To deliberately enable scheduled deletion, set `DAILY_NAS_ENABLE_DELETE=1` in the installed LaunchAgent `EnvironmentVariables` and restart that one user job. For a deliberate manual run, use `DAILY_NAS_ENABLE_DELETE=1 /bin/bash scripts/daily_nas_backup.sh`. Immediately before deletion, the run re-hashes local and decompressed NAS data, waits once per day (wrapper value 5 seconds), and stat-checks the whole delete set. Deletion uses per-file tombstone renames and NAS intent/completion audit records; future runs reconcile incomplete intents by restoring local data or verifying the NAS copy. `--only-day YYYY-MM-DD` and `--max-files N` remain available. `--max-files` caps candidate processing only: if the rest of the selected day already has valid uploads, the completeness barrier can still delete the entire day. The manual trial must use `--only-day` and must not use `--max-files`. `--dry-run` and `--report` remain read-only.

This replaces the previously reviewed model of a 24-hour grace interval across separate runs plus seven-day local retention. The new model uses a fresh full-day rescan and immediate same-run hash verification, while retaining only today and yesterday fully local. This makes completion dependent on one run's fresh evidence instead of persisted grace observations. The tombstone is opened once and hashed through that descriptor. Size, mtime_ns, ctime_ns, and inode are checked against the hashed snapshot using both descriptor fstat and tombstone path stat immediately before unlink. An already-open writer can still write after the last metadata comparison and before unlink; this residual interval spans only the final stat calls and unlink syscall, normally milliseconds, and userspace cannot make them atomic. The six-hour close margin and post-upload rescan reduce the likelihood. If the source filesystem rejects hard links during tombstone recovery, recovery fails closed and leaves the tombstone for operator recovery. Keep hang protections intact: lock before NAS work, process deadline, hard-kill watchdog, I/O heartbeat, and status output.

## Rollout

1. Stage the daily plist with deletion disabled. Fill `__REPO__` and `__HOME__`; preserve `DAILY_NAS_ENABLE_DELETE=0`. Validate the filled plist with `plutil -lint` and run one `--report` invocation. Do not bootstrap the daily job yet.
2. Cut over in order. First unload the hourly uploader: `launchctl bootout gui/$(id -u)/com.ochestration.archive-to-nas`, then rename its installed plist to `.plist.disabled` and run `launchctl disable gui/$(id -u)/com.ochestration.archive-to-nas` so the removal persists across login/reboot. Confirm exit with `pgrep -af '[a]rchive_to_nas.py'`; then verify the lock is free with `/opt/anaconda3/bin/python3 -c 'import fcntl,pathlib; p=pathlib.Path.home()/"Library/Application Support/ochestration-archive/archive_to_nas.lock"; f=p.open("a+"); fcntl.flock(f,fcntl.LOCK_EX|fcntl.LOCK_NB); print("archive flock released")'`. Do not continue until the old PID is gone and the flock check succeeds. Then disable the four-hourly job: `launchctl bootout gui/$(id -u)/com.orchestration.tick-backup`; rename its installed file with `mv ~/Library/LaunchAgents/com.orchestration.tick-backup.plist ~/Library/LaunchAgents/com.orchestration.tick-backup.plist.disabled`; confirm the enabled `.plist` is absent and `.plist.disabled` exists. This intentionally reduces DB and bot-state backups from every four hours to once daily at 03:00. Keep weekly `com.orchestration.tick-archive-weekly` disabled. Only then bootstrap the staged daily job.
3. Run a complete deletion pilot against one old eligible UTC day: `/opt/anaconda3/bin/python3 /Users/user/Desktop/CODE/Ochestration/trading/scripts/archive_to_nas.py --enable-delete --only-day <oldest-eligible-UTC-day> --idle-seconds 5 --max-minutes 150 --throttle-mbps 30 --keep-days 1`. Do not pass `--max-files`: it can still lead to deletion of the entire complete day. `--only-day` is mandatory for the trial. Compare NAS gzip decompressed hashes with a local pre-run copy; inspect the NAS day manifest, local day-complete record, paired `deleted.jsonl` intent/completion records, and confirm only that selected local day is empty.
4. Enable scheduled deletion only after the pilot: set `DAILY_NAS_ENABLE_DELETE=1` in the installed plist and restart that user LaunchAgent. Set it to `0` or remove it to restore upload-only operation. The direct command is `DAILY_NAS_ENABLE_DELETE=1 /bin/bash scripts/daily_nas_backup.sh`.
5. Confirm separate `daily_nas_backup.last_success.no-tick` and `.archive` markers, then aggregate `daily_nas_backup.last_success`, start/end logs, and no unresolved alerts. Archive and aggregate success markers are written only for complete exit-0 runs. Exit 10 writes `daily_nas_backup.last_partial.archive`, returns wrapper status 10, and writes no archive or aggregate success marker; it means healthy but deferred work. Exit 1 or 2 means failure. Mount retries every ten minutes inside the absolute three-hour deadline.

The wrapper paths and binaries can be overridden with `PROJECT_ROOT`, `PYTHON_BIN`, `PERL_BIN`, `OPEN_BIN`, `MOUNT_POINT`, `STATE_DIR`, `DAILY_BACKUP_LOG`, `TICK_BACKUP_SCRIPT`, and `ARCHIVE_SCRIPT`. NAS server/user/share settings can be overridden with `NAS_SERVER`, `NAS_FALLBACK_HOST`, `NAS_USER`, and `NAS_SHARE`, and are passed to the archive process. The helper uses `open -g -j` and polls the mount; it never creates a directory under `/Volumes`. Timeouts use a dedicated process group so child processes are terminated with the timed-out command.

## Rollback

Stop the daily LaunchAgent, inspect the wrapper log and both deletion audit streams, and confirm local data remains for any incomplete day. Restore the prior schedules only after checking they will not overlap the daily uploader; old jobs are user-managed and are not edited by this rollout. Keep `--enable-delete` out of any ad hoc rollback invocation unless deletion is deliberately intended. The daily wrapper lock and state records are under `~/Library/Application Support/ochestration-archive`.


## Corrected staging, status, and cadence notes (2026-11-05)

Stage the filled plist at an absolute path from any current working directory, then lint it before launchd activation:

```bash
REPO="/Users/user/Desktop/CODE/Ochestration"
HOME_DIR="$HOME"
sed -e "s|__REPO__|$REPO|g" -e "s|__HOME__|$HOME_DIR|g" "$REPO/trading/docs/launchd/com.ochestration.daily-nas-backup.plist.template" > "$HOME_DIR/Library/LaunchAgents/com.ochestration.daily-nas-backup.plist"
plutil -lint "$HOME_DIR/Library/LaunchAgents/com.ochestration.daily-nas-backup.plist"
```

After the old jobs are stopped and the hourly plist is renamed `.disabled`, bootstrap, kickstart, and inspect the daily job:

```bash
launchctl bootstrap gui/$(id -u) "$HOME/Library/LaunchAgents/com.ochestration.daily-nas-backup.plist"
launchctl kickstart -k gui/$(id -u)/com.ochestration.daily-nas-backup
launchctl print gui/$(id -u)/com.ochestration.daily-nas-backup
```

State/DB backups (crypto-paper state, DB dumps, bot state) run once daily at 03:00 KST inside the wrapper. There is no `--only no-tick` wrapper mode and no six-hour schedule; the wrapper rejects mode arguments (exit 2).
Final status table:

| Layer | Code | Meaning |
|---|---:|---|
| Python archive | 0 | selected work complete |
| Python archive | 1 | file/day failure |
| Python archive | 2 | setup, mount, lock, space, or invalid day failure |
| Python archive | 3 | I/O watchdog or hard kill |
| Python archive | 10 | deadline deferred work with no operation failure |
| Wrapper | 0 | all enabled steps complete |
| Wrapper | 1 | any step failed; no-tick failure dominates archive deferral |
| Wrapper | 2 | lock unavailable or invalid mode |
| Wrapper | 10 | archive deferred, with no earlier step failure |

Each run clears old success markers before work starts. Exit 10 writes the archive partial marker only. Signal-derived helper status 137 is normalized to timeout status 124.

Disk pressure is time-sensitive: the measured data volume was 88% used, with roughly 51 GB free and a backlog growing 2–4 GB/day. Do not leave deletion disabled for long. First-night sequence: fill and lint the plist, inspect `--report`, run one supervised deletion pilot with the absolute-path `--only-day` command, verify hashes and paired audit rows, then enable scheduled deletion only after that pilot is clean. Repeated upload-only runs increase local disk pressure.
