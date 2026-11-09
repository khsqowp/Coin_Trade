# Independent review 3: archive_to_nas (2026-11-05)

Scope: re-review of `trading/scripts/archive_to_nas.py` (518 lines), `trading/tests/test_archive_to_nas.py`, the install doc, the launchd plist template and the 2026-11-04 report, against the claimed review2 fixes. Review only: no edits to script or tests, no real upload/delete, no commit, launchd untouched. Experiments used synthetic trees in the session scratchpad (`scratchpad/r3/e1..e6.py`, importing the real module). The only real-NAS writes were two tiny files plus a few more in `Trade/tick-archive/.scratch-review3/`; that directory was removed afterward and the tree was verified clean.

## Verdicts

- (a) Install launchd with `--no-delete` now: **YES.** Same condition as before: do the first `kickstart` by hand and read both logs to confirm TCC for `/opt/anaconda3/bin/python3` (not testable here).
- (b) Enable deletion for one old day via `--only-day` after H1 is resolved: **YES, conditional.** The delete path behaved correctly end to end and failed safe on every crash point I injected. Preconditions: H1 resolved (legacy tick job unloaded or its tick branch disabled), because the SMB-fallback "no overwrite" guarantee only holds with a single writer (finding M1). Start with `--enable-delete --only-day <old day> --max-files 1`, spread the two runs at least 24 h apart as the grace requires, and check `deleted.jsonl` (intent plus complete) and the NAS gz after.
- (c) Remaining blocker: **no code blocker for (a). For (b) the only blocker is H1 (open).** The legacy `com.orchestration.tick-archive-weekly` is still loaded (runs=2, last exit 1, interval 604800 s). Its next run is about 2026-11-07 19:32 KST, with the NAS now mounted. It will gzip and then `rm -rf` closed day dirs with no grace.

## Test results

- `/opt/anaconda3/bin/python3 -m pytest tests -q` from `trading/`: **141 passed** (2.9 s).
- `plutil -lint` on the template and on a filled copy: **OK**. Args: `--no-delete --max-minutes 40 --throttle-mbps 10`; `StartInterval` 3600; Nice 10; LowPriorityIO; log paths in `~/Library/Logs` (directory exists).
- No test patches `os.link`, so the SMB hard-link-unsupported fallback is **not covered by the suite** (see M1), although it is the only path that runs in production.

## Real NAS facts (experiment 2)

`/Volumes/HDD2TB` is smbfs. In `.scratch-review3`:

