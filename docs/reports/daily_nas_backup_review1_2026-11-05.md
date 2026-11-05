# Daily NAS backup design - independent review 1 (2026-11-05)

Scope: `trading/scripts/archive_to_nas.py`, `scripts/backup-tick-archive-to-nas.sh` (diff vs HEAD reviewed), `scripts/daily_nas_backup.sh`, `trading/docs/launchd/com.ochestration.daily-nas-backup.plist.template`, both test files, install doc and design report. Review only; no source, launchd, container or NAS change was made.

## Evidence gathered

- `pytest tests -q` (from `trading/`): 173 passed. `bash -n` OK on both shell scripts. `plutil -lint` OK on a filled copy of the plist (scratchpad).
- `--dry-run --report` and `--dry-run --max-files 3` on the real tree: exit 0; before/after `find -ls` of closed tick days, state dir and NAS manifests showed no change from my runs. The only diff was one `state/grace/*.json` written by the live old hourly job (see F-10), not by the dry run (readonly path never writes).
- Report at 2026-11-04 23:59 UTC: 1322 local pending files / 43.0 GB, 84 uploaded, 83 verified, eligible UTC days 2026-10-18..2026-11-03, NAS free 522 GB. Typical day = 65-87 files, 2-3 GB.
- Perl alarm experiments (scratchpad): `perl -e 'alarm shift; exec @ARGV' 2 sleep 20` exits 142 after 2 s (alarm survives exec, so the alarmed process IS the target; docker cp/rsync/gzip are killed directly). `alarm` applied to `bash script` kills only bash; its background child (`sleep 30`) survived (orphaned). If SIGALRM is inherited as ignored, no timeout occurs (rc 0 after full run).
- Live state: launchd currently has `com.ochestration.archive-to-nas` (hourly, `--no-delete`, pid 11121 still running since 00:35, old code, holds the flock), `com.orchestration.tick-archive-weekly` (`tick-only`, RunAtLoad) and `com.orchestration.tick-backup` (`state-db-only`, 6x/day, RunAtLoad) all loaded.
- `~/Library/Logs/tick-archive-backup.log` 08:24:46-47: with Docker daemon down, `[trading-state] ... 컨테이너 안 떠있음 - 건너뜀` (see F-4).
- `trading/scripts/` (archive_to_nas.py) and both new test files are untracked: `git log -- trading/scripts` is empty. The script that the plist references has never been committed.

## Closed-day / margin math (checked against code)

Rule: hour dir day D is scanned only if `D+1 00:00Z + 6h <= now` (`_scan`, py:109-110); delete only if `D < now.date - keep_days` (py:674). Hour dirs are named by the record `ts` (UTC, `now_iso()` in tick_state/crypto_tick_state; `append_batches` appends via open/write/fsync/close per batch, no long-lived fds), so late-flushed records land in the old hour dir either as an append to an existing file or a brand-new file.

- Run 2026-11-06 03:00 KST = 2026-11-05 18:00 UTC: eligible (upload + verify + day_complete) = all D <= 2026-11-04 (11-04 closes 06:00Z 11-05). 11-05 not eligible. Deletable = D < 11-04 i.e. D <= 11-03. So 11-04 is uploaded that night but deleted on the 11-07 03:00 KST run (it is "yesterday"). This matches "keep today+yesterday" but NOT the intent sentence "delete that day in the same run" for the newest closed day; harmless, just document it. The 6h margin is irrelevant to deletion at keep-days 1 (delete age is always >= 24h); it only gates uploads.
- Catch-up at 00:30Z 11-06 (09:30 KST wake): eligible D <= 11-04 (11-05 closes 06:00Z 11-06); deletable D < 11-05 i.e. D <= 11-04, age >= 24.5h. Fine.
- KST has no DST; `now` is `datetime.now(utc)`; no KST arithmetic exists in the python path. Edge 00:00:01Z: deletes only days ended >= 24h earlier. No off-by-one found; `test_keep_days_retains_yesterday` covers it.
- Backlog (10-18..11-03) on the first run: all eligible and all deletable simultaneously (see F-3 for why this will not drain smoothly).
- Late record into an already deleted hour: writer recreates path, next scan sees a new file, `old` upload exists with different size/mtime so it is uploaded as versioned `name.<hash8>.gz`, verified, then deleted. No loss. Late record into a day currently being processed: re-scan finds an un-uploaded file -> day_ok False, day retained, ALERT, exit 1 (safe; noisy).

