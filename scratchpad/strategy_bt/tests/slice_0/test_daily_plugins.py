import importlib.util
import sys
from pathlib import Path

import numpy as np
import pandas as pd
import pytest

ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT))
from common.protocol import check_no_lookahead

PLUGIN_DIR = ROOT / "plugins" / "slice_0"
DATA = ROOT.parent / "bb_stoch_stc" / "data"
PLUGINS = {
    "ibs": "ibs-range-break-meanrev.py",
    "bb": "btc-bollinger-37-16.py",
    "ema": "btc-ema-5-30.py",
    "roc": "btc-roc-36-9pct.py",
    "rsi": "rsi7-30-70-fixed20.py",
    "turtle": "jesse_turtle.py",
}


def load(name):
    path = PLUGIN_DIR / PLUGINS[name]
    spec = importlib.util.spec_from_file_location("slice0_" + name, path)
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


def frame(close, high=None, low=None):
    close = np.asarray(close, dtype=float)
    high = close + 1 if high is None else np.asarray(high, dtype=float)
    low = close - 1 if low is None else np.asarray(low, dtype=float)
    return pd.DataFrame({"open": close, "high": high, "low": low, "close": close})


@pytest.mark.parametrize("name", PLUGINS)
def test_no_lookahead(name):
    rng = np.random.default_rng(2048)
    close = 100 * np.exp(np.cumsum(rng.normal(0, 0.015, 600)))
    spread = rng.uniform(0.2, 2.0, 600)
    df = pd.DataFrame({"open": close, "high": close + spread, "low": close - spread, "close": close}, index=pd.date_range("2020-01-01", periods=600, freq="D", tz="UTC"))
    assert check_no_lookahead(load(name), df)


def test_ibs_hand_computed_entry_bar():
    plugin = load("ibs")
    # At bar 1, rolling high is 10, mean range is 2, lower=8; IBS=(6.5-6)/2=.25.
    df = frame([9.0, 6.5], high=[10, 10], low=[8, 6])
    out = plugin.signals(df, n_high=2, n_range=2, mult=1, ibs_max=0.3)
    assert out.long_entry.tolist() == [False, True]


def test_bollinger_hand_computed_cross_bar():
    out = load("bb").signals(frame([1, 1, 3]), n=2, k=0)
    # At bar 2 close 3 is above its two-point center 2, after bar 1 closed at its center 1.
    assert out.long_entry.tolist() == [False, False, True]


def test_ema_hand_computed_cross_bar():
    out = load("ema").signals(frame([3, 2, 1, 2]), fast=1, slow=2)
    # Seeded EMA(2) is 1.444... at bar 2; close/EMA(1)=2 crosses above it at bar 3.
    assert out.long_entry.tolist() == [False, False, False, True]
    assert out.short_exit.tolist() == [False, False, False, True]


def test_roc_hand_computed_entry_bar():
    out = load("roc").signals(frame([100, 100, 120]), n=2, thr=0.09)
    # At bar 2, 120/100-1=20%, strictly above 9%.
    assert out.long_entry.tolist() == [False, False, True]


def test_rsi_hand_computed_recross_bar():
    out = load("rsi").signals(frame([100, 90, 80, 85]), period=2, os=30, hold=20)
    # RSI is 0 at bar 2; Wilder averages at bar 3 are gain 2.5/loss 5, RSI=33.33.
    assert out.long_entry.tolist() == [False, False, False, True]
    assert out.max_hold.tolist() == [19.0] * 4


def test_turtle_hand_computed_entry_bar():
    out = load("turtle").signals(frame([9, 9, 10], high=[10, 10, 11], low=[8, 8, 9]), entry=2, exit=1, atr_n=2)
    # Bar 2 high 11 reaches above the maximum high (10) of the previous two bars.
    assert out.long_entry.tolist() == [False, False, True]


@pytest.mark.parametrize("name", PLUGINS)
def test_btc_daily_parquet_smoke(name):
    path = DATA / "BTCUSDT_1d.parquet"
    if not path.exists():
        pytest.skip("BTCUSDT_1d.parquet is unavailable")
    df = pd.read_parquet(path)
    out = load(name).signals(df, **load(name).PARAMS)
    assert len(out) == len(df)
    assert out.index.equals(df.index)
    assert (out.long_entry | out.short_entry).any(), f"{name} produced no entries on BTCUSDT_1d"
