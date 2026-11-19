import hashlib
import json

import pytest

from scripts.research.crypto_l2_compact import reduce_capture
from scripts.research.crypto_l2_signal import (
    build_candidates_for_completed_bar,
    prior_aggression_threshold,
)
from scripts.research.crypto_l2_windows import (
    aggregation_code_sha256,
    aggregation_run_id_for,
    manifest_integrity_sha256,
    aggregate_windows,
    eligible_windows_for_completed_bar,
    is_available_by_decision,
)


def _record(kind, symbol, event, t, **extra):
    return {
        "kind": kind,
        "symbol": symbol,
        "event": event,
        "received_at_ms": t,
        "received_monotonic_s": t / 1000,
        "receive_clock_domain": "test-run",
        **extra,
    }


def _write_source(path, records):
    payload = "".join(json.dumps(row, separators=(",", ":")) + "\n" for row in records)
    path.write_text(payload)
    domains = {row.get("receive_clock_domain") for row in records
               if isinstance(row.get("receive_clock_domain"), str)
               and row["receive_clock_domain"]}
    run_id = next(iter(domains)) if len(domains) == 1 else path.parent.name
    (path.parent / "manifest.json").write_text(json.dumps({
        "run_id": run_id,
        "segment": {
            "path": path.name,
            "complete": True,
            "sha256": hashlib.sha256(payload.encode()).hexdigest(),
            "bytes": len(payload.encode()),
            "record_count": len(records),
        },
    }))


def test_legacy_clock_domain_is_derived_only_from_matching_run_manifest(tmp_path):
    source = tmp_path / "capture.jsonl"
    output = tmp_path / "compact.jsonl"
    _write_source(source, [{
        "kind": "connection", "symbol": None, "received_at_ms": 1000,
        "received_monotonic_s": 1.0, "stream": "depth", "state": "connected",
    }])

    manifest = reduce_capture(source, output)
    row = json.loads(output.read_text().splitlines()[0])

    assert row["receive_clock_domain"] == tmp_path.name
    assert manifest["source_records"] == 1


def test_legacy_clock_domain_without_matching_run_manifest_fails_closed(tmp_path):
    source = tmp_path / "capture.jsonl"
    output = tmp_path / "compact.jsonl"
    source.write_text(json.dumps({
        "kind": "connection", "symbol": None, "received_at_ms": 1000,
        "received_monotonic_s": 1.0, "stream": "depth", "state": "connected",
    }) + "\n")

    with pytest.raises(ValueError, match="no verified run manifest"):
        reduce_capture(source, output)
    assert not output.exists()


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


def test_reducer_drops_duplicate_and_out_of_order_aggregate_trade_ids(tmp_path):
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
    ]
    for trade_id, event_ms, receive_ms in ((7, 1012, 1013), (7, 1012, 1014),
                                           (6, 1011, 1015), (8, 1016, 1017)):
        records.append(_record("aggTrade", symbol,
                               {"e": "aggTrade", "s": symbol, "a": trade_id,
                                "f": trade_id, "l": trade_id, "T": event_ms,
                                "p": "100", "q": "0.5", "m": True}, receive_ms))
    _write_source(source, records)

    manifest = reduce_capture(source, output)
    rows = [json.loads(line) for line in output.read_text().splitlines()]

    assert [row["trade_id"] for row in rows if row["kind"] == "agg_trade"] == [7, 8]
    assert {row["category"] for row in rows if row["kind"] == "feed_event"} == {
        "duplicate_agg_trade_id", "out_of_order_agg_trade_id",
    }
    assert manifest["duplicate_trade_ids_dropped"] == 1
    assert manifest["out_of_order_trade_ids_dropped"] == 1


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
        "receive_clock_domain": "test-run",
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
    assert target["feature_available_received_at_ms"] == target["d_plus_2s"]["received_at_ms"]
    assert is_available_by_decision(target, ready + 0.001) is True
    assert is_available_by_decision(target, ready) is False
    assert target["trade_high_event_ms"] == 108_000
    assert target["trade_low_event_ms"] == 101_000
    assert [x["second_start_ms"] for x in target["trade_path"]] == [101_000, 108_000]
    assert target["trade_path"][0]["first"]["best_ask"] == pytest.approx(100.01)


