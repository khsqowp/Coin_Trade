"""Daily Wilder RSI threshold re-entry with a fixed holding horizon."""
import numpy as np
import pandas as pd

SPEC_ID = "rsi7-30-70-fixed20"
PARAMS = {"period": 7, "os": 30, "hold": 20}
PARAM_GRID = {"period": [5, 7, 9], "os": [25, 30, 35], "hold": [15, 20, 25]}
TIMEFRAMES = ["1d"]
SIDES = "both"
DEVIATIONS = [
    "The short threshold is mirrored as 100 minus the oversold threshold.",
    "The engine's max_hold counts bars from entry open through the close of entry_bar+H; hold-1 yields exactly H sessions, closing at the 20th session close.",
    "Recross requires strict prior-side comparison (below/above) and inclusive current threshold crossing.",
    "Signals execute at the next open under the harness.",
    "Opposite signals while a position is open are ignored by the single-position engine.",
]
IMPLEMENTED_FIELDS = ["entry_long", "entry_short", "exit", "filters", "timeframes"]


def _wilder_rsi(close, period):
    close = np.asarray(close, dtype=float)
    out = np.full(len(close), np.nan)
    changes = np.diff(close)
    gains = np.maximum(changes, 0.0)
    losses = np.maximum(-changes, 0.0)
    p = int(period)
    if len(changes) < p:
        return out
    avg_gain = np.mean(gains[:p])
    avg_loss = np.mean(losses[:p])
    def value(g, l):
        if l == 0:
            return 100.0 if g > 0 else 50.0
        if g == 0:
            return 0.0
        return 100.0 - 100.0 / (1.0 + g / l)
    out[p] = value(avg_gain, avg_loss)
    for i in range(p + 1, len(close)):
        g, l = gains[i - 1], losses[i - 1]
        avg_gain = (avg_gain * (p - 1) + g) / p
        avg_loss = (avg_loss * (p - 1) + l) / p
        out[i] = value(avg_gain, avg_loss)
    return out


def signals(df, period=7, os=30, hold=20):
    close = pd.to_numeric(df["close"], errors="coerce").to_numpy(float)
    rsi = pd.Series(_wilder_rsi(close, int(period)), index=df.index)
    ob = 100.0 - float(os)
    long_entry = (rsi.shift(1) < float(os)) & (rsi >= float(os))
    short_entry = (rsi.shift(1) > ob) & (rsi <= ob)
    n = len(df)
    return pd.DataFrame({
        "long_entry": long_entry,
        "short_entry": short_entry,
        "long_exit": False,
        "short_exit": False,
        "max_hold": np.full(n, max(0, int(hold) - 1), dtype=float),
    }, index=df.index).fillna(False).pipe(_bool_signals)


def _bool_signals(frame):
    for name in ("long_entry", "short_entry", "long_exit", "short_exit"):
        frame[name] = frame[name].astype(bool)
    return frame
