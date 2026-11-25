#!/usr/bin/env python3
"""EXPLORATORY SCREEN ONLY -- not part of the 13-round preregistered G-gate track,
not added to TRAIN_TRIALS.csv, no promotion without separate formal preregistration
+ synthetic tests + resource-gated TRAIN run.

Lane G (EXPLORE1000): multi-timeframe alignment / divergence strategies, OB-free.

Writes into this directory: IDEAS.csv, RESULTS.csv, RANKED_TOP20.md.
Reads only: data_access.iter_train_bars("15m" | "1h" | "4h") (TRAIN window, cutoff-safe).
The 1d timeframe is derived from COMPLETE 4h bars (exactly 6 per UTC day).

Conventions (shared by every idea):
  * Timeframes: trigger tf in {15m, 1h}; higher tfs in {1h, 4h, 1d}.
  * Causality: a bar of timeframe X is usable only at its CLOSE time
    (avail = open_time + tf_ms). For a trigger bar i (decision at its close T_i),
    higher-tf features come from the last higher-tf bar with avail <= T_i
    (np.searchsorted side="right"). Lower-tf bars are never used for higher-tf decisions.
    All rolling/ewm features are trailing (causal); prior-N high/low use shift(1).
  * Entry = OPEN of trigger bar i+1. Hold H trigger bars: exit at CLOSE of bar i+H,
    unless an ATR stop (k * ATR14 of trigger bar i, measured at decision time) is hit
    first. Stop fills use the worse of stop level and bar open (gap-through).
  * One position per symbol at a time (signals while in a trade are skipped).
  * Cost: 12bp round trip per trade (net bps = gross - 12).
  * Metrics pooled across symbols: n, win_rate, profit_factor, expectancy_bps (EV),
    rough_sharpe = EV/sd of per-trade returns, halves sign agreement (entry-time
    median split of TRAIN).
  * composite_score = EV * ln(1+n) * min(1, n/30) * min(1, PF)   (same formula as the
    EXPLORE500 A lane for internal consistency; NOT comparable across lanes because
    exit rules differ). Ideas with n < 30 get no composite ("INSUFFICIENT_TRADES").
  * Causality self-check: for one symbol, every idea's signal array is recomputed on
    data truncated at ~70% of the series; signals on the common prefix must match
    exactly. Results go in RESULTS.csv column causal_check.
  * No walk-forward, no multiple-testing correction, not G-eligible.
"""
from __future__ import annotations

import csv
import json
import math
import sys
from pathlib import Path

import numpy as np
import pandas as pd

HERE = Path(__file__).resolve().parent
sys.path.insert(0, str(HERE.parent))  # orderblock_loop (data_access / crypto)
import data_access  # noqa: E402  read-only, cutoff-safe loader

LABEL = ("EXPLORATORY SCREEN ONLY -- not part of the 13-round preregistered G-gate track, "
         "not added to TRAIN_TRIALS.csv, no promotion without separate formal preregistration "
         "+ synthetic tests + resource-gated TRAIN run.")
COST_BPS = 12.0
MIN_TRADES = 30
TF_MS = {"5m": 300_000, "15m": 900_000, "1h": 3_600_000, "4h": 14_400_000, "1d": 86_400_000}
LOAD_TFS = ["15m", "1h", "4h"]
ALL_TFS = ["15m", "1h", "4h", "1d"]
TF_ALIAS = {"1h+4h": ["1h", "4h"], "1h+4h+1d": ["1h", "4h", "1d"]}


# ============================================================ data
def load_tf(tf: str) -> dict:
    out = {}
    for sym, bars, _funding in data_access.iter_train_bars(tf):
        bars = [b for b in bars if b.complete]
        if not bars:
            continue
        df = pd.DataFrame({
            "t": [b.timestamp for b in bars], "o": [b.open for b in bars],
            "h": [b.high for b in bars], "l": [b.low for b in bars],
            "c": [b.close for b in bars], "v": [b.volume for b in bars],
        })
        out[sym] = df.sort_values("t").drop_duplicates("t").reset_index(drop=True)
    return out


