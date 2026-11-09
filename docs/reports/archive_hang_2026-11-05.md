# archive_to_nas / legacy backup hang investigation (2026-11-05)

## What happened
- pid 11121 (launchd com.ochestration.archive-to-nas, runs=1) is STILL ALIVE (state SN, not D) and is NOT hung now. `sample` at 08:29: ~70% time.sleep (throttle), fsync/open on grace JSON + NAS files; lsof shows it reading trading-tick-archive/2026/10/18/08/crypto_spot.jsonl. NAS manifest 2026/10/18/manifest.jsonl modified 08:30:21; 19 grace files written 08:27-08:30 (~1 file / 10 s = expected pace at --throttle-mbps 10, hash + gzip + verify passes).
- The real stall was BEFORE the work phase: lock file mtime = 08:27:03 and manifest `uploaded_at` = 2026-11-04T23:27:03Z (= 08:27:03 KST). `uploaded_at/upload_id` use `current_epoch`, taken at archive_to_nas.py:468, right after the lock write (:466). Process start was 00:35:56. So the process sat ~7h51m between start and line 466 and "really started" at 08:27:03, ~3 min after Docker Desktop was restarted (com.docker.backend started 08:24, legacy docker cp failed 08:24:46).
- Its 40 min budget therefore started at ~08:27, not 00:36. Expected end ~09:07 KST (if deadline works). Not killed.
- No overlapping runs: launchctl shows runs=1 (launchd never spawns a second instance of a running job); error.log is 0 bytes (no "lock contention" lines ever); flock held on fd 3 by 11121 only.

## Root cause (confirmed vs guess)
CONFIRMED: both safeguards are armed too late / start after the blocking section.
- `--max-minutes` deadline is created at archive_to_nas.py:514, only after preflight/scan/orphan rglob/NAS record reads/disk_usage. It never covers startup.
- io-timeout watchdog is armed at :467 (after lock). Anything before it is unguarded: :441-442 `Path(args.dest).resolve()` (lstat on the SMB path, /Volumes/HDD2TB/...), `root.is_dir()`, state mkdir, lock open/flock/write/fsync (:445-466).
- Between :467 and :514 the watchdog is armed but heartbeats (`beat`) only fire in file read loops (:83, :276, :290, :336, :343); calls like `_ensure_mounted`, `_preflight`, `_records(dest/"deleted.jsonl")`, `shutil.disk_usage(dest)`, `day_dir.rglob`, and the whole-file `gzip.open(remote).read()` at ~:561 have no heartbeat and no deadline. The watchdog would os._exit(3) after 300 s, but os._exit cannot finish if the thread is in uninterruptible SMB kernel I/O.
- The process was in 'SN' not 'D' now, and watchdog thread exists (sample shows 2nd thread waiting on Event).
GUESS (most likely): a blocking syscall on the SMB/`/Volumes` path (dest.resolve() or similar) hung from 00:35:56 until ~08:27, and released when Docker Desktop was restarted (Docker VM mounts --virtiofs /Volumes; Mac load avg 12). Not provable: sample was taken only after release, and no per-process unified-log lines exist. Mac did not sleep (Amphetamine/powerd assertions; 04:00 legacy backup ran and wrote to the NAS fine at 04:00:06, so the SMB share itself was reachable then -> hang may be Docker/virtiofs-related or a transient SMB stall at 00:35).
- Auto-mount code (:220-257) did not contribute: NAS was already mounted (mount shows smbfs on /Volumes/HDD2TB), `open -g -j` was not needed; it has subprocess timeout=mount_timeout (90 s) anyway. Unit tests: 42 passed (tests/test_archive_to_nas.py), but they do not cover pre-lock blocking.

## (b) Empty log - monitoring blind spot (confirmed)
logging.basicConfig (:439) logs to stderr at INFO, but launchd stderr -> archive_to_nas.error.log, and normal progress is not logged at all: only WARNING/ERROR on events, plus the final JSON only for --report. A healthy 40-min run and a 7h hang both produce 0-byte logs. No start/heartbeat/summary line exists.

## (d) Legacy scripts/backup-tick-archive-to-nas.sh
Confirmed no timeouts: `docker ps` (:150), `docker cp` (:156), `mount_smbfs` (:45), `rsync` (:158) all run unbounded; `set -e`/exit codes irrelevant when the call never returns. gtimeout/timeout are not installed; perl is (/usr/bin/perl). docker cp at 04:0x hung until Docker was restarted at 08:24 (4h18m), then failed.

## Recommended fixes (NOT applied)
1. archive_to_nas.py: move `_watchdog()` + lock acquisition to the very top of main(), before any `resolve()`/NAS touch; use a hard process-level watchdog (e.g. `signal.alarm(max_minutes*60+grace)` plus SIGALRM -> os._exit, and a thread watchdog with os._exit) so total runtime is bounded regardless of phase. Start `deadline` right after the lock, not at :514. Do all NAS metadata calls (resolve, stat, rglob, _records, disk_usage) from a worker thread/subprocess with a join timeout, or call `beat()` around them with a longer io-timeout.
2. Logging: emit INFO start line (pid, args), per-file progress/every-N-minutes heartbeat and an end summary to stdout; add a staleness check (alert if no log/last_seen_epoch update > 15 min while process alive).
3. Legacy sh: wrap external calls with perl alarm, e.g. `t() { s=$1; shift; perl -e 'alarm shift; exec @ARGV' "$s" "$@"; }` then `t 20 docker ps ...`, `t 300 docker cp ...`, `t 60 mount_smbfs ...`, `t 600 rsync ...` (alarm survives exec; exit 142 on timeout). Or `brew install coreutils` -> gtimeout.
4. Overall: add launchd `ExitTimeOut` is not enough; consider a wrapper cron/health check that kills archive_to_nas.py if elapsed > max-minutes+10 min.
