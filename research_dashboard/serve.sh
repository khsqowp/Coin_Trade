#!/bin/sh
set -eu
HERE=$(CDPATH= cd -- "$(dirname -- "$0")" && pwd)
exec python3 -m http.server 8765 --bind 127.0.0.1 --directory "$HERE/dist"
