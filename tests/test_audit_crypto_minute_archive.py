from datetime import datetime, timezone

import numpy as np
import pyarrow as pa
import pyarrow.parquet as pq

from scripts.research.audit_crypto_minute_archive import audit


def _month_files(root, missing_mark_day=False):
    start = int(datetime(2024, 1, 1, tzinfo=timezone.utc).timestamp() * 1000)
    minute_times = np.arange(31 * 24 * 60, dtype=np.int64) * 60_000 + start
    for dataset in ("spot_klines_1m", "um_klines_1m", "um_markPriceKlines_1m"):
        times = minute_times
        if dataset == "um_markPriceKlines_1m" and missing_mark_day:
            times = times[(times < start + 5 * 86_400_000) | (times >= start + 6 * 86_400_000)]
        path = root / dataset / "BTCUSDT" / "2024-01.parquet"
        path.parent.mkdir(parents=True)
        pq.write_table(pa.table({"open_time": times}), path)
    fund_path = root / "um_fundingRate" / "BTCUSDT" / "2024-01.parquet"
    fund_path.parent.mkdir(parents=True)
    pq.write_table(pa.table({"calc_time": start + np.arange(93, dtype=np.int64) * 8 * 3_600_000,
                             "funding_interval_hours": np.full(93, 8)}), fund_path)


def test_archive_audit_passes_complete_month_and_hashes_files(tmp_path):
    root = tmp_path / "archive"
    _month_files(root)

    result = audit(root, "2024-01", "2024-01", with_hashes=True)

    assert result["status"] == "PASS"
    assert result["complete_file_cohort"] == ["BTCUSDT"]
    assert result["complete_file_cohort_spot_perp_alignment_failures"] == []
    assert all(file["sha256"] for data in result["datasets"].values()
               for file in data["files"] if file["status"] == "PASS")


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
