import numpy as np

from scripts.research.crypto_macro_mtf_sweep_probe import (
    WIDTH_1M,
    WIDTH_5M,
    WIDTH_4H,
    complete_bars,
    find_first_mss,
    macro_structure,
    regimes_for_micro,
    scan_events,
    score_path,
)


def test_complete_bars_rejects_missing_minutes():
    times = np.delete(np.arange(10, dtype=np.int64) * WIDTH_1M, 7)
    prices = np.arange(len(times), dtype=float) + 100
    bars = complete_bars(times, prices, prices + 1, prices - 1, prices, 5 * WIDTH_1M)
    assert bars["t"].tolist() == [0]


def test_confirmed_four_hour_regime_is_causal():
    n = 16
    times = np.arange(n, dtype=np.int64) * WIDTH_4H
    highs, lows = np.full(n, 10.0), np.full(n, 9.0)
    highs[2], highs[7], lows[4], lows[9] = 12, 14, 7, 8
    source = {"t": times, "h": highs, "l": lows}
    state = macro_structure(source)
    assert state[10] == 0  # the second HL is not yet confirmed
    assert state[11] == 1  # right-side confirmation bar 2 has closed
    future_peeking_pivot = highs[2] > max(highs[0], highs[1], highs[3], highs[4])
    assert future_peeking_pivot and state[2] == 0  # negative control would signal too early

    changed = {name: values.copy() for name, values in source.items()}
    changed["h"][12:] *= 100
    changed["l"][12:] /= 100
    assert np.array_equal(macro_structure(changed)[:12], state[:12])

    h4 = {"t": np.array([0, WIDTH_4H, 2 * WIDTH_4H], dtype=np.int64)}
    micro = {"t": np.array([WIDTH_4H - 2 * WIDTH_5M,
                             WIDTH_4H - WIDTH_5M,
                             WIDTH_4H], dtype=np.int64)}
    mapped = regimes_for_micro(micro, h4, np.array([1, -1, -1], dtype=np.int8))
    assert mapped.tolist() == [0, 1, 1]


def test_sweep_mss_are_sequential_and_signal_is_prefix_invariant():
    n = 30
    times = np.arange(n, dtype=np.int64) * WIDTH_5M
    micro = {"t": times, "o": np.full(n, 100.0), "h": np.full(n, 101.0),
             "l": np.full(n, 99.0), "c": np.full(n, 100.0)}
    micro["l"][12], micro["c"][12] = 98, 100
    micro["h"][13], micro["c"][13] = 102, 101.5
    regime = np.ones(n, dtype=np.int8)
    assert find_first_mss(micro, regime, 12, "long") == 13

    raw_times = np.arange(70, 120, dtype=np.int64) * WIDTH_1M
    raw = {"t": raw_times, "o": np.full(50, 100.0), "h": np.full(50, 100.2),
           "l": np.full(50, 99.8), "c": np.full(50, 100.0)}
    _, first = scan_events("TESTUSDT", micro, regime, raw)
    assert len(first) == 1
    assert first[0]["sweep_ms"] == 60 * WIDTH_1M
    assert first[0]["mss_ms"] == 65 * WIDTH_1M
    assert first[0]["entry_ms"] == 70 * WIDTH_1M

    future_changed = {name: values.copy() for name, values in micro.items()}
    future_changed["h"][14:] *= 1.5
    future_changed["l"][14:] *= 0.5
    _, changed_events = scan_events("TESTUSDT", future_changed, regime, raw)
    assert [(e["sweep_ms"], e["mss_ms"], e["entry_ms"]) for e in first] == [
        (e["sweep_ms"], e["mss_ms"], e["entry_ms"]) for e in changed_events]


def test_trade_resolution_is_stop_first_adverse_gap_and_timeout():
    times = np.arange(50, dtype=np.int64) * WIDTH_1M
    opens, highs = np.full(50, 100.0), np.full(50, 100.2)
    lows, closes = np.full(50, 99.8), np.full(50, 100.0)

    highs[0], lows[0] = 103.0, 97.0
    both = score_path("long", 100.0, 99.0, times, opens, highs, lows, closes)
    assert both["outcome"] == "STOP" and both["exit_price"] == 99.0

    opens[0], highs[0], lows[0] = 98.0, 99.0, 97.0
    gap = score_path("long", 100.0, 99.0, times, opens, highs, lows, closes)
    assert gap["outcome"] == "STOP" and gap["exit_price"] == 98.0

    opens[0], highs[0], lows[0] = 100.0, 100.2, 99.8
    timeout = score_path("long", 100.0, 99.0, times, opens, highs, lows, closes)
    assert timeout["outcome"] == "TIMEOUT"
