"""Deterministic, price-only regime classifier (NO LLM, causal). Used (a) as the backtestable proxy of "adaptive selection value",
(b) by the scheduler's carry gate, (c) as the no-AI baseline that any LLM regime judgement must beat in forward records.

Labels: trend_up | trend_down | range | high_vol.  Inputs: OHLC of one symbol on one timeframe.
  efficiency ratio ER(n)   = |c_t - c_{t-n}| / sum(|dc|)  (trend cleanliness, 0..1)
  trend sign               = sign(EMA(fast) - EMA(slow)) and close vs EMA(slow)
  vol percentile           = rank of ATR%(14) within the trailing `vol_win` bars
high_vol overrides when vol percentile >= 0.90 (then direction is reported separately by `direction`)."""
import numpy as np
import pandas as pd

from . import ind

LABELS = ("trend_up", "trend_down", "range", "high_vol")


def classify_series(df, fast=20, slow=50, er_n=30, vol_win=250, er_thr=0.30, vol_q=0.90):
    c = df["close"]
    ef, es = ind.ema(c, fast), ind.ema(c, slow)
    er = (c - c.shift(er_n)).abs() / c.diff().abs().rolling(er_n, min_periods=er_n).sum()
    atrp = ind.atr(df, 14) / c
    volrank = atrp.rolling(vol_win, min_periods=vol_win // 2).apply(lambda x: (x[:-1] < x[-1]).mean(), raw=True)
    lab = pd.Series("range", index=df.index, dtype=object)
    up = (ef > es) & (c > es) & (er > er_thr)
    dn = (ef < es) & (c < es) & (er > er_thr)
    lab[up] = "trend_up"
    lab[dn] = "trend_down"
    lab[volrank >= vol_q] = "high_vol"
    lab[es.isna() | er.isna() | volrank.isna()] = "unknown"
    return lab


def classify_last(df, **kw):
    s = classify_series(df, **kw)
    return str(s.iloc[-1]) if len(s) else "unknown"
