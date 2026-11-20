import csv
from datetime import datetime, timezone
import io
import zipfile

from scripts.research.audit_usdm_timestamps import audit_cohort


def zip_csv(path, columns, rows):
    path.parent.mkdir(parents=True, exist_ok=True)
    text = io.StringIO()
    writer = csv.DictWriter(text, fieldnames=columns)
    writer.writeheader()
    writer.writerows(rows)
    with zipfile.ZipFile(path, "w", zipfile.ZIP_DEFLATED) as archive:
        archive.writestr("data.csv", text.getvalue())


def test_one_month_requires_identical_hour_bars_and_valid_funding(tmp_path):
    symbol, month = "BTCUSDT", "2024-01"
    start = int(datetime(2024, 1, 1, tzinfo=timezone.utc).timestamp() * 1000)
    bar_rows = [{"open_time": start + i * 3_600_000, "open": 1, "high": 1,
                 "low": 1, "close": 1} for i in range(31 * 24)]
    for kind in ("klines_1h", "mark_price_1h"):
        rows = bar_rows if kind == "klines_1h" else [
            {**bar_rows[0], "open_time": start - 3_600_000}, *bar_rows
        ]
        zip_csv(tmp_path / kind / symbol / f"{symbol}-1h-{month}.zip",
                ["open_time", "open", "high", "low", "close"], rows)
    funding_rows = [{"calc_time": start + 15 + i * 8 * 3_600_000,
                     "funding_interval_hours": 8, "last_funding_rate": 0.0001}
                    for i in range(31 * 3)]
    zip_csv(tmp_path / "funding" / symbol / f"{symbol}-fundingRate-{month}.zip",
            ["calc_time", "funding_interval_hours", "last_funding_rate"], funding_rows)
    audit = {"archive_rows": [
        {"symbol": symbol, "month": month, "kind": kind,
         **({"first_ms": start - (3_600_000 if kind == "mark_price_1h" else 0),
             "last_ms": start + (31 * 24 - 1) * 3_600_000}
            if kind in {"klines_1h", "mark_price_1h"} else {})} for kind in
        ("klines_1h", "mark_price_1h", "funding")
    ]}
    coverage = {"cohorts_by_exact_run": {f"{month}..{month}": [symbol]}}

    result = audit_cohort(audit, coverage, tmp_path, f"{month}..{month}")

    assert result["status"] == "PASS"
    assert result["checked"] == 1
    assert result["candle_mark_timestamp_mismatches"] == 0
    assert result["mark_hours_outside_kline_window"] == 1
