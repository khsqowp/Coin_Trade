import json

import pytest

from scripts.research.crypto_h3_l2_pilot import (
    QuotePoint,
    detect_events,
    reconstruct,
)


def q(t, imbalance, *, mid=100.0, epoch=0, source="depth_delta"):
    return QuotePoint("BTCUSDT", t, int(t * 1000), mid - 0.1, mid + 0.1,
                      mid, imbalance, epoch, source)


def test_signal_requires_three_strict_extreme_updates_and_tick_confirmation():
    rows = [q(0.0, 0.60), q(0.2, 0.61), q(0.4, 0.62), q(0.6, 0.63),
            q(0.8, 0.0, mid=100.1)]
    events, eligible = detect_events({"BTCUSDT": rows}, {"BTCUSDT": 0.1})
    assert eligible == {"BTCUSDT": 5}
    assert len(events) == 1
    assert events[0]["side"] == 1
    assert events[0]["entry_mono"] == 0.8


def test_signal_rejected_when_confirmation_is_late_or_less_than_one_tick():
    late = [q(0.0, 0.61), q(0.2, 0.62), q(0.4, 0.63), q(1.41, 0.0, mid=100.2)]
    tiny = [q(0.0, -0.61), q(0.2, -0.62), q(0.4, -0.63), q(0.8, 0.0, mid=99.91)]
    assert detect_events({"BTCUSDT": late}, {"BTCUSDT": 0.1})[0] == []
    assert detect_events({"BTCUSDT": tiny}, {"BTCUSDT": 0.1})[0] == []


def test_confirmation_window_cannot_be_restarted_by_repeated_imbalance():
    rows = [q(t, 0.7) for t in (0.0, 0.2, 0.4, 0.6, 0.8, 1.0)]
    rows.append(q(1.41, 0.0, mid=100.1))
    assert detect_events({"BTCUSDT": rows}, {"BTCUSDT": 0.1})[0] == []


def test_streak_does_not_cross_epoch_or_snapshot_boundary():
    rows = [q(0.0, 0.7), q(0.2, 0.7), q(0.4, 0.7),
            q(0.5, 0.7, epoch=1), q(0.6, 0.7, epoch=1),
            q(0.7, 0.7, epoch=1, source="snapshot_bridge"),
            q(0.8, 0.7, epoch=1)]
    assert detect_events({"BTCUSDT": rows}, {"BTCUSDT": 0.1})[0] == []


def test_overlapping_events_are_suppressed_for_five_seconds():
    rows = []
    for start in (0.0, 1.0, 5.7):
        rows.extend([q(start, 0.7), q(start + 0.2, 0.7), q(start + 0.4, 0.7),
                     q(start + 0.6, 0.0, mid=100.1)])
    events, _ = detect_events({"BTCUSDT": rows}, {"BTCUSDT": 0.1})
    assert len(events) == 2
    assert events[0]["entry_mono"] == 0.6
    assert events[1]["entry_mono"] == 6.3


def test_reconstruct_bridges_snapshot_and_preserves_only_valid_deltas(tmp_path):
    path = tmp_path / "capture.jsonl"
    snapshot = {"lastUpdateId": 10,
                "bids": [[str(p), "2"] for p in (100, 99, 98, 97, 96)],
                "asks": [[str(p), "2"] for p in (101, 102, 103, 104, 105)]}
    bridge = {"U": 10, "u": 11, "pu": 9, "b": [], "a": []}
    next_delta = {"U": 12, "u": 12, "pu": 11, "b": [["100", "50"]], "a": []}
    records = [
        {"kind": "depth_snapshot", "symbol": "BTCUSDT", "event": snapshot,
         "received_monotonic_s": 0.0, "received_at_ms": 0},
        {"kind": "depth_delta", "symbol": "BTCUSDT", "event": bridge,
         "received_monotonic_s": 0.1, "received_at_ms": 100},
        {"kind": "book_state", "symbol": "BTCUSDT", "state": "valid",
         "received_monotonic_s": 0.2, "received_at_ms": 200},
        {"kind": "depth_delta", "symbol": "BTCUSDT", "event": next_delta,
         "received_monotonic_s": 0.3, "received_at_ms": 300},
    ]
    path.write_text("".join(json.dumps(r) + "\n" for r in records))
    points, meta = reconstruct(path)
    assert meta["depth_deltas"] == 2
    assert meta["quotes_by_symbol"]["BTCUSDT"] == 2
    assert points["BTCUSDT"][0].source == "snapshot_bridge"
    assert points["BTCUSDT"][1].imbalance > 0.6


def test_reconstruct_invalidates_on_sequence_gap_until_new_snapshot(tmp_path):
    path = tmp_path / "capture.jsonl"
    snapshot = {"lastUpdateId": 10,
                "bids": [[str(p), "2"] for p in (100, 99, 98, 97, 96)],
                "asks": [[str(p), "2"] for p in (101, 102, 103, 104, 105)]}
    events = [
        {"kind": "depth_snapshot", "symbol": "BTCUSDT", "event": snapshot,
         "received_monotonic_s": 0.0, "received_at_ms": 0},
        {"kind": "depth_delta", "symbol": "BTCUSDT",
         "event": {"U": 10, "u": 11, "pu": 9, "b": [], "a": []},
         "received_monotonic_s": 0.1, "received_at_ms": 100},
        {"kind": "book_state", "symbol": "BTCUSDT", "state": "valid",
         "received_monotonic_s": 0.2, "received_at_ms": 200},
        {"kind": "depth_delta", "symbol": "BTCUSDT",
         "event": {"U": 13, "u": 13, "pu": 12, "b": [], "a": []},
         "received_monotonic_s": 0.3, "received_at_ms": 300},
        {"kind": "book_state", "symbol": "BTCUSDT", "state": "invalid",
         "reason": "sequence_gap", "received_monotonic_s": 0.31, "received_at_ms": 310},
        {"kind": "depth_delta", "symbol": "BTCUSDT",
         "event": {"U": 14, "u": 14, "pu": 13, "b": [], "a": []},
         "received_monotonic_s": 0.4, "received_at_ms": 400},
    ]
    path.write_text("".join(json.dumps(r) + "\n" for r in events))
    points, meta = reconstruct(path)
    assert meta["sequence_errors"] == 1
    assert len(points["BTCUSDT"]) == 1


def test_invalid_input_hash_is_rejected_before_replay(tmp_path):
    path = tmp_path / "capture.jsonl"
    path.write_text("{}\n")
    with pytest.raises(ValueError, match="SHA-256 mismatch"):
        reconstruct(path, "0" * 64)
