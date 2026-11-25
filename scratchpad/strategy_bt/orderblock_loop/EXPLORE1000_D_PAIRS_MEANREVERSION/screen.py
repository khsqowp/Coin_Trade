"""
EXPLORATORY SCREEN ONLY -- not part of the 13-round preregistered G-gate track,
not added to TRAIN_TRIALS.csv, no promotion without separate formal
preregistration + synthetic tests + resource-gated TRAIN run.

Lane D of the one-time 1000-idea exploratory screen: statistical pairs,
spread, ratio and relative-value mean reversion on 1h TRAIN bars only
(data_access.iter_train_bars, cutoff-safe). Ranking pass, not a validation.

Engines (all share: signal on bar t close, entry at open of t+1, 12bp
round-trip cost per traded unit of notional, greedy one open trade per unit):

  pair    spread s_t = lnX_t - b_t * lnY_t, z_t = z-score of s over W bars.
          b_t = rolling W-bar OLS beta (hedge='ols') or 1 (hedge='one').
          Enter on onset of z<=-K (long spread: long X, short b*Y) or z>=K.
          Exit at bar CLOSE when z reverts inside +/-0.5, or |z|>=4 (stop),
          or after H bars (timeout). P&L = d*[(lnC_X,exit - lnO_X,entry)
          - b*(lnC_Y,exit - lnO_Y,entry)]. Cost = 12bp * (1 + |b|).
          Optional gate: only enter when trailing W-bar return correlation
          of X vs Y is below thr (correlation-breakdown variant).
          ref='EW' uses an equal-weight log index of all loaded symbols
          (entry open approximated by previous index close).
  basket  cross-sectional, dollar-neutral, rebalanced every H bars and held
          non-overlapping. Rank symbols on a key at bar t; go long the low
          side and short the high side (sign=+1, reversal), equal weights,
          gross 1.0 (0.5 long, 0.5 short). Entry open t+1, exit close t+H.
          Cost 12bp per rebalance (gross-1 basket). Keys: L-bar return,
          L-bar return residual vs BTC (rolling 720-bar beta), liquidity-
          filtered L-bar return, rolling funding-rate mean.
  single  single-symbol relative value (one leg, cost 12bp): Bollinger
          z on log close, volume-weighted (VWAP/VWMA) deviation z, EMA-ATR
          deviation (z in ATR units), or lead-lag: an extreme 1-bar move of a
          reference (BTC/ETH) z-score triggers a time-exit (H bars) trade in
          the other symbols, following or fading the reference.

Composite (reproducible):
  t_day = mean(daily P&L) / (sd(daily P&L) / sqrt(N)), where daily P&L = sum of
          per-trade net bps on each calendar day (zero on no-trade days), N = all days
  pos_unit_frac = share of units (pairs/symbols; quarters for basket) with
                  positive mean net (units with >= 5 trades; quarters >= 1 trade)
  composite_score = t_day * (0.5 + 0.5 * pos_unit_frac)
  eligible: >= 100 trades, >= 20 trading days, >= 10 units (basket: >= 8 quarters)
Clustering by day is used because pair/cross-sectional trades on the same
day are strongly correlated; a naive per-trade t-stat is also reported.
"""

from __future__ import annotations

import csv
import itertools
import json
import sys
import time
from pathlib import Path

import numpy as np
import pandas as pd

HERE = Path(__file__).resolve().parent
ORDERBLOCK_DIR = HERE.parent
sys.path.insert(0, str(ORDERBLOCK_DIR))

from data_access import iter_train_bars  # noqa: E402  (read-only, cutoff-safe loader)

LABEL = ("EXPLORATORY SCREEN ONLY -- not part of the 13-round preregistered G-gate track, "
         "not added to TRAIN_TRIALS.csv, no promotion without separate formal preregistration "
         "+ synthetic tests + resource-gated TRAIN run.")
TF = "1h"
BAR_MS = 3_600_000
DAY_MS = 86_400_000
COST_BPS = 12.0
EXIT_THR = 0.5
STOP_Z = 4.0
BETA_CAP = 3.0
MIN_SYMBOL_BARS = 1000
MIN_TRADES = 100
MIN_DAYS = 20
MIN_UNITS = 10
MIN_QUARTERS = 8
BASKET_MIN_SYMS = 10
MIN_UNIT_TRADES = 5
REF_SYMBOLS = ("BTCUSDT", "ETHUSDT")
TRADE_COLS = ["unit", "e", "day", "gross", "cost", "net"]

