# Docker prevention: independent re-review 3 (2026-11-05)

Review only. No edits to repo code, no commit, no Docker quit/restart, no recreate, no compose up/down, no launchd install.
`date -u` at review: 2026-11-05 03:31-03:35Z. Next momentum rebalance 09:41Z, so about 6 h of margin.
Test harness and stubs are in the session scratchpad only (`run.sh`, `stubs/`), all run under `env -i` PATH `/usr/bin:/bin:/usr/sbin:/sbin`.

## Verdicts

| | Question | Verdict |
|---|---|---|
| (a) | Recreate non-bot containers now | YES |
| (b) | Recreate the bot container (outside rebalance window) | YES, now through roughly 09:00Z; do not start within about 30 min of 09:41Z |
| (c) | Install watchdog with dead-engine-only auto-restart | YES. The lock bug (M1) is not a blocker because launchd does not overlap runs of one job. Fix it when convenient. |
| (d) | Blockers | None |

## 1. Real process names vs what the script waits on

- `ps -ax -o pid,comm` now (Docker running): the app process is `.../Docker Desktop.app/Contents/MacOS/Docker Desktop`. Helpers are `Docker Desktop Helper`, `Docker Desktop Helper (Renderer)`. Engine processes are `com.docker.backend`, `com.docker.virtualization`, `com.docker.build`, `com.docker.vmnetd`.
- `pgrep -x 'Docker Desktop'` returns 86798, the main app only. Helpers do not match `-x`. `pgrep -f 'Docker Desktop'` returns 4 pids (main plus helpers), so `-f` would be too broad. The script correctly uses `-x`.
- `pgrep -x 'Docker'` matches nothing today. It is a harmless extra, no false match.
- Prior H1 is fixed. The wait loop (`pgrep -x 'Docker Desktop'` AND `pgrep -x 'Docker'` both absent) matches the real name.
- Stuck-quit experiment (pgrep stub always "running"): log shows `ACTION restarting...`, then `ERROR Docker process did not exit within 60s; restart aborted and attempt counted`. `open` was called 0 times, `restart_epochs` was written. An aborted quit never produces a blind open.
- Not verified: the real `osascript -e 'quit app "Docker"'` was never run, per the no-quit rule. The app-name resolution rests on the bundle being `Docker.app`.

## 2. Branches that can reach the restart command

Only one path reaches `quit app`: `docker info` fails or times out (30 s), AND `failures >= 3` AND `now - failure_since >= 360`, AND cooldown (30 min) clear, AND fewer than 2 restarts in 24 h, AND no PAUSE file, AND the Docker Desktop process exists, AND not `--dry-run`. All experiments below used a 120 s cadence.

| Experiment | Result |
|---|---|
| Engine OK (stub exit 0) | No failure counted, no restart, no osascript or open calls |
| Engine fails, app running, 4 runs at +0/120/240/360 | Restart only at +360 (3 failures at +240 are held back by the 6-min span). Quit then open called once each. Next run: `RESTART withheld: 30-minute cooldown active` |
| App not running | `RESTART withheld: Docker Desktop app is not running; alert only`, no quit or open |
| PAUSE file | `RESTART withheld: PAUSE file present; alert only`, no quit or open |
| Counter expiry (fail, fail, fail, OK, fail) | An OK run zeroes the counter. Next failure logs `consecutive=1`, 0 restarts |
| Failure streak older than 900 s | Code path `now - failure_since > 900` resets to 1, so a stale count plus one slow run cannot trigger |
| Wake grace (gap 5000 s after 3 failures) | `WAKE grace: ... counters reset and this cycle skipped`. Next failure is `consecutive=1`, 0 restarts |
| Persist-before-attempt | `restart_epochs` and `last_restart_epoch` are written before `quit`. Verified in the stuck-quit run (1 entry, 0 opens) |
| 2 recent valid epochs plus a garbage line in `restart_epochs` | Garbage ignored, valid ones counted: `maximum two restarts in rolling 24 hours reached` |
| Binary garbage in all 5 state files | Treated as 0, run continues, `consecutive=1`, no crash |
| Hung `docker` (sleep 300) | The perl alarm fires at exactly 30 s (elapsed 30 s measured) and counts as an engine failure (`consecutive=1`), not an instant restart |
| Slow `docker info` that finishes in time | Counts as engine alive. No restart |

