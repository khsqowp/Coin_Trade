#!/usr/bin/env bash
# STOCK_LOOP_COLLECT
set -euo pipefail
R=${STOCK_LOOP_ROOT:-/home/noroot/research/stock_loop}
if [[ $# -lt 2 ]]; then echo "usage: $0 <market> <mode> [extra args]" >&2; exit 2; fi
market=$1; mode=$2; shift 2
mkdir -p "$R/collect/logs"
L=$(cut -d' ' -f1 /proc/loadavg); A=$(awk '/MemAvailable/{print $2}' /proc/meminfo)
if awk -v l="$L" -v a="$A" 'BEGIN{exit !(l>4 || a<2097152)}'; then echo ABORT; exit 3; fi
export XDG_RUNTIME_DIR=/run/user/$(id -u)
cd "$R"
if command -v systemd-run >/dev/null 2>&1; then
  exec flock -w 3600 "$R/.heavy.lock" nice -n 19 ionice -c3 systemd-run --user --scope -q -p MemoryMax=3G /home/noroot/research/gulp_pattern/.venv/bin/python -m collect.yf_collect --market "$market" --mode "$mode" "$@" >> "$R/collect/logs/cron_$market.log" 2>&1
fi
exec flock -w 3600 "$R/.heavy.lock" nice -n 19 ionice -c3 bash -c 'ulimit -v 6000000; exec python -m collect.yf_collect --market "$1" --mode "$2" "${@:3}"' _ "$market" "$mode" "$@" >> "$R/collect/logs/cron_$market.log" 2>&1
