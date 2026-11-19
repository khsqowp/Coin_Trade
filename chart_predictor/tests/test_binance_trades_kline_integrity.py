import csv
import hashlib
import io
import zipfile
from datetime import date, datetime, timezone

from scripts.research.audit_binance_trades_kline_reconciliation import (
    KLINE_HEADER,
    TRADE_HEADER,
    audit_pair,
)


SYMBOL = "BTCUSDT"
DAY = "2025-01-01"
MINUTE_MS = 60_000
DAY_START_MS = int(datetime.combine(
    date.fromisoformat(DAY), datetime.min.time(), timezone.utc
).timestamp() * 1000)


def _write_zip(path, member, header, rows):
    buffer = io.StringIO(newline="")
    writer = csv.writer(buffer, lineterminator="\n")
    writer.writerow(header)
    writer.writerows(rows)
    with zipfile.ZipFile(path, "w", compression=zipfile.ZIP_DEFLATED) as archive:
        archive.writestr(member, buffer.getvalue())
    digest = hashlib.sha256(path.read_bytes()).hexdigest()
    path.with_name(path.name + ".CHECKSUM").write_text(
        f"{digest}  {path.name}\n", encoding="ascii"
    )


def _synthetic_pair(root, *, native_taker_buy_quote="100", native_only_minute=False,
                    trade_quote_qty="100"):
    trades_dir = root / "trades"
    klines_dir = root / "klines"
    trades_dir.mkdir()
    klines_dir.mkdir()

    trade_rows = [
        [1, "100", "1", trade_quote_qty, DAY_START_MS + 1, "false"],
        [2, "101", "1", "101", DAY_START_MS + 2, "true"],
    ]
    _write_zip(
        trades_dir / f"{SYMBOL}-trades-{DAY}.zip",
        f"{SYMBOL}-trades-{DAY}.csv",
        TRADE_HEADER,
        trade_rows,
    )

    kline_rows = []
    for minute in range(1440):
        open_time = DAY_START_MS + minute * MINUTE_MS
        if minute == 0:
            values = ["100", "101", "100", "101", "2", "201", "2", "1", native_taker_buy_quote, "0"]
        elif minute == 1 and native_only_minute:
            values = ["100", "102", "100", "102", "1", "102", "1", "1", "102", "0"]
        else:
            values = ["100", "100", "100", "100", "0", "0", "0", "0", "0", "0"]
        kline_rows.append([
            open_time, values[0], values[1], values[2], values[3], values[4],
            open_time + MINUTE_MS - 1, values[5], values[6], values[7],
            values[8], values[9],
        ])
    _write_zip(
        klines_dir / f"{SYMBOL}-1m-{DAY}.zip",
        f"{SYMBOL}-1m-{DAY}.csv",
        KLINE_HEADER,
        kline_rows,
    )
    return trades_dir, klines_dir


def test_synthetic_raw_trades_reconstruct_one_active_kline_and_full_zero_grid(tmp_path):
    trades_dir, klines_dir = _synthetic_pair(tmp_path)

    result = audit_pair(trades_dir, klines_dir, SYMBOL, DAY)

    assert result["symbol_day_integrity_pass"] is True
    assert {key: result["grid"][key] for key in (
        "expected_minutes", "native_minutes", "native_grid_complete",
        "native_active", "raw_active", "common_active",
        "native_only_active", "raw_only_active",
    )} == {
        "expected_minutes": 1440,
        "native_minutes": 1440,
        "native_grid_complete": True,
        "native_active": 1,
        "raw_active": 1,
        "common_active": 1,
        "native_only_active": 0,
        "raw_only_active": 0,
    }
    assert all(item["count"] == 0 for key, item in result["mismatches"].items()
               if key != "quote_price_times_qty_diagnostic")
    assert result["integrity"]["trade_rows"] == 2
    assert result["quote_qty_arithmetic_anomalies"] == []
    assert result["mismatches"]["taker_buy_quote_price_times_qty_diagnostic"] == {
        "count": 0,
        "denominator": 1440,
        "gating": False,
    }


def test_synthetic_taker_buy_quote_mismatch_fails_full_grid_field_check(tmp_path):
    trades_dir, klines_dir = _synthetic_pair(
        tmp_path, native_taker_buy_quote="99"
    )

    result = audit_pair(trades_dir, klines_dir, SYMBOL, DAY)

    assert result["symbol_day_integrity_pass"] is False
    assert result["mismatches"]["taker_buy_quote"] == {
        "count": 1,
        "denominator": 1440,
    }
    assert {
        "field": "taker_buy_quote",
        "minute_open_time_ms": DAY_START_MS,
        "raw_value": "100",
        "native_value": "99",
        "absolute_difference": "1",
    } in result["mismatch_details"]
    assert "field_mismatch:taker_buy_quote" in result["failure_reasons"]


def test_native_only_active_minute_is_counted_as_ohlc_mismatch_and_reported(tmp_path):
    trades_dir, klines_dir = _synthetic_pair(
        tmp_path, native_only_minute=True
    )

    result = audit_pair(trades_dir, klines_dir, SYMBOL, DAY)

    assert result["mismatches"]["open"] == {"count": 1, "denominator": 2}
    assert result["grid"]["native_only_active_minutes_ms"] == [
        DAY_START_MS + MINUTE_MS
    ]
    assert result["grid"]["raw_active_minutes_ms"] == [DAY_START_MS]
    assert result["grid"]["union_active_minutes_ms"] == [
        DAY_START_MS, DAY_START_MS + MINUTE_MS
    ]
    assert result["integrity"]["min_trade_timestamp_ms"] == DAY_START_MS + 1
    assert result["integrity"]["max_trade_timestamp_ms"] == DAY_START_MS + 2
    assert result["integrity"]["min_kline_open_time_ms"] == DAY_START_MS
    assert result["integrity"]["max_kline_open_time_ms"] == DAY_START_MS + 1439 * MINUTE_MS


def test_quote_qty_arithmetic_anomaly_is_reported_without_gating_product_diagnostic(tmp_path):
    trades_dir, klines_dir = _synthetic_pair(tmp_path, trade_quote_qty="1")

    result = audit_pair(trades_dir, klines_dir, SYMBOL, DAY)

    assert result["quote_qty_arithmetic_anomalies"] == [{
        "trade_id": 1,
        "timestamp_ms": DAY_START_MS + 1,
        "price": "100",
        "qty": "1",
        "quote_qty": "1",
        "price_times_qty": "100",
        "absolute_difference": "99",
        "is_buyer_maker": "false",
    }]
    assert result["mismatches"]["quote_price_times_qty_diagnostic"]["count"] == 0
    assert result["mismatches"]["taker_buy_quote_price_times_qty_diagnostic"]["count"] == 0
    assert "field_mismatch:quote_volume" in result["failure_reasons"]
