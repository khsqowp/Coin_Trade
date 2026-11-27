"""Read-only 1h timestamp coverage screen for a fixed 2018 crypto cohort."""

from __future__ import annotations

import datetime as dt
import os
from pathlib import Path
import zipfile


EXPECTED_DATA_DIR = "/Users/user/CODE/Coin_Trade/trading_data"
ARCHIVE_RELATIVE = Path(
    "external/crypto/kraken/ohlcvt_full_2026-09-30/Kraken_OHLCVT_Full.zip"
)
ASSETS = (
    "XRP", "ETH", "BCH", "ADA", "LTC", "IOTA", "XEM", "XLM", "DASH",
    "XMR", "NEO", "EOS", "BTG", "QTUM", "NANO", "TRX", "ETC", "LSK",
    "BCC", "ICX", "XVG", "BTS", "OMG", "ZEC", "ARDR", "STRAT", "PPT",
    "USDT", "WAVES",
)
BINANCE_COMPLETE = frozenset(
    "XRP ETH ADA LTC IOTA XLM DASH XMR NEO EOS QTUM TRX ETC LSK ICX XVG BTS OMG ZEC WAVES".split()
)
START_TS = 1514764800  # 2018-01-01T00:00:00Z
STOP_TS = 1672444799  # 2022-12-31T23:59:59Z
YEARS = (2018, 2022)


def require_data_root(value: str | None) -> Path:
    if value != EXPECTED_DATA_DIR:
        raise ValueError("TRADING_DATA_DIR must equal the canonical repository data path")
    root = Path(value).resolve(strict=True)
    if str(root) != EXPECTED_DATA_DIR:
        raise ValueError("resolved data root differs from canonical repository data path")
    return root


def choose_member(names: set[str], asset: str) -> str | None:
    if asset == "BCC":
        return None
    for quote in ("USD", "XBT"):
        candidate = f"{asset}{quote}_60.csv"
        if candidate in names:
            return candidate
    return None


def month_key(timestamp: int) -> str:
    return dt.datetime.fromtimestamp(timestamp, dt.timezone.utc).strftime("%Y-%m")


def months_from_timestamp_lines(lines) -> tuple[set[str], str | None]:
    """Read only each CSV line's first field; stop before data after 2022."""
    months: set[str] = set()
    previous: int | None = None
    for raw_line in lines:
        timestamp_field = raw_line.partition(b",")[0].strip()
        try:
            timestamp = int(timestamp_field)
        except ValueError:
            return months, "timestamp-parse"
        if previous is not None and timestamp < previous:
            return months, "timestamp-unsorted"
        previous = timestamp
        if timestamp > STOP_TS:
            break
        if START_TS <= timestamp <= STOP_TS:
            months.add(month_key(timestamp))
    return months, None


def full_years(months: set[str]) -> bool:
    return all(f"{year}-{month:02d}" in months for year in YEARS for month in range(1, 13))


def scan_archive(archive: Path) -> tuple[dict[str, tuple[str | None, set[str], str]], set[str]]:
    root = require_data_root(os.environ.get("TRADING_DATA_DIR"))
    archive = archive.resolve(strict=True)
    if os.path.commonpath((str(root), str(archive))) != str(root):
        raise ValueError("archive must be inside canonical TRADING_DATA_DIR")
    results: dict[str, tuple[str | None, set[str], str]] = {}
    with zipfile.ZipFile(archive, "r") as zipped:
        names = set(zipped.namelist())
        for asset in ASSETS:
            member = choose_member(names, asset)
            if asset == "BCC":
                results[asset] = (None, set(), "identity-unresolved")
            elif member is None:
                results[asset] = (None, set(), "member-missing")
            else:
                with zipped.open(member, "r") as stream:
                    months, error = months_from_timestamp_lines(stream)
                results[asset] = (member, months, error or "ok")
    kraken_complete = {
        asset
        for asset, (_member, months, status) in results.items()
        if status == "ok" and full_years(months)
    }
    return results, kraken_complete


def main() -> int:
    root = require_data_root(os.environ.get("TRADING_DATA_DIR"))
    archive = root / ARCHIVE_RELATIVE
    results, kraken_complete = scan_archive(archive)
    combined = BINANCE_COMPLETE | kraken_complete
    print(f"kraken_1h_month_complete={len(kraken_complete)}/29")
    print(f"binance_fixed_quote_key_complete={len(BINANCE_COMPLETE)}/29")
    print(f"union_preliminary={len(combined)}/29 threshold=25 result={'PASS' if len(combined) >= 25 else 'FAIL'}")
    print("asset,member,status,2018_months,2022_months")
    for asset in ASSETS:
        member, months, status = results[asset]
        y18 = sum(f"2018-{month:02d}" in months for month in range(1, 13))
        y22 = sum(f"2022-{month:02d}" in months for month in range(1, 13))
        print(f"{asset},{member or '-'},{status},{y18}/12,{y22}/12")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
