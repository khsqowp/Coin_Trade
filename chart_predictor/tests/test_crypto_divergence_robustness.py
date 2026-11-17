import numpy as np
import pytest

from chart_predictor import crypto_divergence_robustness as study


def test_divergence_uses_anchor_oscillator_and_emits_only_at_confirmation(monkeypatch):
    sh = np.full(12, np.nan); sl = np.full(12, np.nan)
    sl[5], sl[9] = 10.0, 9.0  # lag 2 => anchors 3 and 7
    monkeypatch.setattr(study, "_unique_confirmed_swings", lambda h, l, lag: (sh, sl))
    osc = np.zeros(12); osc[3], osc[7] = 30.0, 40.0
    osc[5], osc[9] = 90.0, 1.0  # deliberately misleading confirmation-bar values
    signals = study.divergence_signals(np.ones(12)*11, np.ones(12)*10,
                                       np.ones(12)*10.5, osc, lag=2)
    assert len(signals) == 1
    assert signals[0] == study.DivergenceSignal(9, 7, "long", 9.0, 40.0)
    assert all(s.index > s.anchor for s in signals)


def test_unique_pivot_confirmation_rejects_equal_extreme_ties():
    # Equal lows in a centered window must not create duplicate pivot events.
    low = np.array([12, 11, 10, 10, 11, 12, 11], dtype=float)
    high = low + 2
    sh, sl = study._unique_confirmed_swings(high, low, lag=2)
    assert not np.isfinite(sl).any()
    # A strictly unique low is confirmed exactly two bars after its anchor.
    low = np.array([12, 11, 10, 11, 12, 13, 14], dtype=float)
    high = low + 2
    _, sl = study._unique_confirmed_swings(high, low, lag=2)
    assert sl[4] == 10
    assert np.count_nonzero(np.isfinite(sl)) == 1


def test_divergence_features_are_prefix_invariant_and_future_peek_probe_is_detected():
    low = np.array([13, 12, 11, 12, 10, 11, 12, 11, 10, 11, 9, 10, 11, 12, 13, 12, 11], float)
    high = low + np.array([3, 4, 2, 4, 3, 2, 4, 3, 2, 4, 3, 2, 4, 3, 2, 4, 3])
    close = (high + low) / 2
    osc = np.linspace(20, 60, len(low))
    cutoff = 14
    base = study.divergence_signals(high, low, close, osc, lag=2,
                                    macro_direction=np.ones(len(low), dtype=int))
    altered_low, altered_high, altered_close, altered_osc = (x.copy() for x in (low, high, close, osc))
    altered_low[cutoff:] = [100, 1, 100]
    altered_high[cutoff:] = altered_low[cutoff:] + 2
    altered_close[cutoff:] = (altered_high[cutoff:] + altered_low[cutoff:]) / 2
    altered_osc[cutoff:] = -1000
    changed = study.divergence_signals(altered_high, altered_low, altered_close, altered_osc,
                                       lag=2, macro_direction=np.ones(len(low), dtype=int))
    assert [s for s in base if s.index < cutoff] == [s for s in changed if s.index < cutoff]

    # Control: feed a deliberately future-peeking feature to the same
    # prefix-invariance checker and prove the checker rejects it.
    def deliberately_peeking_feature(values):
        return np.full(cutoff, np.min(values[cutoff:]))

    def prefix_invariant(feature, first, second):
        try:
            np.testing.assert_array_equal(feature(first), feature(second))
        except AssertionError:
            return False
        return True

    assert not prefix_invariant(deliberately_peeking_feature, low, altered_low)


def test_macro_filter_blocks_wrong_regime_and_allows_mirror_signal(monkeypatch):
    sh = np.full(12, np.nan); sl = np.full(12, np.nan)
    sl[5], sl[9] = 10.0, 9.0
    monkeypatch.setattr(study, "_unique_confirmed_swings", lambda h, l, lag: (sh, sl))
    osc = np.arange(12, dtype=float)
    args = (np.ones(12)*11, np.ones(12)*10, np.ones(12)*10.5, osc)
    assert study.divergence_signals(*args, lag=2, macro_direction=np.full(12, -1)) == []
    assert study.divergence_signals(*args, lag=2, macro_direction=np.ones(12))


def test_ohlc_path_is_long_short_symmetric_and_stop_wins_same_bar_tie():
    tie = study.resolve_ohlc_path([100], [111], [89], [101],
                                  side="long", stop=90, target=110,
                                  open_times_ms=[0], expected_start_ms=0, expected_count=1)
    mirror = study.resolve_ohlc_path([100], [111], [89], [99],
                                     side="short", stop=110, target=90,
                                     open_times_ms=[0], expected_start_ms=0, expected_count=1)
    assert tie == {"status": "stop", "price": 90.0, "bar_index": 0}
    assert mirror == {"status": "stop", "price": 110.0, "bar_index": 0}


def test_ohlc_path_applies_adverse_stop_gap_and_target_price_on_favorable_gap():
    stop_gap = study.resolve_ohlc_path([85], [88], [80], [82],
                                       side="long", stop=90, target=110,
                                       open_times_ms=[0], expected_start_ms=0, expected_count=1)
    target_gap = study.resolve_ohlc_path([115], [118], [112], [116],
                                         side="long", stop=90, target=110,
                                         open_times_ms=[0], expected_start_ms=0, expected_count=1)
    assert stop_gap == {"status": "stop", "price": 85.0, "bar_index": 0}
    assert target_gap == {"status": "target", "price": 110.0, "bar_index": 0}