Hung docker detail: the perl wrapper kills only the direct child (TERM, 0.5 s, KILL), not the process group. With my bash stub, the grandchild `sleep` was orphaned (I killed those). The real `docker` CLI is a single process for `info`, so this is a non-issue today. See L1.

Lock and concurrency:
- Dead-pid lock, ownerless lock dir, and age over 300 s: all taken over correctly with a WARN.
- Live-owner lock: the second run logs `SKIP watchdog already running`, but see M1.
- Per-attempt persistence means even concurrent runs cannot cause a second restart within the 30 min cooldown.

Other review2 items re-verified:
- Swap alert rate-limit: alert logged once per 6 h window.
- Log rotation: a 1.1 MB log is moved to `watchdog.log.1`.
- HOME fallback: dscl, then `eval ~`, then `/var/tmp`.
- `--dry-run` real run under `env -i`: uses a temp state dir (removed on exit), prints the log to stderr, notifications logged not sent. Output: heartbeat "not-yet-supported" notice and `OK engine available`.
- No secrets: the only inspect is `--format '{{.RestartCount}} {{.State.OOMKilled}} {{.State.Running}}'`. The exec only reads `/app/data/heartbeat.json`.
- `bash -n scripts/docker_watchdog.sh`: OK.
- `plutil -lint` on the filled plist copy: OK.
- Pytest: `tests/test_docker_watchdog.py tests/test_momentum_heartbeat.py`: 14 passed.

## 3. Compose files

Repo `git diff` (non-limit changes only, filtered by grep):
- `docker-compose.yml`: mysql healthcheck `interval 10s -> 30s` plus `start_period: 30s`, and api `JAVA_TOOL_OPTIONS: "-Xmx1536m"`. Everything else is `mem_limit`/`memswap_limit`/`pids_limit`/`oom_score_adj`.
- `docker-compose.trading.yml` and `docker-compose.crypto-data.yml`: only the four limit keys. No env, ports, volumes, entrypoint or profile changes.
- `docker-compose.yml` resolved config: n8n 1610612736 (1536m), pids 96, oom_score_adj 500. api 2560m, pids 256, Xmx1536m. mysql 1280m/192. web, games, cloudflared, db-backup 128m/32.
- Trading resolved config with the 7 running profiles (project `ochestration-trading`, file `docker-compose.trading.yml` only, matching the container labels):

| Service | Limit | pids | oom_score_adj | Live use now |
|---|---|---|---|---|
| momentum-rotation | 1024m | 64 | -500 | 450 MiB, 11 pids |
| paper-funding-arb | 768m | 32 | -300 | 328 MiB |
| coin-swing6 | 768m | 32 | -300 | 367 MiB |
| kr-rotation | 640m | 32 | -300 | 346 MiB |
| tick-stream | 512m | 32 | -300 | 176 MiB |
| us-rotation | 384m | 32 | -300 | 163 MiB |
| kr-opening-scan | 256m | 32 | -300 | 22 MiB |

- `memswap_limit` equals `mem_limit` everywhere, so no swap use inside containers. `crypto-tick-stream` 384m/32 and `crypto-shadow-predictor` 768m/48 (shadow diff also drops one trailing blank line, harmless).
- External files (not git-tracked for scopesentry and artex; dolphin_ai is tracked with +16 lines):
  - scopesentry: mongodb 512m/256, redis 128m/16, scope-sentry 256m/48, scan 768m/1024.
  - artex: postgres 128m/24, artex 128m/24.
  - dolphin: qdrant 512m/96, postgres 128m/16, pipeline 256m/48, chat 2048m/64 (live chat is 1.11 GiB).
- Every live usage is below its limit, with headroom of at least 30% except where noted: mysql 643/1280, api 706/2560, n8n 410/1536.
- Profiles without limits (`trading`, `kr-swing`, `us-swing`, `trx-swing`, `paper-trading` as a name) are not running, so nothing is affected today. See L2.
- Sum of limits is about 16 GiB against an 11.67 GiB Docker VM, so limits are overcommitted by design. Actual total use is about 6.3 GiB. This is informational only.

