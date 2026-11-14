"""Strategy sources + synthetic data for the ablation tests.

PRIOR_DEFECT_* reproduces run-main-002: SMA200 trend entry + ATR(14)x3 trailing exit where the trailing exit
fires but the very same bar re-enters (close is still > SMA200), so the signal equals plain close > SMA200.
Neither the Engineer's unit tests nor the LLM Auditor noticed this.
"""
import numpy as np
import pandas as pd

HEADER = '''import numpy as np
import pandas as pd

SMA_LENGTH = 50
ATR_LENGTH = 14
ATR_MULTIPLE = 3.0
RULES = {"sma_trend_entry": "enter when close > SMA", "sma_exit": "exit when close < SMA",
         "atr_trailing_exit": "exit when close < highest close since entry - 3*ATR"}


def _prep(df):
    close = df["close"].astype(float)
    prev_close = close.shift(1)
    tr = pd.concat([df["high"] - df["low"], (df["high"] - prev_close).abs(), (df["low"] - prev_close).abs()], axis=1).max(axis=1)
    atr = tr.ewm(alpha=1.0 / ATR_LENGTH, adjust=False, min_periods=ATR_LENGTH).mean()
    sma = close.rolling(window=SMA_LENGTH, min_periods=SMA_LENGTH).mean()
    return close, atr, sma

'''

# BUG: after the trailing exit the entry test runs again on the same bar and immediately re-enters.
PRIOR_DEFECT = HEADER + '''
def generate_signals(df, disabled=frozenset()):
    close, atr, sma = _prep(df)
    signals = np.zeros(len(df))
    long_state, highest = False, np.nan
    for i in range(len(df)):
        c, s, a = close.iloc[i], sma.iloc[i], atr.iloc[i]
        if long_state:
            highest = c if np.isnan(highest) else max(highest, c)
            exit_sma = ("sma_exit" not in disabled) and (not np.isnan(s)) and c < s
            exit_trail = ("atr_trailing_exit" not in disabled) and (not np.isnan(a)) and c < highest - ATR_MULTIPLE * a
            if exit_sma or exit_trail:
                long_state, highest = False, np.nan
        if (not long_state) and (not np.isnan(s)) and (c > s or "sma_trend_entry" in disabled):
            long_state, highest = True, c
        signals[i] = 1.0 if long_state else 0.0
    return pd.Series(signals, index=df.index, dtype=float)
'''

# FIX: after a trailing exit the strategy stays flat until price has first closed back below the SMA.
FIXED = HEADER + '''
def generate_signals(df, disabled=frozenset()):
    close, atr, sma = _prep(df)
    signals = np.zeros(len(df))
    long_state, highest, locked = False, np.nan, False
    for i in range(len(df)):
        c, s, a = close.iloc[i], sma.iloc[i], atr.iloc[i]
        if locked and (not np.isnan(s)) and c < s:
            locked = False
        if long_state:
            highest = c if np.isnan(highest) else max(highest, c)
            exit_sma = ("sma_exit" not in disabled) and (not np.isnan(s)) and c < s
            exit_trail = ("atr_trailing_exit" not in disabled) and (not np.isnan(a)) and c < highest - ATR_MULTIPLE * a
            if exit_sma or exit_trail:
                long_state, highest = False, np.nan
                locked = exit_trail and not exit_sma
        if (not long_state) and (not locked) and (not np.isnan(s)) and (c > s or "sma_trend_entry" in disabled):
            long_state, highest = True, c
        signals[i] = 1.0 if long_state else 0.0
    return pd.Series(signals, index=df.index, dtype=float)
'''

# Declares a rule that the code never uses at all.
UNUSED_RULE = '''import pandas as pd

RULES = {"sma_entry": "close > SMA(20)", "volume_filter": "volume above its median"}


def generate_signals(df, disabled=frozenset()):
    sma = df["close"].rolling(20).mean()
    cond = (df["close"] > sma) if "sma_entry" not in disabled else (df["close"] > 0)
    return cond.fillna(False).astype(float)          # volume_filter is declared but never used
'''

