# Independent review 1: archive_to_nas (2026-11-05)

Scope: trading/scripts/archive_to_nas.py, trading/tests/test_archive_to_nas.py, trading/docs/archive_to_nas_install.md, trading/docs/launchd/com.ochestration.archive-to-nas.plist.template, trading/docs/reports/nas_archive_2026-11-04.md. Review only: no edits to the script or tests, nothing real deleted or uploaded, nothing committed.

## Verdict

**Do NOT enable deletion yet.** Running with `--no-delete` (upload + verify only) looks safe.

The core delete gate is sound. Every run fully re-verifies before unlinking: it re-hashes the gzip, decompresses it, re-hashes the local original, and compares against size, mtime_ns, sha256 and gz_sha256. Experiments confirmed it blocks deletion when the NAS gz is replaced by same-size garbage during the grace period.

Deletion should stay off until these are fixed:
- H1: the legacy tick-archive jobs still delete local day folders.
- H2: the plist template deletes by default.
- M1: there is a TOCTOU window between the last stat and unlink.
- M2: a late append leaves a file stuck, so the NAS copy is stale.
- M3: the grace clock trusts a mutable manifest.

## Test results

- `python3 -m pytest trading/tests/test_archive_to_nas.py`: fails to start. Homebrew Python 3.15 has no pytest.
- `/opt/anaconda3/bin/python3 -m pytest trading/tests/test_archive_to_nas.py -q`: **10 passed** in 0.04s.
- `--dry-run --report` against the real tree and NAS: works under both anaconda Python and `/usr/bin/python3` (3.9.6, the CLT shim the plist uses).
  - 1376 local pending files (45.0 GB), 2 uploaded and verified, 0 deletable, NAS free 522 GB.
  - I used a scratchpad `--state-dir`.
- Adversarial experiments used synthetic trees in the scratchpad and the real script module. Results are below.

## Findings

### HIGH

**H1. The legacy jobs still delete local tick data and share the NAS paths.**
- Code: scripts/backup-tick-archive-to-nas.sh, lines 55-100.
- Job: `~/Library/LaunchAgents/com.orchestration.tick-archive-weekly.plist` runs `tick-only` with `RunAtLoad` plus a 7-day interval. It is loaded. `com.orchestration.tick-backup` runs `state-db-only`, so it does not touch ticks.
- What it does: for every UTC day older than today it gzips each file to `<dest>/YYYY/MM/DD/HH/<f>.jsonl.gz`, compares hashes, then runs `rm -rf "$day_dir"`.
- Conflicts:
  - It destroys the 7-day local retention premise. Any run removes every closed day immediately, with no grace period.
  - It writes to the same gz path the new job manages. `mv -f` replaces the new job's gz, so size and hash drift away from the manifest.
  - The new job then re-uploads, and the two jobs thrash.
  - Its hash, `find` and `rm -rf` sequence is not atomic. A late append to an old hour between the hash and the `rm -rf` is lost. The new job does not have this flaw, but the legacy job bypasses all the new job's guards.
- Fix:
  - Remove the tick part of the weekly job (or `launchctl unload` it) before enabling the new job. Keep the DB and state backups.
  - Make the legacy script refuse to delete when the new job's manifest exists.

**H2. The plist template deletes by default.**
- File: com.ochestration.archive-to-nas.plist.template, lines 7-8.
- ProgramArguments has no `--no-delete`, no `--max-minutes` and no `--throttle-mbps`. The doc says "install only after reviewing the plan", but loading the template as-is enables deletion.
- First run: about 45 GB and 1376 files in one unthrottled SMB session, with no time cap.
- Fix:
  - Ship the template with `--no-delete --max-minutes 50`.
  - Make deletion a deliberate second edit.
  - Consider a `--enable-delete` flag, or make `--no-delete` the default.

### MEDIUM

**M1. TOCTOU between the final stat and unlink.**
- Code: lines 383-388. The check is `src.stat()` (383), then the `deleted.jsonl` append with fsync on SMB (386), then `src.unlink()` (387).
- The writer opens files per batch (app/tick_archive.py, `os.open(O_APPEND)`, path derived from the record `ts`). So a late append, such as the in-memory retry queue `pending_archive` after an OSError or Docker VM clock skew after sleep, can land in an old-hour file at any time.
- Scenario: an append between line 383 and line 387 is deleted along with the file. The window is tens of milliseconds to seconds on SMB, and the file is at least 7 days old. The probability is low, but the loss is silent and permanent.
- Fix:
  - Do the stat/unlink step with `os.rename(src, src + ".deleting-<pid>")`, then re-stat and compare, then unlink.
  - If the size or mtime differs, rename the file back or keep it.
  - A later append then creates a fresh file at the original path instead of vanishing.
  - Move the `deleted.jsonl` append to after the unlink succeeds. Today it logs "deleted" even if the unlink fails.

