"""Slice-1 plugin tests: no-lookahead on random walks for all plugins + hand-computed signals on tiny frames."""
import importlib.util
from pathlib import Path
import numpy as np
import pandas as pd
import pytest
from common.protocol import check_no_lookahead

PLUG = Path(__file__).resolve().parents[2] / "plugins" / "slice_1"
IDS = sorted(p.stem for p in PLUG.glob("*.py"))

def load(name):
    spec = importlib.util.spec_from_file_location("plug_" + name.replace("-", "_"), PLUG / f"{name}.py")
    m = importlib.util.module_from_spec(spec); spec.loader.exec_module(m); return m

def mk(closes, freq="1h", start="2024-01-01", half=0.5, opens=None, highs=None, lows=None, vol=100.0):
    c = np.asarray(closes, float); n = len(c)
    o = np.asarray(opens, float) if opens is not None else np.r_[c[0], c[:-1]]
    h = np.asarray(highs, float) if highs is not None else np.maximum(o, c) + half
    l = np.asarray(lows, float) if lows is not None else np.minimum(o, c) - half
    return pd.DataFrame(dict(open=o, high=h, low=l, close=c, volume=np.full(n, vol)),
                        index=pd.date_range(start, periods=n, freq=freq, tz="UTC"))

def idx(s):
    return list(np.flatnonzero(np.asarray(s, bool)))

def walk(n, freq, seed=0):
    r = np.random.default_rng(seed); c = 100 * np.exp(np.cumsum(r.normal(0, 0.01, n)))
    o = np.r_[c[0], c[:-1]]; h = np.maximum(o, c) * (1 + r.random(n) * 0.005); l = np.minimum(o, c) * (1 - r.random(n) * 0.005)
    return pd.DataFrame(dict(open=o, high=h, low=l, close=c, volume=r.random(n) * 100 + 10),
                        index=pd.date_range("2024-01-01", periods=n, freq=freq, tz="UTC"))

@pytest.mark.parametrize("name", IDS)
def test_no_lookahead_random_walk(name):
    m = load(name)
    freq = {"1h": "1h", "4h": "4h", "1d": "1D"}[m.TIMEFRAMES[0]]
    assert check_no_lookahead(m, walk(900, freq, seed=7))
    # signal frame contract
    s = m.signals(walk(300, freq, seed=3), **m.PARAMS)
    for col in ("long_entry", "short_entry", "long_exit", "short_exit"):
        assert col in s and s[col].dtype == bool and len(s) == 300

@pytest.mark.parametrize("name", IDS)
def test_grid_contract(name):
    from common.protocol import validate_grid
    m = load(name)
    assert m.SPEC_ID == name and m.DEVIATIONS and validate_grid(m.PARAM_GRID)
    assert set(m.PARAM_GRID) <= set(m.PARAMS)

# ------------------------------------------------------------------ hand-computed cases
def test_turtle_donchian_hand():
    m = load("c4-turtle-trend-trading-system-racer8")
    df = mk([9.5, 10.5, 11.5, 12.8, 11.0], opens=[9.5, 10.5, 11.5, 12.8, 11.0],
            highs=[10, 11, 12, 13, 12], lows=[9, 10, 11, 12, 10])
    s = m.signals(df, n=2, e=2)
    # close>max(high[t-2],high[t-1]): t=2 (11.5>11), t=3 (12.8>12); t=4 low 10 < min(low[2],low[3])=11 -> exit
    assert idx(s.long_entry) == [2, 3] and idx(s.long_exit) == [4] and idx(s.short_entry) == []

def test_weekend_momentum_hand():
    m = load("crypto-weekend-gated-7d-momentum")
    c = [10, 10, 10, 10, 12, 12, 12, 12, 12, 12, 12, 9, 9, 9]   # 2024-01-01 is Monday; Fridays idx 4 and 11
    df = mk(c, freq="1D")
    s = m.signals(df, lookback=2)
    assert idx(s.long_entry) == [4] and idx(s.short_entry) == [11]   # 12/10-1>0 ; 9/12-1<0
    assert (s.max_hold == 1).all() and not s.long_exit.any()

def test_sessions_day_momentum_night_cash_hand():
    m = load("btc-day-momentum-night-cash-08")
    n = 72; c = np.full(n, 100.0); o = c.copy()
    o[8] = 100; c[19] = 110            # Jan 1 day session [08,20): open 100 -> close 110 (up)
    o[32] = 100; c[43] = 90            # Jan 2 day session: down
    df = mk(c, opens=o, highs=np.maximum(o, c), lows=np.minimum(o, c))
    s = m.signals(df)
    assert idx(s.long_entry) == [31] and idx(s.short_entry) == [55]   # signals at 07:00 of Jan 2 / Jan 3
    assert (s.max_hold == 11).all()                                    # exit at close of the 19:00 bar

