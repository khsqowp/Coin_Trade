import importlib.util
from pathlib import Path

import numpy as np
import pandas as pd
import pytest

from common.protocol import check_no_lookahead

ROOT = Path(__file__).resolve().parents[2] / "plugins" / "slice_4"
IDS = [
    "c5-cci20-minus150-bounce-long-only",
    "c5-fib-bollinger-0.618-lower-ema-filter",
    "c5-rob-booker-adx-breakout-box",
    "c5-upbit-noise-k20-ma5-same-day-close",
]


def load(sid):
    spec = importlib.util.spec_from_file_location(sid.replace("-", "_"), ROOT / f"{sid}.py")
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


def frame(close, high=None, low=None, open_=None, idx=None, volume=None):
    close = np.asarray(close, dtype=float)
    open_ = close.copy() if open_ is None else np.asarray(open_, dtype=float)
    high = np.maximum(open_, close) if high is None else np.asarray(high, dtype=float)
    low = np.minimum(open_, close) if low is None else np.asarray(low, dtype=float)
    return pd.DataFrame({"open": open_, "high": high, "low": low, "close": close,
                         "volume": 1.0 if volume is None else volume}, index=idx)


@pytest.mark.parametrize("sid", IDS)
def test_no_lookahead(sid):
    idx = pd.date_range("2025-01-01", periods=24 * 30, freq="h", tz="UTC")
    c = 100 + np.sin(np.arange(len(idx)) / 7) + np.arange(len(idx)) * 0.01
    df = frame(c, high=c + 1, low=c - 1, open_=c - 0.1, idx=idx)
    p = load(sid)
    assert check_no_lookahead(p, df)


def test_cci_bounce_and_exit_hand_calculation():
    p = load("c5-cci20-minus150-bounce-long-only")
    c = np.array([100, 90, 80, 70, 65, 72, 80, 90], float)
    # length=3 gives finite CCI; lower threshold on preceding bar, current CCI rises,
    # and signal candle body must meet 0.25%.
    o = c.copy(); o[5] = 71
    df = frame(c, high=c + 0.1, low=c - 0.1, open_=o)
    sig = p.signals(df, cci_len=3, entry_level=-50, exit_level=50, min_body=0.0025, stop=0.08)
    cci = p._cci(df, 3)
    expected_entry = (np.r_[np.nan, cci[:-1]] < -50) & (cci > np.r_[np.nan, cci[:-1]]) & (c / o - 1 >= 0.0025)
    np.testing.assert_array_equal(sig.long_entry.to_numpy(), np.nan_to_num(expected_entry, nan=False))
    np.testing.assert_array_equal(sig.long_exit.to_numpy(), cci > 50)
    assert sig.stop_pct.eq(0.08).all()


def test_fib_band_touch_and_cross_hand_calculation():
    p = load("c5-fib-bollinger-0.618-lower-ema-filter")
    # Positive drift makes EMA(2) > EMA(4); final bar deliberately touches the lower band.
    c = np.array([10, 11, 12, 13, 14, 15, 16, 17, 18, 19], float)
    h, l = c + 0.5, c - 0.5
    l[-1] = 0
    df = frame(c, high=h, low=l)
    sig = p.signals(df, length=4, dev_mult=1.5, ema_fast=2, ema_slow=4)
    assert sig.long_entry.iloc[-1]
    # No bar before the last can touch its lower band under the steadily rising series.
    assert not sig.long_entry.iloc[:-1].any()
    assert not sig.long_exit.any()


def test_booker_box_break_and_width_management_hand_calculation(monkeypatch):
    p = load("c5-rob-booker-adx-breakout-box")
    # Force the range filter true; directly verify prior 3-bar box breakout and width stops.
    monkeypatch.setattr(p, "_adx", lambda df, n: np.zeros(len(df)))
    c = np.array([10, 11, 10, 10, 13, 12, 8, 9], float)
    h = np.array([11, 12, 11, 11, 13, 12.5, 9, 9.5], float)
    l = np.array([9, 10, 9, 9, 12, 11.5, 8, 8.5], float)
    df = frame(c, high=h, low=l)
    sig = p.signals(df, adx_len=2, box_len=3, adx_max=18, stop_width=0.5, target_width=1)
    # At i=4, prior box upper=12 and close crosses above it; at i=6, prior lower=9 and close crosses below.
    assert sig.long_entry.iloc[4]
    assert sig.short_entry.iloc[6]
    assert sig.stop_pct.iloc[4] == pytest.approx((12 - 9) / 13 * 0.5)
    assert sig.tp_pct.iloc[4] == pytest.approx((12 - 9) / 13)


def test_upbit_daily_trigger_filter_and_one_entry_hand_calculation():
    p = load("c5-upbit-noise-k20-ma5-same-day-close")
    idx = pd.date_range("2025-01-01", periods=72, freq="h", tz="UTC")
    # Each of the first two days has a 10-point range. Daily closes rise 100 -> 105 -> 110,
    # satisfying day-2's prior-close > SMA(2); day 2 triggers at open(110)+10*prior K.
    o = np.repeat([100.0, 105.0, 110.0], 24)
    c = o.copy()
    h = o + 5
    l = o - 5
    c[23] = 100; c[47] = 105
    # K from prior completed days is 1.0, hence threshold 120 on day 3; first touch at 05:00.
    h[48 + 5] = 121
    c[48 + 5] = 120
    h[48 + 6:] = 121
    df = frame(c, high=h, low=l, open_=o, idx=idx)
    sig = p.signals(df, noise_len=2, ma_len=2)
    entries = np.flatnonzero(sig.long_entry.to_numpy())
    assert entries.tolist() == [53]
    assert sig.max_hold.iloc[53] == 17