def test_completed_bar_gate_rejects_delayed_future_and_bad_quality_features():
    base = {
        "window_final": True,
        "data_quality_ready": True,
        "window_start_ms": 100_000,
        "window_end_ms": 110_000,
        "feature_available_receive_monotonic_s": 12.0,
        "feature_available_received_at_ms": 12_000,
        "feature_receive_clock_domain": "test-run",
    }
    rows = [
        {**base, "symbol": "BTCUSDT"},
        # Old exchange event-time interval, but received after the decision.
        {**base, "symbol": "ETHUSDT", "feature_available_receive_monotonic_s": 13.0,
         "feature_available_received_at_ms": 13_000},
        # Monotonic value looks early, but wall receive time says it was late.
        {**base, "symbol": "LTCUSDT", "feature_available_received_at_ms": 13_000},
        {**base, "symbol": "SOLUSDT", "window_start_ms": 90_000},
        {**base, "symbol": "XRPUSDT", "data_quality_ready": False},
        {**base, "symbol": "ADAUSDT", "window_final": False},
    ]

    eligible, rejected = eligible_windows_for_completed_bar(
        rows, bar_open_ms=100_000, bar_close_ms=120_000,
        decision_receive_monotonic_s=13.0,
        decision_received_at_ms=13_000,
        decision_receive_clock_domain="test-run",
        invalidated_window_keys=set(),
    )

    assert [row["symbol"] for row in eligible] == ["BTCUSDT"]
    assert rejected == {
        "not_final": 1,
        "quality_failure": 1,
        "outside_completed_bar": 1,
        "missing_availability": 0,
        "received_at_or_after_decision": 2,
        "invalidated_by_late_input": 0,
    }


def test_completed_bar_gate_requires_all_feature_windows_to_pass():
    valid = {
        "window_final": True,
        "data_quality_ready": True,
        "window_start_ms": 100_000,
        "window_end_ms": 110_000,
        "feature_available_receive_monotonic_s": 12.0,
        "feature_available_received_at_ms": 12_000,
        "feature_receive_clock_domain": "test-run",
    }
    incomplete = {**valid, "feature_available_receive_monotonic_s": None,
                  "feature_available_received_at_ms": None}
    selected, rejected = eligible_windows_for_completed_bar(
        [valid, incomplete], bar_open_ms=100_000, bar_close_ms=120_000,
        decision_receive_monotonic_s=13.0,
        decision_received_at_ms=13_000,
        decision_receive_clock_domain="test-run",
        invalidated_window_keys=set(),
    )

    assert selected == [valid]
    assert rejected["missing_availability"] == 1


def test_completed_bar_gate_rejects_late_invalidated_finalized_window():
    window = {
        "symbol": "BTCUSDT", "window_final": True, "data_quality_ready": True,
        "window_start_ms": 100_000, "window_end_ms": 110_000,
        "feature_available_receive_monotonic_s": 12.0,
        "feature_available_received_at_ms": 12_000,
        "feature_receive_clock_domain": "test-run",
    }
    selected, rejected = eligible_windows_for_completed_bar(
        [window], bar_open_ms=100_000, bar_close_ms=120_000,
        decision_receive_monotonic_s=13.0, decision_received_at_ms=13_000,
        decision_receive_clock_domain="test-run",
        invalidated_window_keys={("BTCUSDT", 100_000)},
    )

    assert selected == []
    assert rejected["invalidated_by_late_input"] == 1


def test_completed_bar_gate_rejects_invalid_bar_bounds():
    with pytest.raises(ValueError, match="bar bounds"):
        eligible_windows_for_completed_bar(
            [], bar_open_ms=120_000, bar_close_ms=120_000,
            decision_receive_monotonic_s=13.0,
            decision_received_at_ms=13_000,
            decision_receive_clock_domain="test-run",
            invalidated_window_keys=set(),
        )