def test_sessions_reversal_long_hand():
    m = load("btc-08utc-reversal-long")
    n = 72; c = np.full(n, 100.0); o = c.copy(); o[8] = 100; c[19] = 110
    df = mk(c, opens=o, highs=np.maximum(o, c), lows=np.minimum(o, c))
    s = m.signals(df)
    # night long: signals at 19:00 bars (idx 19, 43, 67); day = -sign(prev day ret): Jan 2 07:00 (idx 31) short after Jan 1 up
    assert idx(s.long_entry) == [19, 43, 67] and idx(s.short_entry) == [31]

def test_sma_cross_hand():
    m = load("sma-30-150-always-in")
    df = mk([5, 4, 3, 2, 3, 4, 5, 6, 5, 4, 3], freq="1D")
    s = m.signals(df, fast=2, slow=3)
    assert idx(s.long_exit) == [9] and idx(s.short_exit) == [5]
    assert idx(s.long_entry) == [5, 6] and idx(s.short_entry) == [9, 10]   # +sticky repeat for reversals

def test_macd_hand():
    m = load("btc-macd-15-41-12")
    df = mk([10, 10, 10, 12, 12, 9, 9, 9, 12], freq="1D")
    s = m.signals(df, fast=1, slow=2, signal=2)   # first 4 bars masked as warm-up
    assert idx(s.long_exit) == [4] and idx(s.short_exit) == [6]
    assert idx(s.long_entry) == [6, 7] and idx(s.short_entry) == [4, 5]

def _flat_then_jump():
    c = [100.0] * 6 + [104.0] * 6
    return mk(c, opens=c, highs=[x + 1 for x in c], lows=[x - 1 for x in c], freq="1D")

def test_supertrend_flip_hand():
    m = load("btc-supertrend-3-32")
    s = m.signals(_flat_then_jump(), atr_len=2, mult=1.0)
    # Pine ta.supertrend: bands 102/98 until the 104 close at idx 6 breaks the 102 upper band -> bullish flip, no later exit
    assert idx(s.long_entry) == [6] and idx(s.long_exit) == []

def test_tv_st_ema200_hand():
    m = load("tv_st_ema200_btc1h")
    s = m.signals(_flat_then_jump(), factor=1.0, ema_len=2, atr_len=2)
    assert idx(s.long_entry) == [6, 7] and idx(s.short_entry) == [] and idx(s.short_exit) == [6]

def test_volatility_system_causal_resample_hand():
    m = load("ft_volatility_system")
    c = np.r_[np.full(36, 100.0), np.full(12, 110.0)]
    df = mk(c, opens=c, highs=c + 0.5, lows=c - 0.5)
    s = m.signals(df, atr_mult=2.0, resample_hours=2)
    # 2h bucket 18 (hours 36-37) jumps +10 but is only visible from its end (hour 38): ATR*2 of the previous bucket = 2
    assert idx(s.long_entry) == [38, 39, 40] and idx(s.short_entry) == []

def test_jesse_rsi_hand():
    m = load("jesse_tv_rsi")
    df = mk([10, 11, 12, 11, 10, 11])
    s = m.signals(df, rsi=2, xparam=75)
    # Wilder RSI(2): [nan,nan,100,50,25,62.5]
    assert idx(s.long_entry) == [5] and idx(s.long_exit) == [3]
    assert np.allclose(s.stop_pct, 0.05) and np.allclose(s.tp_pct, 0.10)

def test_ema_supertrend_pine_precedence_hand():
    m = load("c4-ema-supertrend")
    df = mk([10, 10, 10, 12, 14, 13, 9])
    s = m.signals(df, len1=2, len2=3, len4=2)
    assert idx(s.long_entry) == [3, 4] and idx(s.long_exit) == [6]

def test_myth_gaussian_weights_and_twopole():
    m = load("c4-strategy-myth-busting-12-osgfc-supertrend-myn")
    w = m._weights(10)
    assert w.shape == (11,) and abs(w.sum() - 1) < 1e-12 and (np.diff(w) < 0).all()
    assert np.allclose(m._twopole(np.full(30, 5.0), 10.0), 5.0)      # constant input passes through the smoother
    # fib levels 1,2,3,5,8,...: smthper=3 -> size 5, weights exp(-9 i^2/36) i=0..3 normalised
    w3 = m._weights(3); raw = np.exp(-9 * np.arange(4) ** 2 / 36.0)
    assert np.allclose(w3, raw / raw.sum())

def test_ichimoku_state_quirk_and_stop_levels():
    m = load("c4-ichimoku-long-and-short-strategy")
    s = m.signals(walk(600, "1h", seed=11), disp=26, rr=2.0)
    le = idx(s.long_entry); se = idx(s.short_entry)
    ent = s.long_entry | s.short_entry
    assert (s.stop_pct.notna() | ~ent).all()