## Deletion safety walk-through (python)

Per file, in order: barrier rescan of the day (py:647) -> latest upload record must match current size+mtime_ns (654) -> full `_verify` (gz sha/size, decompressed sha, fresh local sha, stat before/after, 326) -> no `.part/.deleting/.late` artifacts (659-667) -> only then, per file: stat equals barrier stat, a second full `_verify` (678), idle sleep, third stat compare (681-683) -> `_safe_delete`: mount identity check, stat equals upload record incl. inode, NAS intent audit (fsync), rename to tombstone, stat tombstone, mount check, unlink, completion audit. Deletion is strictly per verified file (never directory-wide); files not matched by the `*.jsonl` glob, symlinks, and files newer than the scan are never touched. `day_complete` records (NAS manifest and state/day-complete-*.json) are write-only: nothing reads them, so a forged/stale record cannot authorize deletion. Versioned copies: `_latest_upload` is "last upload record for path" and `_verify` checks that exact record's `remote_name` against the current local bytes, so an older version cannot satisfy a newer file. I found no path that deletes without a fresh same-run hash match of the local bytes to a decompressed NAS gzip. Residual (accepted) windows: NAS gz is not re-hashed after the idle sleep (<= idle_seconds + rename, F-L7); an append between the last stat and `tomb.stat()` is detected and restored, an append between `tomb.stat()` and `unlink` through an fd opened before the rename would be lost (microseconds; writer reopens per batch and these files are >= 24h old).

## Findings

### CRITICAL

**F-1 (latent but currently ACTIVE) Legacy `all` / `tick-only` mode still deletes tick days with `rm -rf`, and is the default.** `scripts/backup-tick-archive-to-nas.sh:27` (`BACKUP_MODE="${1:-all}"`), `:83` (`day < today_utc`, zero margin), `:91-109` (file list enumerated once, hash compared once), `:112` (`rm -rf "$day_dir"`), `:121` (`find ... -empty -delete`). Scenario: weekly job (`tick-only`, `RunAtLoad`, currently loaded) fires at login/bootstrap at e.g. 00:05Z; UTC-yesterday's hour 23 (and any ts-late record, any file created after `find` listed it, any append after the per-file hash) is removed by `rm -rf` of the whole date dir after only the pre-listed files matched. It has no same-run rescan, no idle check, no tombstone, no audit, and it will also race the new uploader. Per the task it is "no longer used by enabled jobs" - that is FALSE today: `launchctl list` shows tick-archive-weekly (tick-only) and tick-backup (state-db-only; harmless) loaded, both RunAtLoad. Fix: (1) `launchctl bootout` + move away the plists before installing the daily job; (2) in the script, remove `backup_tick_archive` and the `all`/`tick-only` modes, or require explicit `ALLOW_LEGACY_TICK_DELETE=1` and make a missing arg an error (`${1:?mode required}`) instead of `all`; (3) add a test asserting `all`/`tick-only` refuse without the override.

### HIGH

**F-2 Wrapper cannot run in no-delete mode; the plist therefore enables deletion on the first run.** `scripts/daily_nas_backup.sh:63` hard-codes `--enable-delete`; no env/arg switch; the plist has no EnvironmentVariables. Installing the template = deletion enabled at the next 03:00. Fix: read `DAILY_NAS_DELETE=${DAILY_NAS_DELETE:-0}`, add `--enable-delete` only when `1` (default safe), or add `--no-delete` by default; test that the argv passed to the archive script contains/omits the flag (the current wrapper test uses `/bin/sh` as PYTHON_BIN and never inspects args).

**F-3 Pipeline shape: all-days upload, then all-days barrier; backlog will not drain and fails red every night; serial per-file 30 s idle.** `archive_to_nas.py:572` (single loop over every candidate day), `:645-646` barrier only after the loop, `:680` `time.sleep(idle_seconds)` per file (default 30; wrapper passes none), `:678` `_verify` unguarded. Numbers: 1322 files => 11 h of pure sleep for the backlog; steady state 65-87 files/day => 33-44 min of sleep per day, inside the 150-min budget that also covers 3 throttled local passes per upload (pre-hash, copy, verify), 1 barrier pass and 1 pre-delete pass at 30 MB/s (43 GB ~ 72 min upload passes + 24 + 24 min). If the upload loop hits the deadline (likely for several nights with a 43 GB backlog on an SMB share that did ~1 file/10 s at 10 MB/s), the barrier runs with an expired deadline: every `_verify` raises TimeoutError -> caught at :658 -> every day logs "ALERT day completion/deletion failed", exit 1, no space freed. Once uploads finish, deletion hits the deadline mid-day and the uncaught TimeoutError at :678 aborts main with a traceback (exit 1, no summary; no data loss, per-file deletion). It diverges from the stated intent (per day: upload+verify, check, delete, next day). Fix: restructure as `for day in days_oldest_first: upload day; barrier; delete day`; do one idle sleep per day (sleep once, then stat-compare every file) instead of per file; catch TimeoutError around :678 and stop cleanly with exit 0/1 and a summary; treat "deadline reached with work remaining" as a distinct non-alert status.