def derive_1d(df4: pd.DataFrame) -> pd.DataFrame:
    """Daily bars from complete 4h bars only (exactly 6 contiguous 4h bars per UTC day)."""
    day = (df4["t"] // TF_MS["1d"]) * TF_MS["1d"]
    g = df4.assign(day=day).groupby("day")
    d = pd.DataFrame({
        "t": g["t"].min(), "tmax": g["t"].max(), "n": g.size(),
        "o": g["o"].first(), "h": g["h"].max(), "l": g["l"].min(),
        "c": g["c"].last(), "v": g["v"].sum(),
    })
    ok = (d["n"] == 6) & (d["tmax"] - d["t"] == 5 * TF_MS["4h"])
    return d.loc[ok, ["t", "o", "h", "l", "c", "v"]].reset_index(drop=True)


# ============================================================ features (causal)
def ema(s: pd.Series, n: int) -> pd.Series:
    return s.ewm(span=n, adjust=False).mean()


def feats(d: pd.DataFrame) -> pd.DataFrame:
    c, h, l, o = d["c"], d["h"], d["l"], d["o"]
    f = pd.DataFrame({"t": d["t"].values, "o": o.values, "h": h.values, "l": l.values,
                      "c": c.values, "v": d["v"].values})
    for n in (9, 20, 21, 50, 100):
        f[f"ema{n}"] = ema(c, n).values
    pc = c.shift(1)
    tr = pd.concat([h - l, (h - pc).abs(), (l - pc).abs()], axis=1).max(axis=1)
    atr = tr.rolling(14).mean()
    f["atr14"] = atr.values
    diff = c.diff()
    up = diff.clip(lower=0).ewm(alpha=1 / 14, adjust=False).mean()
    dn = (-diff.clip(upper=0)).ewm(alpha=1 / 14, adjust=False).mean()
    f["rsi14"] = (100 - 100 / (1 + up / dn)).values
    for fast, slow in ((12, 26), (8, 21)):
        m = ema(c, fast) - ema(c, slow)
        f[f"macdh_{fast}_{slow}"] = (m - ema(m, 9)).values
    hh, ll = h.rolling(14).max(), l.rolling(14).min()
    f["stoch14"] = (100 * (c - ll) / (hh - ll)).values
    mid, sd = c.rolling(20).mean(), c.rolling(20).std()
    f["bb_up"] = (mid + 2 * sd).values
    f["bb_lo"] = (mid - 2 * sd).values
    for N in (3, 6, 10, 20, 40, 80):
        f[f"dh{N}"] = h.rolling(N).max().shift(1).values
        f[f"dl{N}"] = l.rolling(N).min().shift(1).values
    for L in (1, 3, 6, 7, 18, 24, 42, 72, 168):
        f[f"mom{L}"] = (c / c.shift(L) - 1).values
    f["atrpct100"] = atr.rolling(100).rank(pct=True).values
    return f


def build_frames(raw: dict, sym: str, cut_t: int | None = None) -> dict | None:
    """feats per tf for one symbol. If cut_t is given, rows are truncated to
    bars available at cut_t (used only by the causality self-check)."""
    frames = {}
    for tf in LOAD_TFS:
        if sym not in raw[tf]:
            return None
        df = raw[tf][sym]
        if cut_t is not None:
            df = df[df["t"] + TF_MS[tf] <= cut_t].reset_index(drop=True)
        frames[tf] = df
    frames["1d"] = derive_1d(frames["4h"])
    out = {}
    for tf in ALL_TFS:
        if len(frames[tf]) < 300:
            return None
        out[tf] = feats(frames[tf])
    return out


def context(frames: dict, trig: str) -> dict:
    """Map every higher-tf feature onto the trigger-tf bar grid (close-time causal)."""
    T = frames[trig]
    avail = T["t"].values + TF_MS[trig]
    M = {(trig, col): T[col].values.astype(float) for col in T.columns}
    for tf in ALL_TFS:
        if TF_MS[tf] <= TF_MS[trig]:
            continue
        H = frames[tf]
        hav = H["t"].values + TF_MS[tf]  # sorted ascending
        idx = np.searchsorted(hav, avail, side="right") - 1
        ok = idx >= 0
        idxc = np.clip(idx, 0, None)
        for col in H.columns:
            if col == "t":
                continue
            arr = H[col].values[idxc].astype(float)
            arr[~ok] = np.nan
            M[(tf, col)] = arr
    return M


# ============================================================ signal helpers
def S(M, tf, col):
    return pd.Series(M[(tf, col)])


def signs(long_, short_) -> np.ndarray:
    lo = np.asarray(long_.fillna(False), dtype=bool)
    sh = np.asarray(short_.fillna(False), dtype=bool)
    out = np.zeros(len(lo), dtype=np.int8)
    out[lo & ~sh] = 1
    out[sh & ~lo] = -1
    return out


def edge(b: pd.Series) -> pd.Series:
    return b & ~b.shift(1, fill_value=False).astype(bool)


# ============================================================ signal families
def sig_F1(M, trig, p):  # 1h: HTF trend + 1h EMA20 reclaim after recent pullback
    htf = p["htf"]
    fa, fb = (int(x) for x in p["pair"].split("_"))
    c, e = S(M, trig, "c"), S(M, trig, "ema20")
    up = S(M, htf, f"ema{fa}") > S(M, htf, f"ema{fb}")
    dn = S(M, htf, f"ema{fa}") < S(M, htf, f"ema{fb}")
    was_below = (c.shift(1) < e.shift(1)) | (c.shift(2) < e.shift(2)) | (c.shift(3) < e.shift(3))
    was_above = (c.shift(1) > e.shift(1)) | (c.shift(2) > e.shift(2)) | (c.shift(3) > e.shift(3))
    return signs(up & was_below & (c > e), dn & was_above & (c < e))


def sig_F2(M, trig, p):  # 15m: HTF trend + 15m Donchian breakout in that direction
    htf, N = p["htf"], p["N"]
    c = S(M, trig, "c")
    up = S(M, htf, "ema20") > S(M, htf, "ema50")
    dn = S(M, htf, "ema20") < S(M, htf, "ema50")
    return signs(up & (c > S(M, trig, f"dh{N}")), dn & (c < S(M, trig, f"dl{N}")))


def sig_F3(M, trig, p):  # 1h: multi-tf momentum alignment (edge trigger)
    tfs = TF_ALIAS[p["align"]]
    L = {"short": {"1h": 24, "4h": 6, "1d": 1},
         "mid": {"1h": 72, "4h": 18, "1d": 3},
         "long": {"1h": 168, "4h": 42, "1d": 7}}[p["scale"]]
    up = pd.Series(True, index=range(len(S(M, trig, "c"))))
    dn = up.copy()
    for tf in tfs:
        m = S(M, tf, f"mom{L[tf]}")
        up &= m > 0
        dn &= m < 0
    return signs(edge(up), edge(dn))


def sig_F4(M, trig, p):  # 1h: lower-tf overextension AGAINST HTF trend (fade into trend)
    htf, zth = p["htf"], p["zth"]
    c, e, a = S(M, trig, "c"), S(M, trig, "ema20"), S(M, trig, "atr14")
    z = (c - e) / a
    up = S(M, htf, "ema20") > S(M, htf, "ema50")
    dn = S(M, htf, "ema20") < S(M, htf, "ema50")
    return signs(up & (z < -zth), dn & (z > zth))


def sig_F5(M, trig, p):  # 1h: HTF prior-N high/low as zone; test + reclaim in HTF trend
    lev, N, band = p["lev"], p["N"], p["band"]
    l, h, c = S(M, trig, "l"), S(M, trig, "h"), S(M, trig, "c")
    up = S(M, lev, "ema20") > S(M, lev, "ema50")
    dn = S(M, lev, "ema20") < S(M, lev, "ema50")
    sup, res = S(M, lev, f"dl{N}"), S(M, lev, f"dh{N}")
    return signs(up & (l <= sup * (1 + band)) & (c > sup),
                 dn & (h >= res * (1 - band)) & (c < res))


def sig_F6(M, trig, p):  # 1h: multi-tf RSI alignment + 1h RSI cross
    tfs = TF_ALIAS[p["combo"]][1:]  # higher tfs only
    thr = p["thr"]
    r = S(M, trig, "rsi14")
    up = pd.Series(True, index=range(len(r)))
    dn = up.copy()
    for tf in tfs:
        rh = S(M, tf, "rsi14")
        up &= rh > thr
        dn &= rh < 100 - thr
    cross_up = (r > 45) & (r.shift(1) <= 45)
    cross_dn = (r < 55) & (r.shift(1) >= 55)
    return signs(up & cross_up, dn & cross_dn)


def sig_F7(M, trig, p):  # MACD histogram sign alignment across tfs (edge trigger)
    tfs = {"A": ["15m", "1h", "4h"], "B": ["1h", "4h", "1d"]}[p["set"]]
    col = f"macdh_{p['macd']}"
    up = pd.Series(True, index=range(len(S(M, trig, "c"))))
    dn = up.copy()
    for tf in tfs:
        m = S(M, tf, col)
        up &= m > 0
        dn &= m < 0
    return signs(edge(up), edge(dn))


def sig_F8(M, trig, p):  # 1h: triple-screen (1d trend, 4h stoch pullback, 1h breakout)
    S_, N = p["stoch"], p["N"]
    c = S(M, trig, "c")
    up = S(M, "1d", "ema20") > S(M, "1d", "ema50")
    dn = S(M, "1d", "ema20") < S(M, "1d", "ema50")
    st = S(M, "4h", "stoch14")
    return signs(up & (st < S_) & (c > S(M, trig, f"dh{N}")),
                 dn & (st > 100 - S_) & (c < S(M, trig, f"dl{N}")))


def sig_F9(M, trig, p):  # 1h: 1d ATR-percentile regime gates MR or BO
    op, thr = p["gate"][:2], float(p["gate"][2:])
    pct = S(M, "1d", "atrpct100")
    gate = (pct < thr) if op == "lt" else (pct > thr)
    c = S(M, trig, "c")
    if p["strat"] == "MR":
        lo, sh = c < S(M, trig, "bb_lo"), c > S(M, trig, "bb_up")
    else:
        lo, sh = c > S(M, trig, "dh20"), c < S(M, trig, "dl20")
    return signs(gate & lo, gate & sh)


def sig_F10(M, trig, p):  # 15m: 4h trend + 15m RSI exhaustion turning back
    fa, fb = (int(x) for x in p["pair"].split("_"))
    lo = p["lo"]
    up = S(M, "4h", f"ema{fa}") > S(M, "4h", f"ema{fb}")
    dn = S(M, "4h", f"ema{fa}") < S(M, "4h", f"ema{fb}")
    r = S(M, trig, "rsi14")
    rising = r > r.shift(1)
    falling = r < r.shift(1)
    mn = r.rolling(4).min().shift(1)
    mx = r.rolling(4).max().shift(1)
    return signs(up & (mn < lo) & rising, dn & (mx > 100 - lo) & falling)


def sig_F11(M, trig, p):  # 1h: price new N-bar extreme vs HTF RSI not confirming (divergence)
    N, d, htf = p["N"], p["delta"], p["htf"]
    c = S(M, trig, "c")
    r = S(M, htf, "rsi14")
    new_hi = c >= c.rolling(N).max()
    new_lo = c <= c.rolling(N).min()
    r_hi_gap = r < r.rolling(N).max() - d
    r_lo_gap = r > r.rolling(N).min() + d
    return signs(new_lo & r_lo_gap, new_hi & r_hi_gap)


def sig_F12(M, trig, p):  # 15m: 1h & 4h EMA stack + 15m EMA pullback reclaim
    fa, fb = (int(x) for x in p["pair"].split("_"))
    up = (S(M, "1h", f"ema{fa}") > S(M, "1h", f"ema{fb}")) & (S(M, "4h", f"ema{fa}") > S(M, "4h", f"ema{fb}"))
    dn = (S(M, "1h", f"ema{fa}") < S(M, "1h", f"ema{fb}")) & (S(M, "4h", f"ema{fa}") < S(M, "4h", f"ema{fb}"))
    c, h, l = S(M, trig, "c"), S(M, trig, "h"), S(M, trig, "l")
    e = S(M, trig, f"ema{fb}")
    return signs(up & (l <= e) & (c > e), dn & (h >= e) & (c < e))


SIG_FN = {"F1": sig_F1, "F2": sig_F2, "F3": sig_F3, "F4": sig_F4, "F5": sig_F5, "F6": sig_F6,
          "F7": sig_F7, "F8": sig_F8, "F9": sig_F9, "F10": sig_F10, "F11": sig_F11, "F12": sig_F12}


# ============================================================ engine
def simulate(sig, M, trig, hold: int, k: float):
    o, h, l, c = M[(trig, "o")], M[(trig, "h")], M[(trig, "l")], M[(trig, "c")]
    atr, t = M[(trig, "atr14")], M[(trig, "t")]
    n = len(sig)
    rets, times = [], []
    busy = -1
    for i in np.flatnonzero(sig):
        if i < busy:
            continue
        e = i + 1
        last = i + hold
        if last >= n:
            break
        d = int(sig[i])
        ep = o[e]
        if not (ep > 0):
            continue
        stop = None
        if k > 0:
            a = atr[i]
            if not np.isfinite(a) or a <= 0:
                continue
            stop = ep - d * k * a
        exitp = c[last]
        if stop is not None:
            for j in range(e, last + 1):
                if d > 0:
                    if o[j] <= stop:
                        exitp, last = o[j], j
                        break
                    if l[j] <= stop:
                        exitp, last = stop, j
                        break
                else:
                    if o[j] >= stop:
                        exitp, last = o[j], j
                        break
                    if h[j] >= stop:
                        exitp, last = stop, j
                        break
        rets.append(d * (exitp / ep - 1.0) * 1e4 - COST_BPS)
        times.append(t[e])
        busy = last
    return np.array(rets, dtype=float), np.array(times, dtype=float)


def metrics(rets: np.ndarray, times: np.ndarray) -> dict:
    n = len(rets)
    if n == 0:
        return dict(n_trades=0, win_rate=np.nan, profit_factor=np.nan, expectancy_bps=np.nan,
                    rough_sharpe=np.nan, composite_score=np.nan, half_ev_1=np.nan,
                    half_ev_2=np.nan, halves_agree="")
    wins, losses = rets[rets > 0], rets[rets <= 0]
    gw, gl = wins.sum(), -losses.sum()
    pf = (gw / gl) if gl > 0 else (np.inf if gw > 0 else np.nan)
    ev = rets.mean()
    sd = rets.std(ddof=1) if n > 1 else np.nan
    sh = ev / sd if (sd and sd > 0) else np.nan
    if pf == np.inf:
        pf_pen = 1.0
    elif not np.isfinite(pf):
        pf_pen = 0.0
    else:
        pf_pen = min(1.0, max(0.0, pf))
    comp = ev * math.log(1 + n) * min(1.0, n / 30.0) * pf_pen
    med = np.median(times)
    a, b = rets[times <= med], rets[times > med]
    h1 = a.mean() if len(a) else np.nan
    h2 = b.mean() if len(b) else np.nan
    agree = "" if not (np.isfinite(h1) and np.isfinite(h2)) else str(bool(np.sign(h1) == np.sign(h2)))
    return dict(n_trades=n, win_rate=float((rets > 0).mean()), profit_factor=float(pf) if np.isfinite(pf) else pf,
                expectancy_bps=float(ev), rough_sharpe=float(sh) if np.isfinite(sh) else np.nan,
                composite_score=float(comp), half_ev_1=float(h1), half_ev_2=float(h2), halves_agree=agree)


# ============================================================ idea catalog
FAMILIES = [
    # code, trig, title, grid (ordered), cap (None = all), mechanism
    ("F1", "1h", "HTF trend + 1h EMA20 pullback-reclaim",
     dict(htf=["4h", "1d"], pair=["20_50", "50_100"], H=[6, 12, 24], k=[1.5, 2.5]), None,
     "Trade with the higher-tf EMA trend after a short 1h pullback below/above EMA20 is reclaimed."),
    ("F2", "15m", "HTF trend + 15m Donchian breakout",
     dict(htf=["4h", "1d"], N=[20, 40, 80], H=[8, 16, 32], k=[0, 2.5]), 20,
     "Breakouts of 15m range only count when the 4h/1d EMA trend agrees (trend-filtered breakout)."),
    ("F3", "1h", "Multi-tf momentum alignment (edge trigger)",
     dict(align=["1h+4h", "1h+4h+1d"], scale=["short", "mid", "long"], H=[12, 24, 48], k=[0, 2.5]), 20,
     "All listed timeframes show same-sign trailing return; enter on the bar the alignment first forms."),
    ("F4", "1h", "Lower-tf overextension against HTF trend (fade)",
     dict(htf=["4h", "1d"], zth=[2.0, 2.5, 3.0], H=[6, 12, 24], k=[0, 2.5]), 20,
     "In an HTF uptrend, a 1h close far below EMA20 (in ATR units) is bought as a dip; mirror for downtrends."),
    ("F5", "1h", "HTF prior-N high/low zone test + reclaim",
     dict(lev=["4h", "1d"], N=[10, 20, 40], band=[0.002, 0.005], H=[12, 24], k=[0, 2.5]), 20,
     "Higher-tf prior-N low (support) in an uptrend tested by 1h lows and reclaimed; mirror at resistance."),
    ("F6", "1h", "Multi-tf RSI alignment + 1h RSI cross",
     dict(combo=["1h+4h", "1h+4h+1d"], thr=[50, 55], H=[12, 24, 48], k=[0, 2.5]), 20,
     "Higher-tf RSI above threshold (all tfs) and 1h RSI crossing back through 45 (55 for shorts)."),
    ("F7", "15m|1h", "MACD histogram sign alignment across tfs (edge)",
     dict(set=["A", "B"], macd=["12_26", "8_21"], H=[8, 16, 32], k=[0, 2.5]), None,
     "All tfs in set share MACD-histogram sign; A trades on 15m (15m,1h,4h), B on 1h (1h,4h,1d)."),
    ("F8", "1h", "Triple screen: 1d trend, 4h stoch pullback, 1h breakout",
     dict(stoch=[20, 30, 40], N=[3, 6], H=[12, 24], k=[0, 2.5]), None,
     "Elder-style triple screen: 1d EMA trend, 4h stochastic pullback, 1h breakout of the N-bar range."),
    ("F9", "1h", "1d ATR-percentile regime gate on MR or breakout",
     dict(gate=["lt0.3", "lt0.5", "gt0.5", "gt0.7"], strat=["MR", "BO"], H=[12, 24], k=[0, 2.5]), 20,
     "Daily ATR-percentile (100d) gates a 1h Bollinger mean-reversion or 20-bar breakout strategy."),
    ("F10", "15m", "4h trend + 15m RSI exhaustion turn",
     dict(pair=["20_50", "9_21"], lo=[20, 30], H=[8, 16, 32], k=[1.5, 2.5]), None,
     "Within a 4h trend, 15m RSI pushes to an extreme and turns back: pullback-exhaustion entry."),
    ("F11", "1h", "Price extreme vs HTF RSI non-confirmation (divergence)",
     dict(N=[24, 48, 96], delta=[3, 8], htf=["4h", "1d"], H=[12, 24], k=[0, 2.5]), 20,
     "1h close at an N-bar extreme while higher-tf RSI sits well inside its own N-bar range: divergence fade."),
    ("F12", "15m", "1h+4h EMA stack + 15m EMA pullback reclaim",
     dict(pair=["9_21", "20_50"], H=[8, 16, 32], k=[1.5, 2.5]), None,
     "Stacked 1h and 4h EMAs; 15m low touches the slow EMA and closes back through it."),
    ("F13", "5m", "5m Donchian breakout in HTF EMA trend [DATA BLOCKED]",
     dict(htf=["1h", "4h"], N=[20, 40], H=[12, 24, 48]), None,
     "Would need 5m bars; none under trading_data/cache/orderblock/bars (only 15m/1h/4h)."),
]


def sample_grid(grid: dict, cap):
    keys = list(grid)
    combos = [dict(zip(keys, vals)) for vals in _product(*[grid[k] for k in keys])]
    if cap is None or len(combos) <= cap:
        return combos
    idx = np.unique(np.linspace(0, len(combos) - 1, cap).round().astype(int))
    return [combos[i] for i in idx]


def _product(*lists):
    if not lists:
        yield ()
        return
    for head in lists[0]:
        for rest in _product(*lists[1:]):
            yield (head,) + rest


def build_catalog():
    ideas = []
    n = 0
    for code, trig, title, grid, cap, mech in FAMILIES:
        for p in sample_grid(grid, cap):
            n += 1
            t = trig
            if code == "F7":
                t = "15m" if p["set"] == "A" else "1h"
            k_ = p.get("k", 0)
            status = "DATA_UNAVAILABLE_5M" if code == "F13" else "PENDING"
            pdesc = ", ".join(f"{kk}={vv}" for kk, vv in p.items())
            ideas.append(dict(
                idea_id=f"G{n:03d}", family=code, trig_tf=t, title=title, params=p,
                name=f"{title} [{pdesc}]", mechanism=mech,
                hold_bars=p.get("H", ""), stop_atr=k_ if k_ else "none",
                status=status,
            ))
    return ideas


def direction_rule(code: str) -> str:
    return {"F1": "trend-direction pullback reclaim", "F2": "breakout with HTF trend",
            "F3": "all-tf momentum same sign (edge)", "F4": "fade against lower-tf overextension",
            "F5": "zone test in HTF trend", "F6": "RSI alignment + cross",
            "F7": "all-tf MACD sign (edge)", "F8": "triple screen",
            "F9": "regime-gated MR/BO", "F10": "exhaustion turn in HTF trend",
            "F11": "new extreme vs HTF RSI non-confirmation", "F12": "EMA stack pullback reclaim",
            "F13": "not screened"}[code]


# ============================================================ run
def causal_check(raw, sym, ideas):
    """Recompute every signal on data truncated at ~70% and compare on the common prefix."""
    full = build_frames(raw, sym)
    if full is None:
        return {}
    res = {}
    cut_by_trig = {}
    for trig in sorted({i["trig_tf"] for i in ideas if i["status"] == "PENDING"}, key=lambda x: TF_MS[x]):
        T = full[trig]
        cut = int(len(T) * 0.7)
        cut_t = int(T["t"].iloc[cut]) + TF_MS[trig]
        tr = build_frames(raw, sym, cut_t=cut_t)
        if tr is None:
            continue
        cut_by_trig[trig] = (cut, context(full, trig), context(tr, trig))
    for idea in ideas:
        if idea["status"] != "PENDING" or idea["trig_tf"] not in cut_by_trig:
            continue
        cut, Mf, Mt = cut_by_trig[idea["trig_tf"]]
        fn = SIG_FN[idea["family"]]
        a = fn(Mf, idea["trig_tf"], idea["params"])
        b = fn(Mt, idea["trig_tf"], idea["params"])
        m = min(cut, len(b))
        res[idea["idea_id"]] = bool(np.array_equal(a[:m], b[:m]))
    return res


def main():
    print(LABEL)
    raw = {tf: load_tf(tf) for tf in LOAD_TFS}
    for tf in LOAD_TFS:
        print(f"loaded {tf}: {len(raw[tf])} symbols")
    ideas = build_catalog()
    print(f"proposed ideas: {len(ideas)}")

    # causality self-check on BTC (all pending families)
    cc_sym = "BTCUSDT"
    cc = causal_check(raw, cc_sym, ideas)
    print(f"causal check on {cc_sym}: {sum(cc.values())}/{len(cc)} identical on common prefix")

    syms_all = sorted(set(raw["1h"]) & set(raw["4h"]) & set(raw["15m"]))
    print(f"symbols with 15m+1h+4h: {len(syms_all)}")
    results = []
    ctx_cache: dict = {}  # (sym, trig) -> context dict; built once, reused by all ideas
    for idea in ideas:
        row = dict(idea_id=idea["idea_id"], family=idea["family"], trig_tf=idea["trig_tf"],
                   name=idea["name"], params=json.dumps(idea["params"], sort_keys=True),
                   causal_check=cc.get(idea["idea_id"], "NA"))
        if idea["status"] != "PENDING":
            row.update(status=idea["status"], n_trades=0, composite_score="", data_flags="no 5m bars in cache")
            results.append(row)
            continue
        trig = idea["trig_tf"]
        need = ["1h", "4h"] if trig == "1h" else ["15m", "1h", "4h"]
        pooled_r, pooled_t, per_sym_ev = [], [], []
        n_raw, dropped = 0, 0
        for sym in sorted(set.intersection(*[set(raw[tf]) for tf in need])):
            key = (sym, trig)
            if key not in ctx_cache:
                frames = build_frames(raw, sym)
                ctx_cache[key] = context(frames, trig) if frames is not None else None
            M = ctx_cache[key]
            if M is None:
                dropped += 1
                continue
            sig = SIG_FN[idea["family"]](M, trig, idea["params"])
            n_raw += int((sig != 0).sum())
            rets, times = simulate(sig, M, trig, int(idea["params"]["H"]), float(idea["params"].get("k", 0)))
            if len(rets):
                pooled_r.append(rets)
                pooled_t.append(times)
                if len(rets) >= 5:
                    per_sym_ev.append(rets.mean())
        rets = np.concatenate(pooled_r) if pooled_r else np.array([])
        times = np.concatenate(pooled_t) if pooled_t else np.array([])
        m = metrics(rets, times)
        status = "SCORED" if m["n_trades"] >= MIN_TRADES else "INSUFFICIENT_TRADES"
        pos_share = (np.mean(np.array(per_sym_ev) > 0) if per_sym_ev else np.nan)
        row.update(status=status, n_raw_signals=n_raw, **{k: (round(v, 4) if isinstance(v, float) else v)
                                                       for k, v in m.items()},
                   n_symbols_traded=len(pooled_r), pct_symbols_pos_ev=round(float(pos_share), 3) if pos_share == pos_share else "",
                   data_flags=f"symbols_dropped_no_frames={dropped}")
        if status != "SCORED":
            row["composite_score"] = ""
        results.append(row)
        print(f"{idea['idea_id']} n={m['n_trades']} EV={m['expectancy_bps']:.1f} comp={m['composite_score']:.1f}" if m["n_trades"] else f"{idea['idea_id']} n=0")

    write_outputs(ideas, results)


RESULT_COLS = ["idea_id", "family", "trig_tf", "name", "params", "status", "n_raw_signals",
               "n_trades", "win_rate", "profit_factor", "expectancy_bps", "rough_sharpe",
               "half_ev_1", "half_ev_2", "halves_agree", "n_symbols_traded", "pct_symbols_pos_ev",
               "composite_score", "causal_check", "data_flags"]


def write_outputs(ideas, results):
    with open(HERE / "IDEAS.csv", "w", newline="", encoding="utf-8") as fh:
        w = csv.writer(fh)
        w.writerow(["idea_id", "family", "trig_tf", "name", "mechanism", "direction_rule",
                    "hold_bars_trig_tf", "stop_atr_mult", "params_json", "screen_status"])
        for i in ideas:
            w.writerow([i["idea_id"], i["family"], i["trig_tf"], i["name"], i["mechanism"],
                        direction_rule(i["family"]), i["hold_bars"], i["stop_atr"],
                        json.dumps(i["params"], sort_keys=True), i["status"]])
    with open(HERE / "RESULTS.csv", "w", newline="", encoding="utf-8") as fh:
        w = csv.DictWriter(fh, fieldnames=RESULT_COLS, extrasaction="ignore")
        w.writeheader()
        for r in results:
            w.writerow({k: r.get(k, "") for k in RESULT_COLS})
    write_ranked(ideas, results)


def write_ranked(ideas, results):
    scored = [r for r in results if r.get("status") == "SCORED" and r.get("composite_score") not in ("", None)]
    scored.sort(key=lambda r: float(r["composite_score"]), reverse=True)
    lines = [
        f"# {LABEL}",
        "",
        "# EXPLORE1000 Lane G (multi-timeframe alignment / divergence) -- TOP 20",
        "",
        "EXPLORATORY SCREEN ONLY. No multiple-testing correction, no walk-forward, no full lookahead audit. "
        "Not G-eligible. Nothing here is a validated candidate.",
        "",
        "Data: TRAIN window only (data_access.iter_train_bars), 15m / 1h / 4h bars; 1d derived from complete 4h bars. "
        "Signals use close-time-available higher-tf bars; entry at next trigger-bar open; 12bp round trip; one position per symbol.",
        "",
        f"Scored: {sum(1 for r in results if r.get('status') == 'SCORED')} of {len(ideas)} proposed. "
        f"Insufficient (<30 trades): {sum(1 for r in results if r.get('status') == 'INSUFFICIENT_TRADES')}. "
        f"Data-blocked (5m bars absent): {sum(1 for r in results if r.get('status') == 'DATA_UNAVAILABLE_5M')}.",
        "",
        "composite_score = EV * ln(1+n) * min(1,n/30) * min(1,PF); same formula as EXPLORE500 lane A, but exit rules differ, so cross-lane comparison is not valid.",
        "",
        "## Top 20",
        "",
    ]
    for rank, r in enumerate(scored[:20], 1):
        flag = "" if r.get("halves_agree") == "True" else " [halves disagree]"
        lines += [
            f"### {rank}. {r['idea_id']} -- {r['name']}{flag}",
            "",
            f"- composite_score: {float(r['composite_score']):.1f}; n_trades: {r['n_trades']}, win_rate: {r['win_rate']}, "
            f"PF: {r['profit_factor']}, EV_bps: {r['expectancy_bps']}, rough_sharpe: {r['rough_sharpe']}",
            f"- halves EV: {r['half_ev_1']} / {r['half_ev_2']}; symbols traded: {r['n_symbols_traded']}, "
            f"share of symbols with positive EV: {r['pct_symbols_pos_ev']}; causal_check: {r['causal_check']}",
            f"- rationale: {next(i['mechanism'] for i in ideas if i['idea_id'] == r['idea_id'])}",
            "",
        ]
    lines += [
        "## Caveats",
        "",
        "- Regime dependence: TRAIN spans a predominantly bullish stretch; trend-following HTF filters look better in that regime than they would in chop or bear markets.",
        "- Overfitting: ~250 ideas screened with no multiple-testing correction; expect a sizeable false-positive share among the top ranks. Parameter neighbors were not checked for plateaus.",
        "- Sample size: pooled trades across symbols are highly correlated (BTC/ETH/alts move together), so effective sample is far smaller than n_trades.",
        "- Lookahead: higher-tf bars are used only after their close; features are trailing. A truncation self-check on BTCUSDT (causal_check column) confirms signals on the common prefix are identical after truncation at 70% of the series. This is necessary, not sufficient.",
        "- Execution: next-bar-open entry, ATR-stop gap fills at bar open, close exits, flat 12bp. No funding, no slippage beyond the convention, no capacity model.",
        "- Ideas with composite driven by tiny |EV| and large n can rank high; check halves_agree and pct_symbols_pos_ev before reading anything into them.",
        "- Blocked ideas (F13, 5m) were proposed for completeness and are not screened.",
    ]
    (HERE / "RANKED_TOP20.md").write_text("\n".join(lines) + "\n", encoding="utf-8")


if __name__ == "__main__":
    main()