def _candidate_window(start, *, available=601.5, received_at_ms=601_500,
                      sell=1000.0, buy=900.0,
                      bid_refill=0.8, ask_refill=0.9, symbol="BTCUSDT"):
    window = {
        "symbol": symbol,
        "window_start_ms": start,
        "window_end_ms": start + 10_000,
        "window_final": True,
        "data_quality_ready": True,
        "feature_available_receive_monotonic_s": available,
        "feature_available_received_at_ms": received_at_ms,
        "feature_receive_clock_domain": "test-run",
        "sell_aggressor_quote_volume": sell,
        "buy_aggressor_quote_volume": buy,
        "bid_replenishment_ratio": bid_refill,
        "ask_replenishment_ratio": ask_refill,
        "trade_low": 99.0,
        "trade_high": 101.0,
        "d_plus_2s": {"event_ms": start + 12_000},
        "aggregation_run_id": _candidate_bars()["aggregation_manifest"]["aggregation_run_id"],
    }
    window["aggregation_row_sha256"] = hashlib.sha256(json.dumps(
        window, sort_keys=True, separators=(",", ":"), allow_nan=False,
    ).encode()).hexdigest()
    return window


def _candidate_bars(*, decision_receive=602.0, decision_received_at_ms=14_403_000,
                    t_receive=600.5, h_receive=600.4, macro=(101.0, 100.0, 99.0)):
    source_sha256 = "a" * 64
    aggregator_code_sha256 = aggregation_code_sha256()
    run_settings = {
        "allowed_lateness_ms": 2000,
        "window_ms": 10_000,
        "refill_observation_ms": 2000,
        "max_depth_endpoint_age_ms": 750,
    }
    quality_counts = {
        "late_input_rows": 0,
        "global_disconnect_events": 0,
        "unknown_time_feed_events": 0,
    }
    settings = {**run_settings, **quality_counts}
    context = {
        "t_bar": {
            "symbol": "BTCUSDT",
            "timeframe_minutes": 10,
            "bar_open_ms": 0,
            "bar_close_ms": 600_000,
            "completed": True,
            "feature_available_receive_monotonic_s": t_receive,
            "feature_available_received_at_ms": 600_500,
            "feature_receive_clock_domain": "test-run",
        },
        "btc_h_bar": {
            "symbol": "BTCUSDT",
            "timeframe_minutes": 240,
            "bar_open_ms": 0,
            "bar_close_ms": 14_400_000,
            "completed": True,
            "feature_available_receive_monotonic_s": h_receive,
            "feature_available_received_at_ms": 14_400_500,
            "feature_receive_clock_domain": "test-run",
            "close": macro[0],
            "ema50": macro[1],
            "ema50_5_bars_ago": macro[2],
        },
        "decision_event_ms": 14_402_000,
        "decision_receive_monotonic_s": decision_receive,
        "decision_received_at_ms": decision_received_at_ms,
        "decision_receive_clock_domain": "test-run",
        "aggregation_manifest": {
            "quality_pass": True,
            "late_invalidated_windows": [],
            "aggregation_run_id": aggregation_run_id_for(
                source_sha256=source_sha256,
                aggregator_code_sha256=aggregator_code_sha256,
                **run_settings,
            ),
            "source_sha256": source_sha256,
            "output_sha256": "b" * 64,
            "aggregator_code_sha256": aggregator_code_sha256,
            **settings,
        },
    }
    context["aggregation_manifest"]["manifest_integrity_sha256"] = manifest_integrity_sha256(
        context["aggregation_manifest"]
    )
    return context


def _build_candidates(windows, **kwargs):
    call_bars = dict(kwargs)
    manifest = dict(call_bars["aggregation_manifest"])
    manifest["output_sha256"] = hashlib.sha256(b"".join(
        json.dumps(row, sort_keys=True, separators=(",", ":"),
                   allow_nan=False).encode() + b"\n" for row in windows
    )).hexdigest()
    manifest["manifest_integrity_sha256"] = manifest_integrity_sha256(manifest)
    call_bars["aggregation_manifest"] = manifest
    return build_candidates_for_completed_bar(windows, **call_bars)


def _prior_aggression(direction):
    return [
        {"symbol": "BTCUSDT", "direction": direction, "event_ms": 10_000,
         "feature_available_received_at_ms": 10_100,
         "feature_available_receive_monotonic_s": 10.1,
         "feature_receive_clock_domain": "test-run",
         "aggression_quote_volume": 500.0},
        {"symbol": "BTCUSDT", "direction": direction, "event_ms": 20_000,
         "feature_available_received_at_ms": 20_100,
         "feature_available_receive_monotonic_s": 20.1,
         "feature_receive_clock_domain": "test-run",
         "aggression_quote_volume": 600.0},
    ]