**F-4 Docker daemon down / `docker ps` failure is reported as success.** `backup-tick-archive-to-nas.sh:164-167`: `if ! with_timeout 300 docker ps | grep -qx ...; then log "컨테이너 안 떠있음 - 건너뜀"; continue` - a failing/timed-out `docker ps` is indistinguishable from "container not running" and leaves `ok=0`. Real evidence in `tick-archive-backup.log` 2026-11-05 08:24:47 during the Docker outage. The wrapper then writes `daily_nas_backup.last_success` although no bot state (trade_log/entry_log) was backed up. Fix: capture `ps` output separately (`names=$(with_timeout 60 docker ps ...) || { log ...; ok=1; continue; }`) then `grep -qx` on the variable; a missing container that is expected should also set `ok=1`.

**F-5 Stale wrapper lock is never recovered (permanent self-disable after a crash/power loss/reboot).** `daily_nas_backup.sh:25-36`: lock is `mkdir` dir removed by an EXIT trap; after SIGKILL, reboot, power loss, or perl-alarm SIGALRM (no trap path), the directory stays; if the recorded pid is dead the script still logs "prior daily wrapper still holds lock" and `exit 2` forever. Result: no backups, no deletions (local disk fills; 44 GB today), only a log line. Python has a proper flock that already makes concurrent runs safe, so wrapper takeover is safe. Fix: if pid is not alive (or `ps -p` command is not this wrapper) remove the lock dir and retry mkdir once; or use `flock`-style lock via `/usr/bin/lockf`/python; emit a notification on repeated lock failures.

### MEDIUM

**F-6 Dangling deletion intents make every future run exit 1 (and block success marker).** `archive_to_nas.py:353` writes the `intent` before the rename; restore paths (:357-367, :371-378) and mount-check/rename failures never write an "abort" phase. Intents are keyed `(path, upload_id)` (:526); if the file is later re-uploaded (new upload_id) the old key stays incomplete forever -> `failures=1` at :555 and ERROR "deletion intent has no completion record" every night. Same for `.deleting-*`/`.late-*` orphans in the local tree (:520-522): permanent exit 1 until a human cleans up. Fix: write `phase=abort` on every restore/failure path after the intent and treat it as resolved; ignore intents whose path no longer exists locally and whose NAS gz verifies.

**F-7 No retry when the NAS is offline at 03:00, and misleading doc about catch-up.** `daily_nas_backup.sh:42-52,53-57`: 2 hosts x (<=90 s open + 60 s poll) ~ 5 min then FAILURE; launchd `StartCalendarInterval` fires once per day (plus once on wake if the Mac slept through 03:00). Replacing the 4-hourly job (6 chances/day for DB dumps and bot state) with one chance/day raises the worst-case bot-state gap to 24-48 h. Fix: add a second/third start (e.g. 03:00, 09:00, 15:00) with an "already succeeded for this UTC date and nothing pending" guard from `last_success`, or a StartInterval of 1-2 h with that guard; send a notification on N consecutive failures.

**F-8 Install doc pilot step cannot exercise deletion.** `archive_to_nas_install.md` step 3 and the report: `--enable-delete --only-day <day> --max-files N`. The doc itself says a `--max-files` capped run cannot pass the day barrier, so the trial never deletes and verdict (b) would be based on nothing. Fix: pilot with `--only-day <oldest> --enable-delete --idle-seconds 5` (no `--max-files`; ~65 files, ~15 min) and a documented manual inspection list (NAS gz sha vs local backup copy, manifest, audit, local dir empty).

