#!/usr/bin/env bash
# Host-side detached orchestration. The fetch container is observation-only.
set -uo pipefail
ROOT="$HOME/trading/pipeline"
KR="$ROOT/research/kr_daily_v2"
IMAGE=tp-pipeline:local
DEADLINE_EPOCH="$(date -u -d '2026-11-06T06:40:00Z' +%s)"
mkdir -p "$KR"
exec >>"$KR/pipeline_supervisor.log" 2>&1
say() { printf '[%s] %s\n' "$(date -u +%FT%TZ)" "$*"; }

progress() {
  python3 - "$KR" <<'PY'
import json, pathlib, sys
p=pathlib.Path(sys.argv[1]); rows=[]
for line in (p/'fetch_log.jsonl').read_text().splitlines():
    try: rows.append(json.loads(line))
    except Exception: pass
keys={str(r.get('code')) for r in rows if r.get('code')}
listed={str(r.get('code')) for r in rows if r.get('code') and r.get('status')=='listed'}
delisted={str(r.get('code')) for r in rows if r.get('code') and r.get('status')=='delisted'}
errors=sum(bool(r.get('error')) for r in rows)
through=max([int(r.get('i',-1)) for r in rows] or [-1])+1
parquet=len(list((p/'data').glob('*.parquet'))); none=len(list((p/'data').glob('*.none')))
print(f'current-order positions traversed {through}/3240; distinct_log_keys={len(keys)}; listed_log_keys={len(listed)}; delisted_log_keys={len(delisted)}; errors={errors}; parquet_files={parquet}; no_row_markers={none}')
PY
}
fetch_index() {
  python3 - "$KR" <<'PY'
import json, pathlib, sys
rows=[]
for line in (pathlib.Path(sys.argv[1])/'fetch_log.jsonl').read_text().splitlines():
    try: rows.append(json.loads(line))
    except Exception: pass
print(max([int(r.get('i',-1)) for r in rows] or [-1])+1)
PY
}

say 'waiting for natural fetch completion or fixed UTC deadline 2026-11-06T06:40:00Z'
while :; do
  progress
  idx="$(fetch_index)"
  state="$(docker inspect -f '{{.State.Running}} {{.State.ExitCode}} {{.State.Status}}' kr2fetch 2>/dev/null || echo 'unknown -1 unknown')"
  read -r running exit_code status <<< "$state"
  now="$(date -u +%s)"
  if [ "$idx" -ge 3240 ] || { [ "$running" = false ] && [ "$exit_code" = 0 ] && [ "$status" = exited ]; }; then
    trigger=fetch_complete; say "fetch loop completed successfully (order_positions=$idx; state=$state); starting analysis"
    break
  fi
  if [ "$now" -ge "$DEADLINE_EPOCH" ]; then
    trigger=deadline; say "fixed deadline reached; proceeding with fetched-so-far snapshot (order_positions=$idx; state=$state)"
    break
  fi
  if [ "$running" = false ]; then say "fetch container exited before full coverage with exit=$exit_code; leave it untouched and wait for deadline"; fi
  sleep 180
done
# Freeze the exact data-file set at the trigger. Hardlinks make this fast and avoid
# mutating source data; the fetcher only creates absent files, so the snapshot stays stable.
SNAPSHOT="$KR/data_snapshot_deadline"
mkdir -p "$SNAPSHOT"
cp -al "$KR/data/." "$SNAPSHOT/"
state="$(docker inspect -f '{{.State.Running}} {{.State.ExitCode}} {{.State.Status}}' kr2fetch 2>/dev/null || echo 'unknown -1 unknown')"
python3 - "$KR" "$trigger" "$idx" "$state" <<'PY'
import json, pathlib, sys, datetime
p=pathlib.Path(sys.argv[1]); rows=[]
for line in (p/'fetch_log.jsonl').read_text().splitlines():
    try: rows.append(json.loads(line))
    except Exception: pass
max_i=max([int(r.get('i',-1)) for r in rows] or [-1])
text=(f"timestamp={datetime.datetime.now(datetime.timezone.utc).strftime('%Y-%m-%dT%H:%M:%SZ')}\n"
      f"trigger={sys.argv[2]}\norder_positions_traversed={int(sys.argv[3])}/3240\n"
      f"container_state={sys.argv[4]}\nlast_logged_index={max_i}\n"
      f"parquet_snapshot={len(list((p/'data_snapshot_deadline').glob('*.parquet')))}\n"
      f"no_row_snapshot={len(list((p/'data_snapshot_deadline').glob('*.none')))}\n"
      f"distinct_log_keys={len({str(r.get('code')) for r in rows if r.get('code')})}\n")
(p/'FETCH_TRIGGER.marker').write_text(text); print(text, end='')
PY

# Every stage is a separate disposable, hardened, offline container. Two total attempts maximum.
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
# Gate script prints the exact item results into the report; extract overall verdict from its final gate heading text.
report=(p/'REPORT_kr_daily_v2.md').read_text()
line=next((x for x in report.splitlines() if x.startswith('**Overall registered gate:')), 'overall=UNKNOWN')
summary=line.replace('**','').replace('.','').strip()
marker=f"{datetime.datetime.now(datetime.timezone.utc).strftime('%Y-%m-%dT%H:%M:%SZ')} | pick={k} | OOS_Sharpe={r['OOS'].get('sharpe')} | DSR_N17={r['FULL'].get('dsr_N17')} | {summary}\n"
(p/'PIPELINE_DONE.marker').write_text(marker)
print(marker.strip())
PY
say 'all pipeline stages completed successfully'
