# Docker outage prevention change set: independent review 1 (2026-11-05)

Reviewer scope: read-only review. No container, compose or launchd action was taken. Throwaway checks used only already-local images (`docker run --rm`, which does not touch existing containers). The DAILY NAS backup work is excluded.

Evidence date: 2026-11-05 ~09:00 KST (2026-11-04 23:58Z). The Docker VM has 11.67 GiB and 11 CPUs. The host has 18 GiB RAM and 17.3 of 18.4 GiB swap used. Compose files: `docker compose config -q` returns rc 0 for all 7. `cd trading && pytest tests -q` gives 173 passed (the prevention report says collection fails on pandas_ta/numba; it does not here, so that line of the report is stale or environment-specific).

## Verdicts

(a) Safe to deploy the compose changes to the live stack now? NO, not as written. The momentum-rotation change itself (limits, heartbeat) is safe to deploy outside the rebalance window. The same change set must not go to `api` (JVM heap silently shrinks, H1) or `n8n` (limit below observed peak, H5) until fixed. Several pids limits are too tight (M1).

(b) Safe to install the watchdog with auto-restart enabled? NO. Under launchd it cannot find `docker` (C1). Before the bot is rebuilt it sees no heartbeat (C2). Either condition makes it restart Docker Desktop on its own schedule. This would bounce the live 4x bot.

(c) Blockers: C1, C2, H1, H2, H3, H4, H5. Details below.

## What was proven safe

### 1. momentum_rotation_loop.py: no trading-logic change
`git diff --numstat` shows 44 added and 6 removed lines, which matches the "50 lines" claim. The hunks are:
- Imports `json` and `Path`.
- A module constant, a `_heartbeat_cycle` counter and `_write_heartbeat()`.
- A wrapper around the existing `run_with_timeout(run_cycle, ...)` call in `main()`.

Equivalence reasoning:
- `run_cycle` is still executed by `run_with_timeout` in the same daemon thread, with the same timeout and the same `on_timeout` message.
- `monitored_cycle` only adds `try/finally: Event.set()`. Exceptions still propagate from the thread to the caller unchanged.
- When `run_cycle` raises, the `finally` runs the heartbeat, then the same exception reaches the same `except Exception` traceback handler. `last_full` is not updated in that case, exactly as before.
- Orders, rebalance timing, kill logic, the `save_state` call sites and `state_seq` CAS are untouched. Transfer-guard code is untouched.
- `_write_heartbeat` calls `load_state()` only. That function is read-only and returns a fresh dict with its own `_loaded_seq`. The heartbeat never calls `save_state` and cannot interact with the CAS.
- The heartbeat temp file is `heartbeat.json.tmp`. The state file's temp is `momentum_rotation_state.tmp`. There is no collision.
- The write is atomic (`os.replace`). A failing write is caught by `except Exception`, so it cannot raise out of the loop.
- Skipping the heartbeat on a timed-out cycle changes nothing about the loop. It only prints a warning.
- The heartbeat adds a synchronous read and parse of the 2.2 MB state file plus a small write to the main thread each cycle. That is a few tens of ms.
- Tests: `tests/test_momentum_heartbeat.py` passes (2 tests).

Residual caveats are in L1 and L2.

### Compose diffs touch only limits and healthchecks
I rendered `docker compose config` for HEAD and the working tree with the same project name and `--profile '*'`, and diffed them. The only differences are added `mem_limit`, `memswap_limit`, `pids_limit` and `oom_score_adj` keys, plus the mysql healthcheck `interval` 10s to 30s and `start_period` 30s.
- Env, ports and volumes for the bot are byte-identical.
- The bot's volumes are `external: true` with fixed names. `ochestration_trading_momentum_rotation_state` exists and is mounted at `/app/data`. `ochestration_trading_control` is mounted at `/app/control`. State survives a recreate.

### oom_score_adj and limits are accepted by Docker Desktop
I ran `docker run --rm --memory 64m --memory-swap 64m --pids-limit 8 --oom-score-adj -500 --entrypoint sh postgres:16-alpine ...` on Docker 29.5.3. Results:
- `/proc/self/oom_score_adj` is `-500`.
- `memory.max` is 67108864.
- `memory.swap.max` is 0.
- `pids.max` is 8.

Negative values are accepted with no privileged flag, so the bot will not fail to start because of this key. Note that the oom score only matters for VM-level OOM. A container exceeding its own cgroup limit is killed regardless of the score. The install doc warns the score may not apply. It does apply, and that warning can be dropped.

