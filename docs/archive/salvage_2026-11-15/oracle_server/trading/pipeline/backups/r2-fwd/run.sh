#!/bin/bash
# Usage: run.sh <data|kis|agent|sandbox|offline|notify|export> [-- docker-extra-args] -- <tp.cli args...>
# Every container: non-root uid, read-only rootfs, no-new-privileges, all caps dropped, mem/pid limits.
set -euo pipefail
P="$(cd "$(dirname "$0")" && pwd)"
ROLE="$1"; shift
# TP_SERVICE=1 (used by svc.sh): detached, restart policy, no --rm. Default: ephemeral foreground container.
if [ "${TP_SERVICE:-0}" = "1" ]; then LIFE=(-d --restart unless-stopped --log-opt max-size=5m --log-opt max-file=3); else LIFE=(--rm); fi
BASE=("${LIFE[@]}" --user "$(id -u):$(id -g)" --read-only --tmpfs /tmp:size=256m --cap-drop ALL
      --security-opt no-new-privileges --pids-limit 256 --memory 1g --cpus 1
      -v "$P/src:/app/src:ro" -v "$P/strategy_pool:/app/strategy_pool:ro")
case "$ROLE" in
  data)    ARGS=("${BASE[@]}" -v "$P/data:/app/data:rw" -v "$P/runs:/app/runs:rw") ;;
  kis)     ARGS=("${BASE[@]}" --env-file "$P/secrets/kis.env" -v "$P/data:/app/data:rw" -v "$P/runs:/app/runs:rw") ;;
  agent)   ARGS=("${BASE[@]}" --env-file "$P/secrets/llm.env" -v "$P/data:/app/data:ro" -v "$P/runs:/app/runs:rw" -v "$P/bench:/app/bench:ro" -v "$P/strategy_library:/app/strategy_library:ro") ;;
  sandbox) ARGS=("${BASE[@]}" --network none -v "$P/data:/app/data:ro" -v "$P/runs:/app/runs:rw" -v "$P/bench:/app/bench:ro" -v "$P/tests:/app/tests:ro") ;;
  offline) ARGS=("${BASE[@]}" --network none -v "$P/data:/app/data:ro" -v "$P/runs:/app/runs:rw" -v "$P/tests:/app/tests:ro") ;;
  # notify: network + ONLY the Telegram vars (secrets/notify.env); no LLM/KIS/exchange keys, no data, runs for the ledger/state
  notify)  ARGS=("${BASE[@]}" --env-file "$P/secrets/notify.env" -v "$P/runs:/app/runs:rw") ;;
  # export: no network, no env. Writes ONLY candidate files: Freqtrade strategies dir + pipeline/candidates. Never touches docker.
  export)  FT_STRAT="${TP_FT_STRATEGIES:-$P/../freqtrade/user_data/strategies}"
           CAND="${TP_CANDIDATES:-$P/candidates}"; mkdir -p "$CAND"
           ARGS=("${BASE[@]}" --network none -e "TP_HOST_ROOT=$(cd "$P/.." && pwd)" -v "$P/runs:/app/runs:ro" -v "$CAND:/app/candidates:rw" -v "$FT_STRAT:/export/strategies:rw") ;;
  # lib: rebuild strategy_library/index.json (no network, no env)
  lib)     ARGS=("${BASE[@]}" --network none -v "$P/strategy_library:/app/strategy_library:rw") ;;
  # news: network, NO env/keys. Writes only data/ (news sqlite/parquet, US daily). Long-running via svc.sh.
  news)    ARGS=("${BASE[@]}" --memory 512m --cpus 0.5 -v "$P/data:/app/data:rw") ;;
  # kiscol: network + ONLY the 2 KIS paper vars (secrets/kis.env). Long-running via svc.sh.
  kiscol)  ARGS=("${BASE[@]}" --memory 512m --cpus 0.5 --env-file "$P/secrets/kis.env" -v "$P/data:/app/data:rw") ;;
  # hl: Hyperliquid read-only public data (info POST + WS subscribe). Network, NO env/keys, writes data/ only.
  hl)      ARGS=("${BASE[@]}" --memory 512m --cpus 0.5 -v "$P/data:/app/data:rw") ;;
  # sched: regime-agent scheduler. Network + ONLY the 2 LLM keys it needs (secrets/sched.env). No ports. data ro, runs rw.
  sched)   ARGS=("${BASE[@]}" --memory 512m --cpus 0.5 --env-file "$P/secrets/sched.env" -e TP_DAILY_CAP="${TP_DAILY_CAP:-0.30}" -v "$P/data:/app/data:ro" -v "$P/runs:/app/runs:rw") ;;
  # watch: watchdog + daily Telegram summary. NO LLM keys; Telegram vars only. data ro, runs rw.
  watch)   ARGS=("${BASE[@]}" --memory 256m --cpus 0.25 --env-file "$P/secrets/notify.env" -v "$P/data:/app/data:ro" -v "$P/runs:/app/runs:rw") ;;
  # research: offline backtests, low priority: memory/CPU capped and low CPU weight so collectors, Freqtrade and Hermes are not disturbed.
  research) ARGS=("${BASE[@]}" --network none --memory 2g --cpus 1 --cpu-shares 128 -v "$P/data:/app/data:ro" -v "$P/runs:/app/runs:rw" -v "$P/tests:/app/tests:ro") ;;
  *) echo "unknown role" >&2; exit 2 ;;
esac
NAMEARG=(); [ -n "${TP_NAME:-}" ] && NAMEARG=(--name "$TP_NAME")
if [ "${TP_SERVICE:-0}" = "1" ]; then IARG=(); else IARG=(-i); fi
exec docker run "${IARG[@]}" "${NAMEARG[@]}" "${ARGS[@]}" tp-pipeline:local "$@"