def test_candidate_builder_uses_macro_to_micro_and_selects_earliest_window():
    bars = _candidate_bars()
    prior_rows = _prior_aggression("long") + [
        # A later T-bar event cannot alter the threshold for the first event.
        {"symbol": "BTCUSDT", "direction": "long", "event_ms": 150_000,
         "feature_available_received_at_ms": 150_100,
         "feature_available_receive_monotonic_s": 150.1,
         "feature_receive_clock_domain": "test-run",
         "aggression_quote_volume": 10_000.0},
    ]
    candidates, rejects = _build_candidates(
        [_candidate_window(100_000), _candidate_window(200_000)],
        **bars,
        prior_aggression_observations=prior_rows,
        aggression_percentile=0.8,
        minimum_aggression_history_n=2,
        minimum_replenishment_ratio=0.5,
        tick_size=0.01,
    )

    assert len(candidates) == 1
    candidate = candidates[0]
    assert candidate["side"] == "long"
    assert candidate["window_start_ms"] == 100_000
    assert candidate["macro_regime"] == "long"
    assert candidate["stop_price_pre_entry"] == pytest.approx(98.99)
    assert candidate["aggression_quote_threshold"] == pytest.approx(580.0)
    assert candidate["aggression_history_n"] == 2
    assert candidate["signal_received_at_ms"] == bars["decision_received_at_ms"]
    assert candidate["entry_price"] is None
    assert candidate["candidate_status"] == "awaiting_executable_post_signal_quote"
    assert rejects["window_not_eligible"] == 0


def test_candidate_builder_requires_passing_aggregation_manifest():
    bars = _candidate_bars()
    bars["aggregation_manifest"] = {
        "quality_pass": False,
        "late_invalidated_windows": [],
        "aggregation_run_id": "test-aggregation-run",
        "source_sha256": "a" * 64,
        "output_sha256": "b" * 64,
        "aggregator_code_sha256": "c" * 64,
        "allowed_lateness_ms": 2000,
        "window_ms": 10_000,
        "refill_observation_ms": 2000,
        "max_depth_endpoint_age_ms": 750,
        "late_input_rows": 0,
        "global_disconnect_events": 0,
        "unknown_time_feed_events": 0,
    }
    bars["aggregation_manifest"]["global_disconnect_events"] = 1
    bars["aggregation_manifest"]["manifest_integrity_sha256"] = manifest_integrity_sha256(
        bars["aggregation_manifest"]
    )
    candidates, rejects = _build_candidates(
        [_candidate_window(100_000)], **bars,
        prior_aggression_observations=_prior_aggression("long"),
        aggression_percentile=0.8,
        minimum_aggression_history_n=2,
        minimum_replenishment_ratio=0.5,
        tick_size=0.01,
    )

    assert candidates == []
    assert rejects["aggregation_quality_failure"] == 1


def test_candidate_builder_rejects_quality_flag_promoted_over_failure_counter():
    bars = _candidate_bars()
    bars["aggregation_manifest"]["global_disconnect_events"] = 1

    with pytest.raises(ValueError, match="quality flag contradicts quality counters"):
        _build_candidates(
            [_candidate_window(100_000)], **bars,
            prior_aggression_observations=_prior_aggression("long"),
            aggression_percentile=0.8,
            minimum_aggression_history_n=2,
            minimum_replenishment_ratio=0.5,
            tick_size=0.01,
        )


def test_candidate_builder_rejects_manifest_fields_changed_without_resealing():
    bars = _candidate_bars()
    bars["aggregation_manifest"]["global_disconnect_events"] = 1

    with pytest.raises(ValueError, match="manifest integrity hash does not match"):
        build_candidates_for_completed_bar(
            [_candidate_window(100_000)], **bars,
            prior_aggression_observations=_prior_aggression("long"),
            aggression_percentile=0.8,
            minimum_aggression_history_n=2,
            minimum_replenishment_ratio=0.5,
            tick_size=0.01,
        )


def test_candidate_builder_rejects_window_from_different_aggregation_manifest():
    bars = _candidate_bars()
    bars["aggregation_manifest"]["aggregation_run_id"] = "another-run"

    with pytest.raises(ValueError, match="run identity does not match"):
        _build_candidates(
            [_candidate_window(100_000)], **bars,
            prior_aggression_observations=_prior_aggression("long"),
            aggression_percentile=0.8,
            minimum_aggression_history_n=2,
            minimum_replenishment_ratio=0.5,
            tick_size=0.01,
        )


