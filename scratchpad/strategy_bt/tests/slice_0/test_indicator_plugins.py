import importlib.util
import sys
from pathlib import Path

import numpy as np
import pandas as pd

ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT))
from common.protocol import check_no_lookahead


def load_plugin(name):
    path = ROOT / "plugins" / "slice_0" / f"{name}.py"
    spec = importlib.util.spec_from_file_location(f"slice0_{name}", path)
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


def test_bband_rsi_hand_computed_entry_at_bar_19():
    plugin = load_plugin("ft_bband_rsi")
    close = np.full(20, 100.0); close[-1] = 80.0
    frame = pd.DataFrame({"open": close, "high": close + 1, "low": close - 1, "close": close, "volume": 1.0})
    # Through bar 18, all closes and typical prices are 100. At 19, RSI is 0
    # after the sole -20 change and the lower band is far above close=80.
    signals = plugin.signals(frame)
    assert signals.index[signals.long_entry].tolist() == [19]


def test_macd_helpers_hand_computed_cross_and_adx():
    plugin = load_plugin("tv_macd_pullback_adx")
    a = np.array([0.0, 1.0, 2.0, 1.0, 0.0]); b = np.ones(5)
    assert np.flatnonzero(plugin.cross_up(a, b)).tolist() == [2]
    assert np.flatnonzero(plugin.cross_down(a, b)).tolist() == [4]
    high = np.array([11., 12., 13., 14., 15.])
    low = np.array([9., 10., 11., 12., 13.])
    close = np.array([10., 11., 12., 13., 14.])
    # With period 2, both observed +DM values equal TR/2 and -DM is zero,
    # so DX=100; its two-value seed yields ADX=100 at index 3.
    adx = plugin.adx_wilder(high, low, close, 2)
    assert np.isnan(adx[2])
    assert adx[3] == 100.0 and adx[4] == 100.0


def test_breakout_hand_computed_signal_at_bar_2():
    plugin = load_plugin("tv_breakout_hunter_60")
    frame = pd.DataFrame({
        "open": [9., 9., 10.], "high": [11., 11., 12.5], "low": [8., 8., 9.5],
        "close": [10., 10., 12.], "volume": [5., 5., 10.],
    })
    # Bar 2 closes above prior HH=11, body fraction=2/3, volume=2x prior
    # average (=5), and above its 2-bar trend midrange of 10.25.
    out = plugin.signals(frame, entry_n=2, exit_n=2, trend_n=2, body_min=.6, vol_mult=2, vol_n=2, stop_n=2)
    assert np.flatnonzero(out.long_entry).tolist() == [2]
    assert out.stop_pct.iloc[2] == 1 / 3


def random_ohlc(seed=31, rows=620):
    rng = np.random.default_rng(seed)
    close = 100 * np.exp(np.cumsum(rng.normal(0, .008, rows)))
    open_ = np.r_[close[0], close[:-1]] * (1 + rng.normal(0, .002, rows))
    high = np.maximum(open_, close) * (1 + rng.uniform(0, .01, rows))
    low = np.minimum(open_, close) * (1 - rng.uniform(0, .01, rows))
    return pd.DataFrame({"open": open_, "high": high, "low": low, "close": close,
                         "volume": rng.lognormal(5, .5, rows)},
                        index=pd.date_range("2025-01-01", periods=rows, freq="h", tz="UTC"))


def test_plugins_pass_protocol_no_lookahead_on_synthetic_frames():
    frame = random_ohlc()
    for name in ("ft_bband_rsi", "tv_macd_pullback_adx", "tv_breakout_hunter_60"):
        assert check_no_lookahead(load_plugin(name), frame)


def test_plugins_smoke_cached_parquet_and_produce_entries():
    data = ROOT.parent / "bb_stoch_stc" / "data"
    cases = {
        "ft_bband_rsi": ["BTCUSDT_1h.parquet"],
        "tv_macd_pullback_adx": ["BTCUSDT_1h.parquet", "BTCUSDT_4h.parquet"],
        "tv_breakout_hunter_60": ["BTCUSDT_1h.parquet", "BTCUSDT_4h.parquet"],
    }
    for name, files in cases.items():
        plugin = load_plugin(name)
        for filename in files:
            frame = pd.read_parquet(data / filename)
            out = plugin.signals(frame, **plugin.PARAMS)
            assert len(out) == len(frame)
            assert (out.long_entry | out.short_entry).any(), f"{name} produced no entry on {filename}"
