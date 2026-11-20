"""Upbit-style daily volatility breakout evaluated on hourly bars."""
from pathlib import Path
import numpy as np
import pandas as pd

SPEC_ID = "c5-upbit-noise-k20-ma5-same-day-close"
PARAMS = {"noise_len": 20, "ma_len": 5}
PARAM_GRID = {}
TIMEFRAMES = ["1h"]
SIDES = "long"
DEVIATIONS = [
    "The daily strategy is evaluated on hourly bars because daily OHLC cannot identify an intraday trigger followed by a same-day close; the cached 1h stream is aggregated into UTC days.",
    "K is the mean noise ratio of the 20 completed prior UTC days, avoiding use of the unfinished current day's noise.",
    "A breakout is the first hourly bar whose high touches the threshold after the preceding close was below it; entry fills at the following hourly open.",
    "The prior-close SMA filter uses the five completed daily closes ending yesterday.",
    "Harness max_hold exits at a later hourly close, so it approximates the source same-day close with up to one-hour delay; UTC timestamps are restored for RangeIndex train/test slices from the cached BTCUSDT 1h reference index.",
    "Harness universe replaces the Upbit market selection."
]
IMPLEMENTED_FIELDS = ["entry_long", "exit", "filters", "timeframes"]


def _utc_index(df):
    idx = df.index
    if isinstance(idx, pd.DatetimeIndex):
        return idx.tz_localize("UTC") if idx.tz is None else idx.tz_convert("UTC")
    data = Path(__file__).resolve().parents[3] / "bb_stoch_stc" / "data"
    if not data.is_dir():
        data = Path(__file__).resolve().parents[4] / "bb_stoch_stc" / "data"
    ref = pd.read_parquet(data / "BTCUSDT_1h.parquet", columns=["close"]).index
    full = len(ref)
    split = int(full * 0.6)
    for size, part in ((full, ref), (split, ref[:split]), (full - split, ref[split:])):
        if len(df) == size:
            return pd.DatetimeIndex(part)
    raise ValueError("RangeIndex length does not match cached 1h full/train/test index")


def signals(df, noise_len=20, ma_len=5, **_):
    idx = _utc_index(df)
    day = idx.normalize()
    bars = pd.DataFrame({k: df[k].to_numpy(float) for k in ("open", "high", "low", "close")}, index=idx)
    daily = bars.groupby(day).agg(open=("open", "first"), high=("high", "max"), low=("low", "min"), close=("close", "last"))
    width = daily.high - daily.low
    noise = 1.0 - (daily.close - daily.open).abs() / width.replace(0, np.nan)
    kval = noise.rolling(int(noise_len), min_periods=int(noise_len)).mean().shift(1)
    prior_close = daily.close.shift(1)
    prior_ma = daily.close.rolling(int(ma_len), min_periods=int(ma_len)).mean().shift(1)
    trigger = daily.open + kval * width.shift(1)
    eligible = (prior_close > prior_ma) & trigger.notna()
    t = trigger.reindex(day).to_numpy(float)
    ok = eligible.reindex(day).fillna(False).to_numpy(bool)
    c = df.close.to_numpy(float)
    o = df.open.to_numpy(float)
    h = df.high.to_numpy(float)
    prevc = np.r_[np.nan, c[:-1]]
    touched = ok & (h >= t) & ((prevc < t) | (o >= t))
    touched_s = pd.Series(touched, index=idx)
    first = touched_s & touched_s.groupby(day).cumsum().eq(1)
    entry = first.to_numpy(dtype=bool).copy()
    exits = np.zeros(len(df), dtype=bool)
    max_hold = np.zeros(len(df), dtype=int)
    # Hourly bar i fills at i+1; max_hold ends at the UTC day boundary by clock time.
    # A signal on the 23:00 bar cannot enter and close within the same day.
    for i in np.flatnonzero(entry):
        fill_hour = int(idx[i].hour) + 1
        if fill_hour >= 24:
            entry[i] = False
        else:
            max_hold[i] = max(1, 23 - fill_hour)
    return pd.DataFrame({"long_entry": entry, "short_entry": False, "long_exit": exits, "short_exit": False,
                         "max_hold": max_hold}, index=df.index).fillna(False)