def test_candidate_builder_rejects_modified_window_row_hash():
    window = _candidate_window(100_000)
    window["sell_aggressor_quote_volume"] = 9_999_999.0
    with pytest.raises(ValueError, match="row hash does not match"):
        _build_candidates(
            [window], **_candidate_bars(),
            prior_aggression_observations=_prior_aggression("long"),
            aggression_percentile=0.8,
            minimum_aggression_history_n=2,
            minimum_replenishment_ratio=0.5,
            tick_size=0.01,
        )


def test_candidate_builder_rejects_output_hash_from_other_window_set():
    bars = _candidate_bars()
    bars["aggregation_manifest"]["output_sha256"] = "d" * 64
    bars["aggregation_manifest"]["manifest_integrity_sha256"] = manifest_integrity_sha256(
        bars["aggregation_manifest"]
    )
    with pytest.raises(ValueError, match="do not match aggregation manifest output hash"):
        build_candidates_for_completed_bar(
            [_candidate_window(100_000)], **bars,
            prior_aggression_observations=_prior_aggression("long"),
            aggression_percentile=0.8,
            minimum_aggression_history_n=2,
            minimum_replenishment_ratio=0.5,
            tick_size=0.01,
        )


@pytest.mark.parametrize(
    ("field", "value", "error"),
    [
        ("source_sha256", "d" * 64, "run identity does not match"),
        ("aggregator_code_sha256", "e" * 64, "code hash does not match"),
        ("allowed_lateness_ms", 3000, "run identity does not match"),
    ],
)
def test_candidate_builder_rejects_manifest_run_descriptor_mutation(field, value, error):
    bars = _candidate_bars()
    bars["aggregation_manifest"][field] = value

    with pytest.raises(ValueError, match=error):
        _build_candidates(
            [_candidate_window(100_000)], **bars,
            prior_aggression_observations=_prior_aggression("long"),
            aggression_percentile=0.8,
            minimum_aggression_history_n=2,
            minimum_replenishment_ratio=0.5,
            tick_size=0.01,
        )


@pytest.mark.parametrize("bar_key", ["t_bar", "btc_h_bar"])
def test_candidate_builder_abstains_when_any_bar_feature_arrives_after_decision(bar_key):
    bars = _candidate_bars()
    bars[bar_key]["feature_available_receive_monotonic_s"] = 602.0
    candidates, rejects = _build_candidates(
        [_candidate_window(100_000)], **bars,
        prior_aggression_observations=_prior_aggression("long"),
        aggression_percentile=0.8,
        minimum_aggression_history_n=2,
        minimum_replenishment_ratio=0.5,
        tick_size=0.01,
    )

    assert candidates == []
    assert rejects["t_bar_unavailable"] + rejects["higher_timeframe_unavailable"] == 1


def test_candidate_builder_abstains_on_non_directional_higher_timeframe_state():
    bars = _candidate_bars(macro=(100.0, 100.0, 100.0))
    candidates, rejects = _build_candidates(
        [_candidate_window(100_000)], **bars,
        prior_aggression_observations=_prior_aggression("long"),
        aggression_percentile=0.8,
        minimum_aggression_history_n=2,
        minimum_replenishment_ratio=0.5,
        tick_size=0.01,
    )

    assert candidates == []
    assert rejects["no_directional_macro_regime"] == 1


def test_candidate_builder_applies_symmetric_short_rules():
    bars = _candidate_bars(macro=(99.0, 100.0, 101.0))
    candidates, _ = _build_candidates(
        [_candidate_window(100_000)], **bars,
        prior_aggression_observations=_prior_aggression("short"),
        aggression_percentile=0.8,
        minimum_aggression_history_n=2,
        minimum_replenishment_ratio=0.5,
        tick_size=0.01,
    )

    assert candidates[0]["side"] == "short"
    assert candidates[0]["stop_price_pre_entry"] == pytest.approx(101.01)


def test_candidate_builder_rejects_wrong_macro_timeframe():
    bars = _candidate_bars()
    bars["btc_h_bar"]["timeframe_minutes"] = 60
    with pytest.raises(ValueError, match=r"max\(240m, 4 x T\)"):
        _build_candidates(
            [_candidate_window(100_000)], **bars,
            prior_aggression_observations=_prior_aggression("long"),
            aggression_percentile=0.8,
            minimum_aggression_history_n=2,
            minimum_replenishment_ratio=0.5,
            tick_size=0.01,
        )


