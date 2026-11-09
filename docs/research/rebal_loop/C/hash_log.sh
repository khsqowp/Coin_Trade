#!/bin/sh
set -eu
cd "$(dirname "$0")/../../../../.."
OUT="trading/docs/research/rebal_loop/C/hashes.log"
{
  date -u '+timestamp_utc=%Y-%m-%dT%H:%M:%SZ'
  for f in \
    trading/docs/research/rebal_loop/C/prereg.md \
    trading/docs/research/rebal_loop/C/hash_log.sh \
    trading/docs/research/rebal_loop/C/rebal_C_feasibility.py \
    trading/docs/research/rebal_loop/C/report.md \
    trading/app/rs_final_engine.py \
    trading/app/rs_lev_r2c_engine.py \
    trading/app/rs_lev_r2c_lib.py \
    trading/app/rs_lev_r2c_data.py \
    trading/docs/research/lev_loop/R2C/r2c_main.py \
    trading/docs/research/lev_loop/R2C/r2c_pit_universe.py \
    trading/docs/research/lev_loop/R2C/data/new_panel_2020_2021.npz \
    trading/docs/research/lev_loop/R2C/data/pit_membership.csv.gz \
    trading/docs/research/lev_loop/R2C/data/daily_1d.csv.gz \
    trading/docs/research/tp_loop/C/report.md \
    trading/docs/research/lev_loop/review2/review.md; do
    if [ -f "$f" ]; then shasum -a 256 "$f"; else printf 'MISSING  %s\n' "$f"; fi
  done
} > "$OUT"