FAMILY_WHY = {
    "PAIR_Z_BTC": "Correlated-coin spreads (log X vs beta*log BTC) tend to revert after dislocations; cointegration-style screen, no external data.",
    "PAIR_Z_ETH": "Same spread-reversion logic against ETH, the second liquid anchor; partially overlaps BTC family by construction.",
    "PAIR_RATIO_BTC": "Price-ratio (beta=1) z-score reversion vs BTC; simplest relative-value variant, sensitive to slow drift in ratios.",
    "PAIR_RATIO_ETH": "Price-ratio (beta=1) z-score reversion vs ETH; same mechanism as the BTC ratio family.",
    "PAIR_CORRBREAK_BTC": "Enter spread reversion only when trailing correlation with BTC has broken down (<thr); tests whether decorrelated dislocations revert.",
    "PAIR_EW": "Spread of each coin vs an equal-weight index of the universe (market-neutral to the alt basket); reversion of idiosyncratic extremes.",
    "BASKET_RET_REV": "Cross-sectional short-horizon reversal: long recent losers, short recent winners, dollar-neutral, non-overlapping rebalance.",
    "BASKET_RESID_REV": "Cross-sectional reversal of BTC-beta-residual returns; removes the common market leg from the ranking key.",
    "BASKET_LIQ_REV": "Cross-sectional reversal restricted to the more liquid half of symbols (dollar volume), to test whether the effect survives liquidity filtering.",
    "BASKET_FUND": "Cross-sectional funding-rate basket: contrarian (long low funding, short high funding) or momentum variant. Rhymes with EXPLORE500 C154 funding contrarian.",
    "SINGLE_BOLL": "Bollinger-style z-score reversion on log close, single symbol, z-exit at mean or 4-sigma stop.",
    "SINGLE_VWAP": "Deviation of log close from rolling VWAP (typical price), normalized by its rolling std; single-leg reversion.",
    "SINGLE_VWMA": "Deviation of log close from volume-weighted moving average of closes, normalized; single-leg reversion.",
    "SINGLE_EMA_ATR": "Close distance from EMA in ATR units; reversion of single-bar-range-scaled extremes.",
    "SINGLE_LEADLAG": "Extreme 1h move in BTC/ETH (z-scored) followed by a time-exit trade in other coins, following or fading the reference.",
}


# ---------------------------------------------------------------------------
# Ideas
# ---------------------------------------------------------------------------
def grid(**kw):
    keys = list(kw)
    return [dict(zip(keys, vals)) for vals in itertools.product(*kw.values())]