def test_candidate_builder_does_not_cross_symbols():
    bars = _candidate_bars()
    bars["t_bar"]["symbol"] = "ETHUSDT"
    candidates, rejects = _build_candidates(
        [_candidate_window(100_000, symbol="BTCUSDT")], **bars,
        prior_aggression_observations=_prior_aggression("long"),
        aggression_percentile=0.8,
        minimum_aggression_history_n=2,
        minimum_replenishment_ratio=0.5,
        tick_size=0.01,
    )

    assert candidates == []
    assert rejects["wrong_symbol"] == 1


def test_prior_aggression_threshold_excludes_current_future_and_other_groups():
    observations = [
        {"symbol": "ETHUSDT", "direction": "long", "event_ms": 1_000,
         "feature_available_received_at_ms": 1_100,
         "aggression_quote_volume": 10.0},
        {"symbol": "BTCUSDT", "direction": "short", "event_ms": 1_500,
         "feature_available_received_at_ms": 1_600,
         "aggression_quote_volume": 1000.0},
        {"symbol": "BTCUSDT", "direction": "long", "event_ms": 1_000,
         "feature_available_received_at_ms": 1_100,
         "feature_available_receive_monotonic_s": 1.1,
         "feature_receive_clock_domain": "test-run",
         "aggression_quote_volume": 10.0},
        {"symbol": "BTCUSDT", "direction": "long", "event_ms": 2_000,
         "feature_available_received_at_ms": 2_100,
         "feature_available_receive_monotonic_s": 2.1,
         "feature_receive_clock_domain": "test-run",
         "aggression_quote_volume": 20.0},
        # Event time is prior, but its feature arrived after this decision anchor.
        {"symbol": "BTCUSDT", "direction": "long", "event_ms": 1_500,
         "feature_available_received_at_ms": 3_500,
         "feature_available_receive_monotonic_s": 3.5,
         "feature_receive_clock_domain": "test-run",
         "aggression_quote_volume": 10_000.0},
        # Different runtime: wall time is not accepted until a clock-sync gate exists.
        {"symbol": "BTCUSDT", "direction": "long", "event_ms": 1_700,
         "feature_available_received_at_ms": 1_800,
         "feature_available_receive_monotonic_s": 1.8,
         "feature_receive_clock_domain": "other-run",
         "aggression_quote_volume": 20_000.0},
        # Current and future rows are excluded before their values are inspected.
        {"symbol": "BTCUSDT", "direction": "long", "event_ms": 3_000,
         "feature_available_received_at_ms": 3_100,
         "feature_available_receive_monotonic_s": 3.1,
         "feature_receive_clock_domain": "test-run",
         "aggression_quote_volume": 30.0},
        {"symbol": "BTCUSDT", "direction": "long", "event_ms": 4_000,
         "feature_available_received_at_ms": 4_100,
         "feature_available_receive_monotonic_s": 4.1,
         "feature_receive_clock_domain": "test-run",
         "aggression_quote_volume": float("nan")},
    ]
    args = {
        "symbol": "BTCUSDT", "direction": "long", "anchor_event_ms": 3_000,
        "anchor_received_at_ms": 3_000,
        "anchor_receive_monotonic_s": 3.0,
        "anchor_receive_clock_domain": "test-run",
        "percentile": 0.5, "lookback_ms": 2_000, "minimum_history_n": 2,
    }

    threshold, count = prior_aggression_threshold(observations, **args)
    threshold_without_future, count_without_future = prior_aggression_threshold(
        observations[:4], **args,
    )

    assert threshold == pytest.approx(15.0)
    assert (threshold, count) == (threshold_without_future, count_without_future)
    assert count == 2


def test_prior_aggression_threshold_returns_no_threshold_below_minimum_history():
    threshold, count = prior_aggression_threshold(
        [{"symbol": "BTCUSDT", "direction": "long", "event_ms": 2_000,
          "feature_available_received_at_ms": 2_100,
          "feature_available_receive_monotonic_s": 2.1,
          "feature_receive_clock_domain": "test-run",
          "aggression_quote_volume": 20.0}],
        symbol="BTCUSDT", direction="long", anchor_event_ms=3_000,
        anchor_received_at_ms=3_000,
        anchor_receive_monotonic_s=3.0,
        anchor_receive_clock_domain="test-run",
        percentile=0.8, lookback_ms=30_000, minimum_history_n=2,
    )

    assert threshold is None
    assert count == 1