def test_ohlc_path_marks_missing_or_malformed_required_path_unresolved():
    missing = study.resolve_ohlc_path([100, 100, 100], [102]*3, [98]*3, [100]*3,
                                      side="long", stop=90, target=110,
                                      open_times_ms=[0, 60_000, 180_000],
                                      expected_start_ms=0, expected_count=3)
    malformed = study.resolve_ohlc_path([100], [99], [98], [100],
                                        side="long", stop=90, target=110,
                                        open_times_ms=[0], expected_start_ms=0, expected_count=1)
    assert missing == {"status": "unresolved", "price": None, "bar_index": 2}
    assert malformed == {"status": "unresolved", "price": None, "bar_index": 0}


def test_ohlc_path_detects_missing_first_and_last_required_bar():
    leading = study.resolve_ohlc_path([100, 100], [102, 102], [98, 98], [100, 100],
                                      side="long", stop=90, target=110,
                                      open_times_ms=[60_000, 120_000],
                                      expected_start_ms=0, expected_count=2)
    trailing = study.resolve_ohlc_path([100], [102], [98], [100],
                                        side="long", stop=90, target=110,
                                        open_times_ms=[0], expected_start_ms=0,
                                        expected_count=2)
    assert leading == {"status": "unresolved", "price": None, "bar_index": 0}
    assert trailing == {"status": "unresolved", "price": None, "bar_index": 1}


def test_ohlc_path_rejects_non_integer_timestamps():
    with pytest.raises(ValueError, match="integer millisecond"):
        study.resolve_ohlc_path([100], [102], [98], [100], side="long", stop=90, target=110,
                                open_times_ms=[0.5], expected_start_ms=0,
                                expected_count=1)


def test_monte_carlo_has_exactly_1000_deterministic_reorders():
    values = [-1.0, 0.8, -0.3, 1.2, -0.5, 0.6]
    a = study.monte_carlo_reorder_mdd(values)
    b = study.monte_carlo_reorder_mdd(values)
    assert a == b
    assert a["simulations"] == 1000
    assert a["permuted_mdd_p95_pct"] >= a["permuted_mdd_median_pct"]
    assert a["permuted_mdd_max_pct"] >= a["permuted_mdd_p95_pct"]


def test_monte_carlo_rejects_wrong_resample_count():
    with pytest.raises(ValueError):
        study.monte_carlo_reorder_mdd([0.1, -0.1], simulations=999)


def test_walk_forward_is_five_half_open_chronological_day_windows():
    windows = study.walk_forward_windows(100)
    assert len(windows) == 5
    assert windows[0] == {"fold": 1, "train_start": 100, "train_end": 604,
                          "test_start": 604, "test_end": 856}
    for a, b in zip(windows, windows[1:]):
        assert b["train_start"] == a["train_start"] + 252
        assert a["test_end"] == b["test_start"]


def _cell(a, b, *, m2=0.85, n=40, ev=0.1, resolved=True):
    return {"params": {"lag": a, "target": b}, "m2": m2, "n": n,
            "net_expectancy": ev, "resolved": resolved}


def test_plateau_rejects_isolated_spike_and_accepts_broad_neighborhood():
    grid = [_cell(a, b, m2=(0.91 if (a, b) == (2, 2) else 0.55),
                  ev=(0.2 if (a, b) == (2, 2) else -0.1))
            for a in (1, 2, 3) for b in (1, 2, 3)]
    expected = [{"lag": a, "target": b} for a in (1, 2, 3) for b in (1, 2, 3)]
    spike = study.plateau_summary(grid, expected_params=expected)
    selected = next(x for x in spike if x["params"] == {"lag": 2, "target": 2})
    assert selected["neighbor_pass_fraction"] == 0
    assert not selected["plateau_robust"]

    broad = [_cell(a, b) for a in (1, 2, 3) for b in (1, 2, 3)]
    plateau = study.plateau_summary(broad, expected_params=expected)
    center = next(x for x in plateau if x["params"] == {"lag": 2, "target": 2})
    assert center["neighbor_pass_fraction"] == 1
    assert center["plateau_robust"]


def test_unresolved_adjacent_cell_counts_as_plateau_failure():
    grid = [_cell(a, b) for a in (1, 2, 3) for b in (1, 2, 3)]
    row = next(x for x in grid if x["params"] == {"lag": 1, "target": 2})
    row["resolved"] = False; row["m2"] = None; row["n"] = 0; row["net_expectancy"] = 0
    expected = [{"lag": a, "target": b} for a in (1, 2, 3) for b in (1, 2, 3)]
    center = next(x for x in study.plateau_summary(grid, expected_params=expected)
                  if x["params"] == {"lag": 2, "target": 2})
    assert center["neighbor_pass_fraction"] < 1
    assert not center["plateau_robust"]


def test_missing_grid_neighbor_counts_as_failure_when_expected_grid_is_frozen():
    params = [{"lag": a, "target": b} for a in (1, 2, 3) for b in (1, 2, 3)]
    grid = [_cell(p["lag"], p["target"]) for p in params
            if p != {"lag": 1, "target": 2}]
    center = next(x for x in study.plateau_summary(grid, expected_params=params)
                  if x["params"] == {"lag": 2, "target": 2})
    assert center["neighbor_count"] == 4
    assert center["neighbor_pass_fraction"] == 0.75
    assert not center["plateau_robust"]


def test_plateau_requires_the_frozen_expected_grid():
    with pytest.raises(TypeError):
        study.plateau_summary([_cell(a, b) for a in (1, 2) for b in (1, 2)])
