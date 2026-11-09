#!/bin/sh
set -eu
cd "$(dirname "$0")"
mode=${1:-pre}
if [ "$mode" = pre ]; then
  sha256sum prereg.md > hash_pre.txt
elif [ "$mode" = post ]; then
  sha256sum prereg.md report.md > hash_post.txt
else
  echo 'usage: hash_log.sh pre|post' >&2
  exit 2
fi
