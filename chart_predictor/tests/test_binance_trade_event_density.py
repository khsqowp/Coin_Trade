import importlib.util
import hashlib
import zipfile
from collections import Counter
from pathlib import Path

import pytest

MODULE_PATH = Path(__file__).parents[2] / "scripts/research/audit_binance_trade_event_density.py"
SPEC = importlib.util.spec_from_file_location("trade_event_density", MODULE_PATH)
MODULE = importlib.util.module_from_spec(SPEC)
SPEC.loader.exec_module(MODULE)


def test_nearest_rank_uses_one_indexed_ceiling_rank():
    counts = Counter({0: 1, 1: 2, 3: 1})
    assert MODULE.nearest_rank(counts, 0.50) == 1
    assert MODULE.nearest_rank(counts, 0.95) == 3


def test_density_summary_counts_empty_bins_in_all_bin_quantiles():
    summary = MODULE.density_summary(Counter({2: 2, 1: 1}), expected_bins=4)
    assert summary["active_bins"] == 2
    assert summary["active_fraction"] == 0.5
    assert summary["all_bins"] == {"p50": 0, "p95": 2, "p99": 2, "max": 2}
    assert summary["active_bins_only"] == {"p50": 1, "p95": 2, "p99": 2, "max": 2}


def test_density_summary_rejects_impossible_or_empty_bin_counts():
    with pytest.raises(ValueError):
        MODULE.density_summary(Counter({0: 1, 1: 1, 2: 1}), expected_bins=2)
    with pytest.raises(ValueError):
        MODULE.density_summary(Counter({-1: 1}), expected_bins=2)


def test_frozen_utc_bin_boundaries_are_half_open():
    start, end = MODULE._bounds("2025-01-01")
    assert end - start == 86_400_000
    assert (start + 999) // 1_000 == (start // 1_000)
    assert (start + 1_000 - start) // 1_000 == 1
    assert (end - 1 - start) // 1_000 == 86_399
    assert not start <= end < end


def _trade_zip(tmp_path, rows):
    symbol, day = "BTCUSDT", "2025-01-01"
    name = f"{symbol}-trades-{day}.csv"
    archive_path = tmp_path / f"{name}.zip"
    with zipfile.ZipFile(archive_path, "w", compression=zipfile.ZIP_DEFLATED) as archive:
        archive.writestr(name, "trade Id,price,qty,quoteQty,time,isBuyerMaker\n" + "".join(rows))
    digest = hashlib.sha256(archive_path.read_bytes()).hexdigest()
    (tmp_path / f"{archive_path.name}.CHECKSUM").write_text(f"{digest}  {archive_path.name}\n")
    return archive_path, digest, symbol, day


def test_trade_parser_counts_fixed_bins_and_maps_aggressor_side(tmp_path):
    start, _ = MODULE._bounds("2025-01-01")
    rows = [
        f"1,ignored,ignored,ignored,{start},false\n",
        f"2,ignored,ignored,ignored,{start + 999},true\n",
        f"3,ignored,ignored,ignored,{start + 1_000},false\n",
        f"4,ignored,ignored,ignored,{start + 10_000},true\n",
        f"5,ignored,ignored,ignored,{start + 60_000},false\n",
        f"6,ignored,ignored,ignored,{start + 86_400_000 - 1},true\n",
    ]
    path, digest, symbol, day = _trade_zip(tmp_path, rows)
    result = MODULE.audit_trade_archive(path, symbol, day, digest)
    assert result["trade_rows"] == 6
    assert result["buyer_initiated_rows"] == 3
    assert result["seller_initiated_rows"] == 3
    assert result["widths_ms"]["1000"]["active_bins"] == 5
    assert result["widths_ms"]["10000"]["active_bins"] == 4
    assert result["widths_ms"]["60000"]["active_bins"] == 3
    assert "_histogram" not in result["widths_ms"]["1000"]


def test_trade_parser_rejects_next_midnight_and_mismatched_sidecar(tmp_path):
    _, end = MODULE._bounds("2025-01-01")
    path, digest, symbol, day = _trade_zip(tmp_path, [f"1,0,0,0,{end},false\n"])
    with pytest.raises(ValueError, match="outside UTC date"):
        MODULE.audit_trade_archive(path, symbol, day, digest)
    path, digest, symbol, day = _trade_zip(tmp_path, [f"1,0,0,0,{end - 1},false\n"])
    Path(f"{path}.CHECKSUM").write_text(f"{'0' * 64}  {path.name}\n")
    with pytest.raises(ValueError, match="hash differs"):
        MODULE.audit_trade_archive(path, symbol, day, digest)


def test_manifest_requires_fixed_original_sample_and_classification():
    with pytest.raises(ValueError):
        MODULE.summarize_manifest({"classification": "other", "rows": []}, Path("."))
    with pytest.raises(ValueError):
        MODULE.summarize_manifest({
            "classification": "historical_source_integrity_only_no_strategy_or_signal_test",
            "rows": [],
        }, Path("."))
