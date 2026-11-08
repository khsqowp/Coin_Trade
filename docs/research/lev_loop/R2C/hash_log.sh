#!/bin/bash
# usage: hash_log.sh "note" file...   (appends "UTC-ts sha256 path note" to hashes.log)
SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
TRADING_ROOT="$(cd "$SCRIPT_DIR/../../../.." && pwd)"
cd "$TRADING_ROOT"
note="$1"; shift
for f in "$@"; do
  printf '%s %s %s %s\n' "$(date -u +%Y-%m-%dT%H:%M:%SZ)" "$(shasum -a 256 "$f" | cut -d' ' -f1)" "$f" "$note" >> docs/research/lev_loop/R2C/hashes.log
done
