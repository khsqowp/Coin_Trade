#!/usr/bin/env python3
# EXPLORATORY SCREEN ONLY - not part of the 13-round preregistered G-gate track, not added to TRAIN_TRIALS.csv, no promotion without separate formal preregistration + synthetic tests + resource-gated TRAIN run.
"""Lane F (candlestick / multi-bar price-action) cheap exploratory screen.

Run:
    /opt/anaconda3/bin/python3 <this file>

Reads only the TRAIN-cutoff-safe 1h bars via data_access.iter_train_bars.
Writes IDEAS.csv, RESULTS.csv and RANKED_TOP20.md next to this file.

Conventions (same shared exit as the EXPLORE500 C lane, so within-lane ranks are comparable):
- Pattern evaluated on bar t close; entry at next bar open (t+1).
- Signal fires on onset (condition becomes true on bar t, was false on t-1).
- Stop = 1.5 x ATR14 (measured at bar t); target = 3.0 x ATR14 (2R).
- Max hold 24 bars; timeout exits at close of the 24th bar.
- Intrabar ambiguity: stop checked before target. Gap through stop fills at the open.
- One position per symbol at a time (greedy, in time order).
- Round-trip cost 12 bp subtracted from every trade.
- No look-ahead: every feature at bar t uses bars <= t; "prior" references use shift(>=1).
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
from data_access import iter_train_bars  # noqa: E402  (read-only loader)

LABEL = ("EXPLORATORY SCREEN ONLY - not part of the 13-round preregistered G-gate track, "
         "not added to TRAIN_TRIALS.csv, no promotion without separate formal preregistration "
         "+ synthetic tests + resource-gated TRAIN run.")
TF = "1h"
COST_BPS = 12.0
STOP_ATR = 1.5
TARGET_ATR = 3.0
MAX_HOLD = 24
MIN_TRADES = 100
MIN_SYMBOLS = 10


# ----------------------------------------------------------------------------
# Features
# ----------------------------------------------------------------------------
def rl(b: pd.Series) -> pd.Series:
    """Consecutive-True run length, counting the current bar."""
    x = b.fillna(False).to_numpy(bool)
    out = np.zeros(len(x), dtype=int)
    for i, f in enumerate(x):
        if f:
            out[i] = (out[i - 1] if i else 0) + 1
    return pd.Series(out, index=b.index)


class Feat:
    def __init__(self, a: dict):
        o, h, l, c, v = (pd.Series(a[k], dtype=float) for k in ("o", "h", "l", "c", "v"))
        self.idx = o.index
        self.n = len(c)
        self.ts = a["ts"]
        self.o, self.h, self.l, self.c, self.v = o, h, l, c, v
        self.pc = c.shift(1)
        self.rng = h - l
        self.top = pd.concat([o, c], axis=1).max(axis=1)
        self.bot = pd.concat([o, c], axis=1).min(axis=1)
        self.body = self.top - self.bot
        self.uw = h - self.top
        self.lw = self.bot - l
        self.tr = pd.concat([h - l, (h - self.pc).abs(), (l - self.pc).abs()], axis=1).max(axis=1)
        self.atr = self.tr.rolling(14).mean()
        self.vr = v / v.rolling(20).mean()
        self._sma: dict[int, pd.Series] = {}
        # numpy copies for the trade simulator
        self.o_np, self.h_np, self.l_np, self.c_np = (x.to_numpy(float) for x in (o, h, l, c))
        self.atr_np = self.atr.to_numpy(float)

    def sma(self, T: int) -> pd.Series:
        if T not in self._sma:
            self._sma[T] = self.c.rolling(T).mean()
        return self._sma[T]

    def true(self) -> pd.Series:
        return pd.Series(True, index=self.idx)


def ctx(F: Feat, T: int, side: str) -> pd.Series:
    """Trend context: side 'up' = close above SMA(T); 'dn' = below. T=0 means no filter."""
    if not T:
        return F.true()
    s = F.sma(T)
    return (F.c > s) if side == "up" else (F.c < s)


def mctx(F: Feat, T: int, mode: str, side: str) -> pd.Series:
    """Mode-aware trend context. Reversal ('rev'/'fade') trades against the trend context,
    continuation ('cont') trades with it. side 'L' or 'S'."""
    if side == "L":
        want_up = (mode == "cont")
    else:
        want_up = (mode != "cont")
    return ctx(F, T, "up" if want_up else "dn")


def volok(F: Feat, V: float) -> pd.Series:
    return F.true() if not V else (F.vr >= V)


def roll_slope(y: np.ndarray, K: int) -> np.ndarray:
    """OLS slope of y over the trailing K bars (x = global bar index; slope sign is what we use)."""
    y = np.asarray(y, float)
    x = np.arange(len(y), dtype=float)

    def rs(a):
        return pd.Series(a).rolling(K).sum().to_numpy()

    sx, sy, sxy, sxx = rs(x), rs(y), rs(x * y), rs(x * x)
    return (K * sxy - sx * sy) / (K * sxx - sx * sx)


def onset(x: np.ndarray) -> np.ndarray:
    prev = np.concatenate([[False], x[:-1]])
    return x & ~prev


# ----------------------------------------------------------------------------
# Pattern families. Each returns (long_bool, short_bool) Series at bar t.
# ----------------------------------------------------------------------------
def p_engulf(F, p):
    c, o = F.c, F.o
    pc, po = c.shift(1), o.shift(1)
    bull = (pc < po) & (c > o) & (o <= pc) & (c >= po)
    bear = (pc > po) & (c < o) & (o >= pc) & (c <= po)
    v = volok(F, p["V"])
    return (bull & mctx(F, p["T"], p["mode"], "L") & v,
            bear & mctx(F, p["T"], p["mode"], "S") & v)


def p_hammer(F, p):
    K, M, N = p["K"], p["M"], p["N"]
    base = F.rng >= M * F.atr
    dn_prior = F.pc < F.c.shift(N + 1)
    up_prior = F.pc > F.c.shift(N + 1)
    L = (F.lw >= K * F.body) & (F.uw <= 0.25 * F.rng) & base & dn_prior
    S = (F.uw >= K * F.body) & (F.lw <= 0.25 * F.rng) & base & up_prior
    return L, S


def p_doji(F, p):
    N, b, pf = p["N"], p["b"], p["pf"]
    hi, lo = F.h.rolling(N).max(), F.l.rolling(N).min()
    pos = (F.c - lo) / (hi - lo)
    doji = F.body <= b * F.rng
    lowx, highx = pos <= pf, pos >= 1 - pf
    if p["mode"] == "rev":
        return doji & lowx, doji & highx
    return doji & highx, doji & lowx


def p_three_bar(F, p):
    K = p["K"]
    dn, up = rl(F.c < F.pc), rl(F.c > F.pc)
    brk_up, brk_dn = F.c > F.h.shift(1), F.c < F.l.shift(1)
    v = volok(F, p["V"])
    if p["mode"] == "rev":
        L = (dn.shift(1) >= K) & brk_up
        S = (up.shift(1) >= K) & brk_dn
    else:
        L = (up.shift(1) >= K) & brk_up
        S = (dn.shift(1) >= K) & brk_dn
    return L & v, S & v


def p_outside(F, p):
    N = p["N"]
    out = (F.h > F.h.shift(1)) & (F.l < F.l.shift(1))
    upc, dnc = F.c > F.h.shift(1), F.c < F.l.shift(1)
    if N:
        newhi = F.h >= F.h.rolling(N).max()
        newlo = F.l <= F.l.rolling(N).min()
    else:
        newhi, newlo = F.true(), F.true()
    if p["mode"] == "cont":
        return out & upc & newhi, out & dnc & newlo
    return out & dnc & newlo, out & upc & newhi


def _impulse(F, K, M):
    imp = F.c.shift(K) - F.c.shift(K + M)
    hiK = F.h.shift(1).rolling(K).max()
    loK = F.l.shift(1).rolling(K).min()
    return imp, imp.abs(), hiK, loK


def p_flag(F, p):
    K, M, Y, X = p["K"], p["M"], p["Y"], p["X"]
    imp, ai, hiK, loK = _impulse(F, K, M)
    big = ai >= X * F.atr
    tight = (hiK - loK) <= Y * ai
    return ((imp > 0) & big & tight & (F.c > hiK),
            (imp < 0) & big & tight & (F.c < loK))


def p_pennant(F, p):
    K, M, X = p["K"], p["M"], p["X"]
    imp, ai, hiK, loK = _impulse(F, K, M)
    big = ai >= X * F.atr
    sh = pd.Series(roll_slope(F.h.shift(1).to_numpy(), K), index=F.idx)
    sl = pd.Series(roll_slope(F.l.shift(1).to_numpy(), K), index=F.idx)
    conv = (sh < 0) & (sl > 0)
    return ((imp > 0) & big & conv & (F.c > hiK),
            (imp < 0) & big & conv & (F.c < loK))


def p_pin_round(F, p):
    tol, e, W = p["tol"], p["e"], p["W"]
    c = F.c_np
    step = 10.0 ** (np.floor(np.log10(c)) - e)
    l, h = F.l_np, F.h_np
    lvl_lo = np.round(l / step) * step
    lvl_hi = np.round(h / step) * step
    near_lo = np.abs(l - lvl_lo) / c <= tol
    near_hi = np.abs(h - lvl_hi) / c <= tol
    rng = F.rng.to_numpy(float)
    lw, uw = F.lw.to_numpy(float), F.uw.to_numpy(float)
    L = near_lo & (lw >= W * rng) & (rng > 0) & (c > lvl_lo)
    S = near_hi & (uw >= W * rng) & (rng > 0) & (c < lvl_hi)
    return pd.Series(L, index=F.idx), pd.Series(S, index=F.idx)


def p_pin_swing(F, p):
    N, W, T = p["N"], p["W"], p["T"]
    lo_prev = F.l.shift(1).rolling(N).min()
    hi_prev = F.h.shift(1).rolling(N).max()
    L = (F.l < lo_prev) & (F.c > lo_prev) & (F.lw >= W * F.rng) & (F.rng > 0) & ctx(F, T, "dn")
    S = (F.h > hi_prev) & (F.c < hi_prev) & (F.uw >= W * F.rng) & (F.rng > 0) & ctx(F, T, "up")
    return L, S


def p_failed(F, p):
    N, confirm, X = p["N"], p["confirm"], p["X"]
    lvl_h = F.h.shift(1).rolling(N).max().shift(1)   # max high of bars t-1-N .. t-2
    lvl_l = F.l.shift(1).rolling(N).min().shift(1)
    a1 = F.atr.shift(1)
    brk_up = F.c.shift(1) > lvl_h + X * a1
    brk_dn = F.c.shift(1) < lvl_l - X * a1
    cbear = (F.c < F.o) if confirm else F.true()
    cbull = (F.c > F.o) if confirm else F.true()
    S = brk_up & (F.c < lvl_h) & cbear
    L = brk_dn & (F.c > lvl_l) & cbull
    return L, S


def p_inside(F, p):
    K, T, mode, V = p["K"], p["T"], p["mode"], p["V"]
    ins = (F.h <= F.h.shift(1)) & (F.l >= F.l.shift(1))
    ok = rl(ins).shift(1) >= K
    up = F.c > F.h.shift(K + 1)
    dn = F.c < F.l.shift(K + 1)
    v = volok(F, V)
    if mode == "cont":
        return ok & up & mctx(F, T, mode, "L") & v, ok & dn & mctx(F, T, mode, "S") & v
    return ok & dn & mctx(F, T, mode, "L") & v, ok & up & mctx(F, T, mode, "S") & v


def p_three_push(F, p):
    P, s, mode, T = p["P"], p["s"], p["mode"], p["T"]
    up_bar = (F.h > F.h.shift(1)) & (F.c > F.pc)
    dn_bar = (F.l < F.l.shift(1)) & (F.c < F.pc)
    upP, dnP = rl(up_bar) >= P, rl(dn_bar) >= P
    shrink = F.tr <= s * F.tr.shift(1)
    expand = F.tr > s * F.tr.shift(1)
    if mode == "rev":
        return dnP & shrink & mctx(F, T, mode, "L"), upP & shrink & mctx(F, T, mode, "S")
    return upP & expand & mctx(F, T, mode, "L"), dnP & expand & mctx(F, T, mode, "S")


def p_bigbar(F, p):
    K, b, mode, T = p["K"], p["b"], p["mode"], p["T"]
    big = F.body >= b * F.atr
    runU = rl((F.c > F.o) & big) >= K
    runD = rl((F.c < F.o) & big) >= K
    if mode == "rev":
        return runD & mctx(F, T, mode, "L"), runU & mctx(F, T, mode, "S")
    return runU & mctx(F, T, mode, "L"), runD & mctx(F, T, mode, "S")


def p_gap(F, p):
    g, mode = p["g"], p["mode"]
    gap = (F.o - F.pc) / F.atr
    gu, gd = gap >= g, gap <= -g
    if mode == "fade_bar":
        return gd & (F.c > F.o), gu & (F.c < F.o)
    if mode == "fill_follow":
        return gd & (F.c >= F.pc), gu & (F.c <= F.pc)
    return gu & (F.c > F.o) & (F.l > F.pc), gd & (F.c < F.o) & (F.h < F.pc)


def p_wick(F, p):
    W, N, V = p["W"], p["N"], p["V"]
    lwf, uwf = F.lw / F.rng, F.uw / F.rng
    lo_ctx = F.l <= F.l.rolling(N).min()
    hi_ctx = F.h >= F.h.rolling(N).max()
    v = volok(F, V)
    return (lwf >= W) & lo_ctx & v, (uwf >= W) & hi_ctx & v


def p_combo(F, p):
    base, V, T = p["base"], p["V"], p["T"]
    if base == "engulf":
        L, S = p_engulf(F, {"mode": "rev", "T": 0, "V": 0})
    elif base == "pin_swing":
        L, S = p_pin_swing(F, {"N": 24, "W": 0.5, "T": 0})
    elif base == "three_bar":
        L, S = p_three_bar(F, {"K": 3, "V": 0, "mode": "rev"})
    elif base == "inside":
        L, S = p_inside(F, {"K": 1, "T": 0, "mode": "fade", "V": 0})
    else:
        L, S = p_doji(F, {"N": 72, "b": 0.2, "pf": 0.2, "mode": "rev"})
    v = volok(F, V)
    return L & v & ctx(F, T, "dn"), S & v & ctx(F, T, "up")


def p_climax(F, p):
    Kv, N, mode = p["Kv"], p["N"], p["mode"]
    vrh = F.vr >= Kv
    clv = (2 * F.c - F.h - F.l) / F.rng
    lwf, uwf = F.lw / F.rng, F.uw / F.rng
    hi_ctx = F.h >= F.h.rolling(N).max()
    lo_ctx = F.l <= F.l.rolling(N).min()
    if mode == "rev":
        return (vrh & (lwf >= 0.5) & (clv >= 0.5) & lo_ctx,
                vrh & (uwf >= 0.5) & (clv <= -0.5) & hi_ctx)
    return (vrh & (F.c > F.o) & (clv >= 0.5) & hi_ctx,
            vrh & (F.c < F.o) & (clv <= -0.5) & lo_ctx)


def p_boll(F, p):
    k, mode, conf = p["k"], p["mode"], p["conf"]
    mid = F.c.rolling(20).mean()
    sd = F.c.rolling(20).std()
    up, dn = mid + k * sd, mid - k * sd
    po_up, po_dn = F.pc > up.shift(1), F.pc < dn.shift(1)
    cbull = (F.c > F.o) if conf else F.true()
    cbear = (F.c < F.o) if conf else F.true()
    if mode == "rev":
        return po_dn & (F.c > dn) & cbull, po_up & (F.c < up) & cbear
    return po_up & (F.c > up) & cbull, po_dn & (F.c < dn) & cbear


def p_pullback(F, p):
    T, K = p["T"], p["K"]
    rdn, rup = rl(F.c < F.pc), rl(F.c > F.pc)
    L = ctx(F, T, "up") & (rdn.shift(1) >= K) & (F.c > F.h.shift(1))
    S = ctx(F, T, "dn") & (rup.shift(1) >= K) & (F.c < F.l.shift(1))
    return L, S


def p_star(F, p):
    b, T = p["b"], p["T"]
    c2, o2 = F.c.shift(2), F.o.shift(2)
    b2, a2 = F.body.shift(2), F.atr.shift(2)
    small = F.body.shift(1) <= 0.3 * b2
    mid2 = (o2 + c2) / 2
    bear2 = (c2 < o2) & (b2 >= b * a2)
    bull2 = (c2 > o2) & (b2 >= b * a2)
    L = bear2 & small & (F.c > F.o) & (F.c > mid2) & ctx(F, T, "dn")
    S = bull2 & small & (F.c < F.o) & (F.c < mid2) & ctx(F, T, "up")
    return L, S


def p_harami(F, p):
    T, mode = p["T"], p["mode"]
    bear_prev = F.pc < F.o.shift(1)
    bull_prev = F.pc > F.o.shift(1)
    inside = (F.top <= F.top.shift(1)) & (F.bot >= F.bot.shift(1))
    cur_bull, cur_bear = F.c > F.o, F.c < F.o
    if mode == "rev":
        return (bear_prev & cur_bull & inside & mctx(F, T, mode, "L"),
                bull_prev & cur_bear & inside & mctx(F, T, mode, "S"))
    return (bull_prev & cur_bull & inside & mctx(F, T, mode, "L"),
            bear_prev & cur_bear & inside & mctx(F, T, mode, "S"))


def p_nr(F, p):
    N, mode, V = p["N"], p["mode"], p["V"]
    nr = F.rng.shift(1) <= F.rng.shift(1).rolling(N).min()
    brk_up, brk_dn = F.c > F.h.shift(1), F.c < F.l.shift(1)
    v = volok(F, V)
    if mode == "cont":
        return nr & brk_up & v, nr & brk_dn & v
    return nr & brk_dn & v, nr & brk_up & v


def p_piercing(F, p):
    f, T = p["f"], p["T"]
    c1, o1 = F.c.shift(1), F.o.shift(1)
    bear1, bull1 = c1 < o1, c1 > o1
    L = bear1 & (F.o <= c1) & (F.c >= c1 + f * (o1 - c1)) & (F.c > F.o) & ctx(F, T, "dn")
    S = bull1 & (F.o >= c1) & (F.c <= c1 - f * (c1 - o1)) & (F.c < F.o) & ctx(F, T, "up")
    return L, S


# ----------------------------------------------------------------------------
# Idea grid. (key, fn, grid, mechanism description, plausibility rationale)
# ----------------------------------------------------------------------------
FAMILIES = [
    ("engulf", p_engulf, dict(mode=["rev", "cont"], T=[24, 72, 168], V=[0, 1.5]),
     "Bullish/bearish engulfing candle (body engulfs prior body). rev = counter-trend at SMA(T) extreme; cont = with trend.",
     "Classic two-bar reversal; crypto 1h engulfing is noisy, expect weak edge after costs."),
    ("hammer", p_hammer, dict(K=[2, 3], M=[0.5, 1.0], N=[3, 6]),
     "Hammer (long lower wick, small upper wick) after N-bar decline -> long; shooting star after rise -> short.",
     "Rejection wick = intrabar buyer absorption; needs prior move and meaningful range."),
    ("doji_ext", p_doji, dict(N=[24, 72, 168], b=[0.1, 0.2], pf=[0.1, 0.3], mode=["rev", "cont"]),
     "Indecision doji (body <= b x range) with close in bottom/top pf fraction of N-bar range. rev fades, cont follows.",
     "Doji at range extremes is a standard exhaustion read; signal is very frequent so edge must be large."),
    ("three_bar", p_three_bar, dict(K=[2, 3, 4], V=[0, 1.3], mode=["rev", "cont"]),
     "K consecutive closes in one direction, then bar closes beyond prior bar's extreme. rev = against run, cont = with run.",
     "Three-bar reversal (Bulkowski style) made systematic; prior-bar break is the confirmation."),
    ("outside", p_outside, dict(mode=["rev", "cont"], N=[0, 24, 72]),
     "Outside bar (new high and new low vs prior bar) closing beyond prior range. rev = key-reversal fade; optional N-bar extreme context.",
     "Key-reversal day pattern; sample of outside bars is small on 1h so effect is hard to resolve."),
    ("flag", p_flag, dict(K=[6, 12], M=[6, 12], Y=[0.5, 0.8], X=[2.5, 4.0]),
     "Flag: impulse of M bars >= X ATR ending K bars ago, tight K-bar consolidation (range <= Y x impulse), close breaks consolidation in impulse direction.",
     "Flag continuation is a staple; overlaps the EXPLORE500 C vol-compression breakout (C066-C069) and may be the same effect."),
    ("pennant", p_pennant, dict(K=[12, 24], M=[12, 24], X=[2.0, 4.0]),
     "Pennant: OLS slope of highs < 0 and lows > 0 over K bars (converging), after impulse of M bars; close breaks the converging range.",
     "Contracting-range breakout via geometric rule; close cousin of the flag family, so correlated with it."),
    ("pin_round", p_pin_round, dict(tol=[0.002, 0.005], e=[0, 1], W=[0.5, 0.67]),
     "Pin bar whose wick pierces within tol of a round price level (step = 10^(floor(log10 price)-e)); long off round support, short off round resistance.",
     "Round-number rejection is a discretionary favourite; the level definition is crude so results are approximate."),
    ("pin_swing", p_pin_swing, dict(N=[12, 48], W=[0.5, 0.67], T=[0, 48]),
     "Pin bar piercing the prior N-bar extreme and closing back inside (failed breakout wick). Optional SMA(T) trend context.",
     "Swing-level liquidity sweep with rejection wick; overlaps the R21/R25 sweep concepts (different trigger: single-bar wick)."),
    ("failed_break", p_failed, dict(N=[12, 24, 72], confirm=[0, 1], X=[0, 0.3]),
     "Previous bar closed beyond the prior N-bar extreme (by X ATR); current bar closes back inside -> fade the breakout.",
     "Fakeout reversal; classic and cheap. Overlaps the EXPLORE500 A/C range-break concepts only loosely."),
    ("inside_chain", p_inside, dict(K=[1, 2, 3], T=[0, 48], mode=["cont", "fade"], V=[0, 1.5]),
     "K consecutive inside bars, then close beyond the mother-bar extreme. cont = follow the break; fade = trade the false break.",
     "Inside-bar breakout (volatility contraction then expansion); similar to vol-compression family."),
    ("three_push", p_three_push, dict(P=[3, 4], s=[1.0, 0.8], mode=["rev", "cont"], T=[0, 48]),
     "P consecutive higher-high/higher-close (or lower) bars. rev = exhaustion when bar range shrinks (tr <= s x prev); cont = acceleration (range expands).",
     "Three-push exhaustion with a range-shrink momentum proxy; no swing-pivot detection, so approximate."),
    ("bigbar_run", p_bigbar, dict(K=[3, 4], b=[0.5, 1.0], mode=["rev", "cont"], T=[0, 48]),
     "K consecutive large-body bars (body >= b x ATR) in one direction. rev = exhaustion fade; cont = momentum follow.",
     "Marubozu-run exhaustion/momentum; differs from C-lane consecutive-close exhaust by requiring large bodies."),
    ("gap", p_gap, dict(g=[0.5, 1.0, 1.5], mode=["fade_bar", "fill_follow", "go"]),
     "Open-to-prior-close gap >= g x ATR. fade_bar = gap-down reclaimed bullishly (long); fill_follow = gap closed intrabar, trade the fill; go = unfilled gap continuation.",
     "Gap-fill and gap-and-go are discretionary staples; crypto 24/7 means gaps are small and rare."),
    ("wick_ratio", p_wick, dict(W=[0.6, 0.75], N=[12, 48], V=[0, 1.5]),
     "Lower (upper) wick >= W of bar range at N-bar low (high) extreme -> long (short), optional volume filter.",
     "Wick-ratio rejection at extremes; closely related to pin-bar family, expect high correlation."),
    ("pat_vol_combo", p_combo, dict(base=["engulf", "pin_swing", "three_bar", "inside", "doji"], V=[1.5, 2.0], T=[0, 48]),
     "Base candle pattern (fixed rev params) + volume >= V x SMA20 volume + counter-trend context SMA(T).",
     "Volume confirmation of a candle reversal; tests whether participation separates real from fake patterns."),
    ("vol_climax", p_climax, dict(Kv=[2, 3], N=[24, 72], mode=["rev", "cont"]),
     "Volume climax (vol >= Kv x SMA20) on a bar with strong close (CLV) and long rejection wick at N-bar extreme. rev fades, cont follows.",
     "Selling/buying climax reversal; volume is a plausible exhaustion proxy."),
    ("bollinger_reject", p_boll, dict(k=[2.0, 2.5], mode=["rev", "cont"], conf=[0, 1]),
     "Prior close outside BB(20,k); current close back inside (rev) or still outside (cont), optional bar-colour confirmation.",
     "Candle-close-through-band rejection; BB itself is common so the price-action layer is the test."),
    ("pullback_trend", p_pullback, dict(T=[48, 168], K=[2, 3]),
     "In SMA(T) trend, K consecutive counter-trend closes, then bar closes beyond prior bar extreme in trend direction.",
     "Pullback-resume entry; trend-following flavour with a candle trigger."),
    ("morning_evening_star", p_star, dict(b=[0.8, 1.2], T=[0, 48]),
     "Three-bar star: large opposite body, small middle body (<= 0.3x), third bar closes beyond midpoint of first body.",
     "Classic three-bar reversal; small middle body requirement makes it rarer."),
    ("harami", p_harami, dict(T=[0, 24, 72], mode=["rev", "cont"]),
     "Current body contained in prior body with colour change (rev) or same colour (cont), optional SMA(T) context.",
     "Harami is a weak classic; included for coverage of the inside-body family."),
    ("nr_breakout", p_nr, dict(N=[4, 7], mode=["cont", "fade"], V=[0, 1.5]),
     "Narrow-range bar (narrowest of N bars) followed by a break of its high/low; cont follows, fade trades the reversal.",
     "NR4/NR7 breakout; a volatility-contraction cousin of the flag and inside-bar families."),
    ("piercing_cloud", p_piercing, dict(f=[0.5, 0.75], T=[0, 48]),
     "Piercing line / dark cloud cover: opposite candle then close beyond fraction f of its body, optional SMA(T) context.",
     "Two-bar reversal with body-penetration rule; similar to engulfing."),
]


def build_ideas():
    ideas = []
    for key, fn, grid, desc, why in FAMILIES:
        keys = list(grid)
        for vals in itertools.product(*(grid[k] for k in keys)):
            params = dict(zip(keys, vals))
            ideas.append(dict(family=key, fn=fn, params=params, desc=desc, why=why))
    for i, idea in enumerate(ideas, 1):
        idea["idea_id"] = f"F{i:03d}"
        ps = "_".join(f"{k}{v}" for k, v in idea["params"].items())
        idea["name"] = f"{idea['family']}_{ps}"
        idea["params_json"] = json.dumps(idea["params"], sort_keys=True)
    return ideas


# ----------------------------------------------------------------------------
# Trade simulation (shared exit, copied in convention from EXPLORE500 C lane)
# ----------------------------------------------------------------------------
def simulate(F: Feat, L: np.ndarray, S: np.ndarray):
    empty = (np.array([]), np.array([], dtype=np.int64))
    sig = np.flatnonzero(L | S)
    if sig.size == 0:
        return empty
    d = np.where(L[sig], 1, -1)
    e = sig + 1
    atr = F.atr_np[sig]
    keep = (e + MAX_HOLD <= F.n) & np.isfinite(atr) & (atr > 0)
    d, e, atr = d[keep], e[keep], atr[keep]
    if e.size == 0:
        return empty
    o, h, l, c = F.o_np, F.h_np, F.l_np, F.c_np
    entry = o[e]
    stop = entry - d * STOP_ATR * atr
    target = entry + d * TARGET_ATR * atr
    T = e.size
    exit_px = np.full(T, np.nan)
    exit_k = np.full(T, MAX_HOLD - 1, dtype=int)
    done = np.zeros(T, dtype=bool)
    for k in range(MAX_HOLD):
        idx = e + k
        op, hi, lo = o[idx], h[idx], l[idx]
        stop_hit = ~done & np.where(d == 1, lo <= stop, hi >= stop)
        fill = np.where(d == 1, np.minimum(stop, op), np.maximum(stop, op))
        exit_px = np.where(stop_hit, fill, exit_px)
        exit_k = np.where(stop_hit, k, exit_k)
        done |= stop_hit
        tgt_hit = ~done & np.where(d == 1, hi >= target, lo <= target)
        exit_px = np.where(tgt_hit, target, exit_px)
        exit_k = np.where(tgt_hit, k, exit_k)
        done |= tgt_hit
    exit_px = np.where(~done, c[e + MAX_HOLD - 1], exit_px)
    exit_idx = e + exit_k
    gross = d * (exit_px - entry) / entry * 1e4
    taken, nxt = [], -1
    for i in range(T):
        if e[i] > nxt:
            taken.append(i)
            nxt = exit_idx[i]
    t = np.asarray(taken, dtype=int)
    return gross[t], F.ts[e[t]]


def load_universe():
    syms = {}
    for sym, bars, _funding in iter_train_bars(TF):
        bars = [b for b in bars if b.complete]
        if len(bars) < 1000:
            continue
        a = dict(ts=np.array([b.timestamp for b in bars], dtype=np.int64),
                 o=np.array([b.open for b in bars]), h=np.array([b.high for b in bars]),
                 l=np.array([b.low for b in bars]), c=np.array([b.close for b in bars]),
                 v=np.array([b.volume for b in bars]))
        syms[sym] = Feat(a)
    return syms


def summarize(per_sym, gross_list, ts_list, years, mid_ts):
    if not per_sym:
        return dict(n_trades=0, n_symbols_traded=0, data_flag="no_signals", eligible=False)
    gross = np.concatenate(gross_list)
    ts = np.concatenate(ts_list)
    net = gross - COST_BPS
    n = net.size
    wins, losses = net[net > 0].sum(), -net[net < 0].sum()
    pf = (wins / losses) if losses > 0 else (99.0 if wins > 0 else 0.0)
    mean = float(net.mean())
    sd = float(net.std(ddof=1)) if n > 1 else float("nan")
    t_stat = mean / (sd / np.sqrt(n)) if sd and sd > 0 else 0.0
    rough = mean / sd * np.sqrt(n / years) if sd and sd > 0 else float("nan")
    sym_means = [float((g - COST_BPS).mean()) for g in per_sym.values() if g.size >= 5]
    pos_frac = float(np.mean([m > 0 for m in sym_means])) if sym_means else 0.0
    first = ts < mid_ts
    ev1 = float(net[first].mean()) if first.any() else float("nan")
    ev2 = float(net[~first].mean()) if (~first).any() else float("nan")
    eligible = n >= MIN_TRADES and len(per_sym) >= MIN_SYMBOLS
    composite = t_stat * (0.5 + 0.5 * pos_frac) if eligible else float("nan")
    flag = "ok" if eligible else "below_min_sample"
    return dict(n_trades=n, n_symbols_traded=len(per_sym), win_rate=float((net > 0).mean()),
                profit_factor=float(pf), expectancy_bps_net=mean,
                expectancy_bps_gross=float(gross.mean()), sd_bps_net=sd, t_stat=float(t_stat),
                rough_sharpe=float(rough), trades_per_year=float(n / years), pos_symbol_frac=pos_frac,
                ev_first_half_bps=ev1, ev_second_half_bps=ev2,
                both_halves_positive=bool(ev1 > 0 and ev2 > 0), eligible=bool(eligible),
                composite_score=float(composite), data_flag=flag)


def fmt(x, nd=4):
    if isinstance(x, (float, np.floating)):
        return "" if not np.isfinite(x) else f"{x:.{nd}f}"
    return x


def write_csv(path: Path, cols, rows):
    with path.open("w", newline="", encoding="utf-8") as fh:
        fh.write(f"# {LABEL}\n")
        w = csv.DictWriter(fh, fieldnames=cols, extrasaction="ignore")
        w.writeheader()
        for r in rows:
            w.writerow({k: fmt(r.get(k, "")) for k in cols})


def main():
    t0 = time.time()
    ideas = build_ideas()
    print(f"ideas: {len(ideas)}", flush=True)
    syms = load_universe()
    years = float(np.mean([(F.ts[-1] - F.ts[0]) / (365.25 * 24 * 3_600_000) for F in syms.values()]))
    mid_ts = (min(F.ts[0] for F in syms.values()) + max(F.ts[-1] for F in syms.values())) / 2
    print(f"loaded {len(syms)} symbols, avg span {years:.2f} years, {time.time()-t0:.1f}s", flush=True)

    results = []
    for idea in ideas:
        t1 = time.time()
        per_sym, gl, tl = {}, [], []
        for sym, F in syms.items():
            L, S = idea["fn"](F, idea["params"])
            L = onset(np.asarray(L, dtype=bool))
            S = onset(np.asarray(S, dtype=bool))
            g, ts = simulate(F, L, S)
            if g.size:
                per_sym[sym] = g
                gl.append(g)
                tl.append(ts)
        m = summarize(per_sym, gl, tl, years, mid_ts)
        m.update(idea_id=idea["idea_id"], family=idea["family"], name=idea["name"],
                 params_json=idea["params_json"], elapsed_s=time.time() - t1)
        results.append(m)

    # Unconditional baselines under the same shared exit (what "positive" should be read against).
    base = {}
    for side in ("L", "S", "every24_L"):
        gl = []
        for F in syms.values():
            L, Sg = np.zeros(F.n, bool), np.zeros(F.n, bool)
            if side == "L":
                L[:] = True
            elif side == "S":
                Sg[:] = True
            else:
                L[::24] = True
            gl.append(simulate(F, L, Sg)[0])
        g = np.concatenate(gl) - COST_BPS
        base[side] = (int(g.size), float(g.mean()))
    print("baselines (n, net bps/trade):", base, flush=True)

    eligible = sorted([r for r in results if r.get("eligible")], key=lambda r: -r["composite_score"])
    rank = {r["idea_id"]: i + 1 for i, r in enumerate(eligible)}
    for r in results:
        r["composite_rank"] = rank.get(r["idea_id"], "")

    # IDEAS.csv
    ideas_cols = ["idea_id", "family", "name", "params_json", "mechanism_one_liner", "rationale_one_liner"]
    write_csv(HERE / "IDEAS.csv", ideas_cols, [
        dict(idea_id=i["idea_id"], family=i["family"], name=i["name"], params_json=i["params_json"],
             mechanism_one_liner=i["desc"] + f" Params: {i['params_json']}. Entry next 1h open; stop 1.5xATR14; target 3.0xATR14; max hold 24 bars; cost 12bp RT.",
             rationale_one_liner=i["why"])
        for i in ideas])

    # RESULTS.csv
    res_cols = ["idea_id", "family", "name", "params_json", "n_trades", "n_symbols_traded", "win_rate",
                "profit_factor", "expectancy_bps_net", "expectancy_bps_gross", "sd_bps_net", "t_stat",
                "rough_sharpe", "trades_per_year", "pos_symbol_frac", "ev_first_half_bps",
                "ev_second_half_bps", "both_halves_positive", "eligible", "composite_score",
                "composite_rank", "data_flag", "elapsed_s"]
    write_csv(HERE / "RESULTS.csv", res_cols, results)

    # RANKED_TOP20.md
    top = eligible[:20]
    lines = ["# RANKED TOP 20 - EXPLORATORY SCREEN ONLY (lane F: candlestick / price-action)", "",
             f"> {LABEL}", "",
             f"Method: {len(syms)} crypto perps, 1h TRAIN bars via data_access.iter_train_bars; shared exit "
             "(stop 1.5 ATR14, target 3.0 ATR14, 24-bar max hold, 12bp RT cost, one position per symbol, "
             "next-bar-open entry, onset-filtered signals). Ranking = composite = t(net bps) x (0.5 + 0.5 x "
             "fraction of symbols with positive mean). Eligibility: >= 100 trades and >= 10 symbols.", "",
             f"Scored {sum(1 for r in results if r['n_trades']>0)} of {len(ideas)} ideas with at least one trade; "
             f"{len(eligible)} met eligibility.", "",
             "| rank | id | name | composite | trades | net bps/trade | win % | PF | t | pos-sym % | EV 1st half | EV 2nd half | both halves > 0 |",
             "|---|---|---|---|---|---|---|---|---|---|---|---|---|"]
    for i, r in enumerate(top, 1):
        lines.append(f"| {i} | {r['idea_id']} | {r['name']} | {r['composite_score']:.2f} | {r['n_trades']} | "
                     f"{r['expectancy_bps_net']:.1f} | {100*r['win_rate']:.1f} | {r['profit_factor']:.2f} | "
                     f"{r['t_stat']:.2f} | {100*r['pos_symbol_frac']:.0f} | {r['ev_first_half_bps']:.1f} | "
                     f"{r['ev_second_half_bps']:.1f} | {'yes' if r['both_halves_positive'] else 'no'} |")
    lines += ["", "## Rationale (one line each)", ""]
    fam_why = {f[0]: f[3] for f in FAMILIES}
    fam_ideas = {i["idea_id"]: i for i in ideas}
    for i, r in enumerate(top, 1):
        idea = fam_ideas[r["idea_id"]]
        stab = "both halves positive" if r["both_halves_positive"] else "not stable across halves"
        lines.append(f"{i}. **{r['idea_id']} {r['name']}** - {idea['desc']} Stats: t={r['t_stat']:.2f}, "
                     f"{r['n_trades']} trades, {stab}.")
    lines += ["", "## Caveats", "",
              "- EXPLORATORY ONLY. 249 ideas screened with no multiple-testing correction; with this many "
              "candidates, several top-20 entries are expected to be false positives.",
              f"- Baselines under the same exit and cost (net bps/trade): unconditional long every bar "
              f"{base['L'][1]:.1f} (n={base['L'][0]}), unconditional short every bar {base['S'][1]:.1f} "
              f"(n={base['S'][0]}), long every 24th bar {base['every24_L'][1]:.1f} (n={base['every24_L'][0]}). "
              f"Median net EV across scored ideas is "
              f"{np.median([r['expectancy_bps_net'] for r in results if r['n_trades'] > 0]):.1f} bps; "
              f"{sum(1 for r in results if r['n_trades'] > 0 and r['expectancy_bps_net'] > 0)} of "
              f"{sum(1 for r in results if r['n_trades'] > 0)} ideas are net positive. A positive "
              "number therefore beats a strongly negative unconditional baseline, but this is a bull-skewed "
              "window: the baseline long is itself near zero-to-negative after costs, and side-split checks "
              "were not run.",
              "- Sample is one 1h TRAIN window (~2.7 years) that is strongly bull-skewed; a rule that "
              "works here may only be trend/beta exposure. Trend-context variants are included but not "
              "regime-tested. The 'both halves > 0' column is the cheapest stability proxy in this screen; "
              "most top-ranked ideas fail it.",
              "- Signals are onset-filtered and traded greedily one position per symbol; trade counts "
              "overlap across symbols, so the t-statistic overstates independent evidence.",
              "- Shared exit (1.5/3.0 ATR, 24 bars) is not tuned per family. Pattern families whose edge lives "
              "on a different horizon will rank low here without that being evidence they are dead.",
              "- Pattern rules are discretionary-style approximations (e.g. 'doji', 'pin bar', 'flag', "
              "'pennant' via OLS slope sign); parameter grids are small and hand-picked, not optimized.",
              "- Composite is comparable only within this lane; do not compare directly to C/A/B lane composites "
              "(different exits and symbol universes).",
              "- Families overlapping the EXPLORE500 C lane (vol-compression/flag breakout, consecutive-run "
              "exhaustion) converge with that lane's ranks; treat that as correlation of the same mechanism, "
              "not independent confirmation.",
              "- Nothing here is a validated candidate. Any lead requires a separate preregistration, synthetic tests, "
              "and a resource-gated TRAIN run."]
    (HERE / "RANKED_TOP20.md").write_text("\n".join(lines) + "\n", encoding="utf-8")

    print(f"done in {time.time()-t0:.1f}s; eligible={len(eligible)}", flush=True)
    for r in top[:10]:
        print(r["idea_id"], r["name"], round(r["composite_score"], 3), r["n_trades"],
              round(r["expectancy_bps_net"], 2), flush=True)


if __name__ == "__main__":
    main()