**F-9 Timeouts do not cover grandchildren; `mkdir`/`mv` on NAS have no timeout.** `daily_nas_backup.sh:60,63` and tick script: `with_timeout 7200 /bin/bash ...` kills bash only (proven: orphaned child survived); rsync forks receiver/generator and SIGALRM to the parent leaves them. Individual docker/rsync/gzip calls are exec'd directly so those are bounded. Not bounded: `mkdir -p "$dest"` (:72,132,147,171) after a mount check taken up to hours earlier. On a hung SMB mount these block in the kernel; the outer alarm cannot help. launchd (no `AbandonProcessGroup`) does clean up the process group when the job exits. Fix: re-run the mounted check immediately before each stage, wrap `mkdir -p` with `with_timeout 30`, and use `perl -e 'setpgrp; ...'`/kill process-group in the helper, or `trap` + `kill -- -$$`.

**F-10 Live conflict with the old hourly job.** pid 11121 (old code, no hard deadline, 8 h elapsed) holds `archive_to_nas.lock`; a daily run during that time exits 2 on lock contention (py:459-466) and the wrapper marks FAILURE. Not a loss risk. Fix: bootout the hourly job before first daily run and verify `lsof`/pid gone; remove the stale `state/grace/` directory later.

**F-11 State/DB backup can replace a good NAS copy with a torn one.** `backup-tick-archive-to-nas.sh:170-172`: `docker cp` of a running container's `/app/data/.` (non-atomic, e.g. mid state-JSON write during the 09:41 UTC rebalance) followed by `rsync -a` with no `--backup`/dated copy overwrites the previous good NAS file. Fix: validate JSON (`python -m json.tool`) before rsync, or `rsync --backup --backup-dir=.../YYYYMMDD`, or keep one dated snapshot per day.

**F-12 All-or-nothing `last_success`, no external alert.** `daily_nas_backup.sh:68-72`: a benign python exit 1 (late-file ALERT, backlog, F-6) hides that DB/state backup succeeded, and nothing pushes the failure anywhere except a log. Fix: separate markers (`last_success.nostate`, `last_success.archive`), exit-code mapping (2 lock contention vs 1 partial), and a notification hook.

**F-13 Untracked artefacts.** `trading/scripts/archive_to_nas.py`, both tests, the plist templates and the new wrapper are untracked; the shell script has uncommitted behaviour changes (SMB defaults guest->88motorcycle, noroot->noroot.local, `mount_smbfs`+`mkdir` -> `open -g -j`, `no-tick`, timeouts). Commit before the plist is installed so the code launchd runs is reviewable/rollbackable. The removal of `mkdir -p "$MOUNT_POINT"` is correct (the log shows it failing with Permission denied on /Volumes, i.e. /Volumes is not writable by the user, so the old trap could not trigger anyway).

### LOW

- **L-1** `archive_to_nas.py:659`: `src.with_name(src.name + ".deleting-*")` is a literal path, never matches; redundant with the rglob at :664 but misleading.
- **L-2** `:517` `datetime.strptime(args.only_day)` ValueError uncaught (traceback instead of exit 2).
- **L-3** Wrapper log `daily_nas_backup.log` and `tick-archive-backup.log` grow unbounded; no rotation.
- **L-4** Tick script `:164` `... | grep -qx` under `pipefail`: grep exits early and docker may get SIGPIPE -> pipeline failure -> false "not running" (small output makes it rare). Fixed by F-4 change.
- **L-5** Wrapper passes none of `NAS_*`/`MOUNT_POINT` overrides to the python script (`--mount/--dest/--nas-*`); overriding env in the wrapper silently mismatches.
- **L-6** Under launchd, `~/Desktop` is TCC-protected; `/bin/bash` and anaconda python need file access. The existing agents already read this tree, but do `launchctl kickstart` of the new agent once with `--report` before relying on 03:00.
- **L-7** NAS gz not re-hashed after the idle sleep; window = idle seconds. Acceptable; could re-check size+mtime of the gz.
- **L-8** Wrapper has no `caffeinate`; the host currently has Amphetamine/caffeinate assertions, so a mid-run sleep (SMB drop) is unlikely but not guaranteed. Suggest `/usr/bin/caffeinate -i` around steps 2-3.
- **L-9** No `EnvironmentVariables.PATH` in the plist; acceptable because wrapper uses absolute perl/python/mount/date and the tick script exports `/opt/homebrew/bin` (docker is `/opt/homebrew/bin/docker`); python invokes `open` from `/usr/bin`. Note for future: do not call homebrew tools from the wrapper itself.

## Inventory of every delete (rm / find -delete / unlink / rmdir) and why it is safe

