# Docker prevention RE-REVIEW 2 (2026-11-05)

Read-only review. Time at review: about 2026-11-05T00:55Z (09:55 KST). Next momentum rebalance 09:41Z, so there are about 8h45m of margin.
Scope: `scripts/docker_watchdog.sh`, the compose diffs, the `.dockerignore` files, and the heartbeat diff. Excluded: daily NAS backup work.
Methods: static read, stub experiments (`env -i`, PATH=/usr/bin:/bin:/usr/sbin:/sbin, scratch state dirs), `docker stats`, `docker inspect`, `docker compose config`, and throwaway `docker run --rm` of existing images for the JVM flags and the oom_score_adj check. No Docker restart, no `up/down`, no launchd install.

## Verdicts

| Question | Verdict |
|---|---|
| (a) Recreate non-bot containers (api, web, mysql, n8n, lab) with the new compose | YES. Strongly recommended: raise n8n to 1536m first (M1). Recommended: raise the pids limits (M2). |
| (b) Recreate the bot container (momentum-rotation) | YES, outside the rebalance window (now is fine, ~8h45m margin). Run `build` as a separate step first. |
| (c) Install the watchdog with auto-restart for a dead engine only | NO, not as written. H1 (wrong process name) makes the restart sequence race itself. H2 (stale failure counter) is a false-positive path on wake. Install after fixing both, or install with restart disabled (alert-only) until then. |
| (d) Blockers | Watchdog only: H1 and H2. No blocker for the compose changes or the bot recreate. |

## Prior findings, verified

| ID | Status | Evidence |
|---|---|---|
| C1/C2 (restart only on dead engine) | Fixed in logic. See H1/H2 for new problems. | Only the `docker info` failure branch (L99-152) reaches the restart code. Stale heartbeat, OOM, restarts, and swap only log and notify. |
| Own PATH and missing-docker config error | Fixed | L5 sets PATH. L61-67 logs CONFIG ERROR and exits 0 when docker is missing. Covered by tests. An `env -i PATH=/usr/bin:/bin` run still finds docker through the script's own `/usr/local/bin`. |
| 3x consecutive failures, 10s timeout | Fixed, with caveats H2 and M3 | Experiment: failures 1, 2, 3 produced a restart on the third run. A 12s `docker info` is treated as a failure at 10.7s. |
| Container-clock heartbeat age >= 600s | Fixed | L179-194 compares the in-container `time.time()` with the heartbeat epoch. |
| PAUSE file | Fixed, but it covers bots only | See L2. |
| Stale lock takeover | Fixed | L71-84 takes over a dead PID or a lock older than 300s. |
| Dry-run isolation | Fixed | The dry-run uses a mktemp state dir and removes it. The real state dir was untouched. See L3. |
| api JAVA_TOOL_OPTIONS | Verified (see "Experiments") | |
| pids/mem caps | Applied, see the table below | |
| .dockerignore | Verified | See "Dockerignore vs COPY". |
| Tests | `cd trading && pytest tests -q` gives 189 passed. `bash -n` OK. `plutil -lint` on a filled plist copy: OK. `docker compose config -q` is clean on docker-compose.yml, crypto-data, shadow, trading, scopesentry, artex-docker, and dolphin_ai. The last two print only the obsolete `version` warning. | |

## NEW / UNFIXED findings (severity-ranked)

### H1 (HIGH). `pgrep -x 'Docker'` never matches, so the quit/open race is not bounded
- Where: `scripts/docker_watchdog.sh:122-131`. The tests stub `pgrep` with `exit 1`, which hides the bug (`trading/tests/test_docker_watchdog.py` lines ~44-48).
- Evidence: on this host the process is named `Docker Desktop` (PID 86798). `pgrep -x Docker` returns rc=1 while Docker is running. Other processes are `com.docker.backend`, `com.docker.virtualization`, and `com.docker.build`.
- Experiment: with the real `/usr/bin/pgrep` and stub osascript/open/docker (info always failing), the log shows:
  - `ACTION restarting`
  - `Docker Desktop open command accepted`, within the same second
  - `ERROR engine did not return within 120s`
  - `act.log` shows `quit app "Docker"` followed immediately by `open -a Docker`.
