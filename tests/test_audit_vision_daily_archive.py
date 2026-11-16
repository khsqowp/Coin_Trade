import csv
import hashlib
import importlib.util
import io
import zipfile
from pathlib import Path


SCRIPT = Path(__file__).parents[1] / "scripts/research/audit_vision_daily_archive.py"
SPEC = importlib.util.spec_from_file_location("audit_vision_daily_archive", SCRIPT)
AUDITOR = importlib.util.module_from_spec(SPEC)
assert SPEC.loader is not None
SPEC.loader.exec_module(AUDITOR)


def _write_metrics_archive(path: Path, rows: list[list[str]]) -> None:
    content = io.StringIO()
    writer = csv.writer(content)
    writer.writerow([
        "create_time", "symbol", "sum_open_interest",
        "count_toptrader_long_short_ratio",
    ])
    writer.writerows(rows)
    with zipfile.ZipFile(path, "w", compression=zipfile.ZIP_DEFLATED) as archive:
        archive.writestr("sample.csv", content.getvalue())
    path.with_suffix(path.suffix + ".CHECKSUM").write_text(
        f"{hashlib.sha256(path.read_bytes()).hexdigest()}  {path.name}\n",
        encoding="utf-8",
    )


def test_expected_grid_uses_archive_day_even_if_early_rows_are_missing(tmp_path: Path) -> None:
    archive = tmp_path / "BTCUSDT-metrics-2024-02-16.zip"
    _write_metrics_archive(archive, [
        ["2024-02-16 00:10:00", "BTCUSDT", "100", "1.2"],
        ["2024-02-16 00:15:00", "BTCUSDT", "101", "1.3"],
    ])

    result = AUDITOR.audit(archive, interval_minutes=5)

    assert result["expected_grid_rows"] == 288
    assert result["missing_grid_slots"] == 286
    assert result["min_timestamp_utc"] == "2024-02-16T00:10:00+00:00"


def test_blank_metric_field_is_reported_without_imputation(tmp_path: Path) -> None:
    archive = tmp_path / "BTCUSDT-metrics-2025-07-22.zip"
    _write_metrics_archive(archive, [
        ["2025-07-22 00:00:00", "BTCUSDT", "100", ""],
    ])

    result = AUDITOR.audit(archive, interval_minutes=5)

    assert result["blank_values_by_column"]["count_toptrader_long_short_ratio"] == 1
    assert result["nonfinite_or_non_numeric_by_column"]["count_toptrader_long_short_ratio"] == 1
