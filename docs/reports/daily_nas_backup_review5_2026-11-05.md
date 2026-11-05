# Daily NAS backup - final delta review 5 (2026-11-05)

Review-only. No source, test, script, plist, launchd or NAS data was changed. Experiments used synthetic trees and stubs in the session scratchpad (`.../scratchpad/r5`: `e1.py` to `e4.py`, `model.py`, `real.py`, `realdry.py`, wrapper stubs in `w/`). Real-system actions were read-only: `--report` and `--dry-run` (with a scratch `--state-dir`) on the real tree, `launchctl list/print`, `ls`, `df`, reading `deleted.jsonl`. NAS file listing and local tree hashes were identical before and after the real dry-run.

## Verdict

**Safe to enable scheduled deletion (`DAILY_NAS_ENABLE_DELETE=1`) now: YES. No data-loss blocker found.** Every failure path I could provoke is fail-closed and self-recovering. The remaining items are doc and hygiene defects, plus operational expectations:

- Night 1 will almost certainly end as exit 10 (partial), not 0. See the runtime section.
- Night 1 is the first execution of the wrapper under launchd (`runs = 0`). Any launchd-only problem (TCC, PATH, docker socket) would show up as a failed night, not as data loss.

Pytest: `cd trading && /opt/anaconda3/bin/python3 -m pytest tests -q` gives **214 passed** (22 s).

## N1-N7 status

| # | Result | Evidence |
|---|---|---|
| N1 | **Fixed** | Line 838 is now `except (BackupError, OSError, EOFError, zlib.error)`. Experiment: corrupt the NAS gz of day 1 just before the delete-stage verify, using truncate, scattered bit-flip, garbage text and empty file. All four give rc 1, no traceback, day 1 untouched (2 files left, no tombstones), and day 2 is still processed and deleted. Recovery: the following night marks the bad copy `invalid` (rc 1 again), and the night after that re-uploads a versioned gz and deletes. That is 2 nights of exit 1, then clean. The failure is not recorded at the delete-stage catch itself, so it takes one more run to be flagged invalid. Acceptable. |
| N2 | **Mostly fixed, one residual** | Line 710: legacy adoption append is guarded by `not readonly`. A legacy-manifest fixture under `--dry-run` and `--report` leaves the whole tree (NAS, source, state) byte and mtime identical. Orphan tombstone plus dangling intent fixture: also no diff. **Residual:** a `--dry-run` that meets a NAS gz which fails verification still calls `mark_failure` (lines 747/758/763/766) and writes `state/failures/<hash>.json`, and creates the state directory. Reproduced with a truncated gz. Effect: a dry-run can put a backoff (60 s doubling to 6 h) on a file and delay the next real run for that file. `--report` is unaffected. Severity LOW. Fix: `if not readonly: mark_failure(...)`. |
| N3 | **Fixed** | Deletion loop (lines 842-865) computes `available = hard_kill_deadline - margin - now` against a per-file estimate and defers when it does not fit. `_safe_delete` receives `grace_end - margin` as its deadline. Experiments with `--max-minutes 0.5` and a monotonic offset: (a) offset pushed past the cut-off after the first delete: rc 10, 1 of 9 files deleted, no tombstone, audit 1 intent / 1 complete; (b) jump during the pre-delete hash of file 2 (before the intent): rc 10, same result; (c) jump during the post-rename tombstone hash: rc 10, source restored by `_safe_delete`, audit 2 intent / 1 complete, no tombstone; the next run writes an `abort` row and deletes normally (final 10 intent / 9 complete / 1 abort); (d) deadline passed but inside the grace window: the started day is finished (3/3) and the next day is not started, rc 10. In all cases the following run reaches rc 0 with local empty, and every file is either local and identical or recoverable from the NAS gz (data-loss check passed). |
| N4 | **Partly fixed, doc defects remain** | See "Doc defects". The installed state on this machine already went through the cutover (see "Real system state"), so these are doc-only. |
| N6 | **Done, state/DB backups did NOT disappear** | See next section. |
| N7 | **Fixed** | Deadline crossed during the very last file of the last day: rc 0, nothing left. The `remaining_days` guard at lines 873-878 only defers when days remain. |

## N6: what the daily job runs now

