import numpy as np
import pandas as pd

from scripts.research import funding_tail_reversal_probe as probe


def test_funding_event_threshold_excludes_current_rate_and_uses_trailing_window():
    times = np.arange(100, dtype=np.int64) * 8 * 60 * 60 * 1000
    rates = np.zeros(100, dtype=float)
    rates[-1] = 0.01
    events = probe.funding_events(times, rates)
    current = next(event for event in events if event["funding_index"] == 99)
    assert current["side"] == "short"
    assert current["q90"] == 0


def test_future_funding_mutation_cannot_change_prefix_threshold_or_signal():
    times = np.arange(120, dtype=np.int64) * 8 * 60 * 60 * 1000
    rates = np.sin(np.arange(120) / 5) * 0.001
    assert probe.causal_future_mutation_check(times, rates)["status"] == "PASS"


def test_same_bar_stop_and_target_is_scored_stop_first():
    frame = pd.DataFrame({"t_open_ms": [0], "o": [100.0], "h": [103.0],
                          "l": [97.0], "c": [100.0]})
    result = probe._m2_path("long", 100.0, 99.0, frame, 1,
                            np.asarray([], dtype=np.int64), np.asarray([], dtype=float))
    assert result["m2_hit"] is False
    assert result["reason"] == "STOP"


def test_non_signal_funding_events_count_toward_coverage_denominator():
    times = np.arange(100, dtype=np.int64) * 8 * 60 * 60 * 1000
    rates = np.zeros(100, dtype=float)
    events = probe.funding_events(times, rates)
    assert len(events) == 70
    assert sum(event["side"] is not None for event in events) == 0
