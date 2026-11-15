import hashlib
import json

import pytest

from scripts.research.crypto_l2_compact import reduce_capture
from scripts.research.crypto_l2_windows import aggregate_windows, is_available_by_decision


def _record(kind, symbol, event, t, **extra):
    return {
        "kind": kind,
        "symbol": symbol,
        "event": event,
        "received_at_ms": t,
        "received_monotonic_s": t / 1000,
        **extra,
    }


def _write_source(path, records):
    path.write_text("".join(json.dumps(row, separators=(",", ":")) + "\n" for row in records))


def test_reducer_replays_snapshot_bridge_then_emits_causal_trade_quote(tmp_path):
    source = tmp_path / "capture.jsonl"
    output = tmp_path / "compact.jsonl"
    symbol = "BTCUSDT"
    records = [
        _record("depth_delta", symbol,
                {"e": "depthUpdate", "s": symbol, "U": 10, "u": 11, "pu": 9,
                 "T": 1000, "b": [["99.99", "2"]], "a": [["100.01", "3"]]}, 1001),
        _record("depth_snapshot", symbol,
                {"lastUpdateId": 12, "bids": [["99.99", "1"]], "asks": [["100.01", "1"]]}, 1002),
        _record("depth_delta", symbol,
                {"e": "depthUpdate", "s": symbol, "U": 12, "u": 13, "pu": 11,
                 "T": 1010, "b": [["99.99", "3"]], "a": []}, 1011),
        _record("depth_delta", symbol,
                {"e": "depthUpdate", "s": symbol, "U": 14, "u": 14, "pu": 13,
                 "T": 1011, "b": [["99.99", "4"]], "a": []}, 1012),
        _record("aggTrade", symbol,
                {"e": "aggTrade", "s": symbol, "a": 7, "f": 7, "l": 7,
                 "T": 1012, "p": "100", "q": "0.5", "m": True}, 1013),
    ]
    _write_source(source, records)

    manifest = reduce_capture(source, output)
    rows = [json.loads(line) for line in output.read_text().splitlines()]

    assert manifest["source_sha256"] == hashlib.sha256(source.read_bytes()).hexdigest()
    assert manifest["output_sha256"] == hashlib.sha256(output.read_bytes()).hexdigest()
    assert manifest["synchronized_snapshots"] == 1
    assert manifest["strategy_metrics"] is None
    trade = rows[-1]
    assert trade["kind"] == "agg_trade"
    assert trade["book_last_update_id"] == 14
    assert trade["book_receive_age_ms"] == pytest.approx(1)
    assert trade["seller_initiated"] is True
    assert trade["bid"] == 99.99
    assert trade["ask"] == 100.01
    assert trade["bid_depth_quote_5bp_top5"] == pytest.approx(399.96)


def test_reducer_fails_closed_after_sequence_gap_and_refuses_overwrite(tmp_path):
    source = tmp_path / "capture.jsonl"
    output = tmp_path / "compact.jsonl"
    symbol = "BTCUSDT"
    records = [
        _record("depth_delta", symbol,
                {"e": "depthUpdate", "s": symbol, "U": 10, "u": 11, "pu": 9,
                 "T": 1000, "b": [], "a": []}, 1001),
        _record("depth_snapshot", symbol,
                {"lastUpdateId": 10, "bids": [["99", "1"]], "asks": [["101", "1"]]}, 1002),
        _record("depth_delta", symbol,
                {"e": "depthUpdate", "s": symbol, "U": 13, "u": 13, "pu": 12,
                 "T": 1010, "b": [], "a": []}, 1011),
        _record("aggTrade", symbol,
                {"e": "aggTrade", "s": symbol, "a": 8, "f": 8, "l": 8,
                 "T": 1012, "p": "100", "q": "1", "m": False}, 1013),
    ]
    _write_source(source, records)

    result = reduce_capture(source, output)
    rows = [json.loads(line) for line in output.read_text().splitlines()]
    assert result["invalidations"] == 1
    assert not any(row["kind"] == "agg_trade" for row in rows)
    with pytest.raises(FileExistsError):
        reduce_capture(source, output)


