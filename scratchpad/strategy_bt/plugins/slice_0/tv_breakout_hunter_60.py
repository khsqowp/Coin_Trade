"""Donchian breakout implementation for the lossy archived summary."""
import numpy as np
import pandas as pd

SPEC_ID = "tv_breakout_hunter_60"
PARAMS = {"entry_n": 60, "exit_n": 30, "trend_n": 400, "body_min": 0.60, "vol_mult": 2.0, "vol_n": 40, "stop_n": 5}
PARAM_GRID = {"entry_n": [50, 60, 70], "vol_mult": [1.5, 2.0, 2.5], "body_min": [0.5, 0.6, 0.7]}
TIMEFRAMES = ["1h", "4h"]
SIDES = "both"
DEVIATIONS = [
    "The archived TradingView extraction is lossy; this implementation follows the supplied mechanical summary and its explicit assumptions.",
    "Both long and short are enabled because the summary specifies mirrored entries.",
    "Body direction is not required; only absolute body as a fraction of range is tested.",
    "The 30-bar exit is a close-based channel break against the prior bars.",
    "Zero-range candles produce an undefined body ratio and cannot enter.",
    "The stop uses the last stop_n bars including the signal bar and converts distance to a fraction of signal close, approximating next-open entry.",
    "The inDate filter and archived 1% equity-risk sizing are unavailable and not implemented.",
]
IMPLEMENTED_FIELDS = ["entry_long", "entry_short", "exit", "stop_loss", "filters", "timeframes"]


def prior_channel(high, low, period):
    hi = pd.Series(np.asarray(high, float)).rolling(int(period), min_periods=int(period)).max().shift(1).to_numpy()
    lo = pd.Series(np.asarray(low, float)).rolling(int(period), min_periods=int(period)).min().shift(1).to_numpy()
    return hi, lo


def body_fraction(open_, high, low, close):
    o, h, l, c = (np.asarray(x, float) for x in (open_, high, low, close))
    span = h - l
    return np.divide(np.abs(c-o), span, out=np.full(len(c), np.nan), where=span != 0)


def signals(df, entry_n=60, exit_n=30, trend_n=400, body_min=0.60, vol_mult=2.0, vol_n=40, stop_n=5):
    o, h, l, c, v = (df[k].to_numpy(float) for k in ("open", "high", "low", "close", "volume"))
    entry_hi, entry_lo = prior_channel(h, l, entry_n)
    exit_hi, exit_lo = prior_channel(h, l, exit_n)
    trend_hi = pd.Series(h, index=df.index).rolling(int(trend_n), min_periods=int(trend_n)).max()
    trend_lo = pd.Series(l, index=df.index).rolling(int(trend_n), min_periods=int(trend_n)).min()
    trend_mid = ((trend_hi + trend_lo) / 2).to_numpy()
    avg_vol_prev = pd.Series(v, index=df.index).rolling(int(vol_n), min_periods=int(vol_n)).mean().shift(1).to_numpy()
    body = body_fraction(o, h, l, c)
    body_ok = body >= body_min; volume_ok = v >= vol_mult * avg_vol_prev
    long_entry = (c > entry_hi) & body_ok & volume_ok & (c > trend_mid)
    short_entry = (c < entry_lo) & body_ok & volume_ok & (c < trend_mid)
    long_exit = c < exit_lo; short_exit = c > exit_hi
    stop_low = pd.Series(l, index=df.index).rolling(int(stop_n), min_periods=int(stop_n)).min().to_numpy()
    stop_high = pd.Series(h, index=df.index).rolling(int(stop_n), min_periods=int(stop_n)).max().to_numpy()
    long_distance = np.divide(c-stop_low, c, out=np.full(len(c), np.nan), where=c != 0)
    short_distance = np.divide(stop_high-c, c, out=np.full(len(c), np.nan), where=c != 0)
    stop_pct = np.where(long_entry, long_distance, np.where(short_entry, short_distance, np.nan))
    return pd.DataFrame({"long_entry": long_entry, "short_entry": short_entry, "long_exit": long_exit,
                         "short_exit": short_exit, "stop_pct": stop_pct}, index=df.index)