### Mongo and MySQL healthchecks
- `bash` exists in `mongo:7.0.28` (`/usr/bin/bash`). `bash -c "echo > /dev/tcp/127.0.0.1/27017"` printed TCPOK against the running container.
- `bash` also exists in `mysql:8.4.4`. A `/dev/tcp` probe to 3306 worked.
- The Qdrant check already uses the same pattern and is healthy.
- No autoheal container exists. `depends_on: condition: service_healthy` exists only for `db-backup` and `api` on mysql, and for the ScopeSentry chain on redis and mongodb. The mongo check does not touch the bot. Unhealthy status alone restarts nothing.
- The TCP-only mongo check no longer verifies auth or ping. That is acceptable.

### Current state of running containers
None of the 24 running containers has any limit yet (Memory=0, Pids=nil, OomScoreAdj=0). So nothing is verified in production, and every observation below is from the pre-change state.

## Findings

### CRITICAL

**C1. Watchdog cannot find `docker` under launchd, so it always reports failure and restarts Docker Desktop.**
- Location: `trading/docs/launchd/com.ochestration.docker-watchdog.plist.template` has no `EnvironmentVariables`. `scripts/docker_watchdog.sh:66,72,88` call bare `docker`.
- launchd gives agents `PATH=/usr/bin:/bin:/usr/sbin:/sbin`. `docker` lives at `/opt/homebrew/bin/docker`.
- Proof: `env -i HOME=$HOME PATH=/usr/bin:/bin:/usr/sbin:/sbin WATCHDOG_STATE_DIR=... bash scripts/docker_watchdog.sh --dry-run --check-once` returns in 0.14 s with `FAIL ... reason=momentum docker inspect failed or timed out`.
- Scenario: install the plist. Checks 1 to 4 (about 6 minutes) fail. The watchdog runs `osascript quit app "Docker"` and `open -a Docker`. This repeats after the 30-minute cooldown, up to 2 times per 24 h. Each bounce SIGTERMs the live bot and every other container. The watchdog never recovers because the PATH is wrong.
- The prevention report's claim that dry-run "passes" was tested from an interactive shell with a full PATH.
- Fix: set `PATH=/opt/homebrew/bin:/usr/local/bin:/usr/bin:/bin:/usr/sbin:/sbin` in the plist (and `HOME`). Better, resolve `DOCKER_BIN` once in the script and treat "docker binary not found" as a configuration error: log it and never restart.

**C2. Heartbeat does not exist in the running bot, so the watchdog fails from the first check and restarts Docker.**
- The running container (image built 13 h ago, started 23:25Z) has no `/app/data/heartbeat.json` (verified: `ls /app/data` shows only the state file; `cat` fails).
- A real (non-dry) run now gives `FAIL ... momentum heartbeat unavailable`. My dry run logged exactly that. The heartbeat code reaches the container only after an image rebuild and a recreate. A compose `up` without `--build` keeps the old image.
- `scripts/docker_watchdog.sh:72-75` treats a missing file the same as a dead VM.
- Fix: distinguish "file missing" from "exec failed". If the container is running but the heartbeat file is absent, log WARN and do not count it as a failure, until the file has existed once (record "heartbeat_seen" in the state dir). Also order the rollout so the watchdog is installed last (see rollout).

### HIGH

**H1. API JVM max heap silently drops from about 2.9 GiB to 640 MiB.**
- Location: `docker-compose.yml` api `mem_limit: 2560m`, and `backend/Dockerfile:14` `ENTRYPOINT ["java","-jar","app.jar"]` with no `-Xmx`.
- Evidence: the running api reports `MaxHeapSize = 3133145088` (25% of host memory). Run in the same image with `--memory 2560m`, it reports `MaxHeapSize = 671088640`.
- The api process RSS is 1.22 GiB now and the cgroup peak since start is 1.40 GiB. Heap use is unknown because there is no jcmd.
- Scenario: the live set exceeds 640 MiB (a large dashboard cache or Binance display refresh). That causes GC thrash or `OutOfMemoryError` in the dashboard and trading API.
- Fix: add `JAVA_TOOL_OPTIONS: "-XX:MaxRAMPercentage=55"` (about 1.4 GiB heap) to the api service, or `-Xmx1536m`. Keep the cap at 2560m or raise it to 3072m. Measure first with `docker exec ... jcmd` or actuator `jvm.memory.used`.

