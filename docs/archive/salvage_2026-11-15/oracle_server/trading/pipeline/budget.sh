#!/bin/bash
# OWNER-ONLY, run on the host. The scheduler agent's daily LLM cap changes ONLY through this script.
#   ./budget.sh status
#   ./budget.sh approve <0.30|0.60|1.00> [--force]   (without --force the pre-registered conditions are re-computed and must all hold)
#   ./budget.sh reset                                 (back to 0.30)
# Code never calls this script; containers cannot see config/ (only tp-watch/offline read it read-only).
set -euo pipefail
P="$(cd "$(dirname "$0")" && pwd)"
CF="$P/config/daily_cap.txt"; HF="$P/config/daily_cap.history"
mkdir -p "$P/config"; [ -f "$CF" ] || echo 0.30 > "$CF"; touch "$HF"
apply() {  # $1=cap $2=mode
  echo "$1" > "$CF"
  echo "$(date -u +%Y-%m-%dT%H:%M:%SZ) $1 $2 by=$(id -un)" >> "$HF"
  "$P/svc.sh" start sched >/dev/null
  echo "daily cap is now $1 USD (scheduler container restarted with it)"
}
case "${1:-status}" in
  status) echo "effective cap file: $(cat "$CF") USD"; tail -3 "$HF"; "$P/run.sh" offline budget-check ;;
  approve) CAP="${2:?cap required}"
    case "$CAP" in 0.30|0.60|1.00) ;; *) echo "cap must be one of 0.30 0.60 1.00"; exit 2;; esac
    if [ "${3:-}" = "--force" ]; then apply "$CAP" "forced-by-owner"; exit 0; fi
    J="$("$P/run.sh" offline budget-check)"
    echo "$J" | python3 -c "
import json,sys
d=json.load(sys.stdin); cap='$CAP'
ok = d.get('eligible') and abs(d.get('next_cap',0)-float(cap))<1e-9
print('eligible=%s next_cap=%s requested=%s' % (d.get('eligible'), d.get('next_cap'), cap))
for c in d['checks']:
    if not c['ok']: print('  NOT MET:', c['name'], c['value'], c['rule'])
sys.exit(0 if ok else 3)" || { echo "conditions not met; use --force only as an explicit owner override"; exit 3; }
    apply "$CAP" "conditions-met" ;;
  reset) apply 0.30 "reset" ;;
  *) echo "usage: $0 status|approve <cap> [--force]|reset"; exit 2 ;;
esac