def build_ideas():
    ideas = []

    def add(family, desc, params, status="SCREENED", req="1h OHLCV"):
        ideas.append(dict(family=family, desc=desc, params=params, status=status, req=req))

    for ref in REF_SYMBOLS:
        short = ref[:3]
        for p in grid(W=[96, 240, 480, 960], K=[1.5, 2.0, 2.5], H=[12, 48, 120]):
            add(f"PAIR_Z_{short}",
                f"Spread X - b*{short}: b = {p['W']}h rolling OLS beta; z = {p['W']}h z-score; "
                f"enter onset |z|>={p['K']} at next open; exit z revert to +/-0.5, stop |z|>=4, or {p['H']}h timeout",
                dict(kind="pair", ref=ref, hedge="ols", gate=None, **p))
    for ref in REF_SYMBOLS:
        short = ref[:3]
        for p in grid(W=[96, 240, 480], K=[2.0, 2.5], H=[24, 96]):
            add(f"PAIR_RATIO_{short}",
                f"Log price ratio X/{short} (beta=1): {p['W']}h z-score; enter |z|>={p['K']}; exit z revert to +/-0.5, stop 4, {p['H']}h timeout",
                dict(kind="pair", ref=ref, hedge="one", gate=None, **p))
    for p in grid(W=[168, 336], thr=[0.3, 0.5], K=[1.5, 2.0], H=[24, 72]):
        add("PAIR_CORRBREAK_BTC",
            f"Spread X - b*BTC ({p['W']}h OLS); only when {p['W']}h return corr < {p['thr']}; z<=-{p['K']} / >={p['K']} onset entry; exit z revert, stop 4, {p['H']}h timeout",
            dict(kind="pair", ref="BTCUSDT", hedge="ols", gate=("corr", p["W"], p["thr"]),
                 W=p["W"], K=p["K"], H=p["H"]))
    for p in grid(W=[96, 240, 480], K=[2.0, 2.5], H=[24, 96]):
        add("PAIR_EW",
            f"Log X minus equal-weight index of universe (beta=1): {p['W']}h z; enter |z|>={p['K']}; exit z revert, stop 4, {p['H']}h timeout",
            dict(kind="pair", ref="EW", hedge="one", gate=None, **p))

    for p in grid(L=[24, 72, 168, 336], H=[12, 24, 72], q=[0.2, 0.3]):
        add("BASKET_RET_REV",
            f"Long bottom {p['q']:.0%} / short top {p['q']:.0%} by {p['L']}h return, dollar-neutral, hold {p['H']}h",
            dict(kind="basket", key="ret", liq=False, sign=1, **p))
    for p in grid(L=[24, 72, 168, 336], H=[24, 72], q=[0.2, 0.3]):
        add("BASKET_RESID_REV",
            f"Long bottom / short top {p['q']:.0%} by {p['L']}h BTC-beta-residual return (720h rolling beta), hold {p['H']}h",
            dict(kind="basket", key="resid", liq=False, sign=1, **p))
    for p in grid(L=[24, 168], H=[12, 24, 72], q=[0.2, 0.3]):
        add("BASKET_LIQ_REV",
            f"As BASKET_RET_REV but only symbols in top-half 168h dollar volume; {p['L']}h key, q={p['q']}, hold {p['H']}h",
            dict(kind="basket", key="ret", liq=True, sign=1, **p))
    for p in grid(W=[24, 72, 168], H=[8, 24], dirn=[1, -1]):
        side = "contrarian (long low funding, short high)" if p["dirn"] == 1 else "momentum (long high funding, short low)"
        add("BASKET_FUND",
            f"Rolling {p['W']}h mean funding rate, cross-sectional, {side}, hold {p['H']}h",
            dict(kind="basket", key="fund", liq=False, L=p["W"], H=p["H"], q=0.3, sign=p["dirn"]),
            req="1h OHLCV + Binance UM funding (local cache)")
    for p in grid(W=[20, 50, 100], K=[2.0, 2.5, 3.0], H=[12, 48]):
        add("SINGLE_BOLL",
            f"Log close z-score {p['W']}h; enter onset |z|>={p['K']} (fade); exit z revert to +/-0.5, stop 4, {p['H']}h timeout",
            dict(kind="single", ind="boll", **p))
    for p in grid(W=[24, 72, 168], K=[1.5, 2.0], H=[12, 48]):
        add("SINGLE_VWAP",
            f"dev = log close - log VWAP_{p['W']}h, z = dev / rolling std; enter |z|>={p['K']}; exit revert/stop/{p['H']}h",
            dict(kind="single", ind="vwap", **p))
    for p in grid(W=[24, 96], K=[2.0, 2.5], H=[12, 48]):
        add("SINGLE_VWMA",
            f"dev = log close - log VWMA_{p['W']}h (volume-weighted closes), z = dev / rolling std; enter |z|>={p['K']}; exit revert/stop/{p['H']}h",
            dict(kind="single", ind="vwma", **p))
    for p in grid(W=[20, 50], K=[2.0, 3.0], H=[6, 24]):
        add("SINGLE_EMA_ATR",
            f"(close - EMA{p['W']}) / ATR14; enter |dev|>={p['K']} ATR; exit |dev|<=0.5 ATR, stop 4 ATR, {p['H']}h timeout",
            dict(kind="single", ind="ema_atr", **p))
    for p in grid(R=list(REF_SYMBOLS), K=[2.0, 3.0], H=[3, 12], dirn=["follow", "fade"]):
        add("SINGLE_LEADLAG",
            f"Reference {p['R'][:3]} 1h return z (720h std) >= {p['K']} (or <= -{p['K']}): {p['dirn']} in other coins, time exit after {p['H']} bars",
            dict(kind="leadlag", ref=p["R"], K=p["K"], H=p["H"], dirn=p["dirn"]))

    # Ideas that cannot be screened with the local OHLCV/funding cache.
    blocked = [
        ("perp-spot basis reversion", "spot OHLCV not in local bar cache; spot PIT coverage not verified"),
        ("open-interest divergence pair reversion", "open interest history not in local cache"),
        ("liquidation-cluster reversion", "liquidation feed not in local cache"),
        ("cross-venue price spread reversion", "second-venue history not in local cache; cross-venue gate pending"),
        ("staked-ETH vs ETH peg-spread reversion", "LST price series not in local cache"),
        ("BTC dominance ratio reversion", "total market-cap index not in local cache"),
        ("implied-vs-realized vol spread reversion", "options implied-vol history not in local cache"),
        ("ETF-flow vs price spread reversion", "ETF flow data not in local cache"),
        ("token-unlock calendar reversion", "unlock schedule not in local cache"),
        ("crypto-vs-KR/US equity pair reversion", "equity bars not in local cache (equity data gate open)"),
    ]
    for name, reason in blocked:
        add("DATA_BLOCKED", f"{name} (not screened: {reason})", dict(kind="blocked"),
            status="DATA_BLOCKED", req=reason)

    for i, idea in enumerate(ideas, start=1):
        idea["idea_id"] = f"D{i:03d}"
        suffix = "_".join(f"{k}{v}" for k, v in idea["params"].items()
                          if k not in ("kind", "ref", "gate") or k == "ref")
        idea["name"] = f"{idea['family']}_{suffix}".replace("'", "").replace(" ", "")
    return ideas


# ---------------------------------------------------------------------------
# Data
# ---------------------------------------------------------------------------
def funding_bar_rates(ts: np.ndarray, funding: dict) -> np.ndarray:
    out = np.full(len(ts), np.nan)
    if not funding:
        return out
    keys = sorted(funding)
    idx = np.searchsorted(ts, np.asarray(keys, dtype=np.int64), side="right") - 1
    for k, i in zip(keys, idx):
        if 0 <= i < len(ts):
            out[i] = funding[k].rate
    return out


def load_panel():
    cols = {k: {} for k in ("o", "h", "l", "c", "v", "f")}
    for sym, bars, funding in iter_train_bars(TF):
        bars = [b for b in bars if b.complete]
        if len(bars) < MIN_SYMBOL_BARS:
            continue
        ts = np.array([b.timestamp for b in bars], dtype=np.int64)
        cols["o"][sym] = pd.Series([b.open for b in bars], index=ts)
        cols["h"][sym] = pd.Series([b.high for b in bars], index=ts)
        cols["l"][sym] = pd.Series([b.low for b in bars], index=ts)
        cols["c"][sym] = pd.Series([b.close for b in bars], index=ts)
        cols["v"][sym] = pd.Series([b.volume for b in bars], index=ts)
        cols["f"][sym] = pd.Series(funding_bar_rates(ts, funding), index=ts)
    frames = {k: pd.DataFrame(v).sort_index() for k, v in cols.items()}
    O, Hh, L, C, V, FR = (frames[k] for k in ("o", "h", "l", "c", "v", "f"))
    lnO, lnC = np.log(O), np.log(C)
    ts = O.index.to_numpy(dtype=np.int64)
    ew_r = lnC.diff().mean(axis=1)
    ew_c = ew_r.fillna(0.0).cumsum()
    dv = (C * V).rolling(168, min_periods=168).mean()
    liq = dv.ge(dv.median(axis=1), axis=0).fillna(False).to_numpy(dtype=bool)
    return dict(ts=ts, O=O, H=Hh, L=L, C=C, V=V, FR=FR, lnO=lnO, lnC=lnC,
                syms=list(C.columns), ew_c=ew_c.to_numpy(dtype=float), liq=liq,
                years=(ts[-1] - ts[0]) / (365.25 * DAY_MS))


