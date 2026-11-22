"""Literal BbandRsi implementation for the shared research harness."""
import numpy as np
import pandas as pd

SPEC_ID = "ft_bband_rsi"
PARAMS = {"rsi_buy": 30, "rsi_sell": 70}
PARAM_GRID = {"rsi_buy": [25, 30, 35], "rsi_sell": [65, 70, 75]}
TIMEFRAMES = ["1h"]
SIDES = "long"
DEVIATIONS = [
    "The archived phrase 'weighted typical price' is ambiguous; Bollinger bands use the plain typical price (high+low+close)/3.",
    "The stated ROI {0: 10%} is represented as a fixed 10% target because the harness supports a per-trade tp_pct, not time-dependent ROI tiers.",
    "RSI uses an SMA seed followed by Wilder smoothing as specified by the task.",
]
IMPLEMENTED_FIELDS = ["entry_long", "exit", "stop_loss", "take_profit", "timeframes"]


def rsi_wilder(close, period=14):
    close = np.asarray(close, dtype=float)
    out = np.full(len(close), np.nan)
    if len(close) <= period:
        return out
    delta = np.diff(close)
    gains = np.maximum(delta, 0.0)
    losses = np.maximum(-delta, 0.0)
    avg_gain = float(np.mean(gains[:period]))
    avg_loss = float(np.mean(losses[:period]))
    out[period] = 100.0 if avg_loss == 0 and avg_gain > 0 else (0.0 if avg_gain == 0 else 100 - 100 / (1 + avg_gain / avg_loss))
    for i in range(period + 1, len(close)):
        g, loss = gains[i - 1], losses[i - 1]
        avg_gain = (avg_gain * (period - 1) + g) / period
        avg_loss = (avg_loss * (period - 1) + loss) / period
        out[i] = 100.0 if avg_loss == 0 and avg_gain > 0 else (0.0 if avg_gain == 0 else 100 - 100 / (1 + avg_gain / avg_loss))
    return out


def signals(df, rsi_buy=30, rsi_sell=70):
    close = df["close"].to_numpy(float)
    typical = (df["high"].to_numpy(float) + df["low"].to_numpy(float) + close) / 3.0
    rsi = rsi_wilder(close, 14)
    lower = pd.Series(typical, index=df.index).rolling(20, min_periods=20).mean() - 2 * pd.Series(typical, index=df.index).rolling(20, min_periods=20).std(ddof=1)
    entry = (rsi < rsi_buy) & (close < lower.to_numpy())
    exit_ = rsi > rsi_sell
    return pd.DataFrame({"long_entry": entry, "short_entry": np.zeros(len(df), dtype=bool), "long_exit": exit_, "short_exit": np.zeros(len(df), dtype=bool),
                         "stop_pct": np.full(len(df), 0.25), "tp_pct": np.full(len(df), 0.10)}, index=df.index)
