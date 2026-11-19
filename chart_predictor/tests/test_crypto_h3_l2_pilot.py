import json
import hashlib

import pytest

from scripts.research.crypto_h3_l2_pilot import (
    QuotePoint,
    _outcome,
    detect_events,
    reconstruct,
    run,
    score,
)


def q(t, imbalance, *, mid=100.0, epoch=0, source="depth_delta"):
    return QuotePoint("BTCUSDT", t, int(t * 1000), mid - 0.1, mid + 0.1,
                      mid, imbalance, epoch, source)


def write_capture(directory, records, *, final_newline=True, manifest_overrides=None):
    path = directory / "capture.jsonl"
    payload = "".join(json.dumps(record) + "\n" for record in records)
    if not final_newline:
        payload = payload.rstrip("\n")
    raw = payload.encode()
    path.write_bytes(raw)
    manifest = {
        "run_id": directory.name,
        "symbols": ["BTCUSDT", "ETHUSDT"],
        "segment": {"path": "capture.jsonl", "complete": True,
                    "bytes": len(raw), "record_count": len(records),
                    "sha256": hashlib.sha256(raw).hexdigest()},
        "coverage": {
            "BTCUSDT": {"valid_seconds": 3599.0, "invalid_seconds": 1.0,
                         "coverage": 0.9997222222222222},
            "ETHUSDT": {"valid_seconds": 3598.0, "invalid_seconds": 2.0,
                         "coverage": 0.9994444444444445},
        },
    }
    if manifest_overrides:
        manifest.update(manifest_overrides)
    (directory / "manifest.json").write_text(json.dumps(manifest))
    return path


def basic_record(kind, t, *, symbol="BTCUSDT", **extra):
    return {"kind": kind, "symbol": symbol, "received_monotonic_s": t,
            "received_at_ms": int(t * 1000), **extra}


def reconstruct_test_capture(path, expected_sha256=None, expected_run_id=None):
    return reconstruct(path, expected_sha256,
                       expected_run_id or path.parent.name)


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


def test_outcome_windows_do_not_overlap_including_one_second_quote_grace():
    rows = []
    for start in (0.0, 1.0, 5.7, 7.6):
        rows.extend([q(start, 0.7), q(start + 0.2, 0.7), q(start + 0.4, 0.7),
                     q(start + 0.6, 0.0, mid=100.1)])
    events, _ = detect_events({"BTCUSDT": rows}, {"BTCUSDT": 0.1})
    assert len(events) == 2
    assert events[0]["entry_mono"] == 0.6
    assert events[1]["entry_mono"] == 8.2
    assert events[1]["entry_mono"] - events[0]["entry_mono"] >= 7.0


def test_reconstruct_bridges_snapshot_and_preserves_only_valid_deltas(tmp_path):
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
    path = write_capture(tmp_path, records)
    points, meta = reconstruct_test_capture(path)
    assert meta["depth_deltas"] == 2
    assert meta["quotes_by_symbol"]["BTCUSDT"] == 2
    assert points["BTCUSDT"][0].source == "snapshot_bridge"
    assert points["BTCUSDT"][1].imbalance > 0.6
    assert meta["input_rows"] == len(records)
    assert meta["coverage_by_symbol"]["BTCUSDT"]["valid_book_seconds"] == 3599.0
    assert meta["jsonl_newline_terminated"] is True


def test_reconstruct_invalidates_on_sequence_gap_until_new_snapshot(tmp_path):
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
    path = write_capture(tmp_path, events)
    points, meta = reconstruct_test_capture(path)
    assert meta["sequence_errors"] == 1
    assert len(points["BTCUSDT"]) == 1


def test_invalid_input_hash_is_rejected_before_replay(tmp_path):
    path = write_capture(tmp_path, [basic_record("aggTrade", 0.0)])
    with pytest.raises(ValueError, match="SHA-256 mismatch"):
        reconstruct_test_capture(path, "0" * 64)


