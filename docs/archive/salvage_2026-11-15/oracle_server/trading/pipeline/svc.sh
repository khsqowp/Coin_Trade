#!/bin/bash
# Long-running collector services. Usage: svc.sh start|stop|status|logs <news|kis|deriv|all>
# Containers: tp-news (role news, no keys), tp-kiscol (role kiscol, 2 KIS paper vars), tp-deriv (role news, public Binance derivatives).
# tp-hl (role hl): Hyperliquid READ-ONLY public info/WS collector, no keys.
# Restart policy unless-stopped, mem 512m, cpus 0.5, read-only rootfs. tp-sched = regime-agent scheduler (LLM, daily cap, stop with: ./svc.sh stop sched). tp-watch = watchdog + daily summary (no LLM).
set -euo pipefail
P="$(cd "$(dirname "$0")" && pwd)"
declare -A ROLE=([news]=news [kis]=kiscol [deriv]=news [hl]=hl [sched]=sched [watch]=watch)
declare -A CMD=([news]=news-collect [kis]=kis-collect [deriv]=deriv-collect [hl]=hl-collect [sched]=sched-run [watch]=watch-run)
declare -A NAME=([news]=tp-news [kis]=tp-kiscol [deriv]=tp-deriv [hl]=tp-hl [sched]=tp-sched [watch]=tp-watch)
act="$1"; w="${2:-all}"; [ "$w" = all ] && ws="news kis deriv hl watch sched" || ws="$w"
for k in $ws; do
  case "$act" in
    start) docker rm -f "${NAME[$k]}" >/dev/null 2>&1 || true
           TP_SERVICE=1 TP_NAME="${NAME[$k]}" "$P/run.sh" "${ROLE[$k]}" "${CMD[$k]}" ;;
    stop)  docker stop "${NAME[$k]}" ;;
    logs)  docker logs --tail 30 "${NAME[$k]}" ;;
    status) docker ps -a --filter "name=${NAME[$k]}" --format '{{.Names}} {{.Status}} restart-policy' ;;
  esac
done