# ---------------------------------------------------------------------------
# Signal helpers
# ---------------------------------------------------------------------------
def roll_z_arr(s: pd.Series, W: int) -> np.ndarray:
    m = s.rolling(W, min_periods=W).mean()
    sd = s.rolling(W, min_periods=W).std()
    return ((s - m) / sd.replace(0.0, np.nan)).to_numpy(dtype=float)


def pair_spread_z(xc: pd.Series, yc: pd.Series, W: int, hedge: str):
    if hedge == "ols":
        var_y = yc.rolling(W, min_periods=W).var()
        cov = xc.rolling(W, min_periods=W).cov(yc)
        b = (cov / var_y.replace(0.0, np.nan)).to_numpy(dtype=float)
    else:
        b = np.ones(len(xc))
    spread = xc - pd.Series(b, index=xc.index) * yc
    return b, roll_z_arr(spread, W)


def onset(cond: np.ndarray, prev_cond: np.ndarray) -> np.ndarray:
    return cond & ~prev_cond


def shifted(z: np.ndarray) -> np.ndarray:
    return np.concatenate([[np.nan], z[:-1]])


def simulate(unit, xo, xc, yo, yc, b, z, long_ev, short_ev, H, use_z_exit, ts):
    """Greedy one-position-per-unit simulation; exits are evaluated at bar closes."""
    T = len(xo)
    empty = pd.DataFrame(columns=TRADE_COLS)
    ev = np.flatnonzero(long_ev | short_ev)
    if ev.size == 0:
        return empty
    d = np.where(long_ev[ev], 1.0, -1.0)
    e = ev + 1
    ok = (e + H) <= T
    ev, e, d = ev[ok], e[ok], d[ok]
    if e.size == 0:
        return empty
    if yo is not None:
        bb = b[ev]
        ok = np.isfinite(bb) & (np.abs(bb) <= BETA_CAP)
        ev, e, d, bb = ev[ok], e[ok], d[ok], bb[ok]
    else:
        bb = np.zeros(e.size)
    ok = np.isfinite(xo[e])
    if yo is not None:
        ok &= np.isfinite(yo[e])
    ev, e, d, bb = ev[ok], e[ok], d[ok], bb[ok]
    if e.size == 0:
        return empty
    exit_idx = e + H - 1
    if use_z_exit:
        found = np.zeros(e.size, dtype=bool)
        for k in range(H):
            zj = z[e + k]
            hit = np.where(d > 0, (zj >= -EXIT_THR) | (zj <= -STOP_Z),
                           (zj <= EXIT_THR) | (zj >= STOP_Z))
            new = hit & ~found
            exit_idx = np.where(new, e + k, exit_idx)
            found |= new
    ret = d * (xc[exit_idx] - xo[e])
    if yo is not None:
        ret = ret - d * bb * (yc[exit_idx] - yo[e])
    gross = ret * 1e4
    cost = COST_BPS * (1.0 + np.abs(bb)) if yo is not None else np.full(e.size, COST_BPS)
    valid = np.isfinite(gross)
    keep, last = [], -1
    for i in range(e.size):
        if valid[i] and e[i] > last:
            keep.append(i)
            last = exit_idx[i]
    if not keep:
        return empty
    k = np.asarray(keep, dtype=int)
    ek = e[k]
    return pd.DataFrame({"unit": unit, "e": ek, "day": ts[ek] // DAY_MS,
                         "gross": gross[k], "cost": cost[k], "net": gross[k] - cost[k]})


# ---------------------------------------------------------------------------
# Engines
# ---------------------------------------------------------------------------
def run_pair(p, P):
    ts, lnO, lnC = P["ts"], P["lnO"], P["lnC"]
    if p["ref"] == "EW":
        ref_c = P["ew_c"]
        ref_o = shifted(ref_c)
    else:
        ref_c = lnC[p["ref"]].to_numpy(dtype=float)
        ref_o = lnO[p["ref"]].to_numpy(dtype=float)
    yc_s = pd.Series(ref_c, index=ts)
    parts = []
    for X in P["syms"]:
        if X == p["ref"]:
            continue
        xc_s = lnC[X]
        xo = lnO[X].to_numpy(dtype=float)
        xc = xc_s.to_numpy(dtype=float)
        b, z = pair_spread_z(xc_s, yc_s, p["W"], p["hedge"])
        pz = shifted(z)
        L_ev = onset(z <= -p["K"], pz <= -p["K"])
        S_ev = onset(z >= p["K"], pz >= p["K"])
        if p["gate"] is not None:
            _, W, thr = p["gate"]
            xr = xc_s.diff()
            yr = pd.Series(ref_c, index=ts).diff()
            corr = xr.rolling(W, min_periods=W).corr(yr).to_numpy(dtype=float)
            g = corr < thr
            L_ev &= g
            S_ev &= g
        parts.append(simulate(X, xo, xc, ref_o, ref_c, b, z, L_ev, S_ev, p["H"], True, ts))
    return pd.concat(parts, ignore_index=True) if parts else pd.DataFrame(columns=TRADE_COLS)


