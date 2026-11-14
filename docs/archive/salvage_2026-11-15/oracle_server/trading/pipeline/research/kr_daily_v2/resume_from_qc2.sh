#!/usr/bin/env bash
set -uo pipefail
ROOT="$HOME/trading/pipeline"
KR="$ROOT/research/kr_daily_v2"
SNAPSHOT="$KR/data_snapshot_deadline"
IMAGE=tp-pipeline:local
exec >>"$KR/pipeline_supervisor.log" 2>&1
say() { printf '[%s] %s\n' "$(date -u +%FT%TZ)" "$*"; }
if ! grep -q '^trigger=fetch_complete$' "$KR/FETCH_TRIGGER.marker" || [ "$(find "$SNAPSHOT" -maxdepth 1 -type f | wc -l)" -ne 3237 ]; then
  say 'resume refused: fetch marker or frozen snapshot validation failed'; exit 2
fi
run_stage() {
  local stage="$1"; shift
  local stamp logfile attempt rc=0
  stamp="$(date -u +%Y%m%dT%H%M%SZ)"
  logfile="$KR/stage_${stage}_${stamp}.log"
  for attempt in 1 2; do
    say "stage=$stage attempt=$attempt start log=$logfile"
    {
      printf '[%s] attempt=%s command=' "$(date -u +%FT%TZ)" "$attempt"; printf '%q ' "$@"; printf '\n'
      docker run --rm --entrypoint python --user "$(id -u):$(id -g)" --read-only --tmpfs /tmp:size=256m \
        --cap-drop ALL --security-opt no-new-privileges --pids-limit 256 --memory 3g --cpus 0.75 --cpu-shares 128 --network none \
        -v "$KR:/app/kr:rw" -v "$SNAPSHOT:/app/kr/data:ro" -v "$ROOT/research/kr_daily_v1:/app/v1:ro" -v "$ROOT/src:/app/src:ro" \
        -w /app/kr "$IMAGE" "$@"
    } >>"$logfile" 2>&1
    rc=$?
    if [ "$rc" -eq 0 ]; then say "stage=$stage succeeded"; return 0; fi
    say "stage=$stage failed exit=$rc"
    if [ "$attempt" -lt 2 ]; then sleep 60; fi
  done
  printf '%s FAILURE stage=%s exit=%s log=%s\n' "$(date -u +%FT%TZ)" "$stage" "$rc" "$logfile" > "$KR/PIPELINE_FAILURE.marker"
  say "pipeline stopped at failed stage=$stage; marker written"
  return "$rc"
}
if ! run_stage qc2 qc2.py; then exit 1; fi
if ! run_stage main bt2.py main; then exit 1; fi
if ! run_stage sens bt2.py sens; then exit 1; fi
if ! run_stage robust bt2.py robust; then exit 1; fi
if ! run_stage null null_test_v2.py; then exit 1; fi
if ! run_stage report gate_report_v2.py; then exit 1; fi
python3 - "$KR" <<'PY'
import json, pathlib, sys, datetime
p=pathlib.Path(sys.argv[1]); d=json.loads((p/'results_main.json').read_text()); k=d['is_pick']; r=d['results'][k]
report=(p/'REPORT_kr_daily_v2.md').read_text()
line=next((x for x in report.splitlines() if x.startswith('**Overall registered gate:')), 'overall=UNKNOWN')
summary=line.replace('**','').replace('.','').strip()
marker=f"{datetime.datetime.now(datetime.timezone.utc).strftime('%Y-%m-%dT%H:%M:%SZ')} | pick={k} | OOS_Sharpe={r['OOS'].get('sharpe')} | DSR_N17={r['FULL'].get('dsr_N17')} | {summary}\n"
(p/'PIPELINE_DONE.marker').write_text(marker); print(marker.strip())
PY
say 'all resumed pipeline stages completed successfully'