**M2. A late append after upload leaves the file stuck, the NAS copy stale, and the job at exit 1 every hour.**
- Code: lines 334-338.
- Experiment A: upload, then append one line, then run again. Result: `source version conflicts with manifest; skipping safely`, rc 1, the file stays.
- This is safe from a loss standpoint, because the local file is never deleted.
- But the new bytes never reach the NAS, and the NAS holds the old shorter version.
- Because the file is never retried and never deleted, retention silently grows without bound. The alert is just a recurring failure code.
- Fix:
  - On a size or mtime change, treat it as a new version. Upload to a versioned name such as `.jsonl.v<mtime_ns>.gz`, or overwrite only after the new gz is fully verified.
  - Record a new `upload` entry with a version.
  - Never delete based on an older upload record.

**M3. The grace clock trusts the mutable manifest, and a missing epoch means "immediate".**
- Code: line 376 (`v.get("verified_at_epoch", 0)`) and lines 107-123, where a legacy-style verified record with no `upload_id` is accepted.
- Experiment C: set `verified_at_epoch=0` in the manifest. The next run deleted immediately, with no 24h wait.
- Hash re-verification still runs, so this only bypasses the grace period. But the "24h grace" safety is only as strong as a file on the NAS that any SMB client can edit.
- Fix:
  - Keep the grace state in the local state dir, keyed by path plus upload_id.
  - Treat a missing or implausible epoch (zero, future, or older than the upload) as "now".
  - Drop the legacy no-`upload_id` match.

**M4. Verification errors write `invalid` records and reset the grace clock.**
- Code: lines 363-365.
- Any exception in `_verify` appends an `invalid` record. That includes a `--max-minutes` TimeoutError, a transient SMB read error, and a missing source.
- Next run: the file is re-uploaded and the grace period restarts. With a tight `--max-minutes`, big files can loop forever.
- Fix:
  - Write `invalid` only on a definite content mismatch (EOFError, BadGzipFile, hash or size mismatch).
  - Skip the file on a timeout or OSError.

**M5. The mount check is not re-evaluated mid-run, and it does not tie `dest` to `mount`.**
- Code: lines 136-161 (preflight, once at start), line 166 (`mkdir(parents=True)`) and line 41 (`_json_append` with `mkdir(parents=True)`).
- Not checked:
  - `dest` need not be under `mount` (both are free arguments).
  - The filesystem type is not verified to be smbfs.
  - There is no re-check before each upload or delete.
- If the NAS drops after preflight and `/Volumes/HDD2TB` still exists as a user-owned directory, `mkdir(parents=True)` silently recreates `Trade/tick-archive/...` on the boot disk. The job then "verifies" against the ghost copy and deletes the originals on a later run.
- Mitigations already present:
  - `/Volumes` is `root:wheel 755`, and the existing legacy log shows `mkdir: /Volumes/HDD2TB: Permission denied`.
  - A normal unmount removes the mount dir. So the ghost case needs a stuck or partial mount directory. It is unlikely but not impossible.
- I confirmed (E2) that deleting `dest` mid-run recreates the tree on the same filesystem.
- Fix:
  - Before every delete (and each upload), re-check `ismount(mount)` and that `os.stat(dest).st_dev == os.stat(mount).st_dev != os.stat(src_root).st_dev`.
  - Check `dest` is a descendant of `mount`.
  - Never use `mkdir(parents=True)` above the day directory.

**M6. A stale SMB mount hangs forever, and launchd cannot recover it.**
- Code: lines 138-157. `ismount`, `is_dir` and the probe write have no timeout.
- A hung SMB mount leaves the process in uninterruptible I/O. It holds the flock, and later runs fail with "another archive job holds the lock".
- Fix: run the preflight in a child process with a timeout, or use a watchdog thread that logs and `os._exit`s.

**M7. Launchd and macOS permissions may break the job silently.**
- The plist uses `/usr/bin/python3`, the Command Line Tools shim. It is 3.9.6 and works here, but it is a different TCC identity from `/bin/bash`.
- The repo is under `~/Desktop`, and the destination is a network volume. Both are TCC-protected.
- A TCC denial surfaces as "source directory missing" (rc 2) or a PermissionError. The existing bash jobs run fine, but that grant is per binary.
- There is no `WorkingDirectory` (harmless because paths are absolute) and no PATH (not needed).
- Fix:
  - Grant Full Disk Access (or Desktop and Network Volumes) to the python binary, or pin an absolute interpreter that already has the grants.
  - Verify with `launchctl kickstart` and check the logs before trusting it.

### LOW

**L1. A partial manifest line corrupts the next record.**
- Code: `_json_append`, lines 39-44.
- Experiment D: a truncated final line without a trailing newline. The next append concatenates onto it, so both records are lost.
- It self-heals on the following run, and no deletion is wrongly allowed, because verification re-runs every time.
- Fix: before appending, check that the file ends with `\n` (read the last byte), or write `"\n" + record` when it does not.

**L2. `shutil.disk_usage(dest)` is unguarded (line 285).** If dest vanishes between preflight and this call, the job dies with a traceback instead of a clean rc 2. This is safe but noisy.