`scripts/daily_nas_backup.sh` has no modes. In order: mount (3 h absolute retry window), step 2 `with_timeout 7200 /bin/bash scripts/backup-tick-archive-to-nas.sh state-db-only`, step 3 `archive_to_nas.py ... --max-minutes 150`. The `state-db-only` case in `backup-tick-archive-to-nas.sh` calls `backup_crypto_paper_state`, `backup_db_dumps` and `backup_trading_state` (the three rotation containers). The script exits 2 for any other mode argument, so tick data cannot be touched by it.

Stub test of the real wrapper with the real tick script (stub `rsync`, `docker`, `mount`, python):
- All ok, `DAILY_NAS_ENABLE_DELETE=1`: invoked rsync `--checksum` on crypto-paper-state, rsync on `backups/`, `docker ps` and `docker cp` plus staged rsync for momentum/kr/us rotation, then the archive with `--enable-delete`. rc 0, markers `last_success`, `.archive`, `.state-db`.
- Default env: archive gets `--no-delete`.
- DB rsync fails, archive ok: rc 1, only `.archive` marker (no `.state-db`, no aggregate); the archive step still runs after a state failure.
- State fails and archive 10: rc 1 (failure dominates), `last_partial.archive` only.
- State ok and archive 10: rc 10, `last_partial.archive` and `.state-db`.
- Archive 1: rc 1, `.state-db` marker only.
- Mode argument (`--only no-tick`): rc 2. The previous `no-tick` mode is gone. Cadence of the state/DB backup drops from every 4 h to once a day (documented).
- Real run evidence: `~/Library/Logs/tick-archive-backup.log` shows the old 4-hourly job completing db + all three bot states at 12:00 today, so the commands work against the real NAS. There was one Docker-daemon-down failure at 08:24 (kr-rotation `docker cp`). With the new wrapper that makes the night rc 1 but does not stop the archive step.

Minor: the mode-argument check runs after the lock is taken and after the success markers are cleared (line 52), so an accidental `daily_nas_backup.sh foo` clears yesterday's markers and holds the lock briefly.

## Test hygiene finding

`trading/tests/test_daily_nas_backup.py` line 92 (`test_wrapper_rejects_modes_and_backup_script_rejects_legacy_modes`) runs the real wrapper without `STATE_DIR` and `DAILY_BACKUP_LOG` overrides. Each pytest run therefore appends to the real `~/Library/Logs/daily_nas_backup.log` (entries at 12:52, 12:53, 13:03 exist), takes the real wrapper lock and deletes the real `daily_nas_backup.last_success*` markers. It is harmless to data, but it can wipe the monitoring markers and would exit 2 (and still pass) if the real nightly run held the lock. Add the two env vars to that test, and ideally check arguments before the lock and marker clearing.

## Doc defects (`trading/docs/archive_to_nas_install.md`)

1. Step 5 and the status table still mention `daily_nas_backup.last_success.no-tick` and "no-tick failure dominates". The real marker is `.state-db`.
2. Step 2 still ends with "Only then bootstrap the staged daily job" before the step 3 pilot, and the appended section still shows `launchctl kickstart -k`. A kickstart starts a long upload-only run that holds the archive flock (pilot would exit 2) and `-k` kills a running instance. Order should be: cutover, pilot, then bootstrap; kickstart without `-k`, or not at all.
3. Step 4 says "restart that user LaunchAgent". Changing `EnvironmentVariables` only takes effect after `launchctl bootout gui/$(id -u)/com.ochestration.daily-nas-backup` followed by `bootstrap`; `kickstart` does not re-read the plist.
4. Rollback lacks `launchctl enable gui/$(id -u)/com.ochestration.archive-to-nas` (the hourly label was disabled).
5. The `--dry-run` read-only claim should note the failure-backoff write, or fix N2 residual.

## Real system state (read-only)

- `com.ochestration.daily-nas-backup` is already bootstrapped: schedule 03:00, `DAILY_NAS_ENABLE_DELETE=0`, `runs = 0`, never executed. The hourly archive job (`.plist.disabled`) and the 4-hourly `com.orchestration.tick-backup` (`.plist.disabled`) are already off. No archive process is running now.
- The supervised pilot already happened: `deleted.jsonl` on the NAS holds 63 paths, each with exactly one `intent` then one `complete` (UTC day 2026-10-18, 2.0 GB). No orphan tombstones, no dangling intents (`--report`).
- To enable: edit the plist value to `1`, then `launchctl bootout` and `launchctl bootstrap` the job (not `kickstart`).

## First unattended run: what would happen (03:00 KST Nov 6 = 18:00 UTC Nov 5)