- Scenario: the "wait up to 60s for exit" loop passes on its first iteration. `open -a Docker` hits the still-quitting app, so it is a no-op or races with the quit. The app can end up quit and never reopened. The attempt is still counted, so there is a 30-minute cooldown and a maximum of 2 per 24h. The engine can stay down for hours.
- Fix: wait on the real names. For example, loop until both `pgrep -x 'Docker Desktop'` and `pgrep -f 'Docker.app/Contents/MacOS/com.docker.(backend|virtualization)'` return nothing. Add a test that stubs `pgrep` to say "alive" for N polls, then "gone", and asserts `open` is only called after that.

### H2 (HIGH/MEDIUM). Failure streak is not time-bounded, so a stale count plus one slow `docker info` triggers a restart
- Where: L95-106. `failure_since` is written but never used in the decision.
- Experiment: with `engine_failure_count=2` left over from long ago (since=1000) and a single failing run, the result was `consecutive=3` followed by `ACTION restarting Docker Desktop`.
- Scenario (false positive):
  1. Docker is slow or being quit for 2 consecutive runs.
  2. The Mac then sleeps, or the launchd job is unloaded or logged out.
  3. On wake, the first `docker info` is not ready within the 10s timeout (VM resume).
  4. That is failure #3, so Docker Desktop is restarted by the watchdog even though there was a single failure after wake. This kills every container.
- Also: every run of the first minutes after login or boot counts. RunAtLoad plus a 120s interval means about 4 minutes of Docker Desktop startup is enough for 3 failures. A cold start with a large state can approach that.
- Fix:
  - Reset the streak if the last failure is older than about 3x the interval (360s).
  - Require `now - failure_since >= 240s`, in addition to 3 failures.
  - Skip, or double the threshold, when the system uptime or wake time is under 5 minutes. For example, the `kern.waketime` sysctl.
  - Treat "Docker Desktop is currently starting" as not-dead. For example, the backend process exists but the socket is missing for less than 5 minutes after the process start time.
  - Add tests for the stale count and for a sleep gap.

### M1 (MEDIUM). n8n cap 1280m leaves about 12% headroom over the observed 1.10 GiB peak
- Where: `docker-compose.yml`, n8n service (`mem_limit: 1280m`).
- Current use is 400 MiB. The peak was 1.10 GiB. With memswap equal to the memory limit, the container is OOM-killed at the first excursion above 1.25 GiB and loses its in-flight workflows. restart:unless-stopped brings it back, but jobs are lost.
- Fix: `mem_limit` and `memswap_limit` 1536m. Optionally set `NODE_OPTIONS=--max-old-space-size=1024`. The VM still has headroom: current total use is about 7.3 GB of 11.67 GiB.

### M2 (MEDIUM). Some pids limits are tight against the thread model
- api: `pids_limit: 128`, observed 57 at idle. application.yml has no tomcat or hikari overrides, so the default Tomcat max is 200 threads plus the JVM's own threads. A burst can hit `OutOfMemoryError: unable to create native thread`. Raise to 256.
- mysql: `pids_limit: 96`, observed 46 (about 40 background threads plus one per connection; the default `max_connections` is 151). Raise to 192.
- n8n: `pids_limit: 48`, observed 20. Task runners and Code nodes fork. Raise to 96.
- Trading bots with `pids_limit: 32` against 11-12 observed are fine. momentum has 64 against 12 observed (OK). kr-opening-scan is 1 against 32 (OK).

### M3 (MEDIUM). Restart attempt is recorded only at the end, and the abort path is never recorded
- Where: L120-148.
- The abort path ("Docker process did not exit within 60s", L128-129) writes nothing. The cooldown is not set, so every 120s run repeats the quit request and a 60s wait. If the watchdog is killed mid-sequence (launchd exit timeout, logout), no cooldown exists at all.
- A manual run during the sequence also takes over the lock after 300s. A restart sequence can take up to about 12 minutes (60 x (10+2) seconds for the engine wait). The lock takeover threshold (300s) is shorter than the maximum restart duration.
- Fix: write `last_restart_epoch` and append to `restart_epochs` BEFORE issuing the quit. Count aborts too (or at least apply a shorter 10-minute cooldown). Refresh the lock owner timestamp during the loop.