def test_reconstruct_rejects_manifest_byte_or_row_count_mismatch(tmp_path):
    path = write_capture(tmp_path, [basic_record("aggTrade", 0.0)])
    manifest_path = tmp_path / "manifest.json"
    manifest = json.loads(manifest_path.read_text())
    manifest["segment"]["record_count"] = 2
    manifest_path.write_text(json.dumps(manifest))
    with pytest.raises(ValueError, match="row count"):
        reconstruct_test_capture(path)


@pytest.mark.parametrize(
    ("manifest_change", "message"),
    [
        ({"run_id": "wrong-run"}, "run_id"),
        ({"segment": {"path": "../capture.jsonl", "complete": True}}, "sibling filename"),
        ({"segment": {"path": "capture.jsonl", "complete": False}}, "complete segment"),
        ({"symbols": ["BTCUSDT"]}, "frozen universe"),
    ],
)
def test_reconstruct_rejects_manifest_scope_mismatch(tmp_path, manifest_change, message):
    path = write_capture(tmp_path, [basic_record("aggTrade", 0.0)])
    manifest_path = tmp_path / "manifest.json"
    manifest = json.loads(manifest_path.read_text())
    manifest.update(manifest_change)
    manifest_path.write_text(json.dumps(manifest))
    with pytest.raises(ValueError, match=message):
        reconstruct_test_capture(path)


def test_reconstruct_rejects_manifest_hash_or_byte_mismatch(tmp_path):
    path = write_capture(tmp_path, [basic_record("aggTrade", 0.0)])
    manifest_path = tmp_path / "manifest.json"
    manifest = json.loads(manifest_path.read_text())
    manifest["segment"]["sha256"] = "0" * 64
    manifest_path.write_text(json.dumps(manifest))
    with pytest.raises(ValueError, match="SHA-256 does not match sibling manifest"):
        reconstruct_test_capture(path)

    path = write_capture(tmp_path, [basic_record("aggTrade", 0.0)])
    manifest = json.loads(manifest_path.read_text())
    manifest["segment"]["bytes"] += 1
    manifest_path.write_text(json.dumps(manifest))
    with pytest.raises(ValueError, match="byte count"):
        reconstruct_test_capture(path)


def test_manifest_coverage_allows_only_millisecond_rounding_error(tmp_path):
    path = write_capture(tmp_path, [basic_record("aggTrade", 0.0)])
    manifest_path = tmp_path / "manifest.json"
    manifest = json.loads(manifest_path.read_text())
    manifest["coverage"]["BTCUSDT"] = {
        "valid_seconds": 3593.381,
        "invalid_seconds": 6.619,
        "coverage": 0.9981614724072279,
    }
    manifest_path.write_text(json.dumps(manifest))
    _, metadata = reconstruct_test_capture(path)
    assert metadata["coverage_by_symbol"]["BTCUSDT"]["book_time_coverage"] == pytest.approx(
        0.9981614724072279
    )

    manifest["coverage"]["BTCUSDT"]["coverage"] = 0.99
    manifest_path.write_text(json.dumps(manifest))
    with pytest.raises(ValueError, match="coverage arithmetic"):
        reconstruct_test_capture(path)


def test_reconstruct_rejects_per_stream_receive_time_regression(tmp_path):
    records = [basic_record("depth_snapshot", 1.0, event={}),
               basic_record("depth_delta", 0.9, event={})]
    path = write_capture(tmp_path, records)
    with pytest.raises(ValueError, match="receive order regressed"):
        reconstruct_test_capture(path)


@pytest.mark.parametrize(
    ("stream", "data_kind"),
    [("depth", "depth_snapshot"), ("aggTrade", "aggTrade")],
)
def test_connection_and_data_records_share_one_stream_order_check(tmp_path, stream, data_kind):
    records = [basic_record("connection", 1.0, stream=stream, state="connected"),
               basic_record(data_kind, 0.9, event={})]
    path = write_capture(tmp_path, records)
    with pytest.raises(ValueError, match=f"receive order regressed in {stream}"):
        reconstruct_test_capture(path)


