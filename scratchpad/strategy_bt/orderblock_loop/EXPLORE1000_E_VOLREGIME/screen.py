#!/usr/bin/env python3
# EXPLORATORY SCREEN ONLY - not part of the 13-round preregistered G-gate track, not added to TRAIN_TRIALS.csv, no promotion without separate formal preregistration + synthetic tests + resource-gated TRAIN run.
"""Lane E (volatility regime as the primary signal) exploratory screen, ~250 ideas.

Run:
    /opt/anaconda3/bin/python3 <this file>

Reads only TRAIN-cutoff-safe 1h bars via data_access.iter_train_bars (same loader the
formal pipeline uses). Writes IDEAS.csv, RESULTS.csv and RANKED_TOP20.md next to this file.

Conventions (match EXPLORE500 lanes A/B/C so ranks are comparable within this lane):
- Signal evaluated on bar t close; entry at next bar open (t+1).
- Signals fire on onset (condition true on bar t, false on t-1) for every side.
- Exit profiles (ATR14 measured at bar t):
    std  = stop 1.5 ATR, target 3.0 ATR, max hold 24 bars   (shared lane-C convention)
    wide = stop 2.5 ATR, no target (99 ATR), max hold 72 bars (trend-holding profile)
- Intrabar ambiguity: stop checked before target. Gap through stop fills at the open.
- One position per symbol at a time (greedy, in time order).
- Round-trip cost 12 bp subtracted from every trade.
- No look-ahead: every rolling window ends at bar t; the 4h-vol feature uses only the
  last COMPLETED 4h bucket. Percentile ranks use trailing windows only.
- Composite score = t_stat(net bps) x (0.5 + 0.5 x fraction of symbols with positive mean),
  eligible if >= 100 pooled trades and >= 10 symbols traded (identical to lane C).
- A null calibration (random entries at matched cost/exit) is printed in RANKED_TOP20.md
  so the reader can see what composite values noise alone produces.
"""
from __future__ import annotations

import csv
import itertools
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
MIN_TRADES = 100
MIN_SYMBOLS = 10
MIN_BARS = 1000
EXITS = {"std": (1.5, 3.0, 24), "wide": (2.5, 99.0, 72)}  # (stop ATR, target ATR, max hold bars)
H4_MS = 4 * 3600 * 1000
LN2 = float(np.log(2.0))
NULL_SEEDS = 20
NULL_P = 0.01  # per-bar probability of a random long and of a random short


# ----------------------------------------------------------------------------
# Feature construction (per symbol) with a lazy cache so shared features are computed once
# ----------------------------------------------------------------------------
def make_features(a: dict) -> dict:
    o, h, l, c, v = (pd.Series(a[k]) for k in ("o", "h", "l", "c", "v"))
    pc = c.shift(1)
    r = np.log(c / pc)
    tr = pd.concat([h - l, (h - pc).abs(), (l - pc).abs()], axis=1).max(axis=1)
    F = dict(n=len(c), ts=a["ts"], o=o, h=h, l=l, c=c, v=v, r=r, pc=pc, tr=tr,
             atr=tr.rolling(14).mean(), cache={})
    F["o_np"], F["h_np"], F["l_np"], F["c_np"] = (x.to_numpy(float) for x in (o, h, l, c))
    return F


def cget(F, key, make):
    cache = F["cache"]
    if key not in cache:
        cache[key] = make()
    return cache[key]


def rv(F, W):
    return cget(F, ("rv", W), lambda: F["r"].rolling(W).std())


def ev(F, hl):
    """EWMA volatility (sqrt of EWMA of squared log returns) with half-life hl bars."""
    return cget(F, ("ev", hl), lambda: np.sqrt((F["r"] ** 2).ewm(halflife=hl, adjust=False).mean()))


