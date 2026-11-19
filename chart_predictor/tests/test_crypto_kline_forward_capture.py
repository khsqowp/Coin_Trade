import pytest
import hashlib
import json
import time

from scripts.research.crypto_kline_forward_capture import (
    CaptureLimitReached,
    JsonlCapture,
    _latest_closed_open_ms,
    parse_closed_kline,
)


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
    assert report["capture_window_elapsed"] is True
    assert report["feed_completeness_verified"] is False
    assert report["duplicates_skipped"] == 1
    assert report["missing_minutes_observed"]["BTCUSDT"] == 1
    assert report["rows_by_symbol"]["BTCUSDT"] == 2
    assert hashlib.sha256(writer.final.read_bytes()).hexdigest() == report["sha256"]
    records = [json.loads(line) for line in writer.final.read_text().splitlines()]
    assert any(record.get("category") == "minute_gap" for record in records)


def test_capture_records_gap_before_first_observed_bar(tmp_path):
    row = parse_closed_kline(kline_message(), {"BTCUSDT"})
    expected_open = row["open_ms"]
    row["open_ms"] += 120_000
    row["close_ms"] += 120_000
    writer = JsonlCapture(tmp_path, ["BTCUSDT"], [{"symbol": "BTCUSDT"}])
    writer.first_connected_ms = expected_open + 1_000
    started = time.monotonic()

    assert writer.append_kline(row, expected_open + 180_000) is True
    writer.finalize(True, 0, started)

    report = json.loads(writer.manifest.read_text())
    assert report["first_open_ms"]["BTCUSDT"] == expected_open + 120_000
    assert report["missing_minutes_observed"]["BTCUSDT"] == 2
    records = [json.loads(line) for line in writer.final.read_text().splitlines()]
    assert any(record.get("category") == "initial_gap" for record in records)


def test_finalize_records_unobserved_tail_minutes(tmp_path):
    now_floor = int(time.time() * 1000) // 60_000 * 60_000
    open_ms = now_floor - 180_000
    row = parse_closed_kline(kline_message(), {"BTCUSDT"})
    row["open_ms"] = open_ms
    row["close_ms"] = open_ms + 59_999
    writer = JsonlCapture(tmp_path, ["BTCUSDT"], [{"symbol": "BTCUSDT"}])
    writer.first_connected_ms = open_ms
    started = time.monotonic()
    assert writer.append_kline(row, open_ms + 60_000) is True
    writer.finalize(True, 0, started)

    report = json.loads(writer.manifest.read_text())
    assert report["tail_missing_minutes_at_finalize"]["BTCUSDT"] >= 1
    assert report["last_open_ms"]["BTCUSDT"] == open_ms


def test_tail_gap_grace_avoids_counting_a_just_closed_candle_too_early():
    minute_open = 1_700_000_040_000
    minute_close_boundary = minute_open + 60_000

    before_delivery_grace = _latest_closed_open_ms(minute_close_boundary + 1_000)
    after_delivery_grace = _latest_closed_open_ms(minute_close_boundary + 20_000)

    assert before_delivery_grace == minute_open - 60_000
    assert after_delivery_grace == minute_open


def test_size_limit_keeps_partial_data_and_writes_manifest(tmp_path):
    row = parse_closed_kline(kline_message(), {"BTCUSDT"})
    writer = JsonlCapture(tmp_path, ["BTCUSDT"], [{"symbol": "BTCUSDT"}])
    writer.max_bytes = writer.bytes_written + 1
    started = time.monotonic()

    with pytest.raises(CaptureLimitReached):
        writer.append_kline(row, 1_700_000_100_000)
    writer.finalize(False, 0, started, "capture_size_limit")

    report = json.loads(writer.manifest.read_text())
    assert report["complete"] is False
    assert report["capture_window_elapsed"] is False
    assert report["feed_completeness_verified"] is False
    assert report["termination_reason"] == "capture_size_limit"
    assert writer.partial.exists()
    assert hashlib.sha256(writer.partial.read_bytes()).hexdigest() == report["sha256"]