## 4. Heartbeat code (`trading/app/momentum_rotation_loop.py`)

- The change only adds `_write_heartbeat()` (json + `os.replace`, all in `try/except Exception`, so it can never raise into the loop) and wraps `run_cycle` to set an Event on completion.
- The trading logic, order paths and `run_with_timeout` semantics are unchanged. The heartbeat is written in a `finally` only when the cycle completed (including a cycle that raised internally). A timed-out cycle skips the heartbeat and logs a warning.
- Timing fits the watchdog's 600 s stale rule: `CHECK_INTERVAL` 120 s plus `CYCLE_TIMEOUT` 300 s gives a worst healthy gap of about 420 s.
- The running image has no heartbeat yet. The watchdog treats missing heartbeat as `not-yet-supported` (one notice, no alert) and switches to alerting if the file later disappears.

## Findings

### Blockers: none.

### M1 (MEDIUM, non-blocking). SKIP path deletes the live owner's lock
`LOCK_DIR` is assigned (line 85) before `mkdir` succeeds, and the EXIT trap `cleanup` does `rm -rf "$LOCK_DIR"`. A second run that hits `SKIP watchdog already running` (also the `SKIP lock takeover race` and the mkdir-failure exits) therefore deletes the first run's lock. Reproduced: live pid in `lock/owner`, run, log says SKIP, then `lock` directory is gone. A third run could then run concurrently with a restart in progress.
Impact is limited: launchd does not start overlapping instances of the same job, and the cooldown/quota are persisted before the attempt, so a concurrent run cannot cause a second restart. Only manual runs overlapping the daemon are exposed.
Suggested fix (owner should apply): set `LOCK_DIR` only after a successful `mkdir`, and on takeover.

### L1 (LOW). Timeout kills only the direct child
The perl wrapper kills only the direct child. A wrapper script around `docker` that spawns children could leave orphans, and an orphan holding a `$(...)` pipe would stall `inspect`/`exec` substitutions. Real `docker` is a single process, so no action needed unless a shell wrapper is introduced. A `setpgrp` plus `kill -TERM, -$pid` would harden it.

### L2 (LOW). Unlimited, non-running profiles
`trading`, `kr-swing`, `us-swing`, `trx-swing` services have no limits. Add them before they are ever started.

### L3 (LOW, behavior note). `--dry-run` can never show a restart decision
It uses a fresh temp state dir, so the failure streak is always 1. The branch is covered only by the tests and my stubbed runs.

### L4 (LOW). A healthcheck change not related to memory limits
mysql `interval 10s -> 30s` with `start_period`. It is reasonable and low risk, but it is outside the stated "limits" scope. It takes effect on mysql recreate.

### L5 (LOW). Slow restart attempts can trigger wake grace
A restart run lasting over about 240 s (worst case) makes the next run see a gap over 360 s. The result is a skipped cycle and counter reset, which is conservative (safe).

## Notes for deployment (no action taken here)

- (a) Non-bot recreate order from review2's deploy sequence still applies. After recreating mysql, wait for `healthy` before api. Recreate dolphin, scopesentry, artex projects with their own compose files and their own project names. Use `docker compose ... up -d --no-deps <svc>` per service and verify `docker inspect -f '{{.HostConfig.Memory}} {{.HostConfig.PidsLimit}}'`.
- (b) Bot: `docker-compose.trading.yml` with `--profile momentum-rotation`, project `ochestration-trading`, `up -d --build --no-deps trading-momentum-rotation`. The heartbeat file should appear within about 2 to 7 min. Confirm it before the 09:41Z rebalance. Env, ports and volumes are unchanged by the diff. RestartCount resets on recreate, which the watchdog tolerates (alerts only on increase).
- (c) Install the plist after the heartbeat has appeared so the first runs do not log "not yet supported". Create `~/Library/Logs` writable path and fill `__REPO__`/`__HOME__`. Start with the `PAUSE` file present if you want an observation period of alert-only behavior.
