import importlib.util
from pathlib import Path
import numpy as np
import pandas as pd
import pytest
from common.protocol import check_no_lookahead

ROOT = Path(__file__).resolve().parents[2] / "plugins" / "slice_4"
DATA = Path(__file__).resolve().parents[3] / "bb_stoch_stc" / "data"
IDS = ["c5-connors-cumulative-rsi-3x3", "c5-larry-williams-3-period-ema-highs-lows", "c5-sc-last-stochastic-39"]

def load(sid):
    spec = importlib.util.spec_from_file_location(sid.replace("-", "_"), ROOT / f"{sid}.py")
    mod = importlib.util.module_from_spec(spec); spec.loader.exec_module(mod); return mod

@pytest.mark.parametrize("sid", IDS)
def test_no_lookahead_on_cached_btc(sid):
    p = load(sid)
    tf = p.TIMEFRAMES[0]
    df = pd.read_parquet(DATA / f"BTCUSDT_{tf}.parquet")
    assert check_no_lookahead(p, df)
    out = p.signals(df, **p.PARAMS)
    assert len(out) == len(df)
    assert list(out.columns[:4]) == ["long_entry", "short_entry", "long_exit", "short_exit"]

def test_larry_hand_computed_ema_signals():
    p = load("c5-larry-williams-3-period-ema-highs-lows")
    df = pd.DataFrame({"high": [10, 11, 12, 13], "low": [8, 9, 10, 11], "close": [7, 8, 12, 14]})
    out = p.signals(df)
    # EMA(3) seeded by first observation gives low EMA [8, 8.5, 9.25, 10.125], high EMA [10, 10.5, 11.25, 12.125].
    assert out.long_entry.tolist() == [True, True, False, False]
    assert out.long_exit.tolist() == [False, False, True, True]

def test_stochastic_week_close_hand_computed():
    p = load("c5-sc-last-stochastic-39")
    # Pin the moving threshold/cross math with shortened periods through public parameters.
    close = np.array([1, 2, 3, 4, 5, 6, 7, 8, 9, 10, 11, 12], float)
    df = pd.DataFrame({"high": close + 1, "low": close - 1, "close": close})
    out = p.signals(df, length=3, week_bars=2)
    assert not out.long_entry.any() and not out.short_entry.any()
    assert not out.long_exit.any() and not out.short_exit.any()

def test_connors_rsi_cumulative_hand_computed_constant_rise():
    p = load("c5-connors-cumulative-rsi-3x3")
    close = np.arange(1., 16.)
    df = pd.DataFrame({"close": close})
    out = p.signals(df, entry=200, exit=300)
    assert out.long_entry.sum() == 0
    assert out.long_exit.sum() == 0
