import pytest
import hashlib
import json
import time

from scripts.research.crypto_kline_forward_capture import JsonlCapture, parse_closed_kline


def kline_message(*, closed=True, quote="100.0", buy_quote="65.0", volume="2",
                  buy_base="1.2", trade_count=10):
    return {
        "stream": "btcusdt@kline_1m",
        "data": {
            "e": "kline", "E": 1_700_000_059_999, "s": "BTCUSDT",
            "k": {
                "t": 1_700_000_040_000, "T": 1_700_000_099_999,
                "s": "BTCUSDT", "i": "1m", "o": "100", "c": "101",
                "h": "102", "l": "99", "v": volume, "n": trade_count,
                "x": closed, "q": quote, "V": buy_base, "Q": buy_quote,
            },
        },
    }


def test_closed_kline_is_normalized_and_keeps_exchange_fields():
    result = parse_closed_kline(kline_message(), {"BTCUSDT"})

    assert result["symbol"] == "BTCUSDT"
    assert result["interval"] == "1m"
    assert result["open_ms"] == 1_700_000_040_000
    assert result["quote_volume"] == "100.0"
    assert result["taker_buy_quote"] == "65.0"
    assert result["is_closed"] is True


def test_unfinished_kline_is_ignored():
    assert parse_closed_kline(kline_message(closed=False), {"BTCUSDT"}) is None


def test_zero_volume_candle_is_retained_but_not_feature_eligible():
    result = parse_closed_kline(
        kline_message(quote="0", buy_quote="0", volume="0", buy_base="0", trade_count=0),
        {"BTCUSDT"},
    )

    assert result["is_closed"] is True
    assert result["feature_eligible"] is False
    assert result["feature_exclusion_reason"] == "zero_volume"


def test_wrong_symbol_or_interval_is_rejected():
    with pytest.raises(ValueError, match="unexpected symbol"):
        parse_closed_kline(kline_message(), {"ETHUSDT"})

    message = kline_message()
    message["data"]["k"]["i"] = "5m"
    with pytest.raises(ValueError, match="interval"):
        parse_closed_kline(message, {"BTCUSDT"})


@pytest.mark.parametrize(
    "quote,buy_quote",
    [("0", "0"), ("100", "-1"), ("100", "101"), ("NaN", "2")],
)
def test_invalid_quote_flow_is_rejected(quote, buy_quote):
    with pytest.raises(ValueError):
        parse_closed_kline(kline_message(quote=quote, buy_quote=buy_quote), {"BTCUSDT"})


def test_nonconsecutive_close_timestamp_is_rejected():
    message = kline_message()
    message["data"]["k"]["T"] -= 1
    with pytest.raises(ValueError, match="close time"):
        parse_closed_kline(message, {"BTCUSDT"})


def test_off_grid_open_time_is_rejected():
    message = kline_message()
    message["data"]["k"]["t"] += 1
    message["data"]["k"]["T"] += 1
    with pytest.raises(ValueError, match="minute grid"):
        parse_closed_kline(message, {"BTCUSDT"})


def test_capture_skips_duplicate_and_records_gap_with_verified_manifest(tmp_path):
    row = parse_closed_kline(kline_message(), {"BTCUSDT"})
    writer = JsonlCapture(tmp_path, ["BTCUSDT"], [{"symbol": "BTCUSDT", "quoteVolume": 1}])
    started = time.monotonic()
    assert writer.append_kline(row, 1_700_000_100_000) is True
    assert writer.append_kline(row, 1_700_000_100_001) is False
    gap_row = dict(row, open_ms=row["open_ms"] + 120_000, close_ms=row["close_ms"] + 120_000)
    assert writer.append_kline(gap_row, 1_700_000_220_000) is True
    writer.finalize(True, 0, started)

    report = json.loads(writer.manifest.read_text())
    assert report["complete"] is True
    assert report["duplicates_skipped"] == 1
    assert report["missing_minutes_observed"]["BTCUSDT"] == 1
    assert report["rows_by_symbol"]["BTCUSDT"] == 2
    assert hashlib.sha256(writer.final.read_bytes()).hexdigest() == report["sha256"]
    records = [json.loads(line) for line in writer.final.read_text().splitlines()]
    assert any(record.get("category") == "minute_gap" for record in records)