| Location | Target | Safe? |
|---|---|---|
| `daily_nas_backup.sh:38` `rm -rf "$lock"` | `"$STATE_DIR/daily_nas_backup.lock"`; STATE_DIR defaults to `$HOME/Library/Application Support/ochestration-archive` (set -u guards HOME; trap is registered only after this process created the dir, so it never removes another run's lock). | Yes |
| `backup-tick-archive-to-nas.sh:99` `rm -f "$tmp_file"` | `${dest_file}.tmp.$$` partial gz, legacy mode only | Yes |
| `:112` `rm -rf "$day_dir"` | local tick date dir under `$SRC_TICK_DIR` found by `find -mindepth 3 -maxdepth 3` - legacy `all`/`tick-only` only | UNSAFE semantics (F-1) |
| `:121` `find "$SRC_TICK_DIR" -mindepth 1 -type d -empty -delete` | any empty dir in tick root (can remove empty current hour dirs; writer re-creates) - legacy only | Low risk, legacy |
| `:183` `rm -rf "$staging"` | `mktemp -d` dir; script exits on mktemp failure under `set -e` | Yes (leak on SIGKILL only) |
| py `_safe_delete` `tomb.unlink()` (:369) | per-file tombstone of a verified file | Yes (analysis above) |
| py `_prune_empty_dirs` `rmdir` (:386-391) | empty dirs between file and `root`, `rmdir` cannot remove non-empty | Yes |
| py probe unlink (:194), `.part` unlink (:301), stale `.part`/0-byte `.gz` sweep on NAS (:580-585, >24h, non-symlink) | own temp files on NAS | Yes |
| py `final.unlink()` on os.replace failure (:293) | zero-byte placeholder it just created with O_EXCL | Yes |
| py `clear_failure` (:568), `_atomic_json` tmp replace | state-dir json | Yes |

## Test gaps

1. No test that the wrapper passes/omits `--enable-delete`/`--no-delete` (stub is `/bin/sh`), nor exit-code mapping per step (F-2).
2. No wrapper test for stale lock (dead pid), live pid, or lock removal on SIGTERM (F-5).
3. No test that legacy `all`/`tick-only` cannot delete (F-1) or that missing mode is rejected.
4. No test for docker-ps failure => failure status (F-4); docker stub always succeeds.
5. No test that perl alarm kills a hung command / that timeout value argument ordering is right (the existing test only records the seconds argument).
6. Archive: no test for deadline expiry with remaining backlog (barrier all-fail path), no test for TimeoutError during the pre-delete `_verify` (:678), no test that idle sleep total fits the budget, no test for dangling intent after a restored tombstone followed by re-upload (F-6), no test for ts-late new file in a day already `day_complete`, no test for orphan `.deleting-*` making exit code 1 forever.
7. `test_plist_is_safe_default` only covers the old hourly template; the daily template has no test (no-delete default, StartCalendarInterval 03:00, label, log paths).
8. No end-to-end test with real `flock` contention between the wrapper's python and the old hourly job.

## Verdicts

**(a) Safe to install the daily plist in `--no-delete` mode: NO as shipped, YES after F-2 (and F-1 step 1).** The wrapper has no no-delete switch, so installing the template enables deletion at 03:00. With a default-off delete switch the uploader is safe in that mode (deletion requires `--enable-delete and not --no-delete`, py:674; no-tick mode never deletes local data). Prerequisites: bootout the hourly job (pid 11121 holds the lock, F-10) and the weekly `tick-only` job (F-1); optionally fix F-4/F-5 first because they make the nightly job lie/self-disable.

**(b) Safe to enable deletion after a manual `--only-day` trial: YES for the per-file delete algorithm (no CRITICAL/HIGH data-loss path found in `archive_to_nas.py`), CONDITIONAL on:** legacy `all`/`tick-only` jobs unloaded and mode guarded (F-1); trial run as in F-8 on the oldest day without `--max-files` (use `--idle-seconds 5`) with manual inspection; F-3 fixed or the operator accepting that the 17-day backlog will be red/not draining for several nights (consider draining it manually day by day with `--only-day` before enabling the unattended deletion).

**(c) Blockers (must fix before unattended deletion):** F-1 (legacy rm -rf, active and default), F-2 (no no-delete switch), F-8 (pilot as documented cannot test deletion). Strongly recommended before relying on it: F-3 (backlog never drains, per-file 30 s sleep), F-5 (permanent self-disable), F-4 (false success), F-13 (commit the code).