I ran `--report` and `--dry-run` on the real tree with `now` forced to 2026-11-05T18:00Z and the wrapper's flags (`--keep-days 1 --close-margin-hours 6`).

- Eligible hours exist for UTC days 2026-10-19 to 2026-11-04 (plus the already-closed morning hours of 11-05; day 11-05 is not deletable). 1332 local candidate files, 44.26 GB. 80 files (2.9 GB, all on 10-19 and 8 on 10-20) are already uploaded and verified on the NAS; 1252 files would be uploaded (dry-run: `PLAN upload` x1252, `verified=80`, `failed=0`, no adoption, no mismatch, no orphans, no dangling intents).
- Keep-days boundary: deletion needs `day < current_date - 1 = 2026-11-04`. So **deleted: the 16 UTC days 2026-10-19 through 2026-11-03** (41.0 GB, 1,259 files). **Retained locally: 2026-11-04 (3.25 GB, uploaded but not deleted) and 2026-11-05.** The newest eligible day for upload is 11-04, matching the doc example.
- Not covered by the archive at all: day-level files such as `2026/10/19/kr.jsonl` (90 MB) and `opening-scan-kr.jsonl` (64 MB). The hour-glob scan skips them, so they are neither uploaded nor deleted and the day directory never empties. Safe (nothing removed) but they are not backed up by this job.
- Disk: used 365 GiB of 460 (88%), 53 GiB free. Deleting about 38 GB in night 1 frees roughly 35 GiB, so about 72% used and about 88 GiB free. NAS has 522 GB free; the gz needs about 10 GB; the space preflight (`free >= pending * 0.25 * 2`) passes.
- Runtime model: with deletion on, a fresh file is read seven times at the 30 MB/s throttle (pre-hash, gzip copy, per-file verify, day verify, delete-stage verify, pre-delete hash, tombstone hash); NAS decompress passes are not throttled. Already-uploaded files need five throttled passes, and the keep-day (no-delete) days four. The model matches the pilot: 2.0 GB took about 440 s measured (4.6 MB/s effective) against 4.5 MB/s predicted. Cumulative estimate for the real backlog is about 151 min to finish deleting through 11-03 and about 158 min including the 11-04 upload, before SMB overhead and idle waits. That is **right at the 150 min budget, so expect night 1 to end with exit 10 and the last one to three days (and 11-04) deferred**; night 2 finishes (about 20 to 30 min of work) and is the first clean exit 0. Oldest days go first, so the most data is freed early. The wrapper reports partial: `last_partial.archive` marker, status 10, no failure.
- If the run exceeds 150 min: at the budget the uploader stops starting files and days. A day whose deletion already started finishes its remaining files only while `deadline + 300 s - 60 s` can cover the next file (estimate 30 s plus 3x size at the throttle), otherwise it defers cleanly (verified above). It then returns 10. Worst case a stuck I/O trips the 300 s watchdog or the hard kill at +300 s (exit 3, wrapper status 1 with an ALERT line); the wrapper timeout is 9300 s, the same instant, so either one wins. These are fail-closed: an interrupted rename leaves a tombstone and an `intent`, which the next run restores or reconciles (tested earlier, review 4 E4, and (c) above). Nothing is lost, and the cost is one red night.
- Other things to know: `os.nice` and `LowPriorityIO` keep it gentle; the Mac must be awake and the SMB mount must survive 2.5 h (sleep loses the mount, the run then exits 2, no data effect; note `time.monotonic` on macOS does not advance during sleep, so the budget can stretch). Docker being down fails the state step (rc 1) but never blocks the archive.

## Remaining risks and recommendations (none blocks)

| Sev | Item |
|---|---|
| LOW | N2 residual: guard `mark_failure` with `not readonly`. |
| LOW | Test writes to real state/log and clears real markers (line 92). |
| LOW | Doc defects 1-5 above (stale `no-tick` marker names, kickstart -k, re-bootstrap needed for env change, rollback `launchctl enable`). |
| LOW | Corrupt NAS copy takes two nights of exit 1 to self-heal. |
| INFO | The wrapper has never run under launchd. If you want to remove that uncertainty before deletion, run the first night with `0` (about 94 min upload-only) and flip to `1` on the next day; disk headroom (53 GiB, growth 2-4 GB/day) allows it. Otherwise enabling now is equally safe from a data standpoint. |
| INFO | Day-level files (`kr.jsonl`, `opening-scan-kr.jsonl`) are outside this archive's scope. |
