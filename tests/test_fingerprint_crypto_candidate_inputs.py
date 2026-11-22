import json

import pytest

from scripts.research.fingerprint_crypto_candidate_inputs import fingerprint


def _fixture(tmp_path):
    root = tmp_path / "archive"
    symbols = [f"S{i:02d}" for i in range(32)]
    months = ([f"2024-{m:02d}" for m in range(10, 13)]
              + [f"2025-{m:02d}" for m in range(1, 13)]
              + [f"2026-{m:02d}" for m in range(1, 11)])
    datasets = {}
    for dataset in ("spot_klines_1m", "um_klines_1m"):
        records = []
        for symbol in symbols:
            for month in months:
                path = root / dataset / symbol / f"{month}.parquet"
                path.parent.mkdir(parents=True, exist_ok=True)
                path.write_bytes(f"{dataset}/{symbol}/{month}".encode())
                info = path.stat()
                records.append({"symbol": symbol, "month": month, "status": "PASS",
                                "size_bytes": info.st_size, "mtime_ns": info.st_mtime_ns})
        datasets[dataset] = {"files": records}
    audit_path = tmp_path / "audit.json"
    audit_path.write_text(json.dumps({
        "ohlc_values_checked": True,
        "start_month": "2024-10",
        "end_month": "2026-10",
        "complete_file_cohort_symbol_count": 32,
        "complete_file_cohort_month_count": 25,
        "complete_file_cohort": symbols,
        "datasets": datasets,
    }))
    return root, audit_path


def test_fingerprints_exact_frozen_spot_perp_cohort(tmp_path):
    root, audit = _fixture(tmp_path)

    result = fingerprint(root, audit)

    assert result["file_count"] == 1600
    assert result["total_bytes"] > 0
    assert len(result["aggregate_sha256"]) == 64
    assert result["all_files_stable"] is True
    assert all(len(item["sha256"]) == 64 for item in result["files"])


def test_fingerprint_rejects_file_changed_since_ohlc_audit(tmp_path):
    root, audit = _fixture(tmp_path)
    path = root / "spot_klines_1m" / "S00" / "2024-10.parquet"
    path.write_bytes(b"mutated")

    with pytest.raises(RuntimeError, match="changed since OHLC audit"):
        fingerprint(root, audit)


def test_fingerprint_rejects_incomplete_cohort(tmp_path):
    root, audit = _fixture(tmp_path)
    payload = json.loads(audit.read_text())
    payload["datasets"]["um_klines_1m"]["files"].pop()
    audit.write_text(json.dumps(payload))

    with pytest.raises(ValueError, match="expected 800 audit records"):
        fingerprint(root, audit)