def test_prior_aggression_threshold_excludes_equal_monotonic_availability():
    threshold, count = prior_aggression_threshold(
        [{"symbol": "BTCUSDT", "direction": "long", "event_ms": 2_000,
          "feature_available_received_at_ms": 2_500,
          "feature_available_receive_monotonic_s": 2.5,
          "feature_receive_clock_domain": "test-run",
          "aggression_quote_volume": 999.0}],
        symbol="BTCUSDT", direction="long", anchor_event_ms=3_000,
        anchor_received_at_ms=3_000,
        anchor_receive_monotonic_s=2.5,
        anchor_receive_clock_domain="test-run",
        percentile=0.8, lookback_ms=30_000, minimum_history_n=1,
    )

    assert threshold is None
    assert count == 0


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

    manifest = aggregate_windows(source, output)
    windows = [json.loads(line) for line in output.read_text().splitlines()]
    target = next(row for row in windows if row["window_start_ms"] == 100_000)

    assert hashlib.sha256(output.read_bytes()).hexdigest() == manifest["output_sha256"]
    bars = _candidate_bars()
    bars["aggregation_manifest"] = manifest
    candidates, _ = build_candidates_for_completed_bar(
        windows, **bars,
        prior_aggression_observations=_prior_aggression("long"),
        aggression_percentile=0.8,
        minimum_aggression_history_n=2,
        minimum_replenishment_ratio=0.5,
        tick_size=0.01,
    )

    assert target["data_quality_ready"] is False
    assert "stale_pre_depth" in target["unscorable_reasons"]
    assert "stale_depth_at_plus_2s" in target["unscorable_reasons"]
    assert candidates == []


def test_10s_aggregator_rejects_required_depth_endpoint_without_receive_wall_time(tmp_path):
    source = tmp_path / "compact.jsonl"
    output = tmp_path / "windows.jsonl"
    rows = [
        _compact_row("book_update", 99_500, 99_510,
                     bid=99.99, ask=100.01, mid=100,
                     bid_depth_quote_5bp_top5=100, ask_depth_quote_5bp_top5=100,
                     last_update_id=1),
        _compact_row("agg_trade", 101_000, 101_020, trade_id=1,
                     quote_quantity=10, seller_initiated=True, price=100,
                     trade_id_gap_before=False, book_receive_age_ms=0),
        _compact_row("book_update", 105_000, 105_030,
                     bid=99.99, ask=100.01, mid=100,
                     bid_depth_quote_5bp_top5=40, ask_depth_quote_5bp_top5=50,
                     last_update_id=2),
        _compact_row("book_update", 111_500, 111_530,
                     bid=100.09, ask=100.11, mid=100.1,
                     bid_depth_quote_5bp_top5=80, ask_depth_quote_5bp_top5=90,
                     last_update_id=3),
        _compact_row("agg_trade", 114_500, 114_520, trade_id=2,
                     quote_quantity=10, seller_initiated=False, price=100.2,
                     trade_id_gap_before=False, book_receive_age_ms=0),
    ]
    rows[3]["received_at_ms"] = None
    _write_source(source, rows)

    aggregate_windows(source, output)
    windows = [json.loads(line) for line in output.read_text().splitlines()]
    target = next(row for row in windows if row["window_start_ms"] == 100_000)

    assert target["data_quality_ready"] is False
    assert "missing_receive_wall_time" in target["unscorable_reasons"]


