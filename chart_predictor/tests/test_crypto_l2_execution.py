import pytest

from scripts.research.crypto_l2_execution import replay_candidate, walk_book, walk_book_for_base


def _quote(event_ms, receive_mono, bid, ask, *, bid_size=20.0, ask_size=20.0):
    return {
        "symbol": "BTCUSDT",
        "event_ms": event_ms,
        "receive_mono": receive_mono,
        "best_bid": bid,
        "best_ask": ask,
        "bid_levels": [[bid, bid_size]],
        "ask_levels": [[ask, ask_size]],
    }


def _candidate(*, side="long", stop=99.0, signal_ms=1000, signal_mono=1.0):
    return {
        "symbol": "BTCUSDT",
        "side": side,
        "signal_event_ms": signal_ms,
        "signal_receive_monotonic_s": signal_mono,
        "stop_price_pre_entry": stop,
    }


def test_quote_notional_depth_walk_sorts_asks_before_filling():
    fill = walk_book([[101.0, 2.0], [100.0, 20.0]], order_side="buy",
                     quote_notional=2100.0)

    assert fill["quote_notional"] == pytest.approx(2100.0)
    assert fill["filled_base"] == pytest.approx(20.0 + 100.0 / 101.0)
    assert fill["vwap"] == pytest.approx(2100 / fill["filled_base"])


def test_base_depth_walk_fills_exact_position_quantity_or_fails_closed():
    fill = walk_book_for_base([[100.0, 1.0], [99.0, 2.0]], order_side="sell",
                              base_quantity=2.0)

    assert fill["filled_base"] == pytest.approx(2.0)
    assert fill["quote_notional"] == pytest.approx(199.0)
    assert walk_book_for_base([[100.0, 1.0]], order_side="sell",
                              base_quantity=2.0) is None


def test_replay_uses_strictly_later_entry_and_scores_target_with_complete_cost_inputs():
    quotes = [
        _quote(1000, 1.1, 99.9, 100.1),  # same event time: cannot enter
        _quote(1100, 1.2, 99.9, 100.1),
        _quote(1600, 1.7, 102.2, 102.3),
        _quote(11_000, 11.1, 102.0, 102.1),
    ]

    result = replay_candidate(
        _candidate(), quotes, horizon_ms=10_000, atr14=2.0, tick_size=0.1,
        funding_events=[], funding_coverage_complete=True,
    )

    assert result["status"] == "SCORED"
    assert result["target_first"] is True
    assert result["exit_reason"] == "target"
    assert result["entry_event_ms"] == 1100
    assert result["exit_event_ms"] == 1600
    assert result["net_return"] is not None
    assert result["stress_net_return"] < result["net_return"]


def test_replay_invalidates_candidate_if_stop_is_hit_before_entry():
    result = replay_candidate(
        _candidate(), [_quote(1050, 1.1, 98.9, 99.0)],
        horizon_ms=10_000, atr14=2.0, tick_size=0.1,
        funding_events=[], funding_coverage_complete=True,
    )

    assert result["status"] == "INVALIDATED_BEFORE_ENTRY"
    assert result["target_first"] is False


def test_replay_marks_stop_first_and_fills_at_the_observed_adverse_quote():
    result = replay_candidate(
        _candidate(), [_quote(1100, 1.1, 99.9, 100.1),
                       _quote(1600, 1.7, 98.8, 98.9)],
        horizon_ms=10_000, atr14=2.0, tick_size=0.1,
        funding_events=[], funding_coverage_complete=True,
    )

    assert result["status"] == "SCORED"
    assert result["target_first"] is False
    assert result["exit_reason"] == "stop"
    assert result["exit"] == pytest.approx(98.8)


def test_replay_scores_short_with_ask_side_exits_and_receives_positive_funding():
    result = replay_candidate(
        _candidate(side="short", stop=101.0),
        [_quote(1100, 1.1, 99.9, 100.1),
         _quote(1600, 1.7, 98.6, 98.7)],
        horizon_ms=10_000, atr14=2.0, tick_size=0.1,
        funding_events=[{"time_ms": 1500, "rate": 0.001, "mark": 100.0}],
        funding_coverage_complete=True,
    )

    assert result["status"] == "SCORED"
    assert result["target_first"] is True
    assert result["exit_reason"] == "target"
    assert result["funding_pnl"] > 0


