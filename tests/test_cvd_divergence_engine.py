import numpy as np

from scripts.research.cvd_divergence_engine import (
    HOUR_MS,
    MarketSeries,
    causal_prefix_check,
    generate_events,
    resolve_barrier,
    replace_pending_for_new_pair,
    next_hour_entry_anchor,
    pending_confirmation_step,
    next_hour_entry_anchor,
    signed_delta,
    utc_daily_cvd,
    wilder_atr_reset_on_gaps,
    atr_available_at_open,
)


def _future(*, first_open=100.0, first_high=100.5, first_low=99.5,
            first_close=100.0):
    opens = np.full(10, 100.0)
    highs = np.full(10, 100.5)
    lows = np.full(10, 99.5)
    closes = np.full(10, 100.0)
    opens[0], highs[0], lows[0], closes[0] = first_open, first_high, first_low, first_close
    times = np.arange(10, dtype=np.int64) * HOUR_MS
    return opens, highs, lows, closes, times


def test_signed_taker_delta_and_utc_daily_cvd_reset():
    delta = signed_delta(np.array([10, 8, 4, 6]), np.array([7, 2, 3, 5]))
    assert delta.tolist() == [4.0, -4.0, 2.0, 4.0]
    times = np.array([0, HOUR_MS, 24 * HOUR_MS, 25 * HOUR_MS], dtype=np.int64)
    assert utc_daily_cvd(times, delta).tolist() == [4.0, 0.0, 2.0, 6.0]


def test_intraday_gap_resets_cvd_and_requires_fourteen_clean_bars_for_atr():
    times = np.r_[np.arange(20) * HOUR_MS, 24 * HOUR_MS + np.arange(15) * HOUR_MS].astype(np.int64)
    volume = np.ones(len(times)) * 4
    taker = np.ones(len(times)) * 3
    cvd = utc_daily_cvd(times, signed_delta(volume, taker))
    assert cvd[19] == 40
    assert cvd[20] == 2
    prices = np.arange(len(times), dtype=float) + 100
    atr = wilder_atr_reset_on_gaps(times, prices + 2, prices - 2, prices)
    assert np.isnan(atr[20])
    assert np.isnan(atr[32])
    assert np.isfinite(atr[33])
    at_open = atr_available_at_open(times, atr)
    assert np.isfinite(at_open[14])
    assert np.isnan(at_open[20])
    assert np.isnan(at_open[33])
    assert np.isfinite(at_open[34])


def test_nondivergent_new_pair_clears_old_pending_setup():
    pending = {"long": {"pivot2_idx": 10}, "short": None}
    replace_pending_for_new_pair(pending, "long", price_divergence=False,
                                 cvd_divergence=True, arm="price_only",
                                 new_setup={"pivot2_idx": 20})
    assert pending["long"] is None
    replace_pending_for_new_pair(pending, "long", price_divergence=True,
                                 cvd_divergence=False, arm="cvd",
                                 new_setup={"pivot2_idx": 30})
    assert pending["long"] is None
    replace_pending_for_new_pair(pending, "long", price_divergence=True,
                                 cvd_divergence=True, arm="cvd",
                                 new_setup={"pivot2_idx": 40})
    assert pending["long"] == {"pivot2_idx": 40}


def test_same_close_new_pair_supersedes_before_older_breakout_is_checked():
    pending = {"long": {"available_idx": 10, "pivot2_idx": 7}, "short": None}
    current_close_idx = 12  # old setup could otherwise confirm on this same close
    assert pending_confirmation_step(pending["long"], current_close_idx) == 2
    new_setup = {"available_idx": current_close_idx, "pivot2_idx": 9}
    replace_pending_for_new_pair(pending, "long", price_divergence=True,
                                 cvd_divergence=True, arm="cvd", new_setup=new_setup)
    assert pending_confirmation_step(pending["long"], current_close_idx) == 0


def test_missing_next_hour_bar_does_not_shift_entry_to_later_observation():
    times = np.array([0, HOUR_MS, 3 * HOUR_MS], dtype=np.int64)
    assert next_hour_entry_anchor(times, 1) == (2 * HOUR_MS, None)


