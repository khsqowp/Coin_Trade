from datetime import datetime, timezone

import numpy as np
import pyarrow as pa
import pyarrow.parquet as pq

from scripts.research.audit_crypto_minute_archive import audit


def _month_files(root, missing_mark_day=False, bad_ohlc=False):
    start = int(datetime(2024, 1, 1, tzinfo=timezone.utc).timestamp() * 1000)
    minute_times = np.arange(31 * 24 * 60, dtype=np.int64) * 60_000 + start
    for dataset in ("spot_klines_1m", "um_klines_1m", "um_markPriceKlines_1m"):
        times = minute_times
        if dataset == "um_markPriceKlines_1m" and missing_mark_day:
            times = times[(times < start + 5 * 86_400_000) | (times >= start + 6 * 86_400_000)]
        count = len(times)
        divisor = 1000 if dataset == "spot_klines_1m" else 1
        stored_times = times * divisor
        highs = np.full(count, 101.0)
        if dataset == "spot_klines_1m" and bad_ohlc:
            highs[0] = 99.0
        data = {"open_time": stored_times, "open": np.full(count, 100.0), "high": highs,
                "low": np.full(count, 99.0), "close": np.full(count, 100.5),
                "volume": np.ones(count), "close_time": stored_times + 59_999 * divisor,
                "quote_volume": np.full(count, 100.0), "count": np.ones(count, dtype=np.int64)}
        path = root / dataset / "BTCUSDT" / "2024-01.parquet"
        path.parent.mkdir(parents=True)
        pq.write_table(pa.table(data), path)
    fund_path = root / "um_fundingRate" / "BTCUSDT" / "2024-01.parquet"
    fund_path.parent.mkdir(parents=True)
    pq.write_table(pa.table({"calc_time": start + np.arange(93, dtype=np.int64) * 8 * 3_600_000,
                             "funding_interval_hours": np.full(93, 8)}), fund_path)


def test_archive_audit_passes_complete_month_and_hashes_files(tmp_path):
    root = tmp_path / "archive"
    _month_files(root)

    result = audit(root, "2024-01", "2024-01", with_hashes=True, validate_values=True)

    assert result["status"] == "PASS"
    assert result["complete_file_cohort"] == ["BTCUSDT"]
    assert result["complete_file_cohort_spot_perp_alignment_failures"] == []
    assert all(file["sha256"] for data in result["datasets"].values()
               for file in data["files"] if file["status"] == "PASS")
    assert all(file["stable_during_hash"] for data in result["datasets"].values()
               for file in data["files"] if file["status"] == "PASS")
    assert result["ohlc_values_checked"] is True
    assert all(not file["ohlc_value_audit"]["error_counts"]
               for data in result["datasets"].values() for file in data["files"]
               if file["status"] == "PASS" and "ohlc_value_audit" in file)


def test_archive_audit_exposes_mark_gap_and_cross_source_mismatch(tmp_path):
    root = tmp_path / "archive"
    _month_files(root, missing_mark_day=True)

    result = audit(root, "2024-01", "2024-01")

    assert result["status"] == "FAIL"
    assert result["datasets"]["um_markPriceKlines_1m"]["failed_count"] == 1
    assert result["complete_file_cohort_price_alignment_failures"] == [
        {"symbol": "BTCUSDT", "month": "2024-01",
         "present_price_datasets": ["spot_klines_1m", "um_klines_1m", "um_markPriceKlines_1m"],
         "timestamp_arrays_equal": False}
    ]


def test_archive_audit_detects_invalid_ohlc_envelope(tmp_path):
    root = tmp_path / "archive"
    _month_files(root, bad_ohlc=True)

    result = audit(root, "2024-01", "2024-01", validate_values=True)

    spot = next(item for item in result["datasets"]["spot_klines_1m"]["files"]
                if item["symbol"] == "BTCUSDT")
    assert spot["status"] == "FAIL"
    assert spot["ohlc_value_audit"]["error_counts"]["HIGH_LOW_ENVELOPE"] == 1