**H2. Watchdog restarts all of Docker Desktop for causes that are not VM failures: intentional stop, a slow rebalance, or an API-side hang.**
- Location: `scripts/docker_watchdog.sh:66-100,136-160`.
- The staleness threshold is 120 s. The loop's own cycle timeout is 300 s (`CYCLE_TIMEOUT_SECONDS`). A timed-out cycle skips the heartbeat on purpose.
- The Binance API can be slow or erroring for 6 or more minutes. Each cycle then runs 300 s and misses the heartbeat. Four checks in a row fail (heartbeat stale), the "6 minute" window is met, and Docker Desktop restarts. This is the moment a mid-rebalance SIGTERM is most harmful. The bot has no SIGTERM handler.
- Other triggers: `docker stop` or `docker compose up --build` of the bot for maintenance that lasts 6 or more minutes (RestartCount or exec failure). There is no maintenance or disable switch.
- Fix: graduate the response.
  - Heartbeat stale but `docker info` OK: alert only, then at most `docker restart <bot>` after a long threshold (for example 15 minutes), never Docker Desktop.
  - `docker info` failing 3 or more times: Docker Desktop restart.
  - Add a flag file `$STATE_DIR/disabled` (or `maintenance`) that suppresses actions.

**H3. A stale lock directory silently disables the watchdog forever.**
- Location: `scripts/docker_watchdog.sh:47-48`. `mkdir "$STATE_DIR/lock" || exit 0` and an EXIT trap that removes it.
- SIGKILL, power loss or a kernel panic during a run leaves `lock` on disk. Every later run exits 0 with no log line.
- Fix: store the PID and start time in the lock. Break the lock if the PID is dead or the lock is older than 5 minutes. Log a line when a run is skipped.