def test_late_feed_error_invalidates_already_emitted_window_for_candidate_gate(tmp_path):
    source = tmp_path / "compact.jsonl"
    output = tmp_path / "windows.jsonl"
    rows = [
        _compact_row("book_update", 99_500, 99_510,
                     bid=99.99, ask=100.01, mid=100,
                     bid_depth_quote_5bp_top5=100, ask_depth_quote_5bp_top5=100,
                     last_update_id=1),
        _compact_row("agg_trade", 101_000, 101_020, trade_id=1,
                     quote_quantity=10, seller_initiated=True, price=100,
                     trade_id_gap_before=False, book_receive_age_ms=0),
        _compact_row("book_update", 105_000, 105_030,
                     bid=99.99, ask=100.01, mid=100,
                     bid_depth_quote_5bp_top5=40, ask_depth_quote_5bp_top5=50,
                     last_update_id=2),
        _compact_row("book_update", 111_500, 111_530,
                     bid=100.09, ask=100.11, mid=100.1,
                     bid_depth_quote_5bp_top5=80, ask_depth_quote_5bp_top5=90,
                     last_update_id=3),
        _compact_row("book_update", 120_000, 120_010,
                     bid=100.19, ask=100.21, mid=100.2,
                     bid_depth_quote_5bp_top5=80, ask_depth_quote_5bp_top5=90,
                     last_update_id=4),
        {"kind": "feed_event", "symbol": "BTCUSDT", "category": "out_of_order_agg_trade_id",
         "exchange_event_ms": 105_000, "received_at_ms": 120_020,
         "received_monotonic_s": 120.02, "receive_clock_domain": "test-run"},
    ]
    _write_source(source, rows)

    manifest = aggregate_windows(source, output)
    windows = [json.loads(line) for line in output.read_text().splitlines()]
    target = next(row for row in windows if row["window_start_ms"] == 100_000)
    bars = _candidate_bars()
    bars["aggregation_manifest"] = manifest
    candidates, candidate_rejects = _build_candidates(
        [target], **bars,
        prior_aggression_observations=_prior_aggression("long"),
        aggression_percentile=0.8,
        minimum_aggression_history_n=2,
        minimum_replenishment_ratio=0.5,
        tick_size=0.01,
    )
    selected, rejected = eligible_windows_for_completed_bar(
        [target], bar_open_ms=100_000, bar_close_ms=110_000,
        decision_receive_monotonic_s=121.0, decision_received_at_ms=121_000,
        decision_receive_clock_domain="test-run",
        invalidated_window_keys={(row["symbol"], row["window_start_ms"])
                                 for row in manifest["late_invalidated_windows"]},
    )

    assert target["data_quality_ready"] is True
    assert manifest["quality_pass"] is False
    assert manifest["late_invalidated_windows"] == [
        {"symbol": "BTCUSDT", "window_start_ms": 100_000}
    ]
    assert selected == []
    assert rejected["invalidated_by_late_input"] == 1
    assert candidates == []
    assert candidate_rejects["aggregation_quality_failure"] == 1


def test_symbol_feed_error_without_any_usable_timestamp_fails_global_quality(tmp_path):
    source = tmp_path / "compact.jsonl"
    output = tmp_path / "windows.jsonl"
    _write_source(source, [{
        "kind": "feed_event", "symbol": "BTCUSDT", "category": "bad_timestamp",
        "exchange_event_ms": None, "received_at_ms": None,
        "received_monotonic_s": 1.0, "receive_clock_domain": "test-run",
    }])

    manifest = aggregate_windows(source, output)

    assert manifest["unknown_time_feed_events"] == 1
    assert manifest["quality_pass"] is False


def test_symbol_feed_error_with_receive_time_but_bad_event_time_blocks_candidates(tmp_path):
    source = tmp_path / "compact.jsonl"
    output = tmp_path / "windows.jsonl"
    _write_source(source, [{
        "kind": "feed_event", "symbol": "BTCUSDT", "category": "bad_event_timestamp",
        "exchange_event_ms": None, "received_at_ms": 120_020,
        "received_monotonic_s": 120.02, "receive_clock_domain": "test-run",
    }])

    manifest = aggregate_windows(source, output)
    bars = _candidate_bars()
    bars["aggregation_manifest"] = manifest
    candidates, rejects = _build_candidates(
        [_candidate_window(100_000)], **bars,
        prior_aggression_observations=_prior_aggression("long"),
        aggression_percentile=0.8,
        minimum_aggression_history_n=2,
        minimum_replenishment_ratio=0.5,
        tick_size=0.01,
    )

    assert manifest["unknown_time_feed_events"] == 1
    assert manifest["unknown_time_feed_symbols"] == ["BTCUSDT"]
    assert manifest["quality_pass"] is False
    assert candidates == []
    assert rejects["aggregation_quality_failure"] == 1