def run_single(p, P):
    ts, lnO, lnC, H_, L_, C_, V_ = P["ts"], P["lnO"], P["lnC"], P["H"], P["L"], P["C"], P["V"]
    parts = []
    if p["kind"] == "leadlag":
        rr = lnC[p["ref"]].diff()
        zR = (rr / rr.rolling(720, min_periods=720).std().replace(0.0, np.nan)).to_numpy(dtype=float)
        hi, lo = zR >= p["K"], zR <= -p["K"]
        if p["dirn"] == "follow":
            L_ev, S_ev = hi, lo
        else:
            L_ev, S_ev = lo, hi
        for X in P["syms"]:
            if X == p["ref"]:
                continue
            xo = lnO[X].to_numpy(dtype=float)
            xc = lnC[X].to_numpy(dtype=float)
            parts.append(simulate(X, xo, xc, None, None, None, None, L_ev, S_ev, p["H"], False, ts))
        return pd.concat(parts, ignore_index=True) if parts else pd.DataFrame(columns=TRADE_COLS)

    for X in P["syms"]:
        xo = lnO[X].to_numpy(dtype=float)
        xc_s = lnC[X]
        xc = xc_s.to_numpy(dtype=float)
        W, K = p["W"], p["K"]
        if p["ind"] == "boll":
            z = roll_z_arr(xc_s, W)
        elif p["ind"] in ("vwap", "vwma"):
            c = C_[X]
            v = V_[X]
            if p["ind"] == "vwap":
                tp = (H_[X] + L_[X] + c) / 3.0
                vw = (tp * v).rolling(W, min_periods=W).sum() / v.rolling(W, min_periods=W).sum()
            else:
                vw = (c * v).rolling(W, min_periods=W).sum() / v.rolling(W, min_periods=W).sum()
            dev = xc_s - np.log(vw.replace(0.0, np.nan))
            z = (dev / dev.rolling(W, min_periods=W).std().replace(0.0, np.nan)).to_numpy(dtype=float)
        else:  # ema_atr
            c = C_[X]
            prev_c = c.shift(1)
            tr = pd.concat([H_[X] - L_[X], (H_[X] - prev_c).abs(), (L_[X] - prev_c).abs()], axis=1).max(axis=1)
            atr = tr.rolling(14, min_periods=14).mean()
            ema = c.ewm(span=W, adjust=False).mean()
            z = ((c - ema) / atr.replace(0.0, np.nan)).to_numpy(dtype=float)
        pz = shifted(z)
        L_ev = onset(z <= -K, pz <= -K)
        S_ev = onset(z >= K, pz >= K)
        parts.append(simulate(X, xo, xc, None, None, None, z, L_ev, S_ev, p["H"], True, ts))
    return pd.concat(parts, ignore_index=True) if parts else pd.DataFrame(columns=TRADE_COLS)


def basket_keys(p, P):
    lnC = P["lnC"]
    if p["key"] == "ret":
        return lnC.diff(p["L"])
    if p["key"] == "resid":
        r = lnC.diff()
        btc = r["BTCUSDT"]
        W = 720
        mx = r.rolling(W, min_periods=W).mean()
        my = btc.rolling(W, min_periods=W).mean()
        mxy = r.mul(btc, axis=0).rolling(W, min_periods=W).mean()
        varb = btc.rolling(W, min_periods=W).var()
        beta = (mxy.sub(mx.mul(my, axis=0), axis=0)).div(varb.replace(0.0, np.nan), axis=0)
        btc_L = lnC["BTCUSDT"].diff(p["L"])
        return lnC.diff(p["L"]) - beta.mul(btc_L, axis=0)
    return P["FR"].rolling(p["L"], min_periods=1).mean()


def run_basket(p, P):
    ts, lnO, lnC = P["ts"], P["lnO"].to_numpy(dtype=float), P["lnC"].to_numpy(dtype=float)
    K = basket_keys(p, P).to_numpy(dtype=float)
    mask = P["liq"] if p["liq"] else np.ones(K.shape, dtype=bool)
    H, q, sign = p["H"], p["q"], p["sign"]
    rows = []
    T = len(ts)
    for t in range(0, T - H - 1, H):
        kt = K[t]
        ok = np.isfinite(kt) & mask[t] & np.isfinite(lnO[t + 1]) & np.isfinite(lnC[t + H])
        idx = np.flatnonzero(ok)
        if idx.size < BASKET_MIN_SYMS:
            continue
        order = idx[np.argsort(kt[idx], kind="stable")]
        m = max(1, int(round(q * idx.size)))
        low, high = order[:m], order[-m:]
        rr = lnC[t + H] - lnO[t + 1]
        long_i, short_i = (low, high) if sign > 0 else (high, low)
        gross = 1e4 * (0.5 * rr[long_i].mean() - 0.5 * rr[short_i].mean())
        rows.append((t + 1, gross))
    if not rows:
        return pd.DataFrame(columns=TRADE_COLS)
    e = np.array([r[0] for r in rows], dtype=int)
    gross = np.array([r[1] for r in rows])
    return pd.DataFrame({"unit": "BASKET", "e": e, "day": ts[e] // DAY_MS, "gross": gross,
                         "cost": COST_BPS, "net": gross - COST_BPS})


