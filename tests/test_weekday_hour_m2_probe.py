import numpy as np

from scripts.research import weekday_hour_m2_probe as probe


def market_data(opens, highs, lows, closes, times=None, funding_times=(), funding_rates=()):
    n = len(opens)
    return {
        "times": np.asarray(times if times is not None else np.arange(n) * probe.HOUR_MS, dtype=np.int64),
        "o": np.asarray(opens, dtype=float), "h": np.asarray(highs, dtype=float),
        "l": np.asarray(lows, dtype=float), "c": np.asarray(closes, dtype=float),
        "funding_times": np.asarray(funding_times, dtype=np.int64),
        "funding_rates": np.asarray(funding_rates, dtype=float),
    }


def test_calendar_side_uses_exact_52_prior_occurrences_and_abstains_on_tie():
    opens = np.full(probe.LOOKBACK_BARS + 1, 100.0)
    closes = np.full_like(opens, 101.0)
    side = probe._calendar_sides(opens, closes)
    assert side[probe.LOOKBACK_BARS - 1] == 0
    assert side[probe.LOOKBACK_BARS] == 1

    closes[probe.LOOKBACK_BARS - 168] = 99.0
    closes[probe.LOOKBACK_BARS - 2 * 168] = 99.0
    # 50 positive and 2 negative occurrences remain long.
    assert probe._calendar_sides(opens, closes)[probe.LOOKBACK_BARS] == 1

    closes[:] = opens
    assert probe._calendar_sides(opens, closes)[probe.LOOKBACK_BARS] == 0


def test_utc_slot_ids_use_utc_weekday_hour():
    # 2026-06-01 00:00 UTC is Monday, slot 0.
    monday = int(np.datetime64("2026-06-01T00:00:00", "ms").astype(np.int64))
    assert probe._utc_slot_ids(np.asarray([monday]))[0] == 0


def test_atr_uses_only_completed_bars_before_entry():
    high = np.full(20, 101.0)
    low = np.full(20, 99.0)
    close = np.full(20, 100.0)
    atr = probe._atr14_prior(high, low, close, 15)
    high[15] = 1_000_000
    low[15] = 1
    assert probe._atr14_prior(high, low, close, 15) == atr
    assert np.isnan(probe._atr14_prior(high, low, close, 14))


def test_same_bar_stop_and_target_is_stop_first():
    data = market_data([100, 100, 100, 100], [100, 102, 100, 100],
                       [100, 98, 100, 100], [100, 100, 100, 100])
    result = probe._path(data, 0, 1, 1.0)
    assert result["reason"] == "STOP"
    assert result["m2_hit"] is False
    assert result["exit_price"] == 99.0


def test_gap_through_stop_fills_at_adverse_open():
    data = market_data([100, 97, 97, 97], [100, 98, 98, 98],
                       [100, 96, 96, 96], [100, 97, 97, 97])
    result = probe._path(data, 0, 1, 1.0)
    assert result["reason"] == "STOP"
    assert result["exit_price"] == 97.0


def test_target_gap_is_credited_at_target_and_counted_hit():
    data = market_data([100, 102, 102, 102], [100, 103, 103, 103],
                       [100, 101, 101, 101], [100, 102, 102, 102])
    result = probe._path(data, 0, 1, 1.0)
    assert result["reason"] == "TARGET"
    assert result["m2_hit"] is True
    assert result["exit_price"] == 101.0


def test_timeout_is_m2_failure_at_fourth_bar_close():
    data = market_data([100] * 4, [100.2] * 4, [99.8] * 4, [100.1] * 4)
    result = probe._path(data, 0, 1, 1.0)
    assert result["reason"] == "TIMEOUT"
    assert result["m2_hit"] is False
    assert result["exit_price"] == 100.1


def test_funding_in_barrier_exit_bar_only_charges_possible_payment():
    t0 = 1_000_000_000
    data = market_data([100] * 4, [102, 100, 100, 100], [100] * 4, [101] * 4,
                       times=t0 + np.arange(4) * probe.HOUR_MS,
                       funding_times=[t0 + 30 * 60_000, t0 + probe.HOUR_MS + 30 * 60_000],
                       funding_rates=[0.001, -0.001])
    result = probe._path(data, 0, 1, 1.0)
    assert result["reason"] == "TARGET"
    # First payment is in the exit bar; later credit is outside the recorded exit bar.
    assert result["funding_cost"] == 0.001


def test_path_rejects_incomplete_window():
    data = market_data([100] * 3, [100] * 3, [100] * 3, [100] * 3)
    try:
        probe._path(data, 0, 1, 1.0)
    except ValueError as exc:
        assert "incomplete" in str(exc)
    else:
        raise AssertionError("incomplete outcome path was accepted")


def test_strategy_suppresses_same_symbol_signals_until_after_exit(monkeypatch):
    monkeypatch.setattr(probe, "LOOKBACK_BARS", 0)
    monkeypatch.setattr(probe, "ATR_BARS", 0)
    monkeypatch.setattr(probe, "_calendar_sides", lambda o, c: np.ones(len(o), dtype=np.int8))
    monkeypatch.setattr(probe, "_atr14_prior", lambda h, l, c, i: 1.0)
    n = 13
    data = market_data([100] * n, [100.2] * n, [99.8] * n, [100.1] * n)
    records, counts = probe._simulate_symbol("BTCUSDT", data, 0, n * probe.HOUR_MS)
    indices = [row["signal_index"] for row in records]
    assert indices == [1, 5, 9]
    assert all(right >= left + probe.HORIZON_BARS for left, right in zip(indices, indices[1:]))
    assert counts["suppressed_open_position"] > 0