def test_reducer_enforces_output_cap_without_finalizing_partial(tmp_path):
    source = tmp_path / "capture.jsonl"
    output = tmp_path / "compact.jsonl"
    symbol = "BTCUSDT"
    _write_source(source, [
        _record("depth_delta", symbol,
                {"e": "depthUpdate", "s": symbol, "U": 10, "u": 11, "pu": 9,
                 "T": 1000, "b": [], "a": []}, 1001),
        _record("depth_snapshot", symbol,
                {"lastUpdateId": 10, "bids": [["99", "1"]], "asks": [["101", "1"]]}, 1002),
    ])

    with pytest.raises(OSError, match="cap exceeded"):
        reduce_capture(source, output, max_output_bytes=128)
    assert not output.exists()
    assert (tmp_path / "compact.jsonl.partial").exists()


def _compact_row(kind, event_ms, receive_ms, **values):
    row = {
        "kind": kind,
        "symbol": "BTCUSDT",
        "exchange_event_ms": event_ms,
        "received_at_ms": receive_ms,
        "received_monotonic_s": receive_ms / 1000,
        **values,
    }
    if kind == "agg_trade":
        row.setdefault("bid", 99.99)
        row.setdefault("ask", 100.01)
        row.setdefault("bid_levels_5bp_top5", [])
        row.setdefault("ask_levels_5bp_top5", [])
    return row


def test_10s_aggregation_uses_utc_event_time_and_computes_refill(tmp_path):
    source = tmp_path / "compact.jsonl"
    output = tmp_path / "windows.jsonl"
    rows = [
        _compact_row("book_update", 99_500, 99_510,
                     bid=99.99, ask=100.01, mid=100,
                     bid_depth_quote_5bp_top5=100, ask_depth_quote_5bp_top5=200,
                     last_update_id=1),
        _compact_row("agg_trade", 101_000, 101_020, trade_id=10,
                     quote_quantity=250, seller_initiated=True, price=100.2,
                     trade_id_gap_before=False, book_receive_age_ms=10),
        _compact_row("book_update", 105_000, 105_030,
                     bid=100.09, ask=100.11, mid=100.1,
                     bid_depth_quote_5bp_top5=30, ask_depth_quote_5bp_top5=80,
                     last_update_id=2),
        _compact_row("agg_trade", 108_000, 108_020, trade_id=11,
                     quote_quantity=125, seller_initiated=False, price=100.3,
                     trade_id_gap_before=False, book_receive_age_ms=20),
        _compact_row("book_update", 111_500, 111_530,
                     bid=100.19, ask=100.21, mid=100.2,
                     bid_depth_quote_5bp_top5=80, ask_depth_quote_5bp_top5=150,
                     last_update_id=3),
        _compact_row("agg_trade", 114_500, 114_520, trade_id=12,
                     quote_quantity=50, seller_initiated=False, price=100.4,
                     trade_id_gap_before=False, book_receive_age_ms=10),
    ]
    _write_source(source, rows)

    manifest = aggregate_windows(source, output, allowed_lateness_ms=2000)
    windows = [json.loads(line) for line in output.read_text().splitlines()]
    target = next(row for row in windows if row["window_start_ms"] == 100_000)

    assert manifest["quality_pass"] is True
    assert target["window_final"] is True
    assert target["trade_count"] == 2
    assert target["sell_aggressor_quote_volume"] == pytest.approx(250)
    assert target["buy_aggressor_quote_volume"] == pytest.approx(125)
    assert target["dpre"]["bid"] == pytest.approx(100)
    assert target["dmin_bid"]["bid"] == pytest.approx(30)
    assert target["d_plus_2s"]["bid"] == pytest.approx(80)
    assert target["bid_replenishment_ratio"] == pytest.approx(50 / 70)
    assert len(target["quote_path"]) == 1
    assert target["quote_path"][0]["bid_levels"] == []
    ready = target["feature_available_receive_monotonic_s"]
    assert ready == pytest.approx(target["d_plus_2s"]["receive_mono"])
    assert is_available_by_decision(target, ready + 0.001) is True
    assert is_available_by_decision(target, ready) is False
    assert target["trade_high_event_ms"] == 108_000
    assert target["trade_low_event_ms"] == 101_000
    assert [x["second_start_ms"] for x in target["trade_path"]] == [101_000, 108_000]
    assert target["trade_path"][0]["first"]["best_ask"] == pytest.approx(100.01)


