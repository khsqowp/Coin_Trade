#!/bin/bash
# Usage: run.sh <data|kis|agent|sandbox|offline|notify|export> [-- docker-extra-args] -- <tp.cli args...>
# Every container: non-root uid, read-only rootfs, no-new-privileges, all caps dropped, mem/pid limits.
set -euo pipefail
P="$(cd "$(dirname "$0")" && pwd)"
ROLE="$1"; shift
BASE=(--rm --user "$(id -u):$(id -g)" --read-only --tmpfs /tmp:size=256m --cap-drop ALL
      --security-opt no-new-privileges --pids-limit 256 --memory 1g --cpus 1
      -v "$P/src:/app/src:ro")
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
  *) echo "unknown role" >&2; exit 2 ;;
esac
NAMEARG=(); [ -n "${TP_NAME:-}" ] && NAMEARG=(--name "$TP_NAME")
exec docker run -i "${NAMEARG[@]}" "${ARGS[@]}" tp-pipeline:local "$@"
