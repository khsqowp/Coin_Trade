# NAS tick archive backup report — 2026-11-04

## Design and scope

`trading/scripts/archive_to_nas.py` is a Python standard-library-only host job. It selects arbitrary `.jsonl` files from UTC `YYYY/MM/DD/HH` directories only when the hour is at least two hours old and the file mtime is more than two hours old. It sorts candidates oldest first. A nonblocking `fcntl.flock` is held under `~/.local/state/archive_to_nas`, off the NAS. The job checks that the configured mount is mounted, applies the extra `st_dev` check for the default `/Volumes/HDD2TB` mount, probes destination write access, and requires free NAS space of twice the estimated compressed pending bytes. The default estimate is 25% of pending source bytes.

Each source is streamed in 1 MiB chunks through gzip level 6 to `<name>.jsonl.gz.part`; the completed gzip is fsynced and atomically renamed. The job records source and compressed SHA-256 values, then reads and decompresses the NAS copy and re-hashes the source before appending a verified manifest record. Changed source versions are skipped with an error. Invalid NAS copies are retried on a later run. Local deletion requires verification, the configured grace period (24 hours by default), and at least seven full days since the UTC hour began. `deleted.jsonl` is at the NAS archive root. Empty source hour/day/month/year directories are pruned only when they are truly empty.

NAS layout is `Trade/tick-archive/YYYY/MM/DD/HH/<name>.jsonl.gz`, with one append-only `manifest.jsonl` at `Trade/tick-archive/YYYY/MM/DD/manifest.jsonl` per day and `Trade/tick-archive/deleted.jsonl` for local deletions. Existing legacy day-level files are untouched; the manifest uses distinct JSONL record types and doesn't replace those legacy data files.

## Verification results

- `python3 -m pytest trading/tests/test_archive_to_nas.py -q` could not start because the default Python 3.15 environment has no pytest installed. No dependency was installed.
- With the existing Anaconda pytest executable: `PATH=/opt/anaconda3/bin:$PATH python3 -m pytest trading/tests/test_archive_to_nas.py -q` — **10 passed**.
- Existing trading tests, run from `trading/` so the repository's `app` imports resolve: `PATH=/opt/anaconda3/bin:$PATH python3 -m pytest tests -q` — **122 passed**.
- Real dry-run report: **1,365** eligible local files, **44,729,375,153** source bytes, **522,916,487,168** bytes free on the NAS; no existing upload/verification records at that time.
- Final real dry-run report after the smoke test: **1,365** local files / **44,729,375,153** bytes, **2** uploaded and verified files / **5,439,471** bytes, **0** deletable files, **522,915,131,392** bytes free.
- Real dry-run `--max-files 5` planned the first five files in oldest-first order. The first two were `2026/10/18/03/crypto_funding.jsonl` (892,305 bytes) and `2026/10/18/03/crypto_perp.jsonl` (4,547,166 bytes).
- Real smoke command: `python3 trading/scripts/archive_to_nas.py --max-files 2 --no-delete`, using the default persistent state directory. Exit code was 0. Local originals were retained; their sizes and nanosecond mtimes still match the manifest.

## Exact NAS smoke artifacts

The two compressed files were created under `/Volumes/HDD2TB/Trade/tick-archive/2026/10/18/03/`; the per-day manifest is `/Volumes/HDD2TB/Trade/tick-archive/2026/10/18/manifest.jsonl`:

| Path | Original bytes | Gzip bytes | Original SHA-256 | Gzip SHA-256 |
|---|---:|---:|---|---|
| `crypto_funding.jsonl.gz` | 892,305 | 58,305 | `de6221969d0bc172e9344affe820451c1c7f226635f3b436363fc1505364c55d` | `36588f048a9c70b175978ffeaa09ef91adaf9baccd442c1a425e495edba550eb` |
| `crypto_perp.jsonl.gz` | 4,547,166 | 373,013 | `7bf9d2e2662b1e0b3f3807c628312cd278d2413940c524a89d7ac26853d60830` | `2da80f81e7415056f7141707494f875b4fc5fbb1b871046198628c20dc9f2c46` |

