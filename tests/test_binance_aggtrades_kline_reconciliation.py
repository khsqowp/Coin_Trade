from __future__ import annotations

import hashlib
import sys
import zipfile
from pathlib import Path

import pytest

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
from scripts.research.audit_binance_aggtrades_kline_reconciliation import audit_pair


def _write_zip(path: Path, member: str, content: str) -> None:
    with zipfile.ZipFile(path, "w", compression=zipfile.ZIP_DEFLATED) as archive:
        archive.writestr(member, content)
    digest = hashlib.sha256(path.read_bytes()).hexdigest()
    Path(f"{path}.CHECKSUM").write_text(f"{digest}  {path.name}\n", encoding="utf-8")


def test_audit_pair_reconciles_valid_archive_pair(tmp_path: Path) -> None:
    day = "2025-01-01"
    _write_zip(
        tmp_path / f"BTCUSDT-aggTrades-{day}.zip",
        f"BTCUSDT-aggTrades-{day}.csv",
        "agg_trade_id,price,quantity,first_trade_id,last_trade_id,transact_time,is_buyer_maker\n"
        "10,100,2,20,20,1735689601000,false\n"
        "11,101,1,22,22,1735689600000,true\n",
    )
    _write_zip(
        tmp_path / f"BTCUSDT-1m-{day}.zip",
        f"BTCUSDT-1m-{day}.csv",
        "open_time,open,high,low,close,volume,close_time,quote_volume,count,taker_buy_volume,taker_buy_quote_volume,ignore\n"
        "1735689600000,101,101,100,100,3,1735689659999,301,2,2,200,0\n",
    )

    result = audit_pair(tmp_path, "BTCUSDT", day)

    assert result["archives"]["publisher_checksums_passed"] is True
    assert result["minutes"] == {
        "expected": 1440,
        "aggTrades": 1,
        "klines": 1,
        "both": 1,
        "aggTrades_only": 0,
        "kline_only": 0,
    }
    assert all(value == 0 for value in result["minute_mismatch_count"].values())
    assert result["integrity"]["nonmonotonic_agg_timestamps"] == 1
    assert result["daily_totals"]["base_match"] is True
    assert result["daily_totals"]["quote_match"] is True


def test_audit_pair_rejects_publisher_checksum_mismatch(tmp_path: Path) -> None:
    day = "2025-01-01"
    archive = tmp_path / f"BTCUSDT-aggTrades-{day}.zip"
    _write_zip(
        archive,
        f"BTCUSDT-aggTrades-{day}.csv",
        "agg_trade_id,price,quantity,first_trade_id,last_trade_id,transact_time,is_buyer_maker\n",
    )
    Path(f"{archive}.CHECKSUM").write_text("0" * 64 + "  bad.zip\n", encoding="utf-8")

    with pytest.raises(ValueError, match="publisher checksum mismatch"):
        audit_pair(tmp_path, "BTCUSDT", day)