### M4 (MEDIUM, design). No way to pause engine auto-restart
- PAUSE only suppresses bot checks (L157-159). If you quit Docker Desktop on purpose (RAM relief, update, maintenance), the watchdog starts it again after about 4 minutes.
- Fix: add `PAUSE_ENGINE` (or `RESTART_DISABLED`). Alternatively, treat "the Docker Desktop process is absent entirely" as alert-only. Document it in `docker_watchdog_install.md`.

### M5 (MEDIUM, info). Host swap is nearly exhausted right now
- `sysctl vm.swapusage`: 17.6 GiB used of 18.0 GiB (96%).
- The watchdog's swap alert (>12 GiB) will fire on the first run and then every 30 minutes. That is expected noise, but the host really is under memory pressure.
- The new caps reduce container sprawl. Sum of caps is about 15.7 GiB against a VM of 11.67 GiB, deliberately overcommitted. Sum of observed use is about 7.3 GB. Lab containers have oom_score_adj +500 and the bots and api have -300/-500, so lab is killed first. That ordering is good.
- Consider lowering the lab caps or stopping unused lab stacks to relieve host swap. This is outside the scope of the diff.

### L1-L5 (LOW)
- L1: unset `HOME` makes the script die with `unbound variable` at L9 (rc=1). launchd sets HOME through the plist, so this is only a manual-run issue. Use `${HOME:-/var/root}` or require `WATCHDOG_STATE_DIR`.
- L2: PAUSE also silences bot-related alerts (documented).
- L3: `--dry-run` prints nothing to the operator, because the log and notifications go to a state dir that is deleted on exit. Print the log to stderr in dry-run.
- L4: `watchdog.log` and `restart_epochs` are unbounded. Add rotation or trimming.
- L5: unlimited services remain in `docker-compose.trading.yml`: `trading`, `trading-kr-swing`, `trading-us-swing`, and `trading-trx-swing`. None are running now. If `trx-swing` (the real-capital bot per the migration note) is restarted later, it has no mem or pids cap. Add caps before using it.
- Note: the heartbeat is written in a `finally` when the cycle thread finished, even if `run_cycle` raised. It means "loop alive", not "cycle healthy". A cycle that raises every time will not alert on heartbeat. This is acceptable but worth knowing.
- Process: `scripts/docker_watchdog.sh`, `trading/docs/launchd/`, and the new tests are untracked. Commit them with the fix. The new `.dockerignore` files for game-server and trading are also untracked (see the git status).
- Hygiene: `docker inspect` on the api container prints all of its environment, including live API keys, tokens, and the admin password. They are not reproduced here. Be careful when pasting inspect output.

## Experiments

JVM (api):
- The image `ochestration-api` has `Entrypoint=["java","-jar","app.jar"]` and `Cmd=null`. There is no `JAVA_OPTS` and no `-Xmx` in the Dockerfile (`backend/Dockerfile:14`) and no wrapper script, so there is no conflict.
- `docker run --rm --memory 2560m -e JAVA_TOOL_OPTIONS=-Xmx1536m --entrypoint java ochestration-api -XX:+PrintFlagsFinal -version` printed `Picked up JAVA_TOOL_OPTIONS: -Xmx1536m` and `MaxHeapSize = 1610612736` (1.5 GiB).
- Without the variable, `MaxHeapSize = 671088640` under a 2560m cgroup (25% ergonomic). So under the 2560m cap, Xmx1536 is actually a raise of the max heap from 640 MiB, not a cap.
- Non-heap headroom is 2560 - 1536 = 1024 MiB. Observed total is 1.23 GiB, peak 1.4 GiB. That is safe.
- The "Picked up JAVA_TOOL_OPTIONS" line appears on stderr and is harmless.

oom_score_adj:
- Negative values are accepted. `docker run --rm --oom-score-adj -500 --memory 64m --memory-swap 64m --pids-limit 8` printed `-500`, `67108864`, and `8` from `/proc/self/oom_score_adj`, `memory.max`, and `pids.max`.

