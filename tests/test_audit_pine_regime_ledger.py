import csv
import io
import json
import zipfile

from scripts.research.audit_pine_regime_ledger import audit


def _write_zip(path, header, rows):
    path.parent.mkdir(parents=True, exist_ok=True)
    payload = io.StringIO(newline="")
    writer = csv.DictWriter(payload, fieldnames=header)
    writer.writeheader()
    writer.writerows(rows)
    with zipfile.ZipFile(path, "w", compression=zipfile.ZIP_DEFLATED) as archive:
        archive.writestr(path.stem + ".csv", payload.getvalue())


def test_independent_raw_archive_audit_recalculates_target_first_trade(tmp_path):
    root = tmp_path / "archives"
    symbol = "BTCUSDT"
    entry_ms = 1_704_067_200_000  # 2024-01-01 00:00 UTC
    klines = []
    for idx in range(20):
        klines.append({
            "open_time": entry_ms + idx * 3_600_000,
            "open": 100.0, "high": 103.0 if idx == 0 else 101.0,
            "low": 100.0 if idx == 0 else 99.0, "close": 101.0,
        })
    _write_zip(root / "klines_1h" / symbol / f"{symbol}-1h-2024-01.zip",
               ["open_time", "open", "high", "low", "close"], klines)
    _write_zip(root / "funding" / symbol / f"{symbol}-fundingRate-2024-01.zip",
               ["calc_time", "last_funding_rate"], [])
    ledger = tmp_path / "signals.jsonl"
    ledger.write_text(json.dumps({
        "symbol": symbol, "signal_close_ms": entry_ms, "entry_open_ms": entry_ms,
        "side": "LONG", "entry": 100.0, "risk": 1.0, "reason": "TARGET",
        "exit_price": 102.0, "net_base": 0.019, "net_stress": 0.017,
    }) + "\n", encoding="utf-8")

    result = audit(root, ledger, sample_size=100)

    assert result["status"] == "PASS"
    assert result["checked"] == 1
    assert result["mismatches"] == 0
