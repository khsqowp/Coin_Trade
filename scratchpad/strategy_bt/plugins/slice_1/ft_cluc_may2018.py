"""Freqtrade ClucMay72018: oversold below lower Bollinger band, exit above mid band, 1% ROI, -5% stop."""
import numpy as np
import pandas as pd

def _ema(x, n):
    """EMA seeded at first value (same convention as common.indicators.ema)."""
    return pd.Series(np.asarray(x, float)).ewm(span=int(n), adjust=False).mean().to_numpy()

def _frame(df, le, se, lx, sx, **extra):
    out = pd.DataFrame({"long_entry": np.asarray(le, bool), "short_entry": np.asarray(se, bool),
                        "long_exit": np.asarray(lx, bool), "short_exit": np.asarray(sx, bool)}, index=df.index)
    for k, v in extra.items():
        out[k] = np.asarray(v, float)
    return out

SPEC_ID = "ft_cluc_may2018"
PARAMS = {"ema_len": 50, "band_factor": 0.985}
PARAM_GRID = {"ema_len": [40, 50, 60], "band_factor": [0.98, 0.985, 0.99]}
TIMEFRAMES = ["1h", "4h"]
SIDES = "long"
IMPLEMENTED_FIELDS = ["entry_long", "entry_short", "exit", "stop_loss", "take_profit", "position_sizing", "filters", "timeframes"]
DEVIATIONS = [
    "Claimed timeframe is 5m, which is not cached: run on 1h and 4h (a 5m-designed strategy on much slower bars; results are not a test of the 5m claim).",
    "Bollinger bands follow the cited source (ClucMay72018.py): window 20, 2 std (pandas ddof=1, as qtpylib) on TYPICAL PRICE (hlc3), not close. Entry: close < EMA(close, ema_len) and close < band_factor*lower and volume < 20*rolling_mean(volume,30).shift(1). Exit: close > middle band. RSI/MACD/ADX columns in the source are unused.",
    "Freqtrade minimal_roi {0: 1%} = take profit +1% (tp_pct=0.01, checked by harness against bar high from the entry bar); stoploss -5% (stop_pct=0.05). Freqtrade ROI/stop fill-price conventions differ slightly from the harness. Long-only.",
]

def signals(df, ema_len=50, band_factor=0.985):
    h = df.high.to_numpy(float); l = df.low.to_numpy(float); c = df.close.to_numpy(float); v = df.volume.to_numpy(float); n = len(c)
    tp = pd.Series((h + l + c) / 3.0)
    mid = tp.rolling(20, min_periods=20).mean(); sd = tp.rolling(20, min_periods=20).std(ddof=1)
    mid = mid.to_numpy(); lower = (mid - 2 * sd.to_numpy())
    vmean = pd.Series(v).rolling(30, min_periods=30).mean().shift(1).to_numpy()
    le = (c < _ema(c, ema_len)) & (c < float(band_factor) * lower) & (v < vmean * 20)
    le &= np.arange(n) >= max(int(ema_len), 30)
    lx = c > mid
    z = np.zeros(n, bool)
    return _frame(df, le, z, lx, z, stop_pct=np.full(n, 0.05), tp_pct=np.full(n, 0.01))