Resolved trading config (`docker compose -p ochestration-trading --profile <all 11> -f docker-compose.trading.yml config`):
- Bare `config --services` prints nothing without profiles, as expected.
- With all profiles, the limits and `oom_score_adj` are applied to the 7 bot services (see the table).

Watchdog branches (stubs):

| Case | Result |
|---|---|
| 3 consecutive failing `docker info` runs | Restart on the third (race in H1). |
| `docker info` takes 12s | Counted as a failure at 10.7s. A merely slow (not hung) call during VM boot or wake is a failure (see H2). |
| `engine_failure_count=2` already on disk, then one failure | Restart (H2). |
| `last_restart_epoch` in the future (clock moved back) | "RESTART withheld: cooldown". Fails safe, but it can block recovery until the clock catches up. |
| Clock jumped forward | The 30-minute cooldown and the 24h window shrink in effect. The max-2 guard can be bypassed. Low risk. |
| docker missing in PATH | CONFIG ERROR, exit 0, no restart (unit-tested). |
| Real engine up, `--dry-run` under `env -i` | rc=0, nothing printed, no real state dir created or changed. |
| No `HOME` | `unbound variable`, rc=1 (L1). |

## Caps vs observed use (docker stats --no-stream now)

| Container | Cap | Use now | Ratio | pids cap / observed | Verdict |
|---|---|---|---|---|---|
| momentum-rotation | 1024m | 450 MiB | 2.3x | 64 / 12 | OK |
| kr-rotation | 640m | 307 MiB | 2.1x | 32 / 11 | OK |
| us-rotation | 384m | 163 MiB | 2.4x | 32 / 11 | OK |
| coin-swing6 | 768m | 367 MiB | 2.1x | 32 / 11 | OK |
| paper-funding-arb | 768m | 328 MiB | 2.3x | 32 / 1 | OK |
| tick-stream (trading) | 512m | 142 MiB | 3.6x | 32 / 12 | OK |
| kr-opening-scan | 256m | 21 MiB | 12x | 32 / 1 | OK |
| crypto-tick-stream (crypto-data) | 384m | 173 MiB | 2.2x | 32 / 14 | OK |
| crypto-shadow-predictor | 768m | 404 MiB | 1.9x | 48 / 22 | OK |
| api | 2560m (Xmx1536) | 1.23 GiB (peak 1.4) | 2.0x | 128 / 57 | OK on memory; pids M2 |
| mysql | 1280m | 604 MiB | 2.1x | 96 / 46 | OK on memory; pids M2 |
| n8n | 1280m | 400 MiB (peak 1.10 GiB) | 1.16x at peak | 48 / 20 | Raise to 1536m (M1), pids M2 |
| web | 128m | 10 MiB | | 32 / 12 | OK |
| games | 128m | 64 MiB | 2.0x | 32 / 11 | OK |
| cloudflared | 128m | 55 MiB | 2.3x | 32 / 16 | OK |
| db-backup | 128m | 1.3 MiB | | 32 / 2 | OK |
| dolphin chat | 2048m | 1.11 GiB | 1.8x | 64 / 27 | OK |
| dolphin qdrant | 512m | 310 MiB | 1.65x | 96 / 44 | OK |
| dolphin pipeline | 256m | 159 MiB | 1.6x | 48 / 16 | OK (tightest of the lab set) |
| dolphin postgres | 128m | 26 MiB | | 16 / 7 | OK |
| scopesentry-scan | 768m | 454 MiB | 1.7x | 1024 / 15 | OK |
| scopesentry-mongodb | 512m | 313 MiB | 1.6x | 256 / 45 | OK |
| scope-sentry | 256m | 97 MiB | | 48 / 15 | OK |
| scopesentry-redis | 128m | 22 MiB | | 16 / 5 | OK |

The running containers still have mem=0 and pids=nil (no limits applied yet). Everything above takes effect only when containers are recreated, or via `docker update` for memory and pids.

## Compose diffs vs HEAD