def test_missing_next_hour_bar_does_not_shift_entry_to_later_observation():
    times = np.array([0, HOUR_MS, 3 * HOUR_MS], dtype=np.int64)
    assert next_hour_entry_anchor(times, 1) == (2 * HOUR_MS, None)


def test_triple_barrier_stop_first_and_adverse_gap_fill():
    opens, highs, lows, closes, times = _future(first_high=102, first_low=98)
    out = resolve_barrier("long", 100, 99, opens, highs, lows, closes, times,
                          np.array([], dtype=np.int64), np.array([]), 10)
    assert out["reason"] == "STOP"
    assert out["m2_hit"] is False
    assert out["exit_price"] == 99
    opens[0] = 98
    gap = resolve_barrier("long", 100, 99, opens, highs, lows, closes, times,
                          np.array([], dtype=np.int64), np.array([]), 10)
    assert gap["exit_price"] == 98


def test_target_and_timeout_labels_and_funding_exit_candle_charge():
    opens, highs, lows, closes, times = _future(first_high=101.2)
    funding_times = np.array([0, 1, 2 * HOUR_MS], dtype=np.int64)
    funding_rates = np.array([0.9, 0.01, -0.03])
    target = resolve_barrier("long", 100, 99, opens, highs, lows, closes, times,
                             funding_times, funding_rates, 10)
    assert target["m2_hit"] is True
    assert target["reason"] == "TARGET"
    assert target["exit_price"] == 101
    assert target["funding_signed"] == 0.01

    opens, highs, lows, closes, times = _future()
    timeout = resolve_barrier("long", 100, 99, opens, highs, lows, closes, times,
                              np.array([], dtype=np.int64), np.array([]), 10)
    assert timeout["reason"] == "TIMEOUT"
    assert timeout["m2_hit"] is False


def test_randomized_causal_prefix_and_future_mutation_are_nontrivial():
    rng = np.random.default_rng(4321)
    n = 24 * 40
    times = np.arange(n, dtype=np.int64) * HOUR_MS
    close = 100 * np.exp(np.cumsum(rng.normal(0, 0.006, n)))
    open_ = np.r_[close[0], close[:-1]]
    high = np.maximum(open_, close) * (1 + rng.uniform(0.0002, 0.005, n))
    low = np.minimum(open_, close) * (1 - rng.uniform(0.0002, 0.005, n))
    volume = rng.uniform(5, 20, n)
    taker = volume * rng.uniform(0.1, 0.9, n)
    data = MarketSeries(times, open_, high, low, close, volume, taker)
    end = int(times[-1] + 21 * HOUR_MS)
    for arm in ("price_only", "cvd"):
        events, _ = generate_events("TESTUSDT", data, arm=arm,
                                    eligible_start_ms=0, eligible_end_ms=end)
        assert len(events) > 0
        check = causal_prefix_check("TESTUSDT", data, arm=arm,
                                    eligible_start_ms=0, eligible_end_ms=end)
        assert check["status"] == "PASS"
        assert check["prefix_signal_count"] > 0

    full_events, _ = generate_events("TESTUSDT", data, arm="price_only",
                                     eligible_start_ms=0, eligible_end_ms=end)
    cut = len(times) // 2
    source = next(row for row in full_events if row["signal_idx"] < cut - 1 and row["entry_idx"] is not None)
    missing_idx = int(source["entry_idx"])
    gapped = MarketSeries(*(np.delete(np.asarray(value), missing_idx) for value in (
        data.times, data.open, data.high, data.low, data.close, data.volume, data.taker_buy_volume)))
    gapped_events, _ = generate_events("TESTUSDT", gapped, arm="price_only",
                                       eligible_start_ms=0, eligible_end_ms=end)
    assert any(row["entry_open_ms"] == source["entry_open_ms"] and row["entry_idx"] is None
               for row in gapped_events)
    check = causal_prefix_check("TESTUSDT", gapped, arm="price_only",
                                eligible_start_ms=0, eligible_end_ms=end)
    assert check["status"] == "PASS"
