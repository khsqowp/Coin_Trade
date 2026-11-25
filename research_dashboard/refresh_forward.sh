#!/bin/sh
set -eu

HERE=$(CDPATH= cd -- "$(dirname -- "$0")" && pwd)
TRADING_ROOT=$(CDPATH= cd -- "$HERE/.." && pwd)
TRADING_DATA_DIR=${TRADING_DATA_DIR:-"$HOME/CODE/Coin_Trade/trading_data"}
HOST=${FORWARD_SSH_HOST:-linuxserver}
FORWARD_DIR="$TRADING_DATA_DIR/cache/forward"

copy_profile() {
  profile=$1
  remote_dir=$2
  destination="$FORWARD_DIR/$profile"
  mkdir -p "$destination"
  rsync -a \
    --include='/forward.db' \
    --include='/forward.db-wal' \
    --include='/forward.db-shm' \
    --exclude='*' \
    "$HOST:$remote_dir/" "$destination/"
}

copy_profile l5_4h '~/CODE/Ochestration/trading-forward-test'
copy_profile l5_12h '~/CODE/Ochestration/trading-forward-test-12h'
copy_profile jbb_1h '~/CODE/Ochestration/trading-forward-test-jbb-1h'

date -u '+%Y-%m-%dT%H:%M:%SZ' > "$FORWARD_DIR/COPIED_AT.txt"
PYTHON=${TRADING_PYTHON:-"$TRADING_ROOT/scratchpad/bb_stoch_stc/.venv/bin/python"}
if [ ! -x "$PYTHON" ]; then
  printf '%s\n' "필요한 Python 환경을 찾을 수 없습니다: $PYTHON" >&2
  exit 2
fi
"$PYTHON" "$HERE/build_data.py" \
  --root "$TRADING_ROOT" \
  --out "$HERE/dist/data.json" \
  --forward-db-dir "$FORWARD_DIR"