def test_reconstruct_rejects_unterminated_jsonl(tmp_path):
    path = write_capture(tmp_path, [basic_record("aggTrade", 0.0)], final_newline=False)
    with pytest.raises(ValueError, match="not newline-terminated"):
        reconstruct_test_capture(path)


def test_reconstruct_rejects_manifest_run_id_not_matching_registration(tmp_path):
    path = write_capture(tmp_path, [basic_record("aggTrade", 0.0)])
    with pytest.raises(ValueError, match="preregistered run"):
        reconstruct(path, expected_run_id="20261116T025255Z-cc3a1f96")


def test_run_rejects_non_registered_capture_path_before_scoring(tmp_path):
    path = write_capture(tmp_path, [basic_record("aggTrade", 0.0)])
    with pytest.raises(ValueError, match="preregistered capture"):
        run(path, tmp_path / "should_not_exist.json")
    assert not (tmp_path / "should_not_exist.json").exists()


def test_outcome_accepts_exact_one_second_quote_grace_but_not_later():
    event = {"entry_mono": 10.0, "epoch": 0, "side": 1,
             "entry_mid": 100.0, "entry_bid": 99.9, "entry_ask": 100.1}
    accepted = [q(12.0, 0.0, mid=100.1)]
    late = [q(12.0001, 0.0, mid=100.1)]
    assert _outcome(accepted, event, 1)["side_correct"] is True
    assert _outcome(late, event, 1) is None


def test_outcome_zero_markout_is_not_a_hit_and_fee_is_subtracted():
    event = {"entry_mono": 0.0, "epoch": 0, "side": 1,
             "entry_mid": 100.0, "entry_bid": 99.9, "entry_ask": 100.1}
    zero = _outcome([q(1.0, 0.0, mid=100.0)], event, 1)
    assert zero["side_correct"] is False

    quote = QuotePoint("BTCUSDT", 1.0, 1000, 101.1, 101.3, 101.2,
                       0.0, 0, "depth_delta")
    scored = _outcome([quote], event, 1)
    expected = ((101.1 / 100.1) - 1.0 - 0.001) * 10000
    assert scored["cross_spread_net_return_bps"] == pytest.approx(expected)

    short_event = {"entry_mono": 0.0, "epoch": 0, "side": -1,
                   "entry_mid": 100.1, "entry_bid": 100.0, "entry_ask": 100.2}
    short_quote = QuotePoint("BTCUSDT", 1.0, 1000, 98.9, 99.0, 98.95,
                             0.0, 0, "depth_delta")
    short_scored = _outcome([short_quote], short_event, 1)
    assert short_scored["cross_spread_net_return_bps"] == pytest.approx(90.0)


def test_score_reports_per_symbol_unscorable_and_count_invariants():
    event = {"symbol": "BTCUSDT", "side": 1, "entry_mono": 0.0,
             "entry_mid": 100.0, "entry_bid": 99.9, "entry_ask": 100.1,
             "epoch": 0}
    coverage = {symbol: {"valid_book_seconds": 10.0,
                         "invalid_book_seconds": 0.0,
                         "book_time_coverage": 1.0}
                for symbol in ("BTCUSDT", "ETHUSDT")}
    result = score({"BTCUSDT": [q(0.0, 0.7)], "ETHUSDT": []}, [event],
                   {"BTCUSDT": 1, "ETHUSDT": 0},
                   {"coverage_by_symbol": coverage},
                   {"BTCUSDT": 0.1, "ETHUSDT": 0.01})
    assert result["protocol_version"] == "H3-L2-pilot-v1.1-amended-2026-11-19"
    for horizon in result["scores"].values():
        assert horizon["n_scored"] + horizon["unscorable"] == horizon["n_signals"] == 1
        assert horizon["by_symbol"]["BTCUSDT"]["unscorable"] == 1
        assert horizon["by_symbol"]["ETHUSDT"]["unscorable"] == 0
    assert result["signal_coverage_per_valid_book_time"]["BTCUSDT"]["valid_book_seconds"] == 10.0