def rvpct(F, W, L):
    """Trailing percentile rank of W-bar realized vol within its own trailing L-bar history."""
    return cget(F, ("rvpct", W, L),
                lambda: rv(F, W).rolling(L, min_periods=L // 2).rank(pct=True))


def ret(F, N):
    return cget(F, ("ret", N), lambda: np.log(F["c"] / F["c"].shift(N)))


def sma(F, N):
    return cget(F, ("sma", N), lambda: F["c"].rolling(N).mean())


def sd(F, N):
    return cget(F, ("sd", N), lambda: F["c"].rolling(N).std())


def bw(F, N=20):
    return cget(F, ("bw", N), lambda: 4.0 * sd(F, N) / sma(F, N))


def bwpct(F, N, L):
    return cget(F, ("bwpct", N, L), lambda: bw(F, N).rolling(L, min_periods=L // 2).rank(pct=True))


def hi_prev(F, N):
    return cget(F, ("hi", N), lambda: F["c"].shift(1).rolling(N).max())


def lo_prev(F, N):
    return cget(F, ("lo", N), lambda: F["c"].shift(1).rolling(N).min())


def vol_parkinson(F, W):
    lh = np.log(F["h"] / F["l"])
    return cget(F, ("pk", W), lambda: np.sqrt((lh ** 2).rolling(W).mean() / (4 * LN2)))


def lr_long(F):
    return cget(F, ("lr2000",), lambda: np.sqrt((F["r"] ** 2).rolling(2000, min_periods=500).mean()))


def intertf_div(F):
    """log(1h realized vol over 24 bars / 4h realized vol per hour), 4h vol from the last
    COMPLETED 4h bucket only (no look-ahead). Positive = 1h louder than the 4h backdrop."""
    def make():
        buckets = F["ts"] // H4_MS
        c4 = pd.Series(F["c_np"], index=buckets).groupby(level=0).last()
        r4 = np.log(c4).diff()
        v4 = r4.rolling(24, min_periods=12).std()
        prev = buckets - 1  # last bucket completed before bar t opens
        v4_bar = v4.reindex(prev).to_numpy()
        v4_bar = pd.Series(v4_bar).ffill().to_numpy() / 2.0  # 4h std -> per-hour std
        return np.log(rv(F, 24).to_numpy() / v4_bar)
    arr = cget(F, ("div41",), make)
    return pd.Series(arr, index=F["c"].index)


def gate_mask(F, gate: str):
    kind, thr = gate.split("_")
    pct = rvpct(F, 168, 1440)
    return (pct <= float(thr)) if kind == "lo" else (pct >= float(thr))


# ----------------------------------------------------------------------------
# Event helpers
# ----------------------------------------------------------------------------
def onset_up(x: pd.Series, X: float) -> pd.Series:
    return (x > X) & (x.shift(1) <= X)


def onset_dn(x: pd.Series, X: float) -> pd.Series:
    return (x < X) & (x.shift(1) >= X)


def dirs(cond: pd.Series, sign: pd.Series, mode: str):
    """cont: trade with sign(sign); fade: trade against it."""
    up, dn = cond & (sign > 0), cond & (sign < 0)
    return (up, dn) if mode == "cont" else (dn, up)


# ----------------------------------------------------------------------------
# Family signal functions: fn(p, F) -> (long_bool Series, short_bool Series)
# ----------------------------------------------------------------------------
def f_ewma_expand(p, F):
    trig = onset_up(ev(F, 6) / ev(F, 168), p["X"])
    return dirs(trig, ret(F, p["N"]), p["mode"])


def f_gate_trend(p, F):
    g = gate_mask(F, p["gate"])
    if p["sig"] == "tsm":
        R = ret(F, p["N"])
        return onset_up(R, 0.0) & g, onset_dn(R, 0.0) & g
    c = F["c"]
    return (c > hi_prev(F, p["N"])) & g, (c < lo_prev(F, p["N"])) & g


def f_gate_revert(p, F):
    g = gate_mask(F, p["gate"])
    dist = (F["c"] - sma(F, p["N"])) / F["atr"]
    return (dist <= -p["k"]) & g, (dist >= p["k"]) & g


def f_vov(p, F):
    W = p["W"]
    lv = cget(F, ("logrv24",), lambda: np.log(rv(F, 24)))
    vov = cget(F, ("vov", W), lambda: lv.rolling(W).std())
    z = (vov - vov.rolling(W).mean()) / vov.rolling(W).std()
    return dirs(z >= p["zt"], ret(F, p["D"]), p["mode"])


def f_range_exp(p, F):
    h, l, c, o = F["h"], F["l"], F["c"], F["o"]
    rng = (h - l).replace(0.0, np.nan)
    rex = (rng / F["atr"].shift(1)) >= p["k"]
    clv = (c - l) / rng
    bull = rex & (clv >= p["q"]) & (c > o)
    bear = rex & (clv <= 1 - p["q"]) & (c < o)
    return (bull, bear) if p["mode"] == "cont" else (bear, bull)


def f_bbw_sq(p, F):
    pct = bwpct(F, 20, p["L"])
    sq = pct.shift(1) <= p["p"]
    m, s, b = sma(F, 20), sd(F, 20), bw(F, 20)
    rising = b > b.shift(1)
    up = (F["c"] > m + 2 * s) & rising
    dn = (F["c"] < m - 2 * s) & rising
    return (sq & up, sq & dn) if p["mode"] == "cont" else (sq & dn, sq & up)


def f_bbw_ext(p, F):
    pct = bwpct(F, 20, p["L"])
    trig = (pct >= p["q"]) & (pct.shift(1) < p["q"])
    m, s = sma(F, 20), sd(F, 20)
    return trig & (F["c"] <= m - 2 * s), trig & (F["c"] >= m + 2 * s)


def f_intertf(p, F):
    d = intertf_div(F)
    cond = (d <= -p["thr"]) if p["mode"] == "calm1h" else (d >= p["thr"])
    return dirs(cond, ret(F, 24), p["dir"])


def f_garch(p, F):
    hl = {"fast": 11, "slow": 34}[p["hl"]]
    ratio = ev(F, hl) / lr_long(F)
    trig = onset_dn(ratio, p["thr"])
    return dirs(trig, ret(F, 24), p["mode"])


def f_vol_decay(p, F):
    ratio = rv(F, 24) / rv(F, 720)
    recent = ratio.shift(1).rolling(48).max() >= p["X"]
    decay = onset_dn(ratio, p["d"]) & recent
    return dirs(decay, ret(F, p["D"]), "cont")


def f_spike_disl(p, F):
    vs = rv(F, 12) / rv(F, 168)
    m = (F["c"] - F["c"].shift(p["K"])) / F["atr"]
    spike = vs >= p["X"]
    return spike & (m <= -p["k"]), spike & (m >= p["k"])


def f_vol_extreme(p, F):
    pct = rvpct(F, 168, 1440)
    trig = (pct >= p["p"]) & (pct.shift(1) < p["p"])
    return dirs(trig, ret(F, p["N"]), p["mode"])


def f_calm_dir(p, F):
    pct = rvpct(F, 168, 1440)
    trig = (pct <= p["p"]) & (pct.shift(1) > p["p"])
    return dirs(trig, ret(F, p["N"]), p["mode"])


def f_calm_drift(p, F):
    pct = rvpct(F, 168, 1440)
    trig = (pct <= p["p"]) & (pct.shift(1) > p["p"])
    none = pd.Series(False, index=F["c"].index)
    return (trig, none) if p["side"] == "long" else (none, trig)


def f_exp_break(p, F):
    trig = onset_up(ev(F, 6) / ev(F, 168), p["X"])
    recent = trig.rolling(3, min_periods=1).max() > 0
    c = F["c"]
    return recent & (c > hi_prev(F, p["N"])), recent & (c < lo_prev(F, p["N"]))


def f_rv_sq(p, F):
    sq = (rv(F, 24) / rv(F, 336)).shift(1) <= p["q"]
    c = F["c"]
    up = c > hi_prev(F, p["N"])
    dn = c < lo_prev(F, p["N"])
    return (sq & up, sq & dn) if p["mode"] == "cont" else (sq & dn, sq & up)


def f_range_vs_close(p, F):
    pr = vol_parkinson(F, p["W"]) / rv(F, p["W"])
    trig = (pr >= p["thr"]) & (pr.shift(1) < p["thr"])
    bull = F["r"] > 0
    bear = F["r"] < 0
    return (trig & bull, trig & bear) if p["mode"] == "fade" else (trig & bear, trig & bull)


# ----------------------------------------------------------------------------
# Family table: grid, function, mechanism template, rationale, prior likelihood (0-10)
# ----------------------------------------------------------------------------
FAMILIES = [
    dict(key="ewma_vol_expand_dir", grid=dict(X=[1.5, 2.0], N=[6, 24], mode=["cont", "fade"], exit=["std", "wide"]),
         fn=f_ewma_expand,
         mech="At onset of EWMA-vol ratio (halflife 6 bars / halflife 168 bars) crossing above {X}, trade {mode} the sign of the {N}-bar log return.",
         why="Fast-vs-slow EWMA vol crossovers mark volatility-regime transitions; the direction of the first move after an expansion may persist (cont) or over-extend (fade).",
         prior=5, note="EWMA regime switch with directional tie-break; cont vs fade is a genuine open question"),
    dict(key="vol_gated_breakout", grid=dict(gate=["lo_0.2", "lo_0.35", "hi_0.65", "hi_0.8"], N=[24, 96],
                                             sig=["tsm", "dch"], exit=["std", "wide"]),
         fn=f_gate_trend,
         mech="Trade a directional signal ({sig}: tsmom sign cross if tsm, close beyond {N}-bar channel if dch) only while 168-bar realized-vol percentile is in regime {gate} (lo_x: pct<=x; hi_x: pct>=x).",
         why="Vol-regime-gated trend following: trend signals are traded only in low-vol (orderly trends) or high-vol (liquidation-driven runs) regimes.",
         prior=6, note="vol-regime gate on trend; gate thresholds on trailing percentile, no look-ahead"),
    dict(key="vol_gated_stretch_revert", grid=dict(gate=["lo_0.2", "lo_0.35", "hi_0.65", "hi_0.8"], N=[20, 50],
                                                   k=[1.5, 2.5]),
         fn=f_gate_revert,
         mech="Fade price stretched {k} ATR14 from SMA{N}, only while 168-bar realized-vol percentile is in regime {gate}.",
         why="Mean reversion is expected to work in quiet regimes and fail in breakouts; the gate tests whether the regime, not the stretch, separates winners from losers.",
         prior=5, note="gated stretch fade; overlaps ema_dist_revert in C but gate is the variable"),
    dict(key="vol_of_vol_spike", grid=dict(W=[168, 720], zt=[2.0, 3.0], D=[6, 24], mode=["cont", "fade"]),
         fn=f_vov,
         mech="When the z-score (window {W}) of the rolling std of log(1h realized vol) reaches {zt} (vol-of-vol spike, onset), trade {mode} the sign of the {D}-bar return.",
         why="Vol-of-vol spikes mark regime instability; whether the subsequent move continues or reverts is tested directly, with no price-structure condition.",
         prior=4, note="vol-of-vol trigger; both reversal and continuation tested"),
    dict(key="range_expansion_bar", grid=dict(k=[1.5, 2.0, 2.5], q=[0.75, 0.85], mode=["cont", "fade"],
                                              exit=["std", "wide"]),
         fn=f_range_exp,
         mech="When bar range >= {k} x prior ATR14 and close is in the top (bottom) {q} of its range, trade {mode} the bar direction, entry next open.",
         why="Range-expansion days with decisive closes: follow-through versus fade is an empirical question about whether volatility shocks carry information.",
         prior=5, note="close-location filter distinguishes decisive from indecisive expansion bars"),
    dict(key="bb_width_squeeze_release", grid=dict(p=[0.1, 0.2], L=[200, 500], mode=["cont", "fade"],
                                                   exit=["std", "wide"]),
         fn=f_bbw_sq,
         mech="Bollinger-width percentile (L={L}-bar window) <= {p} on bar t-1 (squeeze); on bar t a close beyond the 2-sigma band with width rising, trade {mode}.",
         why="Bandwidth-percentile squeeze release, with longer percentile windows than the classic 100-bar squeeze.",
         prior=6, note="overlaps M001/M002 in lane A; distinct via 200/500-bar percentile and fade variant"),
    dict(key="bb_width_extreme_fade", grid=dict(q=[0.9, 0.95], L=[200, 500], exit=["std"]),
         fn=f_bbw_ext,
         mech="Onset of Bollinger-width percentile >= {q} (L={L}); fade a close beyond the 2-sigma band (long below lower, short above upper).",
         why="Extreme band width with price at a band edge signals capitulation, expecting a snap-back toward the mean.",
         prior=4, note="band-width extreme with band-edge confirmation"),
    dict(key="intertf_vol_divergence", grid=dict(thr=[0.4, 0.7], mode=["calm1h", "loud1h"], dir=["cont", "fade"],
                                                 exit=["std", "wide"]),
         fn=f_intertf,
         mech="log(1h vol24 / 4h vol per hour, 24 4h-bars, last completed bucket) beyond {thr} (mode {mode}); trade {dir} the sign of the 24-bar return.",
         why="When short-horizon volatility disagrees with the longer-horizon backdrop, the direction of the 24-bar move may persist (cont) or reverse (fade).",
         prior=4, note="inter-timeframe vol divergence; 4h vol uses only completed 4h buckets"),
    dict(key="ewma_garch_calm_switch", grid=dict(hl=["fast", "slow"], thr=[0.6, 0.8], mode=["cont", "fade"],
                                                 exit=["std", "wide"]),
         fn=f_garch,
         mech="At onset of EWMA-vol (halflife {hl}-profile, 11 or 34 bars) / 2000-bar RMS vol falling below {thr} (calm onset), trade {mode} the 24-bar return sign.",
         why="GARCH-like vol clustering heuristic: a fall into a calm regime after a long-run baseline may set up direction-following or reversal.",
         prior=4, note="simple EWMA regime switch as GARCH proxy; no fitted parameters"),
    dict(key="vol_spike_decay_cont", grid=dict(X=[2.0, 3.0], d=[1.0, 1.2], D=[24, 48], exit=["std", "wide"]),
         fn=f_vol_decay,
         mech="After 24-bar/720-bar vol ratio reached {X} in the last 48 bars, at onset of decay back below {d}, go with the sign of the {D}-bar return.",
         why="Post-spike decay: once volatility normalizes, the direction set during the spike may continue as trend-following capital returns.",
         prior=4, note="post-shock continuation; state-based trigger"),
    dict(key="vol_spike_dislocation_bounce", grid=dict(X=[2.0, 3.0], k=[2.0, 3.0], K=[6, 12], exit=["std", "wide"]),
         fn=f_spike_disl,
         mech="When 12-bar vol / 168-bar vol >= {X} and the {K}-bar move is <= -{k} ATR (up if >= +{k}), trade against the move (capitulation bounce).",
         why="Liquidation-driven vol spikes with a large dislocation tend to over-shoot; the bounce captures the normalization.",
         prior=5, note="overlaps C vol_spike_fade in spirit but requires a price dislocation"),
    dict(key="vol_extreme_regime_dir", grid=dict(p=[0.9, 0.95, 0.98], N=[12, 24], mode=["cont", "fade"], exit=["std"]),
         fn=f_vol_extreme,
         mech="Onset of 168-bar realized-vol percentile >= {p} (vs trailing 1440 bars); trade {mode} the {N}-bar return sign.",
         why="Extreme-vol regime onset: whether direction persists or unwinds during very high volatility is tested directly.",
         prior=4, note="vol-regime direction test"),
    dict(key="calm_regime_dir", grid=dict(p=[0.05, 0.1, 0.2], N=[12, 24], mode=["cont", "fade"], exit=["std"]),
         fn=f_calm_dir,
         mech="Onset of 168-bar realized-vol percentile <= {p} (calm regime); trade {mode} the {N}-bar return sign.",
         why="Calm regime direction test: quiet markets may trend cleanly (cont) or drift back (fade).",
         prior=4, note="calm-regime direction test"),
    dict(key="calm_regime_drift", grid=dict(p=[0.05, 0.15], side=["long", "short"], exit=["std"]),
         fn=f_calm_drift,
         mech="At onset of 168-bar realized-vol percentile <= {p} (calm), unconditionally {side}. Proxy for a short-vol / carry-like premium that accrues while volatility is low (OHLCV only, no options).",
         why="Volatility risk premium proxy: in calm regimes, long exposure is often rewarded; the short side is a control.",
         prior=3, note="VRP proxy on OHLCV only; NOT an options-based VRP estimate"),
    dict(key="vol_expansion_breakout", grid=dict(X=[1.5, 2.0], N=[12, 24, 48], exit=["std", "wide"]),
         fn=f_exp_break,
         mech="Within 3 bars after EWMA-vol ratio (6/168) crosses above {X}, take a close beyond the prior {N}-bar channel (long up, short down).",
         why="Volatility expansion plus price breakout: the breakout is only taken as volatility regime shifts up.",
         prior=5, note="vol-onset breakout; differs from C vol_compr_break (ATR-ratio compression)"),
    dict(key="rv_squeeze_channel_break", grid=dict(q=[0.5, 0.6], N=[24, 48], mode=["cont", "fade"], exit=["std", "wide"]),
         fn=f_rv_sq,
         mech="When 24-bar / 336-bar realized-vol ratio <= {q} (squeeze, prior bar), trade {mode} a close beyond the prior {N}-bar channel.",
         why="Realized-vol squeeze (close-to-close) released by a channel break; cont vs fade tests whether low-vol breakouts are real.",
         prior=5, note="realized-vol squeeze, distinct from ATR-based C vol_compr_break"),
    dict(key="intrabar_range_noise", grid=dict(thr=[1.2, 1.5], W=[72, 168], mode=["fade", "cont"], exit=["std"]),
         fn=f_range_vs_close,
         mech="When Parkinson (high-low) vol / close-to-close vol over {W} bars crosses above {thr} (intrabar noise dominates), {mode} the last bar direction.",
         why="When high-low range overstates close-to-close vol, the last bar is more likely noise and may reverse (fade).",
         prior=3, note="estimator-divergence regime; weak theory"),
]

FAMILY_MECH_SUFFIX = " Entry next 1h open; stop/target/hold per exit profile (std=1.5/3.0 ATR, 24 bars; wide=2.5 ATR stop, no target, 72 bars); cost 12bp RT."


def expand_ideas():
    ideas = []
    for fam_index, fam in enumerate(FAMILIES):
        keys = list(fam["grid"].keys())
        for values in itertools.product(*fam["grid"].values()):
            p = dict(zip(keys, values))
            mech = fam["mech"].format(**p) + FAMILY_MECH_SUFFIX
            ideas.append(dict(family=fam["key"], fam_index=fam_index, params=p, mech=mech,
                              why=fam["why"], prior=fam["prior"], note=fam["note"], fn=fam["fn"]))
    for i, idea in enumerate(ideas, start=1):
        idea["idea_id"] = f"E{i:03d}"
        suffix = "_".join(f"{k}{v}" for k, v in idea["params"].items())
        idea["name"] = f"{idea['family']}_{suffix}"
    return ideas


# ----------------------------------------------------------------------------
# Data load
# ----------------------------------------------------------------------------
def load_universe():
    syms = {}
    dropped = []
    for sym, bars, _funding in iter_train_bars(TF):
        bars = [b for b in bars if b.complete]
        if len(bars) < MIN_BARS:
            dropped.append(sym)
            continue
        a = dict(ts=np.array([b.timestamp for b in bars], dtype=np.int64),
                 o=np.array([b.open for b in bars]), h=np.array([b.high for b in bars]),
                 l=np.array([b.low for b in bars]), c=np.array([b.close for b in bars]),
                 v=np.array([b.volume for b in bars]))
        syms[sym] = make_features(a)
    return syms, dropped


# ----------------------------------------------------------------------------
# Trade simulation (identical logic to lane C, with exit profile parameter)
# ----------------------------------------------------------------------------
def simulate(F, L, S, exit_key):
    """Return (raw_gross_bps, market_hedged_gross_bps) arrays for the greedy-taken trades.

    Hedged = trade gross minus d x (equal-weight basket log return over the same bars),
    which strips the common crypto drift that dominates a 2.7-year bull-leaning sample.
    """
    empty = (np.array([]), np.array([]))
    stop_k, tgt_k, hold = EXITS[exit_key]
    n = F["n"]
    sig = np.flatnonzero(L | S)
    if sig.size == 0:
        return empty
    d = np.where(L[sig], 1, -1)
    e = sig + 1
    atr = F["atr"].to_numpy(float)[sig]
    keep = (e + hold <= n) & np.isfinite(atr) & (atr > 0)
    d, e, atr = d[keep], e[keep], atr[keep]
    if e.size == 0:
        return empty
    o, h, l, c = F["o_np"], F["h_np"], F["l_np"], F["c_np"]
    entry = o[e]
    stop = entry - d * stop_k * atr
    target = entry + d * tgt_k * atr
    T = e.size
    exit_px = np.full(T, np.nan)
    exit_k = np.full(T, hold - 1, dtype=int)
    done = np.zeros(T, dtype=bool)
    for k in range(hold):
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
    exit_px = np.where(~done, c[e + hold - 1], exit_px)
    exit_idx = e + exit_k
    gross = d * (exit_px - entry) / entry * 1e4
    taken, nxt = [], -1
    for i in range(T):
        if e[i] > nxt:
            taken.append(i)
            nxt = exit_idx[i]
    tk = np.asarray(taken, dtype=int)
    mk = F["mkt_cum"]
    mkt_bps = (mk[exit_idx[tk]] - mk[e[tk] - 1]) * 1e4
    hedged = gross[tk] - d[tk] * mkt_bps
    return gross[tk], hedged


def onset_np(x: np.ndarray) -> np.ndarray:
    prev = np.concatenate([[False], x[:-1]])
    return x & ~prev


def run_idea(idea, syms):
    exit_key = idea["params"].get("exit", "std")
    per_sym = {}
    for sym, F in syms.items():
        L, S = idea["fn"](idea["params"], F)
        L = onset_np(np.asarray(L, dtype=bool))
        S = onset_np(np.asarray(S, dtype=bool))
        g, hg = simulate(F, L, S, exit_key)
        if g.size:
            per_sym[sym] = (g, hg)
    return per_sym


def _stats(net: np.ndarray, n_syms: int, sym_nets: list, years: float):
    """Shared t-stat / composite helper. net = per-trade net bps (after cost)."""
    n = net.size
    sdv = float(net.std(ddof=1)) if n > 1 else float("nan")
    mean = float(net.mean())
    t_stat = mean / (sdv / np.sqrt(n)) if sdv and sdv > 0 else 0.0
    pos_frac = float(np.mean([m > 0 for m in sym_nets])) if sym_nets else 0.0
    eligible = n >= MIN_TRADES and n_syms >= MIN_SYMBOLS
    composite = t_stat * (0.5 + 0.5 * pos_frac) if eligible else float("nan")
    return dict(mean=mean, sd=sdv, t=float(t_stat), pos_frac=pos_frac,
                eligible=bool(eligible), composite=float(composite), rough=(mean / sdv * np.sqrt(n / years)
                                                                          if sdv and sdv > 0 else float("nan")))


def summarize(per_sym, years):
    if not per_sym:
        return dict(n_trades=0, n_symbols_traded=0, eligible=False, composite_score=float("nan"),
                    hedged_composite=float("nan"))
    gross = np.concatenate([g for g, _ in per_sym.values()])
    hedged = np.concatenate([h for _, h in per_sym.values()])
    net = gross - COST_BPS
    hnet = hedged - COST_BPS
    n = net.size
    wins, losses = net[net > 0].sum(), -net[net < 0].sum()
    pf = wins / losses if losses > 0 else (99.0 if wins > 0 else 0.0)
    raw = _stats(net, len(per_sym), [float((g - COST_BPS).mean()) for g, _ in per_sym.values() if g.size >= 5],
                 years)
    hdg = _stats(hnet, len(per_sym), [float((h - COST_BPS).mean()) for _, h in per_sym.values() if h.size >= 5],
                 years)
    return dict(n_trades=n, n_symbols_traded=len(per_sym),
                win_rate=float((net > 0).mean()), profit_factor=float(pf),
                expectancy_bps_net=raw["mean"], expectancy_bps_gross=float(gross.mean()),
                sd_bps_net=raw["sd"], t_stat=raw["t"], rough_sharpe=raw["rough"],
                trades_per_year=float(n / years), pos_symbol_frac=raw["pos_frac"],
                eligible=bool(hdg["eligible"]), composite_score=raw["composite"],
                hedged_expectancy_bps_net=hdg["mean"], hedged_t_stat=hdg["t"],
                hedged_pos_symbol_frac=hdg["pos_frac"], hedged_composite=hdg["composite"],
                hedged_win_rate=float((hnet > 0).mean()))


def null_calibration(syms, years, exit_key="std"):
    """Random long/short entries at NULL_P per bar, same cost and std exit: noise yardstick."""
    rows = []
    for seed in range(NULL_SEEDS):
        rng = np.random.default_rng(seed)
        per_sym = {}
        for sym, F in syms.items():
            L = rng.random(F["n"]) < NULL_P
            S = rng.random(F["n"]) < NULL_P
            g, hg = simulate(F, L, S, exit_key)
            if g.size:
                per_sym[sym] = (g, hg)
        m = summarize(per_sym, years)
        rows.append((m["n_trades"], m.get("expectancy_bps_net", np.nan), m.get("t_stat", np.nan),
                     m.get("composite_score", np.nan), m.get("hedged_expectancy_bps_net", np.nan),
                     m.get("hedged_composite", np.nan)))
    return np.array(rows, dtype=float)


def attach_market(syms):
    """Equal-weight basket cumulative log return on each symbol's own bar index (no look-ahead:
    cum[t] includes only returns through bar t's close)."""
    rr = pd.DataFrame({s: pd.Series(F["r"].to_numpy(), index=F["ts"]) for s, F in syms.items()})
    rr = rr.sort_index()
    mkt_cum = rr.mean(axis=1, skipna=True).fillna(0.0).cumsum()
    for F in syms.values():
        F["mkt_cum"] = mkt_cum.reindex(F["ts"]).to_numpy()


def fmt(x, nd=4):
    if isinstance(x, (float, np.floating)):
        return "" if not np.isfinite(x) else f"{x:.{nd}f}"
    return x


def write_csv(path, header_cols, rows):
    with path.open("w", newline="", encoding="utf-8") as fh:
        fh.write(f"# {LABEL}\n")
        w = csv.DictWriter(fh, fieldnames=header_cols)
        w.writeheader()
        for r in rows:
            w.writerow({k: fmt(r.get(k, "")) for k in header_cols})


def main():
    t0 = time.time()
    ideas = expand_ideas()
    syms, dropped = load_universe()
    attach_market(syms)
    years = float(np.mean([(F["ts"][-1] - F["ts"][0]) / (365.25 * 24 * 3_600_000) for F in syms.values()]))
    print(f"{len(ideas)} ideas; loaded {len(syms)} symbols (dropped {len(dropped)} short), "
          f"avg span {years:.2f} years, {time.time()-t0:.1f}s", flush=True)

    prior_order = sorted(ideas, key=lambda x: (-x["prior"], x["fam_index"], x["idea_id"]))
    prior_rank = {x["idea_id"]: i + 1 for i, x in enumerate(prior_order)}

    results = []
    for idea in ideas:
        ts0 = time.time()
        per_sym = run_idea(idea, syms)
        m = summarize(per_sym, years)
        m.update(idea_id=idea["idea_id"], family=idea["family"], name=idea["name"],
                 prior_rank=prior_rank[idea["idea_id"]], prior_score=idea["prior"],
                 data_available=True, screened=True, elapsed_s=time.time() - ts0)
        results.append(m)

    eligible = [r for r in results if r.get("eligible")]
    eligible.sort(key=lambda r: -r["hedged_composite"])
    comp_rank = {r["idea_id"]: i + 1 for i, r in enumerate(eligible)}
    for r in results:
        r["composite_rank"] = comp_rank.get(r["idea_id"], "")

    with (HERE / "IDEAS.csv").open("w", newline="", encoding="utf-8") as fh:
        fh.write(f"# {LABEL}\n")
        w = csv.DictWriter(fh, fieldnames=["idea_id", "family", "name", "params", "mechanism_one_liner",
                                           "rationale_one_liner", "data_needed", "prior_rank_note"])
        w.writeheader()
        for idea in ideas:
            w.writerow(dict(idea_id=idea["idea_id"], family=idea["family"], name=idea["name"],
                            params=";".join(f"{k}={v}" for k, v in idea["params"].items()),
                            mechanism_one_liner=idea["mech"], rationale_one_liner=idea["why"],
                            data_needed="1h OHLCV only",
                            prior_rank_note=f"prior_rank={prior_rank[idea['idea_id']]}; "
                                            f"prior_score={idea['prior']}/10; {idea['note']}"))

    res_cols = ["idea_id", "family", "name", "data_available", "screened", "prior_rank", "prior_score",
                "n_trades", "n_symbols_traded", "win_rate", "profit_factor", "expectancy_bps_net",
                "expectancy_bps_gross", "sd_bps_net", "t_stat", "rough_sharpe", "trades_per_year",
                "pos_symbol_frac", "hedged_expectancy_bps_net", "hedged_win_rate", "hedged_t_stat",
                "hedged_pos_symbol_frac", "eligible", "composite_score", "hedged_composite",
                "composite_rank", "elapsed_s"]
    results.sort(key=lambda r: r["idea_id"])
    write_csv(HERE / "RESULTS.csv", res_cols, results)

    scored = [r for r in results if r["n_trades"] > 0]
    zero = [r["idea_id"] for r in results if r["n_trades"] == 0]
    top20 = eligible[:20]
    null = null_calibration(syms, years, "std")
    null_w = null_calibration(syms, years, "wide")
    null_t, null_c, null_e = null[:, 2], null[:, 3], null[:, 1]
    hnull_c, hnull_e = null[:, 5], null[:, 4]
    wnull_c = null_w[:, 5]
    lines = ["# RANKED TOP 20 - EXPLORATORY SCREEN ONLY (lane E: volatility regime)", "",
             f"> {LABEL}", "",
             f"Method: {len(syms)} crypto perps with TRAIN 1h bars ({len(dropped)} symbols with too few bars dropped), "
             "data_access.iter_train_bars. Shared engine with lane C: next-open entry, 12bp RT cost, one position per symbol, "
             "stop checked before target. Two exit profiles: std (1.5/3.0 ATR, 24 bars) and wide (2.5 ATR stop, no target, 72 bars). "
             "RANKING METRIC = hedged_composite: each trade's net bps minus d x (equal-weight 31-coin basket return over the same "
             "holding window), so common crypto drift in this bull-leaning sample is removed. "
             "hedged_composite = t(hedged net bps) x (0.5 + 0.5 x fraction of symbols with positive hedged mean). "
             "Raw (unhedged) composite_score is kept in RESULTS.csv for reference only. "
             "Eligibility: >= 100 pooled trades and >= 10 symbols.",
             "",
             f"Proposed {len(ideas)} ideas; scored {len(scored)} with at least one trade; "
             f"{len(eligible)} met eligibility; no-trade ideas: {len(zero)}. "
             "All ideas use OHLCV only, so none were data-blocked.", "",
             "| rank | idea_id | name | hedged composite | n_trades | hedged exp net bps | hedged win % | hedged t | hedged pos-sym % | raw exp net bps | prior rank |",
             "|---|---|---|---|---|---|---|---|---|---|---|"]
    for i, r in enumerate(top20, start=1):
        lines.append(f"| {i} | {r['idea_id']} | {r['name']} | {r['hedged_composite']:.2f} | {r['n_trades']} | "
                     f"{r['hedged_expectancy_bps_net']:.1f} | {100*r['hedged_win_rate']:.1f} | {r['hedged_t_stat']:.2f} | "
                     f"{100*r['hedged_pos_symbol_frac']:.0f} | {r['expectancy_bps_net']:.1f} | {r['prior_rank']} |")
    why_by_family = {f["key"]: f["why"] for f in FAMILIES}
    idea_by_id = {x["idea_id"]: x for x in ideas}
    lines += ["", "## Why-notes (top 20)", ""]
    for i, r in enumerate(top20, start=1):
        lines.append(f"{i}. **{r['name']}** ({r['idea_id']}): {why_by_family[r['family']]}")
    if len(eligible) >= 3:
        prior_e = pd.Series([r["prior_rank"] for r in eligible])
        emp_e = pd.Series([comp_rank[r["idea_id"]] for r in eligible])
        rho = float(prior_e.corr(emp_e, method="spearman"))
    else:
        rho = float("nan")
    lines += ["", "## Null calibration (random entries, same cost and std exit)", "",
              f"{NULL_SEEDS} seeds, random long and short at {NULL_P*100:.1f}% of bars each. "
              f"Pooled trades ~{np.median(null[:,0]):.0f} median. "
              f"Raw (unhedged) null expectancy (net bps): mean {np.mean(null_e):.1f}, range {np.min(null_e):.1f} to {np.max(null_e):.1f}. "
              f"Hedged null expectancy (net bps): mean {np.mean(hnull_e):.1f}, range {np.min(hnull_e):.1f} to {np.max(hnull_e):.1f}. "
              f"Hedged null composite: mean {np.nanmean(hnull_c):.2f}, max {np.nanmax(hnull_c):.2f}. "
              f"Raw null composite max {np.nanmax(null_c):.2f} (shows drift contamination of the raw metric). "
              f"Wide-exit hedged null composite: mean {np.nanmean(wnull_c):.2f}, max {np.nanmax(wnull_c):.2f}. "
              "Ideas whose hedged composite is not clearly above the hedged null band are indistinguishable from noise at this sample size.",
              "", "## Caveats", "",
              "- EXPLORATORY SCREEN ONLY. Not G-eligible, not added to TRAIN_TRIALS.csv or any ledger, not counted toward the 13-round cap.",
              "- No look-ahead audit beyond construction rules; no walk-forward and no out-of-sample split inside TRAIN.",
              "- No multiple-testing correction across the full grid; top t-stats are optimistic and selection-biased.",
              "- Regime dependence: the TRAIN span is dominated by a bull-leaning sample, and vol-regime percentiles are relative to the trailing 1440 bars, so a regime shift can flip conditional results.",
              "- Vol-regime gates are expressed as trailing percentiles, not fitted thresholds, but the thresholds themselves are a grid choice.",
              "- 'Wide' exit shares a single 72-bar hold across ideas; families whose edge lives on a different horizon are judged only on these two exits.",
              "- VRP-style ideas use OHLCV realized vol only. They are NOT options-based volatility risk premium estimates.",
              f"- Spearman rank correlation between the pre-run prior ranking and empirical composite ranking (eligible ideas): {rho:.2f}.",
              "- Exit confound: most of the top 20 use the 'wide' exit (no target, 72-bar hold). Compare within exit: see the std-exit list below.",
              "- Hedge caveat: hedging against one equal-weight basket assumes beta ~1 to the basket. Where a signal is mostly short in a bull sample, the hedge can flip the sign (e.g., E166 raw -133 bps, hedged +31 bps on 152 trades). Treat sign flips with suspicion.",
              "- Sample size: most top-20 ideas have 2,700 to 9,000 trades, but these are overlapping, serially correlated trades across 31 coins in one bull-leaning ~2.7-year span, so effective sample size is far smaller than the trade count.",
              "- Promotion to any candidate requires separate formal preregistration, synthetic tests, and a resource-gated TRAIN run."]
    std_elig = [r for r in eligible if "exitwide" not in r["name"]]
    lines += ["", "## Best standard-exit ideas (exit = std: 1.5/3.0 ATR, 24 bars), hedged ranking", "",
              "| rank | idea_id | name | hedged composite | n_trades | hedged exp net bps | hedged t |",
              "|---|---|---|---|---|---|---|"]
    for i, r in enumerate(std_elig[:5], start=1):
        lines.append(f"| {i} | {r['idea_id']} | {r['name']} | {r['hedged_composite']:.2f} | {r['n_trades']} | "
                     f"{r['hedged_expectancy_bps_net']:.1f} | {r['hedged_t_stat']:.2f} |")
    (HERE / "RANKED_TOP20.md").write_text("\n".join(lines) + "\n", encoding="utf-8")
    print(f"done in {time.time()-t0:.1f}s; scored {len(scored)}/{len(ideas)}; eligible {len(eligible)}", flush=True)
    print(f"null hedged composite max {np.nanmax(hnull_c):.2f}; raw null composite max {np.nanmax(null_c):.2f}", flush=True)
    for i, r in enumerate(top20[:10], start=1):
        print(i, r["idea_id"], r["name"], "hedged", round(r["hedged_composite"], 2), r["n_trades"],
              round(r["hedged_expectancy_bps_net"], 2), "raw", round(r["expectancy_bps_net"], 2), flush=True)


if __name__ == "__main__":
    main()