- `os.link(a, l1)` raised `OSError [Errno 45] Operation not supported`. **The real NAS does not support hard links.** `errno.ENOTSUP` is 45 on this macOS, so the script's `(ENOTSUP, EOPNOTSUPP, EXDEV)` tuple does catch it.
- `os.link(b, l1)` onto an existing name also returned errno 45, not `FileExistsError`. The fallback therefore always runs, including on collisions.
- `os.rename(a, b)` onto an existing file **silently replaced it** (b then held a's contents).
- `open(x, "xb")` and `os.open(..., O_CREAT|O_EXCL)` **are honoured**: the second create raised `FileExistsError`.

Consequence: in production the "exclusive hard-link publish" is really `final.exists()` followed by `os.rename`, a non-atomic check-then-replace.

## Findings, severity ranked

### MEDIUM

**M1. SMB fallback can overwrite an existing NAS gz under a concurrent writer; the fallback is untested.**
- Code: `_copy_gzip`, the `except OSError` branch (about lines 245-252).
- Experiment (`e1.py`), with `os.link` forced to ENOTSUP to emulate the NAS:
  - Single-writer: manifest lost and source changed, same target name. The old gz was preserved and a versioned `t.jsonl.<hash8>.<ns>.gz` was published. OK.
  - Race: a second writer creates `t.jsonl.gz` between the `exists()` check and the `rename`. The rename replaced the other writer's file. **Other file lost.**
- Practical exposure: only another writer on the NAS. That is the legacy job (H1). Its `mv -f` also replaces, but only when the gz is missing or fails `gzip -t`. So the exposure is small but real, and it is exactly the case the author's "never overwrite" claim covers.
- Suggested fix, since O_EXCL works on this NAS: reserve the final name with `os.open(final, O_CREAT|O_EXCL)` first, and `os.replace(part, final)` only after the reservation succeeds. On `FileExistsError`, take a versioned name. Note the legacy script treats a zero-length or invalid gz as replaceable, so the real mitigation is still resolving H1. Add a test that patches `os.link` to raise ENOTSUP.

### LOW

**L1. Uncaught OSError/TimeoutError in the delete phase aborts the whole run with a traceback.**
- Experiment `e6.py`: (i) an OSError (EIO) while appending the `deleted.jsonl` intent; (ii) a TimeoutError in the second pre-delete `_verify`. Both propagated out of `main` as uncaught exceptions. Only `BackupError` is caught around `_safe_delete`; the second `_verify` and the `os.stat` calls are unguarded.
- Safe: the source was retained in both cases and the next run retries. The cost is that remaining files that run are skipped, and the error goes to the log as a traceback only. A max-minutes expiry during the delete verify is plausible.

**L2. Alerting for orphans and dangling audit intents is log-only.**
- Experiment `e3.py`: crash after rename and before unlink leaves `t.jsonl.deleting-<pid>` with the source gone, and the gz is intact (data recoverable). Reruns log ERROR for the orphan on every run, and `--report` lists it, but the exit code stays 0, so launchd shows nothing.
- A crash after unlink and before the completion append leaves a lone `intent` record. Nothing flags an intent without a matching `complete`.
- Suggested: return a non-zero code, or emit a one-line summary, when orphans exist.

**L3. Legacy-record handling: report disagrees with the run, and re-upload makes duplicates.**
- `--report` counts the 2 real legacy records (no `upload_id`) as uploaded and verified (the report's `_verified` matches `None == None`). The actual run treats them as unverified and re-uploads them to `*.jsonl.<hash8>.gz`, so about 5 MB is duplicated. The install doc states both facts ("2 existing verified uploads" and "legacy records treated as unverified").
- Experiment `e5.py` (synthetic legacy-shaped records): the old gz was kept, a versioned gz was added, and grace restarted. Delete worked after two more runs, with intent and complete written. Behaviour is safe; only the reporting and cost are off.
- Similarly, a crash after gz publish and before the manifest append leaves an orphan gz, and the rerun publishes `t.jsonl.<hash8>.1.gz`. Safe, but it leaves unreferenced duplicates.

**L4. `--max-files` window can stall.** It slices the oldest N candidates. If those N keep failing (for example a permanently invalid gz), later files never get processed. This is benign for the intended single-day use.

### INFO

- A wrong wall clock between two separate runs (a forward jump across runs) can still satisfy grace. A jump within one run cannot (same `run_id`), and a future-dated grace file resets. Accepted residual.
- A writer holding an open descriptor on the renamed inode can still append in the post-rename and pre-unlink window (already documented). The idle check and two-hour closure remain the defence.
- The watchdog heartbeat is not refreshed during `_json_append` or `_mount_check`; those are covered only by `--io-timeout` (300 s).

## Verification of the author's claims

| Claim | Result |
|---|---|
| Never overwrite an NAS gz (exclusive hard link plus fallback) | Holds for a single writer (pre-existence check, hash compare, versioned names; `e1`). On the real NAS the link is unsupported, so the mechanism is check-then-rename and loses a concurrent writer (M1). Fallback untested. |
| Legacy records without `upload_id` | Confirmed: re-uploaded, a new grace is started, deletion works afterward (`e5`). Reporting inconsistent (L3). |
| `--max-files` and `--only-day` | Confirmed (`e2`): `--only-day 2026-10-01 --max-files 1` deleted exactly the oldest 1 file; the next run took the other file of that day; the other day was untouched. |
| Dry-run and report strictly read-only | Confirmed (see below). |
| Rename-back exclusive | In code (`os.link` restore, `FileExistsError` goes to `.late-*`); covered by an existing test. Not re-experimented. |
| Orphan alerts | Confirmed as log plus report only (L2). |
| Clock-jump guard | Confirmed by code reading: a grace entry with `first_seen_run == run_id`, or a future epoch, yields no grace. |
| Idle check | Confirmed by code and an existing test. |
| Mount-check test | Present (`test_production_mount_check_fails_closed_on_plain_tmp`). |

## Delete path end to end (experiment 3, `e2.py` and `e3.py`)

Synthetic tree: 3 files across 2 old days, `--enable-delete`, with hard links forced to fail to emulate the NAS.

- Run 1 uploads and verifies and starts grace. Same-instant and +1 h runs delete nothing.
- At +25 h with `--only-day 2026-10-01 --max-files 1`: exactly one file deleted. The audit has `intent` then `complete`, and the empty hour and day directories were pruned.
- At +26 h with `--only-day`: the second file of that day was deleted. At +27 h with `--no-delete --enable-delete`: nothing deleted. At +27 h with plain `--enable-delete`: the remaining day deleted. All gz stayed on the NAS and decompressed to the original hash.
- Crash injection (`BaseException`, simulating a kill):
  - After intent, before rename: the source is intact and a dangling intent remains. The rerun deletes it, giving `intent, intent, complete`.
  - After rename, before unlink: only the tombstone remains, the gz is intact, and later runs and `--report` flag the orphan (rc 0, see L2). No data lost.
  - After unlink, before complete: the source is gone and a lone `intent` remains (L2). The gz is intact.
- Failure injection: see L1.

## Dry-run and report read-only (experiment 4, `e4.py`)

For each of 6 scenarios (fresh tree, uploaded, corrupt gz, stale `.part`, legacy records, source changed plus orphan tombstone) and 4 modes (`--dry-run`, `--report`, `--dry-run --enable-delete`, `--report --enable-delete --max-files 1`, with the clock set 30 h later), a full tree snapshot (source, NAS, state; size, mtime_ns, content hash) was **identical before and after** in all 24 cases. A dry-run against a nonexistent state dir did not create it, and created no lock or NAS files.

## Real tree dry-run (experiment 5)

- `--dry-run`, `--report`, and `--dry-run --enable-delete --keep-days 0 --grace-hours 0`, using a scratch `--state-dir`: all rc 0. The state dir was not created.
- 1376 pending (45.03 GB), 2 reported uploaded and verified (the legacy `10/18/03` records), **0 deletable** even with grace and keep-days forced to 0, since no grace record exists. The 2 legacy files appear as `PLAN upload+verify` (L3). No warnings or invalid records. The listing of `/Volumes/HDD2TB/Trade` (83 files) was identical before and after.

## Plist lint (6)

Passes `plutil -lint`. No `ThrottleInterval` or `RunAtLoad`; the first run is at load plus 3600 s unless kickstarted (cosmetic). A 40-minute cap against a 3600 s interval leaves a margin. With throttle 10 MB/s and about three source reads per file (pre-hash, copy, verify), the 45 GB backlog needs roughly 6 or more runs of 40 minutes (probably a few hours of hourly runs). That is acceptable, and the NAS has 522 GB free.