# ---------------------------------------------------------------------------
# Statistics
# ---------------------------------------------------------------------------
def summarize(tr: pd.DataFrame, years: float, basket: bool, DAYS: pd.Index):
    base = dict(n_trades=0, n_units=0, n_days=0, win_rate=float("nan"), profit_factor=float("nan"),
                expectancy_bps_net=float("nan"), expectancy_bps_gross=float("nan"),
                expectancy_bps_net_trim1=float("nan"), worst_year_exp_net=float("nan"),
                pos_year_frac=float("nan"), max_abs_trade_bps=float("nan"),
                sd_bps_net=float("nan"),
                t_naive=float("nan"), t_day=float("nan"), sharpe_day_ann=float("nan"),
                trades_per_year=0.0, pos_unit_frac=float("nan"),
                eligible=False, composite_score=float("nan"), daily=None)
    if tr.empty:
        return base
    net = tr["net"].to_numpy(dtype=float)
    n = net.size
    wins, losses = net[net > 0].sum(), -net[net < 0].sum()
    pf = wins / losses if losses > 0 else (99.0 if wins > 0 else 0.0)
    sd = float(net.std(ddof=1)) if n > 1 else float("nan")
    lo_q, hi_q = np.quantile(net, [0.01, 0.99])
    trim = net[(net >= lo_q) & (net <= hi_q)]
    # Daily P&L proxy: sum of per-trade net bps per calendar day, zero on days without trades.
    daily_traded = tr.groupby("day")["net"].sum()
    daily = daily_traded.reindex(DAYS, fill_value=0.0)
    N = int(daily.size)
    D = int(daily_traded.size)
    dsd = float(daily.std(ddof=1)) if N > 1 else float("nan")
    dmean = float(daily.mean())
    t_day = dmean / (dsd / np.sqrt(N)) if dsd and dsd > 0 else 0.0
    sharpe = dmean / dsd * np.sqrt(365.25) if dsd and dsd > 0 else float("nan")
    if basket:
        qtr = pd.to_datetime(tr["day"] * DAY_MS, unit="ms", utc=True).dt.to_period("Q")
        qmeans = tr.groupby(qtr.values)["net"].mean()
        pos = float((qmeans > 0).mean())
        n_units = int(qmeans.size)
        eligible = n >= MIN_TRADES and D >= MIN_DAYS and n_units >= MIN_QUARTERS
    else:
        um = tr.groupby("unit")["net"].agg(["mean", "size"])
        n_units = int(um.shape[0])
        big = um[um["size"] >= MIN_UNIT_TRADES]
        pos = float((big["mean"] > 0).mean()) if len(big) else float("nan")
        eligible = n >= MIN_TRADES and D >= MIN_DAYS and n_units >= MIN_UNITS
    pos_eff = pos if np.isfinite(pos) else 0.0
    composite = t_day * (0.5 + 0.5 * pos_eff)
    # Calendar-year stability (years with >= 30 trades only).
    yr = pd.to_datetime(tr["day"] * DAY_MS, unit="ms", utc=True).dt.year.values
    ym = tr.groupby(yr)["net"].agg(["mean", "size"])
    ym = ym[ym["size"] >= 30]
    worst_year = float(ym["mean"].min()) if len(ym) else float("nan")
    pos_year = float((ym["mean"] > 0).mean()) if len(ym) else float("nan")
    return dict(n_trades=n, n_units=n_units, n_days=D, win_rate=float((net > 0).mean()),
                profit_factor=float(pf), expectancy_bps_net=float(net.mean()),
                expectancy_bps_gross=float(tr["gross"].mean()),
                expectancy_bps_net_trim1=float(trim.mean()) if trim.size else float("nan"),
                worst_year_exp_net=worst_year, pos_year_frac=pos_year,
                max_abs_trade_bps=float(np.abs(net).max()),
                sd_bps_net=sd,
                t_naive=float(net.mean() / (sd / np.sqrt(n))) if sd and sd > 0 else 0.0,
                t_day=t_day, sharpe_day_ann=sharpe, trades_per_year=float(n / years),
                pos_unit_frac=pos, eligible=bool(eligible),
                composite_score=float(composite) if eligible else float("nan"),
                daily=daily)


def fmt_corr(x):
    if isinstance(x, (float, np.floating)) and np.isfinite(x):
        return f"{x:.2f}"
    return ""


def fmt(x, nd=4):
    if isinstance(x, (float, np.floating)):
        return "" if not np.isfinite(x) else f"{float(x):.{nd}f}"
    if isinstance(x, (bool, np.bool_)):
        return str(bool(x))
    return x


def write_csv(path, cols, rows):
    with path.open("w", newline="", encoding="utf-8") as fh:
        fh.write(f"# {LABEL}\n")
        w = csv.DictWriter(fh, fieldnames=cols)
        w.writeheader()
        for r in rows:
            w.writerow({k: fmt(r.get(k, "")) for k in cols})


