from types import SimpleNamespace

import numpy as np
import pandas as pd

from scripts.research import long_history_setup_m2_probe as probe


def fixture_frame(rows=300):
    index = np.arange(rows)
    close = 100 + 0.03 * index + 2 * np.sin(index / 4)
    open_ = np.r_[close[0], close[:-1]]
    return pd.DataFrame({
        "t_open_ms": index.astype(np.int64) * 3_600_000,
        "o": open_, "h": np.maximum(open_, close) + 0.5,
        "l": np.minimum(open_, close) - 0.5, "c": close,
        "v": 1000 + 10 * np.cos(index / 3),
    })


def test_actual_setup_families_are_prefix_invariant_under_future_mutation():
    result = probe.causal_future_mutation_check(fixture_frame())
    assert result["status"] == "PASS"
    assert result["setup_count"] == 38


def test_causal_guard_detects_future_dependent_signal(monkeypatch):
    def leaky(frame, setup):
        return [SimpleNamespace(index=10, side="long", stop=float(frame.c.iloc[-1]))]

    monkeypatch.setattr(probe, "generate_signals", leaky)
    result = probe.causal_future_mutation_check(fixture_frame(), setups=("leaky",))
    assert result["status"] == "FAIL"
    assert "future mutation" in result["failures"][0]["error"]


def test_invalid_entry_is_scored_as_nonhit_not_dropped():
    frame = pd.DataFrame({
        "t_open_ms": [0, 3_600_000], "o": [100, 101], "h": [101, 102],
        "l": [99, 100], "c": [100, 101], "v": [1, 1],
    })
    result = probe._m2_path("long", 101, 102, frame.iloc[1:], 1,
                            np.asarray([], dtype=np.int64), np.asarray([], dtype=float))
    assert result["m2_hit"] is False
    assert result["reason"] == "INVALID_ENTRY"


def test_opportunity_count_includes_last_complete_horizon_anchor():
    times = np.arange(25, dtype=np.int64) * 3_600_000
    assert probe._eligible_opportunities(times, 0, 25 * 3_600_000, 20) == 5