- `docker-compose.yml`: only `mem_limit`, `memswap_limit`, `pids_limit`, and `oom_score_adj` added on each service. Also the mysql healthcheck (`interval` 10s to 30s, `start_period: 30s` added) and `JAVA_TOOL_OPTIONS: "-Xmx1536m"` on api.
- `docker-compose.crypto-data.yml`, `docker-compose.trading.yml`, `trading/shadow_predictor/docker-compose.shadow.yml`: only limit and oom keys added (shadow also lost a trailing blank line). Bot env, ports, and volumes are identical. I checked this by reading the full diffs.
- `dolphin_ai/docker-compose.yml`: only limit and oom keys. The scopesentry and artex-docker compose files are not git repos; their limit keys are present and `config -q` is clean.
- Note: the mysql healthcheck change means compose will treat mysql as changed and recreate it (see the deploy sequence).

## Heartbeat code (`git diff trading/app/momentum_rotation_loop.py`)

- The change is only an import addition, `_write_heartbeat()` (an atomic temp file plus `os.replace`, wrapped in try/except so failures only print), and a wrapper around the existing `run_with_timeout(run_cycle, ...)`. The wrapper sets an Event in `finally` and writes the heartbeat afterwards. The trading logic is untouched.
- A hung cycle (timeout) leaves the event unset, so there is no heartbeat refresh and the watchdog sees staleness. That is correct.
- The check interval is 15s (compose env), so the heartbeat updates about every 15-20s, against a threshold of 600s.
- `/app/data` in the container is the state volume, owned by `app`, and writable (touch test OK). The running image predates the heartbeat code (created 2026-11-04T10:40Z), so after the recreate, check that a heartbeat appears. Until then the watchdog reports `not-yet-supported`.
- Tests: `test_momentum_heartbeat.py` passes (part of the 189).

## Dockerignore vs COPY (read-only)

| Build | COPY / ADD | Ignored by | Result |
|---|---|---|---|
| backend | `pom.xml`, `src`, then `target/*.jar` from the build stage | `target`, `.env`, `*.log`, `.git`, `.DS_Store` | OK |
| frontend | `package.json package-lock.json`, `COPY . .`, `nginx.conf`, `dist` from the build stage | `node_modules`, `dist`, `.env`, `.git`, `.DS_Store`, `coverage`, `*.log` | OK |
| game-server | `index.mjs`, `lib` | `.git`, `.DS_Store`, `node_modules`, `coverage`, `*.log`, `tests`, `*.md` | OK. `lib/` has only two `.mjs` files. |
| trading (bots and crypto-data, context `./trading`) | `requirements.txt`, `app` | `**/.git`, `docs/`, `data/`, `*.npz`, `*.pkl`, `*.pickle`, `*.log`, ... | OK. In `.dockerignore`, `docs/`, `data/`, and `*.pkl` are root-anchored. `app/` contains none of those files. The research modules that read `docs/*.json` are not part of the production entrypoints. |
| shadow (context `trading/`) | `shadow_predictor/requirements.txt`, `archive_store.py`, `core.py`, `main.py` | none of these ignored | OK |

## Deploy sequence (exact commands)

Pre-flight (read-only):
```bash
cd /Users/user/Desktop/CODE/Ochestration
date -u   # must be well before 2026-11-05T09:41Z (next rebalance); skip if inside +-20 min
docker compose -p ochestration -f docker-compose.yml config -q && docker compose -p ochestration-trading --profile momentum-rotation -f docker-compose.trading.yml config -q
docker inspect ochestration-trading-trading-momentum-rotation-1 --format '{{.Image}}'   # note for rollback
docker image inspect ochestration-api --format '{{.Id}}'                                  # note for rollback
```
Apply the M1 edit first (n8n 1536m) and, optionally, the M2 pids edits. Then:

Step 1: web, games, cloudflared, db-backup, n8n (no dependencies; project `ochestration`, no `-p ochestration-trading`):
```bash
docker compose -p ochestration -f docker-compose.yml up -d --no-deps --no-build web games cloudflared db-backup n8n
```
Step 2: mysql (about a 10-30s DB blip; the api reconnects through Hikari). Wait for healthy:
```bash
docker compose -p ochestration -f docker-compose.yml up -d --no-deps --no-build mysql
until [ "$(docker inspect -f '{{.State.Health.Status}}' ochestration-mysql-1)" = healthy ]; do sleep 5; done
```
Step 3: api (image unchanged, so there is NO `--build`. This only recreates it with the new limits and JAVA_TOOL_OPTIONS):
```bash
docker compose -p ochestration -f docker-compose.yml up -d --no-deps --no-build api
```
Step 4: the crypto-data stack (project `ochestration` with two files, since its config file label is `docker-compose.crypto-data.yml`) and the other lab stacks, each from their own directory:
```bash
docker compose -p ochestration -f docker-compose.crypto-data.yml up -d --no-deps --no-build crypto-tick-stream
docker compose -p shadow_predictor -f trading/shadow_predictor/docker-compose.shadow.yml up -d --no-deps --no-build crypto-shadow-predictor
(cd /Users/user/Desktop/CODE/dolphin_ai && docker compose up -d --no-build)
(cd /Users/user/Desktop/CODE/ARTEX/scopesentry && docker compose up -d --no-build)
```
(Check the project name label first with `docker compose ls`; it must match the existing project so the containers are recreated and not duplicated. Do not run bare `docker compose up -d` in Ochestration, because it would also treat the crypto-data containers as orphans.)

Step 5: other bots (kr-rotation, us-rotation, coin-swing6, paper-funding-arb, tick-stream, kr-opening-scan) each by name, only when not near their own rebalance or trading hours (check KST market hours for kr-rotation). Optional; they can wait. No build is needed:
```bash
docker compose -p ochestration-trading --profile coin-swing6 -f docker-compose.trading.yml up -d --no-deps --no-build trading-coin-swing6
```
Step 6: momentum-rotation LAST. Build separately first so a failed build recreates nothing:
```bash
docker compose -p ochestration-trading --profile momentum-rotation -f docker-compose.trading.yml build trading-momentum-rotation
date -u   # re-check the window
docker compose -p ochestration-trading --profile momentum-rotation -f docker-compose.trading.yml up -d --no-deps trading-momentum-rotation
```
Note: if an immediate recreate is not wanted, `docker update --memory 1024m --memory-swap 1024m --pids-limit 64 ochestration-trading-trading-momentum-rotation-1` applies the caps live. That still skips the heartbeat code and the oom_score_adj.

Verification:
```bash
docker stats --no-stream
docker inspect -f '{{.Name}} mem={{.HostConfig.Memory}} swap={{.HostConfig.MemorySwap}} pids={{.HostConfig.PidsLimit}} oom={{.HostConfig.OomScoreAdj}}' $(docker ps -q)
docker exec ochestration-api-1 sh -c 'cat /proc/1/cmdline | tr "\0" " "; env | grep -c JAVA_TOOL_OPTIONS'
docker logs --tail 5 ochestration-api-1 | grep -i "Picked up JAVA_TOOL_OPTIONS\|Started"
docker exec ochestration-trading-trading-momentum-rotation-1 cat /app/data/heartbeat.json   # epoch must be fresh, repeat after 30s
docker logs --since 5m ochestration-trading-trading-momentum-rotation-1 | tail -20          # state restored, no errors, no duplicate orders
curl -sf http://localhost:<web-port>/ >/dev/null && echo web-ok
```
Rollback:
- Per service: `git stash` or `git checkout -- docker-compose*.yml`, then `up -d --no-deps <service>` with the same project and file, so the old config is applied.
- Bot image: the previous image ID is kept on disk. Retag it (`docker tag <old-id> ochestration-trading-trading-momentum-rotation`) and rerun `up -d --no-deps --no-build`.
- Named and external volumes are not touched by any of these commands, so the bot state (`ochestration_trading_momentum_rotation_state`) survives.

## Summary

- Compose changes: safe and verified. The limits, `oom_score_adj`, and JAVA_TOOL_OPTIONS take effect only on recreate. Raise n8n to 1536m (M1) and optionally the pids limits (M2) before the deploy.
- Watchdog: not ready. H1 (the wrong process name makes the restart sequence race) and H2 (a stale failure count allows a false-positive restart after sleep or wake) must be fixed, with tests that use a realistic `pgrep` and a time gap, before enabling auto-restart.