# generate_signals without a `disabled` parameter.
NO_DISABLED_PARAM = '''import pandas as pd

RULES = {"sma_entry": "close > SMA(20)"}


def generate_signals(df):
    return (df["close"] > df["close"].rolling(20).mean()).fillna(False).astype(float)
'''

NO_RULES = '''import pandas as pd


def generate_signals(df, disabled=frozenset()):
    return (df["close"] > df["close"].rolling(20).mean()).fillna(False).astype(float)
'''

RAISES_WHEN_DISABLED = '''import pandas as pd

RULES = {"sma_entry": "close > SMA(20)"}


def generate_signals(df, disabled=frozenset()):
    if disabled:
        raise RuntimeError("not supported")
    return (df["close"] > df["close"].rolling(20).mean()).fillna(False).astype(float)
'''

# Good two-rule strategy: SMA entry/exit + a volume filter that really matters.
TWO_EFFECTIVE = '''import pandas as pd

RULES = {"sma_entry": "close > SMA(20)", "volume_filter": "volume above its trailing 20-bar median"}


def generate_signals(df, disabled=frozenset()):
    sma = df["close"].rolling(20).mean()
    cond = (df["close"] > sma) if "sma_entry" not in disabled else (df["close"] > 0)
    if "volume_filter" not in disabled:
        cond = cond & (df["volume"] > df["volume"].rolling(20).median())
    return cond.fillna(False).astype(float)
'''

# A rule with a tiny effect: holds one extra bar after the long run whose exit bar had the smallest absolute move.
WEAK_RULE = '''import numpy as np
import pandas as pd

RULES = {"sma_entry": "close > SMA(20)", "one_extra_bar": "stay long one more bar after one particular exit"}


def generate_signals(df, disabled=frozenset()):
    cond = (df["close"] > df["close"].rolling(20).mean()) if "sma_entry" not in disabled else (df["close"] > 0)
    sig = cond.fillna(False).astype(float)
    if "one_extra_bar" not in disabled:
        v = sig.values
        move = df["close"].pct_change().abs().values
        ends = [i for i in range(1, len(v) - 1) if v[i - 1] == 1 and v[i] == 0 and v[i + 1] == 0]
        if ends:
            k = min(ends, key=lambda i: move[i])
            sig.iloc[k] = 1.0
    return sig
'''

NONDETERMINISTIC = '''import numpy as np
import pandas as pd

RULES = {"coin": "random"}
_state = {"n": 0}


def generate_signals(df, disabled=frozenset()):
    _state["n"] += 1
    sig = (df["close"] > df["close"].rolling(20).mean()).fillna(False).astype(float)
    sig.iloc[100 + _state["n"]] = 1.0 - sig.iloc[100 + _state["n"]]
    return sig
'''


def make_df(n=1000, seed=7, crash_at=700, crash=-0.17):
    """Seeded uptrend with noise; one sharp -17% drop at `crash_at` that stays above the lagging SMA."""
    rng = np.random.RandomState(seed)
    r = 0.0035 + 0.012 * rng.randn(n)
    r[crash_at] = crash
    close = 100 * np.exp(np.cumsum(r))
    open_ = np.concatenate([[close[0]], close[:-1]]) * (1 + 0.002 * rng.randn(n))
    high = np.maximum(open_, close) * (1 + 0.004 * np.abs(rng.randn(n)))
    low = np.minimum(open_, close) * (1 - 0.004 * np.abs(rng.randn(n)))
    vol = 1000 + 300 * rng.rand(n) + 200 * rng.randn(n).clip(-1, 1)
    idx = pd.date_range("2020-01-01", periods=n, freq="D", tz="UTC")
    return pd.DataFrame({"open": open_, "high": high, "low": low, "close": close, "volume": vol}, index=idx)


def load_fn(src, tmp_path, name="strat"):
    import importlib.util
    p = tmp_path / (name + ".py")
    p.write_text(src)
    spec = importlib.util.spec_from_file_location(name, str(p))
    mod = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(mod)
    return mod