def main():
    t0 = time.time()
    ideas = build_ideas()
    print(f"proposed {len(ideas)} ideas", flush=True)
    P = load_panel()
    print(f"loaded {len(P['syms'])} symbols, {len(P['ts'])} aligned bars, "
          f"span {P['years']:.2f}y, {time.time() - t0:.1f}s", flush=True)
    DAYS = pd.Index(np.unique(P["ts"] // DAY_MS))

    results, daily_map = [], {}
    for idea in ideas:
        ts0 = time.time()
        p = idea["params"]
        row = dict(idea_id=idea["idea_id"], family=idea["family"], name=idea["name"],
                   status=idea["status"], params=json.dumps(
                       {k: (list(v) if isinstance(v, tuple) else v) for k, v in p.items() if k != "kind"},
                       sort_keys=True),
                   data_flags=idea["req"] if idea["status"] == "DATA_BLOCKED" else "ok")
        if idea["status"] == "DATA_BLOCKED":
            row.update(summarize(pd.DataFrame(columns=TRADE_COLS), P["years"], False, DAYS))
            row.pop("daily")
        else:
            kind = p["kind"]
            if kind == "pair":
                tr = run_pair(p, P)
                st = summarize(tr, P["years"], False, DAYS)
            elif kind == "basket":
                tr = run_basket(p, P)
                st = summarize(tr, P["years"], True, DAYS)
            else:
                tr = run_single(p, P)
                st = summarize(tr, P["years"], False, DAYS)
            if st["daily"] is not None:
                daily_map[idea["idea_id"]] = st["daily"]
            st.pop("daily")
            row.update(st)
        row["elapsed_s"] = time.time() - ts0
        results.append(row)
        if idea["status"] == "SCREENED":
            print(f"{idea['idea_id']} {idea['name']}: n={row['n_trades']} comp={row['composite_score']}", flush=True)

    # Convergence check: daily PnL correlation with the best eligible funding-basket idea.
    fund = [r for r in results if r["family"] == "BASKET_FUND" and r["status"] == "SCREENED"]
    fund_elig = [r for r in fund if r["eligible"]]
    ref_pool = fund_elig or [r for r in fund if r["n_trades"]]
    best_fund = None
    if ref_pool:
        best_fund = max(ref_pool, key=lambda r: (r["composite_score"] if r["eligible"] else r["t_day"]))["idea_id"]
    fund_series = daily_map.get(best_fund)
    for r in results:
        s = daily_map.get(r["idea_id"])
        if s is None or fund_series is None or r["idea_id"] == best_fund:
            r["corr_daily_with_best_FUND"] = "" if r["idea_id"] != best_fund else 1.0
            continue
        a = s.reindex(DAYS, fill_value=0.0)
        b = fund_series.reindex(DAYS, fill_value=0.0)
        r["corr_daily_with_best_FUND"] = float(np.corrcoef(a.values, b.values)[0, 1]) if a.std() > 0 and b.std() > 0 else float("nan")

    # Convergence check 2: EXPLORE500 C154-style funding-threshold contrarian proxy
    # (single symbol, funding bar rate <= -0.0005 long / >= +0.0005 short, next-open entry,
    # 24-bar time exit, 12bp). Used only as a reference series for correlation.
    c154_parts = []
    for X in P["syms"]:
        fr = P["FR"][X].to_numpy(dtype=float)
        c154_parts.append(simulate(X, P["lnO"][X].to_numpy(dtype=float), P["lnC"][X].to_numpy(dtype=float),
                                   None, None, None, None, fr <= -0.0005, fr >= 0.0005, 24, False, P["ts"]))
    c154_tr = pd.concat(c154_parts, ignore_index=True)
    c154_daily = c154_tr.groupby("day")["net"].sum().reindex(DAYS, fill_value=0.0)
    print(f"C154 proxy: n={len(c154_tr)} exp_net={c154_tr['net'].mean():.2f} bps", flush=True)
    for r in results:
        s = daily_map.get(r["idea_id"])
        if s is None:
            r["corr_daily_with_C154_proxy"] = ""
            continue
        a = s.reindex(DAYS, fill_value=0.0)
        r["corr_daily_with_C154_proxy"] = float(np.corrcoef(a.values, c154_daily.values)[0, 1]) if a.std() > 0 and c154_daily.std() > 0 else float("nan")

    eligible = sorted([r for r in results if r["eligible"]], key=lambda r: -r["composite_score"])
    comp_rank = {r["idea_id"]: i + 1 for i, r in enumerate(eligible)}
    for r in results:
        r["composite_rank"] = comp_rank.get(r["idea_id"], "")

    with (HERE / "IDEAS.csv").open("w", newline="", encoding="utf-8") as fh:
        fh.write(f"# {LABEL}\n")
        w = csv.DictWriter(fh, fieldnames=["idea_id", "family", "name", "mechanism_one_liner",
                                           "rule_params", "status", "data_requirement"])
        w.writeheader()
        for idea in ideas:
            w.writerow(dict(idea_id=idea["idea_id"], family=idea["family"], name=idea["name"],
                            mechanism_one_liner=idea["desc"],
                            rule_params=json.dumps({k: (list(v) if isinstance(v, tuple) else v)
                                                    for k, v in idea["params"].items()}, sort_keys=True),
                            status=idea["status"], data_requirement=idea["req"]))

    res_cols = ["idea_id", "family", "name", "status", "params", "data_flags", "n_trades", "n_units",
                "n_days", "win_rate", "profit_factor", "expectancy_bps_net", "expectancy_bps_gross",
                "expectancy_bps_net_trim1", "worst_year_exp_net", "pos_year_frac", "max_abs_trade_bps",
                "sd_bps_net", "t_naive", "t_day", "sharpe_day_ann", "trades_per_year",
                "pos_unit_frac", "eligible", "composite_score", "composite_rank",
                "corr_daily_with_best_FUND", "corr_daily_with_C154_proxy", "elapsed_s"]
    write_csv(HERE / "RESULTS.csv", res_cols, results)

    top = eligible[:20]
    scored = [r for r in results if r["status"] == "SCREENED"]
    lines = ["# RANKED TOP 20 - EXPLORATORY SCREEN ONLY", "", f"> {LABEL}", "",
             "Lane D (statistical pairs / spread / relative-value mean reversion), 1h TRAIN bars via "
             "data_access.iter_train_bars. Cost 12bp round-trip per unit traded (pair trades: 12bp x (1+|beta|)). "
             "Entries at next open, exits at bar closes, greedy one open trade per unit.",
             "",
             f"Proposed {len(ideas)} ideas; screened {len(scored)}; data-blocked (not run) "
             f"{len(ideas) - len(scored)}; eligible {len(eligible)}.",
             f"Composite = t_day x (0.5 + 0.5 x positive-unit fraction). t_day clusters trades by day. "
             f"Eligibility: >=100 trades, >=20 trading days, >=10 units (basket: >=8 quarters).",
             "",
             "| rank | idea_id | name | composite | n_trades | units | exp net bps | trim1% exp | worst-year exp | max abs trade bps | win % | PF | t_day | pos-unit % | corr w/ FUND | corr w/ C154 proxy |",
             "|---|---|---|---|---|---|---|---|---|---|---|---|---|---|---|---|"]
    for i, r in enumerate(top, start=1):
        lines.append(f"| {i} | {r['idea_id']} | {r['name']} | {r['composite_score']:.2f} | {r['n_trades']} | "
                     f"{r['n_units']} | {r['expectancy_bps_net']:.1f} | {r['expectancy_bps_net_trim1']:.1f} | "
                     f"{r['worst_year_exp_net']:.1f} | {r['max_abs_trade_bps']:.0f} | {100 * r['win_rate']:.1f} | "
                     f"{r['profit_factor']:.2f} | {r['t_day']:.2f} | {100 * r['pos_unit_frac']:.0f} | "
                     f"{fmt_corr(r['corr_daily_with_best_FUND'])} | {fmt_corr(r['corr_daily_with_C154_proxy'])} |")
    n_stable = sum(1 for r in eligible if r["worst_year_exp_net"] > 0)
    lines += ["", "## Rationale (top 20)", ""]
    for i, r in enumerate(top, start=1):
        why = FAMILY_WHY.get(r["family"], "")
        lines.append(f"{i}. **{r['name']}** ({r['idea_id']}): {why} Net {r['expectancy_bps_net']:.1f} bps/trade over "
                     f"{r['n_trades']} trades, t_day {r['t_day']:.2f}.")
    lines += ["", "## Caveats", "",
              "- EXPLORATORY ONLY. Nothing here is a validated candidate; no multiple-testing correction, walk-forward, or lookahead audit was run.",
              f"- Year stability: only {n_stable} of {len(eligible)} eligible ideas have a positive mean net in every calendar year "
              "(years with >=30 trades). Most top ideas are carried by 2021-2022 alt-season dislocations; this is the main reason none is a lead by itself.",
              "- Tail/path risk: pair and ratio trades reach |net| of several thousand bps (alt-vs-BTC moves of 50-70% in a few days) "
              "because exits are bar-close only and there is no dollar stop; the hedged spread is not a bounded-risk position.",
              "- Regime dependence: the TRAIN window is dominated by a strong up-trend for most alts; reversion signals can be "
              "mistaken for stable edge when they are really short-side losses in trends.",
              "- Overfitting risk: 250 ideas over shared grids; the top of a ~250-idea grid is expected to contain false positives even under a null.",
              "- Pair/ratio and basket trades are clustered: many pairs share the BTC/ETH leg, so trade counts overstate independent evidence. Day clustering partly corrects this.",
              "- Simplifications: bar-close exits (no intrabar stops), EW index entry approximated by previous close, "
              "OLS beta on levels (not a cointegration test), 12bp per leg for pairs (stricter than the single-symbol convention).",
              "- Convergence check: corr_daily_with_best_FUND is the daily-PnL correlation with the best eligible funding-basket idea; "
              "high correlation means a lead rhymes with the EXPLORE500 funding-contrarian theme rather than adding a new one.",
              ""]
    (HERE / "RANKED_TOP20.md").write_text("\n".join(lines) + "\n", encoding="utf-8")
    print(f"done in {time.time() - t0:.1f}s; eligible={len(eligible)}", flush=True)


if __name__ == "__main__":
    main()
