#!/bin/bash
# usage: kr/run_heavy.sh <python args...>   (one heavy job at a time, nice/ionice, 3G cap, abort on load/RAM)
R=/home/noroot/research/stock_loop
L=$(cut -d" " -f1 /proc/loadavg); A=$(awk '/MemAvailable/{print $2}' /proc/meminfo)
if (( $(echo "$L > 4" | bc -l) )) || (( A < 2097152 )); then echo "ABORT load=$L avail_kB=$A"; exit 3; fi
export XDG_RUNTIME_DIR=/run/user/$(id -u)
exec flock $R/.heavy.lock nice -n 19 ionice -c3 systemd-run --user --scope -q -p MemoryMax=3G \
  /home/noroot/research/gulp_pattern/.venv/bin/python "$@"