def test_replay_refuses_insufficient_entry_depth():
    result = replay_candidate(
        _candidate(), [_quote(1100, 1.1, 99.9, 100.1, ask_size=1.0)],
        horizon_ms=10_000, atr14=2.0, tick_size=0.1,
        funding_events=[], funding_coverage_complete=True,
    )

    assert result["status"] == "UNSCORABLE"
    assert result["reason"] == "insufficient_entry_depth"


def test_replay_rejects_risk_over_two_atr_and_requires_full_horizon():
    large_risk = replay_candidate(
        _candidate(stop=95.0), [_quote(1100, 1.1, 99.9, 100.1)],
        horizon_ms=10_000, atr14=2.0, tick_size=0.1,
        funding_events=[], funding_coverage_complete=True,
    )
    short_path = replay_candidate(
        _candidate(), [_quote(1100, 1.1, 99.9, 100.1), _quote(5000, 5.1, 100.0, 100.1)],
        horizon_ms=10_000, atr14=2.0, tick_size=0.1,
        funding_events=[], funding_coverage_complete=True,
    )

    assert large_risk["reason"] == "risk_exceeds_2_atr"
    assert short_path["reason"] == "execution_quote_gap_exceeds_750ms"


def test_replay_rejects_risk_smaller_than_twice_spread_depth_and_fee_cost():
    result = replay_candidate(
        _candidate(stop=99.98), [_quote(1100, 1.1, 99.99, 100.01)],
        horizon_ms=10_000, atr14=1.0, tick_size=0.01,
        funding_events=[], funding_coverage_complete=True,
    )

    assert result["status"] == "REJECTED_RISK"
    assert result["reason"] == "risk_below_2x_round_trip_cost"


def test_replay_times_out_only_after_continuous_quote_coverage_to_horizon():
    quotes = [_quote(1100, 1.1, 99.9, 100.1)]
    quotes.extend(_quote(event_ms, event_ms / 1000, 99.9, 100.1)
                  for event_ms in range(1600, 11_001, 500))
    quotes.append(_quote(11_000, 11.0, 99.9, 100.1))

    result = replay_candidate(
        _candidate(), quotes, horizon_ms=10_000, atr14=2.0, tick_size=0.1,
        funding_events=[], funding_coverage_complete=True,
    )

    assert result["status"] == "SCORED"
    assert result["target_first"] is False
    assert result["exit_reason"] == "timeout"
    assert result["exit_event_ms"] == 11_000


def test_replay_rejects_off_tick_stop_and_receive_order_conflict():
    off_tick = replay_candidate(
        _candidate(stop=99.05), [_quote(1100, 1.1, 99.9, 100.1)],
        horizon_ms=10_000, atr14=2.0, tick_size=0.1,
        funding_events=[], funding_coverage_complete=True,
    )
    out_of_order = replay_candidate(
        _candidate(), [_quote(1100, 2.0, 99.9, 100.1),
                       _quote(1200, 1.5, 99.9, 100.1)],
        horizon_ms=10_000, atr14=2.0, tick_size=0.1,
        funding_events=[], funding_coverage_complete=True,
    )

    assert off_tick["reason"] == "stop_off_exchange_tick"
    assert out_of_order["reason"] == "receive_order_conflicts_with_event_order"


def test_replay_reports_target_label_but_withholds_net_return_without_funding_coverage():
    result = replay_candidate(
        _candidate(), [_quote(1100, 1.1, 99.9, 100.1),
                       _quote(1600, 1.7, 102.2, 102.3)],
        horizon_ms=10_000, atr14=2.0, tick_size=0.1,
        funding_events=[], funding_coverage_complete=False,
    )

    assert result["status"] == "SCORED_GROSS_FUNDING_UNVERIFIED"
    assert result["target_first"] is True
    assert result["net_return"] is None


def test_replay_applies_funding_cashflow_and_stress_fee_slippage():
    result = replay_candidate(
        _candidate(), [_quote(1100, 1.1, 99.9, 100.1),
                       _quote(1600, 1.7, 102.2, 102.3)],
        horizon_ms=10_000, atr14=2.0, tick_size=0.1,
        funding_events=[{"time_ms": 1500, "rate": 0.001, "mark": 100.0}],
        funding_coverage_complete=True,
    )

    assert result["funding_pnl"] < 0
    assert result["net_return"] < result["stress_net_return"] + 0.01
    assert result["stress_net_return"] < result["net_return"]
