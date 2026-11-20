import importlib.util
from pathlib import Path

import numpy as np
import pandas as pd
from common.protocol import check_no_lookahead

ROOT = Path(__file__).resolve().parents[2] / "plugins" / "slice_4"
PLUGIN_PATH = ROOT / "c5-turtle-crypto-20-10-donchian-2n-stop.py"

def load():
    spec = importlib.util.spec_from_file_location("turtle_crypto_slice4", PLUGIN_PATH)
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module

def frame(index, open_, high, low, close):
    return pd.DataFrame({"open": open_, "high": high, "low": low, "close": close}, index=index)

def test_turtle_donchian_no_lookahead():
    plugin = load()
    index = pd.date_range("2024-01-01", periods=24 * 35, freq="h", tz="UTC")
    close = 100 + np.arange(len(index), dtype=float) * 0.01
    df = frame(index, close, close + 1, close - 1, close + 0.1)
    assert check_no_lookahead(plugin, df)
    # Alter only future prices; every earlier output must remain identical.
    full = plugin.signals(df)
    changed = df.copy()
    changed.iloc[24 * 30:, changed.columns.get_indexer(["high", "low", "close"])] *= 3
    revised = plugin.signals(changed)
    pd.testing.assert_frame_equal(full.iloc[:24 * 30], revised.iloc[:24 * 30], check_dtype=False)

def test_turtle_daily_levels_and_wilder_n_hand_computed():
    plugin = load()
    # One hourly candle per UTC date makes daily OHLC and true range explicit.
    index = pd.date_range("2024-01-01", periods=22, freq="D", tz="UTC")
    high = np.full(22, 11.0)
    low = np.full(22, 9.0)
    close = np.full(22, 10.0)
    high[0:20] = np.arange(11.0, 31.0)
    low[0:20] = np.arange(9.0, 29.0)
    close[0:20] = np.arange(10.0, 30.0)
    high[20] = 35.0
    low[20] = 29.0
    close[20] = 32.0
    high[21] = 20.0
    low[21] = 18.0
    close[21] = 19.0
    df = frame(index, close, high, low, close)
    result = plugin.signals(df, entry_days=20, exit_days=10, n_days=20, stop_n=2.0)
    # Day 20 uses days 0..19 for its entry bound: max high = 30, close=32.
    assert bool(result.long_entry.iloc[20])
    # Daily TR for days 0..19 is 2; N seed is therefore 2 and is used one day later.
    assert np.isclose(result.atr_stop.iloc[20], 4.0)
    # Day 21 lower bound uses days 11..20, whose minimum low is 20; close=19 signals exit.
    assert bool(result.long_exit.iloc[21])

HOBBIE_PATH = ROOT / "c5-hobbiecode-ibs-monday-reversal.py"
RASCHKE_PATH = ROOT / "c5-raschke-anti-stochastic-7-10-3-hook.py"
DATA = Path(__file__).resolve().parents[3] / "bb_stoch_stc" / "data"

def load_path(path, name):
    spec = importlib.util.spec_from_file_location(name, path)
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module

def test_hobbiecode_recovers_symbol_specific_daily_split_timestamps():
    plugin = load_path(HOBBIE_PATH, "hobbiecode_slice4")
    for symbol in ("BTCUSDT", "ETHUSDT", "BNBUSDT", "XRPUSDT"):
        path = DATA / f"{symbol}_1d.parquet"
        if not path.exists():
            continue
        source = pd.read_parquet(path)
        split = int(len(source) * .6)
        for part in (source.iloc[:split], source.iloc[split:]):
            frame = part.reset_index(drop=True)
            restored = plugin._utc_index(frame)
            expected = part.index.tz_localize("UTC") if part.index.tz is None else part.index.tz_convert("UTC")
            assert restored.equals(expected), f"wrong recovered timestamps for {symbol} length={len(frame)}"
            assert check_no_lookahead(plugin, frame)

def test_raschke_same_day_max_hold_is_prefix_causal():
    plugin = load_path(RASCHKE_PATH, "raschke_hook_slice4")
    # Build oscillating candles that create signals, then cut the frame inside a day.
    index = pd.date_range("2024-01-01", periods=24 * 8, freq="h", tz="UTC")
    close = 100 + np.sin(np.arange(len(index)) * .7) * 8
    high = close + 1 + (np.arange(len(index)) % 3) * .2
    low = close - 1 - (np.arange(len(index)) % 4) * .2
    df = frame(index, close, high, low, close)
    assert check_no_lookahead(plugin, df)
    full = plugin.signals(df)
    for end in (77, 101, 143):
        prefix = plugin.signals(df.iloc[:end])
        pd.testing.assert_frame_equal(full.iloc[:end].reset_index(drop=True), prefix.reset_index(drop=True), check_dtype=False)


def test_both_repaired_plugins_pass_cached_symbol_timeframe_lookahead_sweep():
    plugins = (
        (load_path(HOBBIE_PATH, "hobbiecode_sweep_slice4"), ("1d",)),
        (load_path(RASCHKE_PATH, "raschke_sweep_slice4"), ("1h", "4h")),
    )
    for plugin, timeframes in plugins:
        for timeframe in timeframes:
            paths = sorted(DATA.glob(f"*_{timeframe}.parquet"))
            for path in paths:
                df = pd.read_parquet(path)
                assert check_no_lookahead(plugin, df, plugin.PARAMS), f"lookahead: {path.name}"
