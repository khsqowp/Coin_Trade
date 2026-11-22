import importlib.util
from pathlib import Path

import numpy as np
import pandas as pd
import pytest

from common.protocol import check_no_lookahead

ROOT = Path(__file__).resolve().parents[1]
IDS = [
    "btc-08utc-cash-long", "btc-08utc-long-momentum",
    "btc-08utc-momentum-reversal", "btc-08utc-reversal-short",
    "btc-08utc-short-reversal", "btc-night-reversal-day-cash-08",
    "eth-day-reversal-night-cash-05",
]

def load_plugin(spec_id):
    path = ROOT / f"{spec_id}.py"
    spec = importlib.util.spec_from_file_location(spec_id.replace('-', '_'), path)
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module

def sample(h):
    idx = pd.date_range("2026-01-01", periods=24 * 6, freq="h", tz="UTC")
    opens = np.full(len(idx), 100.0)
    closes = opens.copy()
    # For every completed session, make D returns positive and N returns negative.
    origin = pd.Timestamp("1970-01-01", tz="UTC") + pd.Timedelta(hours=h)
    starts = origin + ((idx - origin) // pd.Timedelta(hours=12)) * pd.Timedelta(hours=12)
    for start in pd.unique(starts):
        pos = np.flatnonzero(starts == start)
        if len(pos) == 12:
            closes[pos[-1]] = 101.0 if int((start - origin) / pd.Timedelta(hours=12)) % 2 == 0 else 99.0
    return pd.DataFrame({"open": opens, "high": np.maximum(opens, closes),
                         "low": np.minimum(opens, closes), "close": closes,
                         "volume": 1.0}, index=idx)

@pytest.mark.parametrize("spec_id", IDS)
def test_synthetic_no_lookahead(spec_id):
    plugin = load_plugin(spec_id)
    df = sample(plugin.PARAMS["h"])
    assert check_no_lookahead(plugin, df)

def test_hand_computed_fixed_momentum_reversal_signals():
    df = sample(8)
    # 2026-01-02 08:00 session starts; entry signal is prior bar close.
    sigrow = pd.Timestamp("2026-01-02 07:00", tz="UTC")
    fixed = load_plugin("btc-08utc-cash-long").signals(df)
    momentum = load_plugin("btc-08utc-long-momentum").signals(df)
    reversal = load_plugin("btc-08utc-momentum-reversal").signals(df)
    # Prior day return was +1%; prior night return was -1%.
    assert bool(fixed.loc[sigrow, "long_entry"]) is False  # daytime leg is cash
    assert bool(momentum.loc[sigrow, "long_entry"]) is True
    assert bool(momentum.loc[sigrow, "short_entry"]) is False
    assert bool(reversal.loc[sigrow, "long_entry"]) is True
    assert momentum.loc[sigrow, "max_hold"] == 11
    # 2026-01-02 19:00 signals the night session; prior night was negative.
    night_row = pd.Timestamp("2026-01-02 19:00", tz="UTC")
    assert bool(fixed.loc[night_row, "long_entry"]) is True
    assert bool(momentum.loc[night_row, "short_entry"]) is True
    assert bool(reversal.loc[night_row, "long_entry"]) is True
