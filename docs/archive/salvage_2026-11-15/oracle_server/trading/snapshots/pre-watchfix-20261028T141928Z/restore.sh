#!/bin/bash
# Restores the pre-watchfix snapshot exactly (src/tests/config from tarball, state files). Does not restart containers.
set -e
SNAP="$(cd "$(dirname "$0")" && pwd)"
PIPE=$HOME/trading/pipeline
cd "$SNAP" && sha256sum -c MANIFEST.sha256 >/dev/null && echo "manifest verified"
cd $PIPE
for d in src tests config; do rm -rf "$d.restore-old" ; mv "$d" "$d.restore-old"; echo "moved current $d -> $d.restore-old"; done
tar xzf "$SNAP/pipeline-src-tests-config.tar.gz" -C $PIPE && echo "restored src tests config from tarball"
[ -f "$SNAP/files/watch_state.json" ] && cp -p "$SNAP/files/watch_state.json" $PIPE/runs/watch_state.json && echo "restored runs/watch_state.json"
[ -f "$SNAP/files/gdelt_cooldown.json" ] && cp -p "$SNAP/files/gdelt_cooldown.json" $PIPE/data/news/gdelt_cooldown.json && echo "restored data/news/gdelt_cooldown.json"
echo "done: old dirs kept as *.restore-old in $PIPE (remove manually). Containers NOT restarted."
