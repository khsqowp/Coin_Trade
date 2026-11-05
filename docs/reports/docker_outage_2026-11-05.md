# Docker Desktop outage 2026-11-05 (KST) - root cause report
(UTC = KST - 9h. Sources: ~/Library/Containers/com.docker.docker/Data/log/{host,vm}/*, docker logs. Read-only investigation.)

## Timeline (KST)
- 10-29 09:23  VM boot (uptime ~164h at crash). Docker 4.77.0, macOS 27.0.1, VM = 12288 MiB RAM / 11 CPU / 2 GiB swap, host RAM 18 GiB.
- 11-05 02:06-02:23  mongod in container scopesentry-mongodb logs NOTHING from 17:06:20Z to 17:23:25Z (whole guest stalled ~17 min; it normally logs ~290 lines/10min).
- 02:15:17  FIRST guest OOM kill (console.log: `POST /analytics/track/oom-kills`). ~2,053 OOM-kill events total, 425/548/614/466 per hour (17Z-20Z).
- 02:20  host electron log: `GET /containers/<id>/json: No response from server (Headers Timeout Error)`; backend `stats ... GET /ping context deadline exceeded` (1,077 times in retained logs).
- 02:23-05:38  momentum-rotation bot container is OOM-killed and restarted ~300 times (a "loop start" line every ~30 s). LAST healthy period: 10:40Z-17:22Z (19:40-02:22 KST), single start at 10:40Z. LAST bot log before VM death: 20:38:59Z = 05:38:59 KST (just another restart line; bot logs only at start, no heartbeat).
- 05:36-05:39  guest kernel dumps task tables / Mem-Info (init.log rotates 3x in 2 min). sysrq "Show State" at 20:38:58Z.
- 05:39:04  `engine linux/virtualization-framework shutdown requested` -> `init failed to shutdown the VM: Post "http://ipc/shutdown": context deadline exceeded` -> `com.docker.virtualization: process terminated due to explicit cancel` (VM force-killed, no "VM has stopped" line). Error dialog pid 38424 started 05:39:16. Engine 503s from then.
- 08:18 (23:18Z) repeated `returning engine error` while engine was down (symptom, not cause). 08:24-08:25 manual restart (VM up 23:24:55Z); bot container started 23:24:59Z, no OOMKilled flag, restarts=0.

## Root cause (high confidence): guest-VM memory exhaustion by leaked `mongosh` healthcheck processes
Decisive evidence (vm/init.log.20261105-053709, Mem-Info 20:37:12Z):
`active_anon:1965943 inactive_anon:800265 ... free:20953` (~11 GiB anon of 12 GiB), `Free swap = 244kB` / `Total swap = 2097148kB`, pagetables 685 MB.
Task dump (8 dumps): 381 concurrent `mongosh` processes = 8,664 MiB RSS of 11,023 MiB total; later dump still 203 = 5,214 MiB. Kills hit mongosh, mysqld, python, ScopeSentry, cloudflared (random victims) -> containers incl. the bot died repeatedly.
Source: container `scopesentry-mongodb` (/Users/user/Desktop/CODE/ARTEX/scopesentry/docker-compose.yml) healthcheck `["CMD","mongosh","--eval","db.adminCommand('ping')"]` interval 10s, timeout 5s, retries 10, no mem_limit. Each mongosh (node) is ~140 MB anon when running; when the guest stalled/slowed, probes timed out but the exec'd mongosh were not reaped and piled up (~6/min), exhausting RAM+swap; OOM killer then thrashed (2,000+ kills) until dockerd/initd became unresponsive (/ping and /shutdown deadlines) and the VM was killed.
Not the cause: VM disk (Docker.raw 45 GB sparse, host Data volume 54 GiB free, no ENOSPC), no VM crash report/panic, no sleep/wake in pmset (caffeinate active), no DiagnosticReports for Docker, no Docker update.

## Secondary / unresolved
2. Trigger of the initial 17-min guest stall at 02:06 KST - UNKNOWN (guess). Host is memory-starved: `vm.swapusage total 18432M used 16883M` right now, 18 GiB RAM with a 12 GiB VM + Chrome/Claude/mds; host swap thrash can freeze the VM. Heavy host I/O is also a candidate: archive_to_nas.py (launchd com.ochestration.archive-to-nas, pid 11121, running 7h56m with `--max-minutes 40` -> exceeded its own limit) started ~00:30 KST; virtiofs 45 GB tick-archive bind mount + hung `docker cp` not directly evidenced in VM logs (no I/O errors, no hung_task lines). Treat as contributing-unproven.
3. Co-tenant overcommit: ~26 containers (scopesentry x5 incl. 800-worker trufflehog scanner, dolphin, artex, n8n, mysql...) share the same 12 GiB VM with the live bot; no per-container limits (mem=0 everywhere), so any one leak kills the trading bot.
4. Docker 4.77.0 / Virtualization.framework known-issue angle: not verified (no network lookup done); log shows no framework-level error, so lowest ranked.

## State check
momentum_rotation_state.json: state_seq=24194, last write 23:31:53Z, last_rebalance 11-02 09:41Z, next 11-05 09:41Z (not missed), kill_ts=None. Note first post-restart cycle logged `-1021 Timestamp outside recvWindow` (VM clock drift after restart; GUARD deferred kill, benign but watch). Open mainnet 4x positions were unmonitored/flapping from 02:23 KST (~6h), not just 05:39-08:25 (~2.8h).

## Prevention
- Fix source: replace mongosh healthcheck with cheap one (`mongosh --quiet --norc ...` still heavy; prefer `bash -c 'echo > /dev/tcp/127.0.0.1/27017'` or `timeout 4 mongosh ...` with interval 30s, start_period) in ARTEX/scopesentry compose; add `mem_limit`/`pids_limit` on scopesentry-*, dolphin-*, artex.
- Protect the bot: `mem_limit` on every non-trading container, `oom_score_adj: -500` on trading containers, separate noisy security stack from the trading VM or stop it when not needed.
- Docker Desktop settings: raise Swap 2->4 GiB only as buffer; consider Memory 10 GiB so host (18 GiB) is not in swap; keep Resource Saver off for this host.
- Host: free RAM (host swap 16.9/18.4 GiB); stop archive_to_nas runaway (enforce `--max-minutes` with `timeout`, `nice`/`taskpolicy -b`).
- Monitoring: external watchdog (launchd, 1 min) checking `docker info` + bot heartbeat file age; alert on guest OOM (`docker events`, count of `oom-kills` in vm/console.log) and on RestartCount growth; Telegram/e-mail on failure. Auto-restart: watchdog runs `osascript -e 'quit app "Docker"'; open -a Docker` after 2 failed checks (restart: unless-stopped then revives containers).
- Bot: add heartbeat log each cycle and exchange-side stop-loss/reduce-only protection so outages while positions are open are bounded.