`2026/10/18/manifest.jsonl` contains an upload and a verified record for each gzip. No `.part` files or `deleted.jsonl` were created. Both local source files still exist and match the recorded size and `mtime_ns`. The final invocation against the same two candidates was idempotent and did not rewrite the gzip files. During implementation, the initial smoke manifest was created at the wrong hour-level path; that job-created manifest was moved to the required day-level path, then the latest script was rerun and confirmed idempotent.

## Open risks and boundaries

- SMB atomic rename and fsync durability depend on the NAS/server implementation; the smoke run confirms this mount accepted the operations, not crash durability under power loss.
- UTC hour-folder age plus file mtime is a conservative heuristic. A writer that keeps an older file open after the hour changes could still append after selection; the job detects many changes through size/mtime/hash checks, but the source writer does not provide an explicit close signal.
- Real data deletion was not exercised. The smoke run used `--no-delete`; deletion behavior is covered only by synthetic tests. Keep `--no-delete` until operations deliberately authorize cleanup.
- The 25% gzip estimate is configurable and may not represent actual tick JSONL compression. The 2x free-space margin can still be inaccurate for unusual data or NAS accounting behavior.
- Verification and deletion are separated by the configured 24-hour grace period; NAS corruption after verification is only caught by later runs if the source remains local. Local originals retained by the grace/7-day rules provide the recovery window.

## 2026-11-05 independent review remediation addendum

The 2026-11-04 implementation and smoke-run details above describe the state at that time. The independent review on 2026-11-05 found the following operational conflict, which remains unresolved and blocks deletion:

### Legacy tick-only job conflict (H1)

The loaded `com.orchestration.tick-archive-weekly` LaunchAgent runs `scripts/backup-tick-archive-to-nas.sh tick-only` at load and on a seven-day interval. Its tick-only branch gzips closed day/hour files to the same NAS paths used here (`YYYY/MM/DD/HH/<file>.jsonl.gz`) and then removes the local day directory with `rm -rf`. It has no verification grace period. Its `mv -f` can replace a newer job's gzip without updating the newer manifest; the two jobs can consequently overwrite each other's archive, and an append in the legacy hash-to-`rm -rf` window can be lost. Do not modify or unload that job or script as part of this change.

Options:

- **A. Disable only the tick portion of the weekly job and retain its DB/state backup.** This preserves the useful database/state backup while removing overlapping tick writes and deletes.
- **B. Retire the entire weekly job.** This removes the conflict but also removes its DB/state backup unless that work is migrated first.
- **C. Change the legacy script to refuse tick deletion when the new manifest exists.** This is a useful guard, but still leaves two writers targeting the same gzip path and does not prevent overwrite/thrash.

Recommendation: **A**, after the operator has verified DB/state backup coverage and deliberately changed the weekly job configuration. Until that resolution is confirmed, keep `--enable-delete` absent. The new template does not enable deletion by default.

Implementation state after review: deletion now defaults off and requires `--enable-delete`; the template includes `--no-delete --max-minutes 40`. Late source revisions get a hash-versioned gzip and manifest upload record. Grace state is held locally. Mount identity is rechecked at operations, delete uses same-directory rename and post-rename identity checks, and an I/O watchdog bounds a hung operation. Validation results belong to the 2026-11-05 change record and must be appended after running the requested tests.


### 2026-11-05 validation

- `/opt/anaconda3/bin/python3 -m pytest trading/tests/test_archive_to_nas.py -q` — **21 passed**.
- From `trading/`, `/opt/anaconda3/bin/python3 -m pytest tests -q` — **133 passed**. Running collection at the repository root does not resolve the pre-existing `app` imports; using `trading/` as the working directory is required.
- `/opt/anaconda3/bin/python3 trading/scripts/archive_to_nas.py --dry-run --report --state-dir /tmp/archive-final-verify-anaconda` — exit **0**; report: 1,376 local pending, 2 uploaded/verified, 0 deletable. The scratch state directory was used. No real upload or local deletion was run.
- The same real-path dry-run report was exercised successfully with `/opt/homebrew/bin/python3` and `/usr/bin/python3` during interpreter selection. `/opt/anaconda3/bin/python3` is pinned because its pytest environment is available and the dry-run report passed.

