import hashlib
import json

import pytest

from scripts.research.crypto_l2_compact import reduce_capture


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
