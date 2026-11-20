import numpy as np
import pandas as pd

from scripts.research.hourly_return_reversal_screen import (
    generate_records, screening_decisions, signal_side,
)


def _frame(opens, closes):
    hours = len(opens)
    return pd.DataFrame({
        "t_open_ms": np.arange(hours, dtype=np.int64) * 3_600_000,
        "o": np.asarray(opens, dtype=float),
        "h": np.maximum(opens, closes),
        "l": np.minimum(opens, closes),
        "c": np.asarray(closes, dtype=float),
        "v": np.ones(hours),
    })


def test_signal_side_is_strictly_contrarian_and_zero_abstains():
    assert signal_side(np.asarray([100.0, 110.0]), 1) == -1
    assert signal_side(np.asarray([100.0, 90.0]), 1) == 1
    assert signal_side(np.asarray([100.0, 100.0]), 1) == 0


def test_entry_is_next_open_and_exit_is_one_or_four_closed_bars_later():
    frame = _frame([100, 110, 100, 105, 101, 99, 97],
                   [110, 100, 105, 101, 99, 97, 95])
    h1 = generate_records("BTCUSDT", frame, np.array([], dtype=np.int64),
                          np.array([], dtype=float), 1)
    first = next(r for r in h1 if r["signal_close_ms"] == 2 * 3_600_000)
    assert first["side"] == 1
    assert first["entry_ms"] == 2 * 3_600_000
    assert first["exit_ms"] == 3 * 3_600_000
    assert first["entry_price"] == 100.0
    assert first["exit_price"] == 105.0

    frame4 = _frame([100 + i for i in range(20)], [101 + i for i in range(20)])
    h4 = generate_records("BTCUSDT", frame4, np.array([], dtype=np.int64),
                          np.array([], dtype=float), 4)
    assert h4
    assert all((r["signal_close_ms"] // 3_600_000) % 4 == 0 for r in h4)
    assert all(r["exit_ms"] - r["entry_ms"] == 4 * 3_600_000 for r in h4)


def test_funding_at_entry_excluded_and_funding_at_exit_included():
    frame = _frame([100, 90, 90, 90], [100, 90, 90, 91])
    entry_ms, exit_ms = 2 * 3_600_000, 3 * 3_600_000
    ft = np.asarray([entry_ms, exit_ms], dtype=np.int64)
    fr = np.asarray([0.01, 0.02], dtype=float)
    records = generate_records("BTCUSDT", frame, ft, fr, 1)
    row = next(r for r in records if r["entry_ms"] == entry_ms)
    assert row["funding_rate_sum"] == 0.02


def test_hourly_gap_is_a_hard_data_error():
    frame = _frame([100, 99, 98, 97], [99, 98, 97, 96])
    frame.loc[2, "t_open_ms"] += 1
    try:
        generate_records("BTCUSDT", frame, np.array([], dtype=np.int64),
                         np.array([], dtype=float), 1)
    except ValueError as exc:
        assert "not unique and contiguous" in str(exc)
    else:
        raise AssertionError("timestamp gap was not rejected")


def test_screening_gate_includes_cost_ci_and_symbol_concentration():
    row = {
        "horizon_h": 1, "split": "all_exposed", "net_base": 0.01,
        "net_stress": 0.005, "net_base_market_time_ci": [0.001, 0.02],
        "net_stress_market_time_ci": [0.0001, 0.01],
        "top_symbol_positive_gross_share": 0.24,
    }
    outcome = screening_decisions([row])
    assert outcome["horizons"]["1"]["progress_to_separate_m2_design"]
    assert outcome["overall"] == "PROGRESS_TO_M2_DESIGN"

    row["top_symbol_positive_gross_share"] = 0.26
    outcome = screening_decisions([row])
    assert not outcome["horizons"]["1"]["progress_to_separate_m2_design"]
    assert outcome["overall"] == "REJECT_SOURCE_INSPIRED_SETUP"