### 2026-11-05 review3 remediation

The follow-up fixes address M1 and L1-L4 from `nas_archive_review3_2026-11-05.md`. The SMB hard-link fallback now reserves a target using `O_CREAT|O_EXCL` before `os.replace`; a competing target causes a versioned filename. A zero-byte reservation is not verified as a gzip, and stale zero-byte `.gz` files are swept after 24 hours alongside stale `.part` files. Delete-phase OSError and timeout failures are handled per source, logged without a traceback, and produce a nonzero run result while retaining the source if deletion did not complete. Orphan tombstones and audit intents without completions now appear in report output and produce nonzero exit status. Reports exclude legacy upload records lacking `upload_id` from uploaded/verified counts, matching the run's requirement to refresh them. Per-file failure backoff starts at one minute and doubles to a six-hour cap; `--max-files` applies after backoff filtering so later files can progress.

- From `trading/`, `/opt/anaconda3/bin/python3 -m pytest tests -q` — **146 passed**.
- Synthetic SMB fallback test forces `os.link` to raise errno 45 and creates a competing target before fallback reservation; both copies remain present.
- Real NAS `/opt/anaconda3/bin/python3 scripts/archive_to_nas.py --dry-run --report --state-dir scratchpad/nas-review3-readonly-state` — exit **0**; 1,376 pending (45,028,149,294 bytes), 0 uploaded/verified (the two old manifest records have no `upload_id` and are intentionally treated as unverified), 0 deletable, 522,679,390,208 NAS free bytes, no orphan tombstones or dangling intents. The scratch state path was absent before and after. No real upload or deletion was run.

### 2026-11-05 review2 remediation

The review2 findings N1-N4 and the requested race hardening were implemented in `scripts/archive_to_nas.py` and covered by synthetic tests. Legacy manifest upload records without `upload_id` are no longer eligible for deletion: the source is re-uploaded under exclusive publication, receives a current ID, and starts a new grace period. Deletion audit writes an intent record before rename/unlink and a completion record after unlink; missing optional manifest fields are read with `.get`.

An existing NAS gzip is never overwritten. The job publishes with `os.link` exclusive-create semantics, selects a versioned name on collision, and records the actual published filename. An SMB hard-link unsupported fallback uses check-then-rename under the per-state-directory writer lock; it does not coordinate independent hosts. `--max-files` limits the sorted candidate set, and `--only-day YYYY-MM-DD` filters both upload and deletion selection.

Dry-run and report do not create the state directory or lock and do not write manifests or grace state. They skip locking to remain read-only. Grace requires a first-seen run and a later distinct process run after the configured elapsed interval, preventing a single forward clock jump from satisfying the rule. Deletion also requires unchanged size, `mtime_ns`, and inode across the `--idle-seconds` interval (default 30), plus a post-rename identity/size check. Restore is exclusive; a recreated original path is preserved and the tombstone is kept as `.late-*`. Each run logs orphan `.deleting-*` and `.late-*` files; report output lists them.

Residual open-descriptor risk remains: a writer that already holds the renamed inode can append after the post-rename stat and before unlink, losing that append. The seven-day retention and two-hour closure heuristics are the main protection. The SMB fallback also assumes one writer host. No launchd operation, legacy script/container/writer edit, real upload, or real deletion was performed during this remediation.

- Archive tests after remediation: **29 passed**.
- Full requested suite: from `trading/`, `/opt/anaconda3/bin/python3 -m pytest tests -q .` — **141 passed** (2.51 s).
- Real-path `/opt/anaconda3/bin/python3 scripts/archive_to_nas.py --dry-run --report --state-dir scratchpad/nas-review2-readonly-state` — exit **0**; 1,376 local pending (45,028,149,294 bytes), 2 uploaded and verified (5,439,471 bytes), 0 deletable, 522,679,828,480 NAS free bytes, and no orphan tombstones. The state path was absent before and after the command; no dry-run files were created. No real upload or deletion was run.
