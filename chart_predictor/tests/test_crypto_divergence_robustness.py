import numpy as np
import pytest

from chart_predictor import crypto_divergence_robustness as study


def test_divergence_uses_anchor_oscillator_and_emits_only_at_confirmation(monkeypatch):
    sh = np.full(12, np.nan); sl = np.full(12, np.nan)
    sl[5], sl[9] = 10.0, 9.0  # lag 2 => anchors 3 and 7
    monkeypatch.setattr(study.indicators, "confirmed_swings", lambda h, l, lag: (sh, sl))
    osc = np.zeros(12); osc[3], osc[7] = 30.0, 40.0
    osc[5], osc[9] = 90.0, 1.0  # deliberately misleading confirmation-bar values
    signals = study.divergence_signals(np.ones(12)*11, np.ones(12)*10,
                                       np.ones(12)*10.5, osc, lag=2)
    assert len(signals) == 1
    assert signals[0] == study.DivergenceSignal(9, 7, "long", 9.0, 40.0)
    assert all(s.index > s.anchor for s in signals)


def test_macro_filter_blocks_wrong_regime_and_allows_mirror_signal(monkeypatch):
    sh = np.full(12, np.nan); sl = np.full(12, np.nan)
    sl[5], sl[9] = 10.0, 9.0
    monkeypatch.setattr(study.indicators, "confirmed_swings", lambda h, l, lag: (sh, sl))
    osc = np.arange(12, dtype=float)
    args = (np.ones(12)*11, np.ones(12)*10, np.ones(12)*10.5, osc)
    assert study.divergence_signals(*args, lag=2, macro_direction=np.full(12, -1)) == []
    assert study.divergence_signals(*args, lag=2, macro_direction=np.ones(12))


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
    spike = study.plateau_summary(grid)
    selected = next(x for x in spike if x["params"] == {"lag": 2, "target": 2})
    assert selected["neighbor_pass_fraction"] == 0
    assert not selected["plateau_robust"]

    broad = [_cell(a, b) for a in (1, 2, 3) for b in (1, 2, 3)]
    plateau = study.plateau_summary(broad)
    center = next(x for x in plateau if x["params"] == {"lag": 2, "target": 2})
    assert center["neighbor_pass_fraction"] == 1
    assert center["plateau_robust"]


def test_unresolved_adjacent_cell_counts_as_plateau_failure():
    grid = [_cell(a, b) for a in (1, 2, 3) for b in (1, 2, 3)]
    row = next(x for x in grid if x["params"] == {"lag": 1, "target": 2})
    row["resolved"] = False; row["m2"] = None; row["n"] = 0; row["net_expectancy"] = 0
    center = next(x for x in study.plateau_summary(grid)
                  if x["params"] == {"lag": 2, "target": 2})
    assert center["neighbor_pass_fraction"] < 1
    assert not center["plateau_robust"]