def test_10s_aggregator_fails_closed_on_late_event_after_finalization(tmp_path):
    source = tmp_path / "compact.jsonl"
    output = tmp_path / "windows.jsonl"
    rows = [
        _compact_row("agg_trade", 101_000, 101_010, trade_id=1,
                     quote_quantity=10, seller_initiated=True, price=100,
                     trade_id_gap_before=False, book_receive_age_ms=0),
        _compact_row("agg_trade", 120_000, 120_010, trade_id=2,
                     quote_quantity=20, seller_initiated=False, price=101,
                     trade_id_gap_before=False, book_receive_age_ms=0),
        _compact_row("agg_trade", 105_000, 120_020, trade_id=3,
                     quote_quantity=30, seller_initiated=True, price=99,
                     trade_id_gap_before=False, book_receive_age_ms=0),
    ]
    _write_source(source, rows)

    manifest = aggregate_windows(source, output, allowed_lateness_ms=2000)
    windows = [json.loads(line) for line in output.read_text().splitlines()]

    assert manifest["late_input_rows"] == 1
    assert manifest["quality_pass"] is False
    finalized = next(row for row in windows if row["window_start_ms"] == 100_000)
    assert finalized["sell_aggressor_quote_volume"] == pytest.approx(10)


def test_10s_aggregator_marks_global_feed_disconnect_as_quality_failure(tmp_path):
    source = tmp_path / "compact.jsonl"
    output = tmp_path / "windows.jsonl"
    rows = [
        {"kind": "feed_event", "symbol": None, "state": "disconnected",
         "stream": "depth", "received_at_ms": 100_000},
        _compact_row("agg_trade", 101_000, 101_010, trade_id=1,
                     quote_quantity=10, seller_initiated=True, price=100,
                     trade_id_gap_before=False, book_receive_age_ms=0),
    ]
    _write_source(source, rows)

    manifest = aggregate_windows(source, output)

    assert manifest["global_feed_events"] == 1
    assert manifest["global_disconnect_events"] == 1
    assert manifest["quality_pass"] is False


def test_10s_aggregator_rejects_stale_depth_endpoints_after_gap(tmp_path):
    source = tmp_path / "compact.jsonl"
    output = tmp_path / "windows.jsonl"
    rows = [
        _compact_row("book_update", 90_000, 90_010,
                     bid=99.99, ask=100.01, mid=100,
                     bid_depth_quote_5bp_top5=100, ask_depth_quote_5bp_top5=200,
                     last_update_id=1),
        _compact_row("book_update", 101_000, 101_010,
                     bid=100.09, ask=100.11, mid=100.1,
                     bid_depth_quote_5bp_top5=40, ask_depth_quote_5bp_top5=60,
                     last_update_id=3),
        _compact_row("book_update", 111_000, 111_010,
                     bid=100.19, ask=100.21, mid=100.2,
                     bid_depth_quote_5bp_top5=80, ask_depth_quote_5bp_top5=120,
                     last_update_id=4),
        _compact_row("agg_trade", 114_000, 114_010, trade_id=1,
                     quote_quantity=10, seller_initiated=True, price=100.3,
                     trade_id_gap_before=False, book_receive_age_ms=0),
    ]
    _write_source(source, rows)

    aggregate_windows(source, output)
    windows = [json.loads(line) for line in output.read_text().splitlines()]
    target = next(row for row in windows if row["window_start_ms"] == 100_000)

    assert target["data_quality_ready"] is False
    assert "stale_pre_depth" in target["unscorable_reasons"]
    assert "stale_depth_at_plus_2s" in target["unscorable_reasons"]
