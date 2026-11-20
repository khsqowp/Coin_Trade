"""Long-only Turtle System 1 approximation with hourly execution."""
from pathlib import Path

import numpy as np
import pandas as pd

SPEC_ID = "c5-turtle-crypto-20-10-donchian-2n-stop"
PARAMS = {"entry_days": 20, "exit_days": 10, "n_days": 20, "stop_n": 2.0}
PARAM_GRID = {
    "entry_days": [18, 20, 22],
    "exit_days": [9, 10, 11],
    "stop_n": [1.8, 2.0, 2.2],
}
TIMEFRAMES = ["1h"]
SIDES = "long"
DEVIATIONS = [
    "The archived BTCUSDT/ETHUSDT restriction is generalized to the harness crypto-major universe; instrument selection cannot be expressed per plugin.",
    "The harness timestamp reset is handled by restoring UTC timestamps from the cached BTCUSDT 1h index by full/train/test slice length. Only timestamps are read; actual hourly OHLC comes from the supplied frame. The TEST slice starts cold without preceding daily bars.",
    "UTC daily OHLC is aggregated from the supplied hourly OHLC bars. Daily highs/lows and Wilder N are shifted one full UTC day before hourly use, so a partial current day never contributes to its own levels. Missing hourly bars are not repaired.",
    "The specification's average(open, close) entry fill cannot be represented: the harness fills at the next hourly open after a close-known signal. Entry signal is emitted when hourly close exceeds the prior-day 20-day upper bound.",
    "The 2N stop is emitted as atr_stop on every hourly bar, so the harness captures the signal bar's 2N distance when the next-open entry fills and holds that fixed distance for the position. The engine checks the stop intrabar; the lower-channel exit is a close signal filled at the following open.",
    "The archive's all-capital sizing and 0.1% per-side fee are replaced by the harness fixed-notional sizing and configured fees/slippage. No pyramiding, take profit, or short side is implemented.",
]
IMPLEMENTED_FIELDS = ["entry_long", "exit", "stop_loss", "filters", "timeframes"]


def _utc_index(df):
    """Restore UTC bar-open timestamps for RangeIndex train/test slices."""
    idx = df.index
    if isinstance(idx, pd.DatetimeIndex):
        return idx.tz_localize("UTC") if idx.tz is None else idx.tz_convert("UTC")
    here = Path(__file__).resolve()
    data = next((base / "bb_stoch_stc" / "data" for base in here.parents
                 if (base / "bb_stoch_stc" / "data").is_dir()), None)
    if data is None:
        raise RuntimeError("cached bb_stoch_stc/data not found for timestamp restoration")
    ref = pd.read_parquet(data / "BTCUSDT_1h.parquet", columns=["close"]).index
    train_len = int(len(ref) * 0.6)
    for size, part in ((len(ref), ref), (train_len, ref[:train_len]),
                       (len(ref) - train_len, ref[train_len:])):
        if len(df) == size:
            return pd.DatetimeIndex(part).tz_localize("UTC") if part.tz is None else pd.DatetimeIndex(part).tz_convert("UTC")
    raise ValueError("UTC index removed and slice length matches no cached 1h split")


def _wilder(values, period):
    out = np.full(len(values), np.nan, dtype=float)
    if len(values) < period:
        return out
    out[period - 1] = np.mean(values[:period])
    for i in range(period, len(values)):
        out[i] = ((period - 1) * out[i - 1] + values[i]) / period
    return out


def signals(df, entry_days=20, exit_days=10, n_days=20, stop_n=2.0):
    n = len(df)
    out = pd.DataFrame({
        "long_entry": np.zeros(n, dtype=bool),
        "short_entry": np.zeros(n, dtype=bool),
        "long_exit": np.zeros(n, dtype=bool),
        "short_exit": np.zeros(n, dtype=bool),
        "atr_stop": np.full(n, np.nan),
    }, index=df.index)
    if n == 0:
        return out

    idx = _utc_index(df)
    hourly = pd.DataFrame({
        "high": df["high"].to_numpy(float),
        "low": df["low"].to_numpy(float),
        "close": df["close"].to_numpy(float),
    }, index=idx)
    daily = hourly.resample("1D", origin="start_day", label="left", closed="left").agg(
        high=("high", "max"), low=("low", "min"), close=("close", "last")
    ).dropna(subset=["high", "low", "close"])
    prev_close = daily["close"].shift(1)
    tr = pd.concat([
        daily["high"] - daily["low"],
        (daily["high"] - prev_close).abs(),
        (daily["low"] - prev_close).abs(),
    ], axis=1).max(axis=1).to_numpy(float)
    daily["upper"] = daily["high"].rolling(int(entry_days), min_periods=int(entry_days)).max().shift(1)
    daily["lower"] = daily["low"].rolling(int(exit_days), min_periods=int(exit_days)).min().shift(1)
    daily["n"] = pd.Series(_wilder(tr, int(n_days)), index=daily.index).shift(1)

    days = idx.normalize()
    aligned = daily.reindex(days)
    upper = aligned["upper"].to_numpy(float)
    lower = aligned["lower"].to_numpy(float)
    n_value = aligned["n"].to_numpy(float)
    close = df["close"].to_numpy(float)
    out["long_entry"] = np.isfinite(upper) & (close > upper)
    out["long_exit"] = np.isfinite(lower) & (close < lower)
    out["atr_stop"] = float(stop_n) * n_value
    return out
