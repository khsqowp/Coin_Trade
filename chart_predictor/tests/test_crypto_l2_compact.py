import hashlib
import json

import pytest

from scripts.research.crypto_l2_compact import reduce_capture
from scripts.research.crypto_l2_signal import (
    build_candidates_for_completed_bar,
    prior_aggression_threshold,
)
from scripts.research.crypto_l2_windows import (
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


def test_completed_bar_gate_rejects_delayed_future_and_bad_quality_features():
    base = {
        "window_final": True,
        "data_quality_ready": True,
        "window_start_ms": 100_000,
        "window_end_ms": 110_000,
        "feature_available_receive_monotonic_s": 12.0,
    }
    rows = [
        {**base, "symbol": "BTCUSDT"},
        # Old exchange event-time interval, but received after the decision.
        {**base, "symbol": "ETHUSDT", "feature_available_receive_monotonic_s": 13.0},
        {**base, "symbol": "SOLUSDT", "window_start_ms": 90_000},
        {**base, "symbol": "XRPUSDT", "data_quality_ready": False},
        {**base, "symbol": "ADAUSDT", "window_final": False},
    ]

    eligible, rejected = eligible_windows_for_completed_bar(
        rows, bar_open_ms=100_000, bar_close_ms=120_000,
        decision_receive_monotonic_s=13.0,
    )

    assert [row["symbol"] for row in eligible] == ["BTCUSDT"]
    assert rejected == {
        "not_final": 1,
        "quality_failure": 1,
        "outside_completed_bar": 1,
        "missing_availability": 0,
        "received_at_or_after_decision": 1,
    }


def test_completed_bar_gate_requires_all_feature_windows_to_pass():
    valid = {
        "window_final": True,
        "data_quality_ready": True,
        "window_start_ms": 100_000,
        "window_end_ms": 110_000,
        "feature_available_receive_monotonic_s": 12.0,
    }
    incomplete = {**valid, "feature_available_receive_monotonic_s": None}
    selected, rejected = eligible_windows_for_completed_bar(
        [valid, incomplete], bar_open_ms=100_000, bar_close_ms=120_000,
        decision_receive_monotonic_s=13.0,
    )

    assert selected == [valid]
    assert rejected["missing_availability"] == 1


def test_completed_bar_gate_rejects_invalid_bar_bounds():
    with pytest.raises(ValueError, match="bar bounds"):
        eligible_windows_for_completed_bar(
            [], bar_open_ms=120_000, bar_close_ms=120_000,
            decision_receive_monotonic_s=13.0,
        )


def _candidate_window(start, *, available=601.5, sell=1000.0, buy=900.0,
                      bid_refill=0.8, ask_refill=0.9, symbol="BTCUSDT"):
    return {
        "symbol": symbol,
        "window_start_ms": start,
        "window_end_ms": start + 10_000,
        "window_final": True,
        "data_quality_ready": True,
        "feature_available_receive_monotonic_s": available,
        "sell_aggressor_quote_volume": sell,
        "buy_aggressor_quote_volume": buy,
        "bid_replenishment_ratio": bid_refill,
        "ask_replenishment_ratio": ask_refill,
        "trade_low": 99.0,
        "trade_high": 101.0,
        "d_plus_2s": {"event_ms": start + 12_000},
    }


def _candidate_bars(*, decision_receive=602.0, t_receive=600.5,
                    h_receive=600.4, macro=(101.0, 100.0, 99.0)):
    return {
        "t_bar": {
            "symbol": "BTCUSDT",
            "timeframe_minutes": 10,
            "bar_open_ms": 0,
            "bar_close_ms": 600_000,
            "completed": True,
            "feature_available_receive_monotonic_s": t_receive,
        },
        "btc_h_bar": {
            "symbol": "BTCUSDT",
            "timeframe_minutes": 240,
            "bar_open_ms": 0,
            "bar_close_ms": 14_400_000,
            "completed": True,
            "feature_available_receive_monotonic_s": h_receive,
            "close": macro[0],
            "ema50": macro[1],
            "ema50_5_bars_ago": macro[2],
        },
        "decision_event_ms": 14_402_000,
        "decision_receive_monotonic_s": decision_receive,
    }


def _prior_aggression(direction):
    return [
        {"symbol": "BTCUSDT", "direction": direction, "event_ms": 10_000,
         "aggression_quote_volume": 500.0},
        {"symbol": "BTCUSDT", "direction": direction, "event_ms": 20_000,
         "aggression_quote_volume": 600.0},
    ]


def test_candidate_builder_uses_macro_to_micro_and_selects_earliest_window():
    bars = _candidate_bars()
    prior_rows = _prior_aggression("long") + [
        # A later T-bar event cannot alter the threshold for the first event.
        {"symbol": "BTCUSDT", "direction": "long", "event_ms": 150_000,
         "aggression_quote_volume": 10_000.0},
    ]
    candidates, rejects = build_candidates_for_completed_bar(
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
    assert candidate["entry_price"] is None
    assert candidate["candidate_status"] == "awaiting_executable_post_signal_quote"
    assert rejects["window_not_eligible"] == 0


@pytest.mark.parametrize("bar_key", ["t_bar", "btc_h_bar"])
def test_candidate_builder_abstains_when_any_bar_feature_arrives_after_decision(bar_key):
    bars = _candidate_bars()
    bars[bar_key]["feature_available_receive_monotonic_s"] = 602.0
    candidates, rejects = build_candidates_for_completed_bar(
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
    candidates, rejects = build_candidates_for_completed_bar(
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
    candidates, _ = build_candidates_for_completed_bar(
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
        build_candidates_for_completed_bar(
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
    candidates, rejects = build_candidates_for_completed_bar(
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
         "aggression_quote_volume": 10.0},
        {"symbol": "BTCUSDT", "direction": "short", "event_ms": 1_500,
         "aggression_quote_volume": 1000.0},
        {"symbol": "BTCUSDT", "direction": "long", "event_ms": 1_000,
         "aggression_quote_volume": 10.0},
        {"symbol": "BTCUSDT", "direction": "long", "event_ms": 2_000,
         "aggression_quote_volume": 20.0},
        # Current and future rows are excluded before their values are inspected.
        {"symbol": "BTCUSDT", "direction": "long", "event_ms": 3_000,
         "aggression_quote_volume": 30.0},
        {"symbol": "BTCUSDT", "direction": "long", "event_ms": 4_000,
         "aggression_quote_volume": float("nan")},
    ]
    args = {
        "symbol": "BTCUSDT", "direction": "long", "anchor_event_ms": 3_000,
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
          "aggression_quote_volume": 20.0}],
        symbol="BTCUSDT", direction="long", anchor_event_ms=3_000,
        percentile=0.8, lookback_ms=30_000, minimum_history_n=2,
    )

    assert threshold is None
    assert count == 1


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
