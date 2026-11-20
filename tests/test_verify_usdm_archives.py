import hashlib

from scripts.research.verify_usdm_archives import archive_path, verify


def test_archive_path_mapping_and_hash_verification(tmp_path):
    row = {"kind": "klines_1h", "symbol": "BTCUSDT", "month": "2024-01"}
    path = archive_path(tmp_path, row)
    assert path == tmp_path / "klines_1h/BTCUSDT/BTCUSDT-1h-2024-01.zip"
    path.parent.mkdir(parents=True)
    path.write_bytes(b"fixture")
    row["sha256"] = hashlib.sha256(b"fixture").hexdigest()
    result = verify({"archive_rows": [row]}, tmp_path)
    assert result["status"] == "PASS"
    assert result["checked"] == 1


def test_missing_and_mismatched_archives_fail_closed(tmp_path):
    rows = [
        {"kind": "funding", "symbol": "BTCUSDT", "month": "2024-01", "sha256": "0" * 64},
        {"kind": "mark_price_1h", "symbol": "ETHUSDT", "month": "2024-01", "sha256": "1" * 64},
    ]
    result = verify({"archive_rows": rows}, tmp_path)
    assert result["status"] == "FAIL"
    assert result["missing"] == 2
