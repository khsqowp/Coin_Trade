import io
import zipfile

import pandas as pd
import pytest

from scripts.research.audit_usdm_metrics_sample import (
    EXPECTED_COLUMNS, parse_and_validate_zip, parse_checksum, sample_requests,
)


def _zip_for(rows):
    frame = pd.DataFrame(rows, columns=EXPECTED_COLUMNS)
    raw = frame.to_csv(index=False).encode()
    out = io.BytesIO()
    with zipfile.ZipFile(out, "w", zipfile.ZIP_DEFLATED) as archive:
        archive.writestr("metrics.csv", raw)
    return out.getvalue()


def _row(timestamp, symbol="BTCUSDT"):
    return [timestamp, symbol, 1.0, 2.0, 0.9, 1.1, 0.8, 1.2]


def test_preregistered_sample_includes_fixed_dates_boundaries_and_missing_neighbors():
    selected = sample_requests(
        ["BTCUSDT"],
        [{"symbol": "BTCUSDT", "zip_missing": ["2023-12-16"]}],
    )
    assert ("BTCUSDT", "2023-12-15") in selected
    assert ("BTCUSDT", "2023-12-17") in selected
    assert ("BTCUSDT", "2023-12-16") not in selected
    assert "label_boundary_outside_cohort" in selected[("BTCUSDT", "2026-06-24")]


def test_publisher_checksum_digest_is_extracted():
    assert parse_checksum(b"ab" * 32 + b"  file.zip\n") == "ab" * 32
    with pytest.raises(ValueError):
        parse_checksum(b"not a sha256")


def test_zip_schema_and_five_minute_grid_validate():
    payload = _zip_for([_row(300_000), _row(600_000)])
    result = parse_and_validate_zip(payload, "BTCUSDT", "1970-01-01")
    assert result["row_count"] == 2
    assert result["timestamp_min_ms"] == 300_000


def test_exchange_datetime_string_is_parsed_as_utc():
    row = _row("1970-01-01 00:05:00")
    result = parse_and_validate_zip(_zip_for([row]), "BTCUSDT", "1970-01-01")
    assert result["timestamp_min_ms"] == 300_000


@pytest.mark.parametrize(
    "rows,reason",
    [
        ([_row(300_000), _row(300_000)], "duplicate timestamp"),
        ([_row(300_001)], "off the 5-minute UTC grid"),
        ([_row(300_000, "ETHUSDT")], "symbol field"),
    ],
)
def test_data_defects_fail_closed(rows, reason):
    with pytest.raises(ValueError, match=reason):
        parse_and_validate_zip(_zip_for(rows), "BTCUSDT", "1970-01-01")
