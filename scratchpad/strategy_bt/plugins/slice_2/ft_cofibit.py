"""Archived spec ft_cofibit (freqtrade CofiBit): StochF + EMA5 + ADX mean-reversion long."""
import sys
from pathlib import Path
import numpy as np
sys.path.insert(0, str(Path(__file__).resolve().parent))
import s2_lib as L

SPEC_ID = "ft_cofibit"
PARAMS = {"buy_fastx": 25, "buy_adx": 25, "sell_fastx": 75}
PARAM_GRID = {"buy_fastx": [20, 25, 30], "buy_adx": [20, 25, 30]}
TIMEFRAMES = ["1h", "4h"]
SIDES = "long"
IMPLEMENTED_FIELDS = ["entry_long", "exit", "stop_loss", "take_profit", "filters", "timeframes"]
DEVIATIONS = [
    "Spec claims 5m; no 5m cache, so 1h and 4h are run instead (a different strategy regime than the published one).",
    "minimal_roi {0:10%,20m:7%,30m:6%,40m:5%} collapsed to a constant 5% take-profit (every bar after the entry bar is >= 40 min old at 1h/4h); the 10%/7%/6% early tiers and entry-bar behaviour cannot be modelled. Favourable to hit-rate.",
    "stoploss -25% implemented as stop_pct=0.25 (intrabar, harness stop rules).",
    "STOCHF(5,3,0,3,0): fastk=100*(C-LL5)/(HH5-LL5) (0 when range 0), fastd=SMA3(fastk). EMA5 of high/low are TA-Lib style (seeded with SMA). ADX = Wilder 14.",
    "crossed_above(x,L) read as x[t]>L and x[t-1]<=L. Entry uses the signal candle's own open vs EMA5(low) (candle just closed), next-open fill. 'fastk crosses above fastd' same convention.",
    "Exit signals (open>=EMA5(high), fastk/fastd crossing above sell_fastx) are executed on next open (harness), freqtrade would do the same on the next candle.",
]

def signals(df, buy_fastx=25, buy_adx=25, sell_fastx=75):
    o = df.open.to_numpy(float); h = df.high.to_numpy(float); l = df.low.to_numpy(float); c = df.close.to_numpy(float)
    import pandas as pd
    hh = pd.Series(h).rolling(5, min_periods=5).max().to_numpy(); ll = pd.Series(l).rolling(5, min_periods=5).min().to_numpy()
    with np.errstate(divide="ignore", invalid="ignore"):
        k = np.where(hh > ll, 100 * (c - ll) / (hh - ll), 0.0)
    k = np.where(np.isfinite(hh), k, np.nan); d = pd.Series(k).rolling(3, min_periods=3).mean().to_numpy()
    ema_l = L.ema_ta(l, 5); ema_h = L.ema_ta(h, 5); adx = L.adx_wilder(h, l, c, 14)
    with np.errstate(invalid="ignore"):
        entry = (o < ema_l) & L.crossed_above(k, d) & (k < buy_fastx) & (d < buy_fastx) & (adx > buy_adx)
        ex = (o >= ema_h) | L.crossed_above(k, sell_fastx) | L.crossed_above(d, sell_fastx)
    n = len(c)
    return L.frame(df, le=entry, lx=ex, stop_pct=np.full(n, 0.25), tp_pct=np.full(n, 0.05))