**L3. Misleading comment and `.part` cleanup.**
- Lines 200-202 say "leave crash artifacts … as documented".
- A failed upload leaves a 100+ MB `.part` on the NAS until the same file is retried.
- A source that disappears leaves an orphan `.part` forever.
- Fix: delete `.part` in a finally block, or sweep `*.part` older than a day.

**L4. Symlinks.**
- Experiment F: a symlinked `.jsonl` pointing outside the root is gzipped, and later only the link would be unlinked (the target stays).
- Path traversal is not possible, because the glob is digit-only and the manifest `path` never builds a filesystem path.
- Fix: skip `is_symlink()` entries, and skip symlinked directories.

**L5. Time and retention.**
- Retention is computed as UTC hour start + 7 days against the UTC `now`. That matches the writer, which takes the path from the first 13 characters of `ts` (verified `+00:00` for crypto and KR data).
- If a producer ever emits `+09:00` timestamps, the folders become local-hour folders. The script would then treat them as UTC. With a negative offset (the US), closure would be later than assumed. The mtime check (>2h) mitigates that.
- The 2h/2h closure heuristic is reasonable. In the current data I found 0 files whose mtime is more than 1h05 after the hour. It is still only a heuristic, because the writer gives no close signal.
- `now` is fixed at the start of the run (conservative for long runs). The epoch comes from `time.time()` while the comparison uses the injected `now`, so tests with a fake `now` do not exercise real grace semantics.

**L6. Plist polish.**
- `os.nice(10)` in the script plus `Nice 10` in the plist stacks, which is harmless.
- `LowPriorityIO` is fine.
- All stderr logging (including INFO) goes to `archive_to_nas.error.log`, and neither log rotates.
- There is no `ThrottleInterval` or `ExitTimeOut`, and no secrets are present.
- The label spelling differs from the existing `com.orchestration.*` jobs (`ochestration` vs `orchestration`), which is cosmetic but easy to confuse.

**L7. No ongoing integrity check on the NAS copies.**
- After local deletion the NAS gz is the only copy, and nothing re-validates it.
- Add a periodic `gzip -t` plus manifest cross-check scrub, or retain the monthly offsite copy.

**L8. No cross-host or cross-state-dir mutual exclusion.** The flock lives in the local state dir only. Two hosts, or a different `--state-dir`, can write the same NAS manifest concurrently.

## Specifically attacked, and held

- **Truncated or replaced NAS gz during the grace period:** caught. `_verify` runs on every run before delete and compares the gz size, the gz sha256 and the decompressed sha256 against the original. Experiment B (same-size zero-fill) gave rc 1, with the file kept and an `invalid` record written.
- **Stale or forged `upload` record:** harmless to deletion, because the content hash is recomputed from the real source and the real gz (the record only supplies expected values).
- **Original changed:** the size and mtime_ns checks are repeated at lines 187, 231, 378 and 384.
- **Hash source:** the original hash is computed on the same bytes that are compressed, so the original-vs-decompressed comparison is meaningful.
- **Idempotency and crashes:** the `.part` plus `os.replace` flow is atomic. `.part` is overwritten on retry.
- **Concurrent runs:** the local flock works, and the test passes.
- **Dry-run:** it writes nothing to the NAS (the state dir and lock are still created).
- **Directory pruning:** it uses `rmdir`, so it only removes empty directories.

## Test gaps

All 10 tests are single-file happy-path style. Missing:
- Late append after upload (M2) and an append between the last stat and unlink (M1). No race injection around the delete.
- NAS gz replaced or truncated after verification, during the grace period, with the same size, plus a zero-length gz and a trailing-garbage gz. The existing test only corrupts before the run.
- Forged, stale or partial manifest lines (M3, L1), and a verified record without an epoch.
- Mount lost mid-run or ghost directory (M5), read-only destination (probe), `st_dev` equality, and stale-mount timeout.
- Insufficient free space, `--max-files`, and `--max-minutes` expiry (M4 behaviour).
- A crash (SIGKILL) mid-copy with a `.part` left, and an orphan `.part`.
- Symlinks (L4), exact keep-days boundary (hour + 7d), and grace boundaries (23h59 and 24h).
- Non-UTC `ts` / timezone handling, and `--report` output correctness.
- Multi-file runs where one failure must not stop the rest; `deleted.jsonl` content; unlink-failure handling.
- `test_grace_and_seven_day_retention` uses `datetime.now()` for `now` but `time.time()` for epochs, so its grace logic is tautological.
- `test_plain_local_dir_is_not_mount` checks `/tmp` (a symlink on macOS), which is weak.
- No test that the plist/doc defaults are non-destructive.

## Required before enabling deletion

1. Disable the tick-only legacy job (H1).
2. Ship the plist with `--no-delete` and a time cap, and flip deletion deliberately (H2).
3. Use rename-then-verify-then-unlink, and log deletion after success (M1).
4. Add versioned re-upload for late appends (M2).
5. Keep the grace state locally and treat a missing epoch as now (M3).
6. Re-check the mount and `st_dev` before every upload and delete (M5).
7. Add tests for M1 through M5.

After that, run `--no-delete` for a few days. Deletion can then be switched on for one old day first, with a manual spot check of the NAS gz against the local file.
