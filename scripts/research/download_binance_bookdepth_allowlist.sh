#!/bin/bash
set -euo pipefail

# Fixed historical-only sample registered in
# docs/research/binance-bookdepth-archive-feasibility-prereg-2026-11-19.md.
# No live endpoints, outcome data, or symbols/dates outside this allowlist.

root="${1:-/private/tmp/binance-bookdepth-audit-20261119}"
mkdir -p "$root"
manifest="$root/http_status.tsv"
printf 'symbol\tdate_utc\tchecksum_http_status\tarchive_http_status\n' > "$manifest"

symbols=(BTCUSDT ETHUSDT BNBUSDT SOLUSDT XRPUSDT ADAUSDT DOGEUSDT TRXUSDT LTCUSDT BCHUSDT LINKUSDT DOTUSDT AVAXUSDT XLMUSDT ETCUSDT FILUSDT UNIUSDT AAVEUSDT NEARUSDT APTUSDT)
main_days=(2025-01-01 2025-04-01 2025-07-01 2025-10-01)
diagnostic_symbols=(SOLUSDT BTCUSDT ETHUSDT AVAXUSDT)
diagnostic_days=(2026-09-02 2026-09-03 2026-09-04 2026-09-05 2026-09-06)
total=100
done_count=0

download_one() {
  local symbol="$1" day="$2" directory filename base checksum_status archive_status expected actual
  directory="$root/$symbol"
  mkdir -p "$directory"
  filename="${symbol}-bookDepth-${day}.zip"
  base="https://data.binance.vision/data/futures/um/daily/bookDepth/${symbol}/${filename}"
  checksum_status="$(curl --fail --silent --show-error --location --max-time 45 --retry 2 --retry-delay 1 --output "$directory/${filename}.CHECKSUM.part" --write-out '%{http_code}' "${base}.CHECKSUM")"
  [[ "$checksum_status" == "200" ]]
  mv "$directory/${filename}.CHECKSUM.part" "$directory/${filename}.CHECKSUM"
  expected="$(awk 'NR == 1 {print $1}' "$directory/${filename}.CHECKSUM")"
  [[ "${#expected}" -eq 64 && "$expected" != *[!0-9a-fA-F]* ]]
  archive_status="$(curl --fail --silent --show-error --location --max-time 90 --retry 2 --retry-delay 1 --output "$directory/${filename}.part" --write-out '%{http_code}' "$base")"
  [[ "$archive_status" == "200" ]]
  actual="$(shasum -a 256 "$directory/${filename}.part" | awk '{print $1}')"
  [[ "$actual" == "$expected" ]]
  mv "$directory/${filename}.part" "$directory/$filename"
  printf '%s\t%s\t%s\t%s\n' "$symbol" "$day" "$checksum_status" "$archive_status" >> "$manifest"
  done_count=$((done_count + 1))
  printf 'download %s/%s symbol=%s date=%s checksum=pass HTTP=%s/%s\n' "$done_count" "$total" "$symbol" "$day" "$checksum_status" "$archive_status"
}

for day in "${main_days[@]}"; do
  for symbol in "${symbols[@]}"; do
    download_one "$symbol" "$day"
  done
done

for day in "${diagnostic_days[@]}"; do
  for symbol in "${diagnostic_symbols[@]}"; do
    download_one "$symbol" "$day"
  done
done

printf 'download complete: %s/%s symbol-days; raw files=%s; HTTP manifest=%s\n' "$done_count" "$total" "$root" "$manifest"
