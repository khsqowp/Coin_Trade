#!/usr/bin/env bash
# Archive KEEP/COMPRESS items from the Ochestration repo to $DEST as tar.zst + sha256 manifests,
# verify by extracting and re-hashing, and ONLY THEN remove the archived original files.
# Default is a dry run. Nothing is touched without --execute.
#
#   apply.sh                       dry run: prints the plan
#   apply.sh --execute             archive + verify + remove originals (KEEP/COMPRESS lines)
#   apply.sh --execute --allow-discard   additionally delete DISCARD lines (no archive!)
# Options: --allowlist FILE (default: allowlist.txt next to this script), --dest DIR (default ~/CODE/trading_data)
# Safety: never uses rm -r; deletes only files that were listed, then removes empty dirs under the entry root.
# Refuses anything under trading/data_tick, trading-tick-archive, inbox, trading/scratchpad, strategy_archive, .git.
set -euo pipefail

HERE="$(cd "$(dirname "$0")" && pwd)"
REPO="$(cd "$HERE/../.." && pwd)"
ALLOW="$HERE/allowlist.txt"
DEST="${HOME}/CODE/trading_data"
EXECUTE=0; ALLOW_DISCARD=0
while [ $# -gt 0 ]; do
  case "$1" in
    --execute) EXECUTE=1;;
    --allow-discard) ALLOW_DISCARD=1;;
    --allowlist) ALLOW="$2"; shift;;
    --dest) DEST="$2"; shift;;
    -h|--help) sed -n 2,12p "$0"; exit 0;;
    *) echo "unknown arg $1" >&2; exit 2;;
  esac; shift
done
[ -f "$ALLOW" ] || { echo "allowlist not found: $ALLOW" >&2; exit 2; }
command -v zstd >/dev/null || { echo "zstd not installed (brew install zstd)" >&2; exit 2; }
if command -v sha256sum >/dev/null; then SHA() { sha256sum "$@"; }; else SHA() { shasum -a 256 "$@"; }; fi
cd "$REPO"

blocked() { case "$1" in
  trading/data_tick*|trading-tick-archive*|inbox*|trading/scratchpad*|trading/strategy_archive*|.git*|/*|*..*) return 0;; esac; return 1; }

# file list for one entry: $1 pattern, $2 excludes -> stdout (NUL-free, one path per line)
list_files() {
  local pat="$1" ex="$2" root e
  for root in $pat; do
    [ -e "$root" ] || continue
    blocked "$root" && { echo "REFUSED path: $root" >&2; return 1; }
    local args=(-type f ! -name .gitkeep ! -name .DS_Store)
    IFS=',' read -r -a exs <<< "$ex"
    for e in "${exs[@]:-}"; do
      [ -n "$e" ] || continue
      args+=(! -path "$root/$e" ! -path "$root/$e/*")
    done
    find "$root" "${args[@]}"
  done | LC_ALL=C sort
}

prune_empty_dirs() { # remove now-empty dirs below each root, never the repo
  local pat="$1" root
  for root in $pat; do [ -d "$root" ] && find "$root" -depth -type d -empty -delete 2>/dev/null || true; done
}

n=0; total=0
echo "repo=$REPO dest=$DEST execute=$EXECUTE allow_discard=$ALLOW_DISCARD"
while IFS='|' read -r ACTION PAT EX SUB || [ -n "${ACTION:-}" ]; do
  case "${ACTION:-}" in ''|\#*) continue;; esac
  ACTION="$(echo "$ACTION" | tr -d ' ')"
  n=$((n+1)); label="$(printf '%02d_' "$n")$(echo "$PAT" | tr -c 'A-Za-z0-9\n' '_' | cut -c1-70)"
  tmp_list="$(mktemp)"; list_files "$PAT" "$EX" > "$tmp_list" || { rm -f "$tmp_list"; exit 1; }
  cnt=$(wc -l < "$tmp_list" | tr -d ' ')
  bytes=0; [ "$cnt" -gt 0 ] && bytes=$(tr '\n' '\0' < "$tmp_list" | xargs -0 stat -f %z 2>/dev/null | awk '{s+=$1}END{print s+0}' || echo 0)
  total=$((total+bytes))
  printf '%-8s files=%-6s bytes=%-12s %s\n' "$ACTION" "$cnt" "$bytes" "$PAT${EX:+  [excl $EX]}"
  if [ "$cnt" -eq 0 ]; then rm -f "$tmp_list"; continue; fi
  case "$ACTION" in
    DISCARD)
      if [ "$EXECUTE" = 1 ] && [ "$ALLOW_DISCARD" = 1 ]; then
        while IFS= read -r f; do rm -f -- "$f"; done < "$tmp_list"
        prune_empty_dirs "$PAT"; echo "  -> discarded $cnt files"
      fi;;
    KEEP|COMPRESS)
      if [ "$EXECUTE" = 1 ]; then
        out="$DEST/${SUB:-misc}"; mkdir -p "$out"
        arc="$out/$label.tar.zst"; man="$out/$label.sha256"
        [ -e "$arc" ] && { echo "  archive exists, refusing to overwrite: $arc" >&2; exit 1; }
        # free space guard: need >= source bytes
        avail=$(df -k "$out" | awk 'NR==2{print $4*1024}')
        [ "$avail" -gt "$bytes" ] || { echo "  not enough free space in $out" >&2; exit 1; }
        tr '\n' '\0' < "$tmp_list" | xargs -0 shasum -a 256 > "$man"
        tar -cf - -T "$tmp_list" | zstd -T0 -10 -q -o "$arc"
        zstd -t -q "$arc"
        ver="$(mktemp -d)"
        zstd -dc "$arc" | tar -xf - -C "$ver"
        ( cd "$ver" && shasum -a 256 -c "$man" --quiet ) \
          || { echo "  VERIFY FAILED for $arc - originals kept" >&2; rm -rf "$ver"; exit 1; }
        got=$(find "$ver" -type f | wc -l | tr -d ' ')
        [ "$got" = "$cnt" ] || { echo "  file count mismatch ($got vs $cnt) - originals kept" >&2; rm -rf "$ver"; exit 1; }
        # manifest is relative-path based; make it checkable from repo root too
        ( cd "$REPO" && shasum -a 256 -c "$man" --quiet ) || { echo "  source changed during archive - originals kept" >&2; rm -rf "$ver"; exit 1; }
        rm -rf "$ver"
        SHA "$arc" > "$arc.sha256"
        while IFS= read -r f; do rm -f -- "$f"; done < "$tmp_list"
        prune_empty_dirs "$PAT"
        echo "  -> archived+verified+removed: $arc"
      fi;;
    *) echo "  unknown ACTION '$ACTION' skipped" >&2;;
  esac
  rm -f "$tmp_list"
done < "$ALLOW"
echo "total bytes covered by allowlist: $total"
[ "$EXECUTE" = 1 ] || echo "DRY RUN only. Re-run with --execute (and --allow-discard for DISCARD lines)."
echo "Note: tracked files removed here will show as deleted in git status; commit or 'git checkout' as you decide."
