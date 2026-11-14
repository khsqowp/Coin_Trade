#!/bin/bash
# usage: us/run_heavy.sh <python args...>  (run from /home/noroot/research/stock_loop; one heavy job at a time, 3G cap, abort on load/RAM)
R=/home/noroot/research/stock_loop
cd $R
L=$(cut -d" " -f1 /proc/loadavg); A=$(awk '/MemAvailable/{print $2}' /proc/meminfo)
if (( $(echo "$L > 4" | bc -l) )) || (( A < 2097152 )); then echo "ABORT load=$L avail_kB=$A"; exit 3; fi
export XDG_RUNTIME_DIR=/run/user/$(id -u)
exec flock $R/.heavy.lock nice -n 19 ionice -c3 systemd-run --user --scope -q -p MemoryMax=3G \
  /home/noroot/research/gulp_pattern/.venv/bin/python "$@"