**H4. Heartbeat age compares the container clock to the host clock.**
- Location: `scripts/docker_watchdog.sh:77-82`. `epoch` is `time.time()` inside the VM. `now` is the host `perl time`.
- The outage report already records VM clock drift after restart (`-1021 Timestamp outside recvWindow`; I saw the same message in today's logs). Any drift over 120 s, or after a Mac sleep or wake, makes age negative or large, so the check reports "stale" even though the bot is writing.
- Three consecutive failures plus 6 minutes then restarts Docker.
- Fix: compute the age inside the container in one exec, for example `docker exec C python -c "import json,time;print(time.time()-json.load(open('/app/data/heartbeat.json'))['epoch'])"`. Or compare file mtime against the container's `date +%s`.

**H5. n8n limit (800m) is below its observed peak.**
- `docker-compose.yml` n8n `mem_limit: 800m`, versus a cgroup peak of 1.10 GB (1,100,677,120 bytes) in only 30 minutes since the Docker restart.
- It will be OOM-killed under normal use and restart-loop. This is not a trading container, but the failure is certain, not speculative.
- Fix: 1536m or more. If n8n is optional, keep it at oom_score_adj +500.

### MEDIUM

**M1. pids limits are too tight, and `docker exec` and healthchecks consume pids.**
Peaks are cgroup `pids.peak` since the Docker restart, and my own `docker exec` calls inflate them slightly.

| Service | pids_limit | pids.peak | Comment |
|---|---:|---:|---|
| paper-funding-arb | 8 | 7 | Python plus threads, no headroom |
| kr-opening-scan | 8 | 7 | Same |
| db-backup | 8 | 8 | Backup is bash plus mysqldump plus gzip plus find; at the limit |
| web | 24 | 18 | nginx workers scale with 11 CPUs |
| games | 24 | 17 | |
| tick-stream | 24 | 18 | |
| kr-rotation, coin-swing6, us-rotation | 24 | 17 | |
| momentum-rotation | 24 | 18 | Steady state 11 threads |
| dolphin-pipeline | 32 | 22 | |
| scope-sentry | 32 | 22 | |
| mongodb | 96 | 62 (45 steady) | mongod uses a thread per connection; a busy scanner could exceed 96 |

- Momentum's 11 threads are the main thread plus numpy/OpenBLAS pool threads sized to the 11 VM CPUs. If you raise Docker Desktop CPUs, every Python container grows its thread count at import.
- A hung cycle leaks one daemon thread each time (pre-existing design). With a 24 limit, about 13 more leaked threads would make `Thread.start()` raise inside the loop. The loop would print tracebacks forever with no trading and no heartbeat, which the watchdog would then turn into a Docker Desktop restart.
- Fix: use 32 for the small services, 48 to 64 for momentum, web, and anything with a thread pool, and 192 for mongodb. Optionally set `OPENBLAS_NUM_THREADS=1` for the Python bots in a later change.
- `scopesentry-scan` pids_limit 1024 versus actual peak 37 is fine. The limit is a fork-bomb guard. The 1.5 GiB memory cap versus 491 MB peak is fine, but a Chrome screenshot burst may exceed it. That is acceptable for a lab service (restart:always gives a restart backoff).

**M2. Other limits versus observed usage and peaks (since the Docker restart, so the history is short).**

| Service | Limit | Now | Peak | Verdict |
|---|---:|---:|---:|---|
| momentum-rotation | 1024m | 422 MiB | 500 MB (cache included; anon 378 MB) | OK. The 14-day ranking fetches 1d bars for about 47 symbols sequentially, so the rebalance adds little. Margin about 2x. A future load of state grows with `equity_history` (13,161 points, 2.2 MB). |
| kr-rotation | 640m | 285 MiB | 420 MB | OK |
| us-rotation | 384m | 162 MiB | 179 MB | OK |
| coin-swing6 | 768m | 367 MiB | 427 MB | OK |
| paper-funding-arb | 768m | 328 MiB | 364 MB | OK |
| trading tick-stream | 512m | 130 MiB | 152 MB | OK |
| crypto-tick-stream | 384m | 171 MiB | 226 MB | OK |
| shadow-predictor | 832m | 404 MiB | 470 MB | OK |
| mysql | 1280m | 584 MiB | 630 MB | OK. The innodb buffer pool could not be queried (root login from the shell failed), so unverified. |
| dolphin-chat | 2560m | 1.11 GiB | 1.76 GB | OK |
| dolphin-qdrant | 640m | 310 MiB | 486 MB | Tight if indexing runs. 768m advised. |
| scopesentry-mongodb | 640m | 301 MiB | 480 MB | Tight during scans. 768m to 1024m advised. |
| n8n | 800m | 397 MiB | 1.10 GB | Too low (H5) |
| api | 2560m | 1.23 GiB | 1.40 GB | The cap fits, but the heap does not (H1) |

No limit on a trading bot looks capable of an OOM kill at rebalance time. This is a judgment from short-history peaks and code reading, not a measured rebalance peak. `memory.peak` was captured only since 23:25Z and no rebalance has run in that window. The next rebalance is at 2026-11-05T09:41:30Z (18:41 KST). To confirm headroom, record `memory.peak` and `pids.peak` right after that rebalance before tightening anything further.

**M3. Sum of caps (17.4 GiB) versus the 11.67 GiB VM.**
- The sum is Ochestration 11,232 MiB plus dolphin 3,648 plus scopesentry 2,496 plus artex 448 = 17,824 MiB. Current actual usage is about 7 GiB.
- This does not defeat the main purpose. A cap bounds a leak inside one container, which is how the mongosh leak would have been contained: mongodb pids 96 and 640m would have stopped it from growing to the VM limit. Caps are ceilings, not reservations. Per-container cgroup OOM kills ignore oom_score_adj.
- The sum does mean a simultaneous peak of lab containers can still push the VM into a global OOM. In that case the kernel kills the highest score first (+500 lab, then 0, then -300 trading, then -500 bot), which is the right order.
- The real extra risk is the host. Swap is 17.3 of 18.4 GiB used and the VM takes 65% of RAM. Swap exhaustion on the host would stall the VM no matter what the limits are. The watchdog's swap alert will therefore fire every 30 minutes today.
- Suggested combination:
  - Keep the bot at -500. Keep other trading and infra containers at -300. Keep lab at +500.
  - Cut lab headroom where actual use is low: scopesentry-scan 1536m to 1024m, dolphin-chat 2560m to 2048m (peak 1.76 GB). That brings the lab sum down by about 1 GiB.
  - Do not use -1000 (the OOM-immune value) for any container.
  - Reduce the Docker Desktop VM RAM or free host memory; the swap pressure is the larger lever.

**M4. Docker Desktop restart action is racy and unverified.**
- Location: `scripts/docker_watchdog.sh:153-160`. `osascript quit app "Docker"` is followed immediately by `open -a Docker`. There is no wait for the app to exit. If the quit is slow, or the app is wedged, `open -a` only activates the still-running app. No restart happens, but the action is logged and counted against the 2-per-24h budget.
- Also the script never checks that Docker came back. A wedged VM may ignore the AppleScript quit.
- Fix: poll until the Docker process is gone (up to 60 s), then `open -a`, then poll `docker info` up to a few minutes. If quit fails, alert and do not count it.

**M5. State handling in the watchdog.**
- `--dry-run` is not side-effect free. It creates `$STATE_DIR` (default `~/Library/Application Support/ochestration-watchdog`) and writes `failure_count`, `failure_since_epoch`, `previous_restart_count`, `last_swap_alert_epoch` and the log. My default-directory dry run left `failure_count=1`; I removed it afterwards. Repeated dry-runs against the default directory therefore pre-load the failure counter for a later real run. The install doc's `mktemp -d` example is correct, but `--dry-run` without it is hazardous. Fix: dry-run should not write counters (or should use a temp dir by default).
- State files are written with plain `printf >` (not atomic) and `last_restart_file` and `last_swap_alert_file` are not validated. A truncated or garbage file turns `((now - last_restart < 1800))` into a syntax error or 0, which silently drops the 30-minute cooldown. The 24-hour cap (`restart_epochs`) still holds because garbage lines are skipped, but a deleted state directory resets all limits.
- The 10-minute post-restart rule at line 150 is unreachable behind the 30-minute cooldown, and it also sits after the DRY-RUN branch.
- `heartbeat` empty but exec successful (empty file) is treated as healthy (line 76).
- `OOMKilled` is read from container state. Whether it resets on the next start is unverified here. If it stays true after one past OOM, the watchdog is permanently unhealthy and keeps restarting Docker (2 per day). Fix: alert on a transition only (compare with a stored value).

**M6. No `.dockerignore` for the trading build.**
`trading/` is 1.9 GB (1.8 GB is `docs/`, with untracked research pickles and npz). `Dockerfile` only copies `requirements.txt` and `app`, but the full directory is the build context. A rebuild of the bot streams or hashes about 1.9 GB through the VM while it is already under memory pressure. Fix: add `trading/.dockerignore` excluding `docs`, `data` and similar before rebuilding.

### LOW

- **L1.** `_write_heartbeat` runs in the main loop thread. A stuck or very slow disk would delay the 5 s control polling (manual flat and kill commands). The path is a named volume on the VM disk, so this is a theoretical risk. Putting the write in `try` does not bound its duration.
- **L2.** The heartbeat is written even when `run_cycle` raised (the `finally` sets the event). So "alive" means "the loop ran", not "the cycle succeeded". A corrupt state file makes `load_state` fail inside the heartbeat, which is swallowed, and then the heartbeat stops while the cycle continues. The heartbeat does not need `load_state` at all. Dropping `state_seq` removes the extra 2.2 MB parse and this coupling.
- **L3.** `docker_watchdog_install.md` mentions `SCOPESENTRY_MONGODB_CONTAINER`, which the script does not use. The `oom_score_adj` warning in the docs can be removed (verified working).
- **L4.** A redis healthcheck in ScopeSentry puts `-a <password>` in argv, so the password is visible in `docker inspect` (pre-existing; I did not copy it here). `REDIS_PASSWORD` is also visible in the process list.
- **L5.** `osascript display notification` from a LaunchAgent may be silently suppressed by notification permissions. There is no off-box channel, so a failing watchdog can go unseen when the user is away. Consider a Telegram or webhook channel if one is wanted. The memory notes show none exists in code.
- **L6.** The launchd plist has no `ProcessType`, `Nice` or `ThrottleInterval`. It runs `/bin/bash` out of `~/Desktop/...`, so macOS file-protection (TCC) prompts or denials for the Desktop folder should be checked after install (`~/Library/Logs/ochestration-watchdog-launchd.error.log`). `plutil -lint` on a filled copy returned OK.
- **L7.** `run_timeout` kills only the direct child. A grandchild that holds the stdout pipe inside `$(...)` could delay capture; the actual callers (`docker`, `osascript`, `sysctl`, `date`) are single processes, so this is theoretical. Perl alarm handling itself is correct: TERM, 0.5 s, KILL, `waitpid`, exit 124 (tested with a TERM-ignoring child: returned in 2.5 s).

## Test gaps

- No test that `main()` skips the heartbeat on a timed-out cycle, or that an exception in `run_cycle` still propagates after the wrapper.
- No test that an unwritable heartbeat directory leaves `main()` running (the existing test only calls `_write_heartbeat`).
- No tests for `scripts/docker_watchdog.sh` at all: PATH, missing heartbeat, stale lock, garbage state files, restart gating (3 fails, 6 min, 30 min cooldown, 2 per 24 h), dry-run side effects. A bats-style test with a fake `docker` on PATH would cover all of these.
- No post-deploy assertion script: `docker inspect` should be checked for Memory, PidsLimit, OomScoreAdj and Health on every recreated container.

## Safe deploy sequence

Preconditions: fix C1, C2, H1, H5, M1 first. Avoid the window 09:00Z to 11:00Z on any rebalance day (next rebalance 2026-11-05T09:41:30Z). Never run a bare `docker compose up -d`; always target one service with `--no-deps`.

1. Save a rollback anchor: `docker tag ochestration-trading-trading-momentum-rotation:latest ochestration-trading-trading-momentum-rotation:pre-heartbeat` (current image id 8d660b9cf1d1). Record `docker inspect` output of the bot's Env, Mounts and ports for later comparison.
2. Add `trading/.dockerignore` (M6), then build the bot image only (no recreate): `docker compose -p ochestration-trading -f docker-compose.trading.yml --profile momentum-rotation build trading-momentum-rotation`.
3. Recreate lab and auxiliary stacks one at a time, checking `docker inspect` (Memory, MemorySwap, PidsLimit, OomScoreAdj, Health) after each:
   - dolphin_ai, artex, scopesentry (bind-mounted data is preserved);
   - shadow predictor, crypto tick-stream;
   - n8n and games (after raising n8n).
4. Recreate the non-bot trading services (paper-funding-arb, kr/us rotation, coin-swing6, kr-opening-scan, tick-stream) with `-p ochestration-trading -f docker-compose.trading.yml up -d --no-deps <service>`. These are paper or capture bots.
5. Recreate mysql, then api (only after H1 is fixed), web and cloudflared, in the main project `ochestration`. Check the dashboard and the mysql healthcheck.
6. Recreate the live bot last: `docker compose -p ochestration-trading -f docker-compose.trading.yml --profile momentum-rotation up -d --no-deps --no-build trading-momentum-rotation`. Use the same project name `ochestration-trading` and the same file path, so the compose labels match. The volumes are external with fixed names, so state is kept regardless. Expected downtime is about 10 to 30 s (the Python process takes SIGTERM, then SIGKILL after 10 s, since there is no handler). Do this when no order is in flight (not within 30 minutes of the rebalance time, and not during a kill or guard event).
7. Verify the bot: `state_seq` advances in `/app/data/momentum_rotation_state.json`; `/app/data/heartbeat.json` appears and updates about every 20 s; `docker inspect` shows Memory=1073741824, PidsLimit=24 (or the new value) and OomScoreAdj=-500; there is no `OOMKilled`; the logs show no `[상태저장 거부]`.
8. Only then install the watchdog (after C1, C2 and H2 are fixed): fill the plist, run `--dry-run` with `WATCHDOG_STATE_DIR=$(mktemp -d)` under `env -i PATH=/usr/bin:/bin:/usr/sbin:/sbin`, and start with an alert-only mode for a few days before enabling auto-restart.

## Rollback

- Bot: `docker tag ochestration-trading-trading-momentum-rotation:pre-heartbeat ochestration-trading-trading-momentum-rotation:latest`, then `git checkout -- docker-compose.trading.yml trading/app/momentum_rotation_loop.py`, then `docker compose -p ochestration-trading -f docker-compose.trading.yml --profile momentum-rotation up -d --no-deps --no-build --force-recreate trading-momentum-rotation`. State is unaffected.
- Other services: `git checkout --` the compose files (Ochestration), restore the ARTEX and dolphin_ai compose files from backup (they have no git history, so copy the originals before editing), then `up -d --no-deps` each service.
- Watchdog: `launchctl bootout "gui/$(id -u)" ~/Library/LaunchAgents/com.ochestration.docker-watchdog.plist`, then remove the plist and the state directory `~/Library/Application Support/ochestration-watchdog`.

## Cleanup done by this review

I removed `~/Library/Application Support/ochestration-watchdog`, which my default-directory dry run created. Temporary files were written only to the session scratchpad.

## Developer resolution — 2026-11-05

### Finding status

| Finding | Status | Resolution / remaining limit |
|---|---|---|
| C1 | Fixed | Watchdog owns its PATH, rejects missing or non-executable Docker CLI as CONFIG ERROR, alerts, exits without restart. Tested in an env-i process with an invalid CLI path because this host's fixed Homebrew path does contain Docker. |
| C2 | Fixed | Missing heartbeat before it has ever existed is `not-yet-supported` with one-time notice. It cannot increment engine failure state or restart Docker. |
| H1 | Fixed | API gets `JAVA_TOOL_OPTIONS=-Xmx1536m`; Dockerfile launches `java -jar app.jar`, so JVM reads the option. API cap remains 2560 MiB. |
| H2 | Fixed | Only three consecutive failed/timed-out `docker info` checks can enter the Docker Desktop restart path. Bot, OOM, RestartCount and swap events alert only. PAUSE suppresses bot checks/alerts. |
| H3 | Fixed | Lock owner PID and epoch are recorded; dead PID or age >300s is recovered with a log entry. |
| H4 | Fixed | Heartbeat epoch and `date +%s` equivalent are obtained from one container exec; stale threshold is 600 seconds. |
| H5 | Fixed | n8n cap is 1536 MiB, above the review's 1100 MiB peak. |
| M1 | Fixed | Tight pids caps raised as specified; additional near-peak web, games, rotations, tick-stream, ScopeSentry app and dolphin pipeline caps raised. |
| M2 | Partial / runtime unverified | Current usage could not be read because Docker socket access was denied. Several lab caps were reduced to make the explicit 4 GiB +500 total; chat, Qdrant, MongoDB, scanner and shadow are now below review-observed peaks and can OOM. |
| M3 | Cap sum fixed; service-safety tradeoff | +500 configured ceilings total exactly 4096 MiB. This is not reserved memory. Achieving the target forced known peak services below observed usage; see prevention report table. Do not deploy these lab caps without human acceptance of the service failures they can cause. |
| M4 | Fixed | Desktop process exit is polled up to 60 seconds; restart is aborted if process remains. Engine readiness is polled up to 120 seconds and outcome is logged. |
| M5 | Fixed | Dry-run uses and removes a private temp state dir; persisted integers are validated; state values are atomically replaced; heartbeat empty/invalid is alert-only; OOMKilled alerts only on transition; unreachable 10-minute branch removed with the engine-only policy. |
| M6 | Fixed | `.dockerignore` files cover trading, backend, frontend and game-server contexts. Context paths and Dockerfile COPY/ADD instructions were read without building. |

### Verification and action boundary

- Watchdog and heartbeat tests: 8 passed. Full requested pytest collection did not complete: 7 existing modules fail during collection because installed `pandas_ta` triggers Numba `no locator available` for cached `fibonacci` in site-packages.
- `docker compose -f <file> config -q`: all 7 files exit 0. Existing obsolete `version` warnings remain for ScopeSentry and dolphin_ai.
- `bash -n scripts/docker_watchdog.sh` and `plutil -lint` on a filled plist copy pass.
- `docker stats --no-stream` was attempted read-only and failed with Docker socket permission denied. Current memory use, heartbeat presence and live cap fit remain unverified.
- No daily NAS backup script, archive code, NAS test or NAS doc was edited. No commit, push, build, deploy, restart, `docker compose up` or `down` occurred.

### Human deployment sequence and rollback

The next rebalance timestamp is 2026-11-05T09:41Z. Recreate the live momentum bot last and outside its rebalance window, only after the human confirms no order/guard/kill event is in flight. Apply and verify small lab groups first; the 4 GiB lab caps contain known below-peak limits and may cause OOM. Apply main API only with `JAVA_TOOL_OPTIONS` present, then non-momentum trading services, then the bot last. A human must run any Compose up/down command; none was run in this work. Verify each recreated service's memory, swap, PID, OOM score and health, then verify the bot state volume and heartbeat before installing launchd.

For rollback, restore the saved Compose copies and previous bot image/source. Keep external trading state volumes intact. Disable the watchdog with `launchctl bootout` and remove its plist. Roll back `.dockerignore` only if the next context requires those files. Full per-container limits and exact commands are in `docker_prevention_2026-11-05.md`.
