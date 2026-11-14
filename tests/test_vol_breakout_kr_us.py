import sys
from pathlib import Path

import pandas as pd
import pytest

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
from app import vol_breakout_kr_us_backtest as m


def test_breakout_fill_and_next_open_exit_with_nonbreakout_day():
    dates = pd.date_range("2024-01-01", periods=5, freq="D", tz="UTC")
    frame = pd.DataFrame(
        {
            "Open": [100, 102, 103, 104, 105],
            "High": [110, 107, 106, 106, 106],
            "Low": [90, 100, 102, 103, 104],
            "Close": [105, 104, 105, 105, 105],
        },
        index=dates,
    )
    trades = m.make_trades(frame, 0.5)

    # Day 2 uses day 1 range (20): trigger=102+10=112, so no breakout.
    # Day 3 uses day 2 range (7): trigger=103+3.5=106.5, so no breakout.
    # Day 4 uses day 3 range (4): trigger=104+2=106, so breakout and next
    # day's open (105) is the exact exit. Day 4 is also evaluated freshly.
    assert len(trades) == 1
    assert trades[0]["entry_date"] == dates[3].isoformat()
    assert trades[0]["entry_price"] == pytest.approx(106.0)
    assert trades[0]["exit_date"] == dates[4].isoformat()
    assert trades[0]["exit_price"] == pytest.approx(105.0)


def test_exit_day_can_also_be_a_fresh_entry_day():
    dates = pd.date_range("2024-02-01", periods=4, freq="D", tz="UTC")
    frame = pd.DataFrame({"Open": [100, 100, 100, 100],
                          "High": [110, 110, 110, 100],
                          "Low": [90, 90, 90, 90]}, index=dates)
    trades = m.make_trades(frame, 0.5)
    assert len(trades) == 2
    assert trades[0]["entry_date"] == dates[1].isoformat()
    assert trades[0]["exit_date"] == dates[2].isoformat()
    assert trades[1]["entry_date"] == dates[2].isoformat()
    assert trades[1]["exit_date"] == dates[3].isoformat()
