#!/usr/bin/env python3
# EXPLORATORY SCREEN ONLY - not part of the 13-round preregistered G-gate track, not added to TRAIN_TRIALS.csv, no promotion without separate formal preregistration + synthetic tests + resource-gated TRAIN run.
"""Cheap read-only exploratory screen of 166 crypto factor / behavioural rules.

Run from anywhere:
    /opt/anaconda3/bin/python3 <this file>

Reads only the TRAIN-cutoff-safe 1h bars via data_access.iter_train_bars.
Writes IDEAS.csv, RESULTS.csv and RANKED_TOP20.md next to this file.

Conventions (shared by every idea in this lane):
- Signal evaluated on bar t close; entry at next bar open (t+1).
- Signal fires on onset (condition becomes true on bar t, was false on t-1).
- Stop = 1.5 x ATR14 (measured at bar t); target = 3.0 x ATR14 (2R).
- Max hold 24 bars; timeout exits at close of the 24th bar.
- Intrabar ambiguity: stop checked before target. Gap through stop fills at the open.
- One position per symbol at a time (greedy, in time order).
- Round-trip cost 12 bp subtracted from every trade.
- No look-ahead in features: every rolling window ends at bar t.
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
STOP_ATR = 1.5
TARGET_ATR = 3.0
MAX_HOLD = 24
MIN_TRADES = 100
MIN_SYMBOLS = 10
XS_LOOKBACKS = (24, 72, 168, 336)


# ----------------------------------------------------------------------------
# Feature helpers
# ----------------------------------------------------------------------------
def run_length(flag: np.ndarray) -> np.ndarray:
    out = np.zeros(len(flag), dtype=int)
    for i, f in enumerate(flag):
        if f:
            out[i] = (out[i - 1] if i else 0) + 1
    return out


def rsi(close: pd.Series, n: int) -> pd.Series:
    d = close.diff()
    gain = d.clip(lower=0.0).ewm(alpha=1.0 / n, adjust=False).mean()
    loss = (-d).clip(lower=0.0).ewm(alpha=1.0 / n, adjust=False).mean()
    return 100.0 - 100.0 / (1.0 + gain / loss)


def base_features(a: dict) -> dict:
    o, h, l, c, v = (pd.Series(a[k]) for k in ("o", "h", "l", "c", "v"))
    pc = c.shift(1)
    r = np.log(c / pc)
    tr = pd.concat([h - l, (h - pc).abs(), (l - pc).abs()], axis=1).max(axis=1)
    F = dict(n=len(c), ts=a["ts"], o=o, h=h, l=l, c=c, v=v, r=r, pc=pc, tr=tr,
             atr=tr.rolling(14).mean(), atr100=tr.rolling(100).mean(),
             sig168=r.rolling(168).std(), rv720=r.rolling(720).std(),
             hour=(a["ts"] // 3_600_000) % 24)
    up = (c > pc).fillna(False).to_numpy(bool)
    dn = (c < pc).fillna(False).to_numpy(bool)
    F["run_up"] = run_length(up)
    F["run_dn"] = run_length(dn)
    F["o_np"], F["h_np"], F["l_np"], F["c_np"] = (x.to_numpy(float) for x in (o, h, l, c))
    return F


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


def _cross_up(x: pd.Series) -> pd.Series:
    return (x > 0) & (x.shift(1) <= 0)


def _cross_dn(x: pd.Series) -> pd.Series:
    return (x < 0) & (x.shift(1) >= 0)


def _vr(F: dict, W: int, q: int = 4) -> pd.Series:
    r = F["r"]
    rq = np.log(F["c"] / F["c"].shift(q))
    return rq.rolling(W).var() / (q * r.rolling(W).var())


# ----------------------------------------------------------------------------
# Signal functions: return (long_bool, short_bool) Series, before onset filter
# ----------------------------------------------------------------------------
def sig_tsmom(p, F, mode):
    R = np.log(F["c"] / F["c"].shift(p["N"]))
    up, dn = _cross_up(R), _cross_dn(R)
    return (up, dn) if mode == "cont" else (dn, up)


def sig_kmove(p, F):
    z = np.log(F["c"] / F["c"].shift(p["k"])) / (F["sig168"] * np.sqrt(p["k"]))
    return z <= -p["z"], z >= p["z"]


def sig_bar_z(p, F):
    z = F["r"] / F["r"].rolling(p["W"]).std()
    return z <= -p["z"], z >= p["z"]


def sig_gap(p, F):
    gap = (F["o"] - F["pc"]) / F["tr"].rolling(p["A"]).mean().shift(1)
    return gap <= -p["G"], gap >= p["G"]


def sig_dip(p, F):
    dd = F["c"] / F["h"].rolling(p["W"]).max() - 1.0
    return (dd <= -p["D"] / 100.0) & (F["c"] > F["o"]), pd.Series(False, index=F["c"].index)


def sig_rally(p, F):
    up = F["c"] / F["l"].rolling(p["W"]).min() - 1.0
    return pd.Series(False, index=F["c"].index), (up >= p["D"] / 100.0) & (F["c"] < F["o"])


def sig_exhaust(p, F):
    c = F["c_np"]
    n = F["n"]

    def move(run):
        idx = np.arange(n) - run
        base = c[np.clip(idx, 0, None)]
        return np.where(idx >= 0, c - base, np.nan)

    dn_run, up_run = F["run_dn"], F["run_up"]
    atr = F["atr"].to_numpy(float)
    mv_dn = move(dn_run)
    mv_up = move(up_run)
    L = (dn_run == p["N"]) & (mv_dn <= -p["m"] * atr)
    S = (up_run == p["N"]) & (mv_up >= p["m"] * atr)
    return pd.Series(L, index=F["c"].index), pd.Series(S, index=F["c"].index)


def sig_donchian_atr(p, F):
    hi = F["h"].shift(1).rolling(p["N"]).max()
    lo = F["l"].shift(1).rolling(p["N"]).min()
    return F["c"] > hi + p["a"] * F["atr"], F["c"] < lo - p["a"] * F["atr"]


def sig_vol_compr(p, F):
    comp = (F["atr"] / F["atr100"]) <= p["q"]
    hi = F["h"].shift(1).rolling(p["N"]).max()
    lo = F["l"].shift(1).rolling(p["N"]).min()
    return comp & (F["c"] > hi), comp & (F["c"] < lo)


def sig_vol_spike(p, F):
    spike = F["r"].rolling(p["fast"]).std() / F["rv720"] >= p["x"]
    return spike & (F["r"] < 0), spike & (F["r"] > 0)


def sig_skew(p, F):
    sk = F["r"].rolling(p["W"]).skew()
    return sk <= -p["s"], sk >= p["s"]


def sig_vr(p, F, mode):
    VR = _vr(F, p["W"])
    R = np.log(F["c"] / F["c"].shift(p["N"]))
    if mode == "trend":
        ok = VR >= p["v"]
        return _cross_up(R) & ok, _cross_dn(R) & ok
    ok = VR <= 1.0 / p["v"]
    return _cross_dn(R) & ok, _cross_up(R) & ok


def sig_utc_slot(p, F):
    n = F["n"]
    L = np.zeros(n, bool)
    S = np.zeros(n, bool)
    P = np.flatnonzero((F["hour"] == p["h"]) & (np.arange(n) >= 1) & (np.arange(n) + 3 < n))
    if P.size == 0:
        return pd.Series(L, index=F["c"].index), pd.Series(S, index=F["c"].index)
    occ_ret = np.log(F["c_np"][P + 3] / F["o_np"][P])
    past_mean = pd.Series(occ_ret).rolling(p["D"], min_periods=p["D"]).mean().shift(1).to_numpy()
    ok = np.isfinite(past_mean)
    L[P[ok & (past_mean > 0)] - 1] = True
    S[P[ok & (past_mean < 0)] - 1] = True
    return pd.Series(L, index=F["c"].index), pd.Series(S, index=F["c"].index)


def sig_vol_regime(p, F):
    vr = F["v"].rolling(24).mean() / F["v"].rolling(336).mean()
    cond = (vr >= 1.5) if p["regime"] == "hi" else (vr <= 0.7)
    R = np.log(F["c"] / F["c"].shift(p["N"]))
    return _cross_up(R) & cond, _cross_dn(R) & cond


def sig_vol_climax(p, F):
    v = F["v"]
    vz = (v - v.rolling(p["W"]).mean()) / v.rolling(p["W"]).std()
    cond = vz >= p["z"]
    return cond & (F["c"] < F["o"]), cond & (F["c"] > F["o"])


def sig_nr(p, F):
    rng = F["h"] - F["l"]
    nr = rng.shift(1) <= rng.shift(1).rolling(p["K"]).min()
    return nr & (F["c"] > F["h"].shift(1)), nr & (F["c"] < F["l"].shift(1))


def sig_ema_dist(p, F):
    ema = F["c"].ewm(span=p["N"], adjust=False).mean()
    dist = (F["c"] - ema) / F["atr"]
    return dist <= -p["d"], dist >= p["d"]


def sig_rsi(p, F):
    R = rsi(F["c"], p["n"])
    return R <= p["thr"], R >= 100 - p["thr"]


def sig_bb(p, F):
    m = F["c"].rolling(p["N"]).mean()
    s = F["c"].rolling(p["N"]).std()
    return F["c"] <= m - p["k"] * s, F["c"] >= m + p["k"] * s


def sig_donchian_close(p, F):
    hi = F["c"].shift(1).rolling(p["N"]).max()
    lo = F["c"].shift(1).rolling(p["N"]).min()
    return F["c"] > hi, F["c"] < lo


def sig_consec(p, F):
    return (pd.Series(F["run_dn"] == p["K"], index=F["c"].index),
            pd.Series(F["run_up"] == p["K"], index=F["c"].index))


def sig_atr_dd(p, F):
    hi = F["h"].rolling(p["W"]).max()
    lo = F["l"].rolling(p["W"]).min()
    return (hi - F["c"]) / F["atr"] >= p["k"], (F["c"] - lo) / F["atr"] >= p["k"]


def sig_funding(p, F):
    fr = pd.Series(F["fund_rate_bar"], index=F["c"].index)
    return fr <= -p["f"], fr >= p["f"]


def sig_xs(p, F, mode):
    top, bot = F["xs"][p["N"]]
    idx = pd.Series(False, index=F["c"].index)
    top_s = pd.Series(top, index=F["c"].index)
    bot_s = pd.Series(bot, index=F["c"].index)
    return (top_s, bot_s) if mode == "mom" else (bot_s, top_s)


def sig_rsi2(p, F):
    R2 = rsi(F["c"], 2)
    em = F["c"].ewm(span=p["E"], adjust=False).mean()
    return (R2 <= p["thr"]) & (F["c"] > em), (R2 >= 100 - p["thr"]) & (F["c"] < em)


# ----------------------------------------------------------------------------
# Family table: grid, function, mechanism template, rationale, prior likelihood
# ----------------------------------------------------------------------------
FAMILIES = [
    dict(key="tsmom_cross", grid=dict(N=[6, 12, 24, 48, 120, 336]), fn=lambda p, F: sig_tsmom(p, F, "cont"),
         mech="Long at 1h close when ln(C_t/C_t-{N}) crosses above 0 (prior bar <=0); short on cross below 0 (N={N} bars).",
         why="Trend persistence in crypto perps: leveraged flow and slow narrative diffusion keep multi-day moves going.",
         prior=6, note="well-known TSMOM idea; short N likely whipsaw-dominated"),
    dict(key="tsmom_fade", grid=dict(N=[6, 12, 24, 48, 120, 336]), fn=lambda p, F: sig_tsmom(p, F, "fade"),
         mech="Short at 1h close when ln(C_t/C_t-{N}) crosses above 0; long on cross below 0 (contrarian to the N={N} cross).",
         why="Over-extended cross-overs in liquid perps can unwind as liquidation cascades and basis trades reverse.",
         prior=3, note="mirror control of tsmom_cross; usually weaker at long N"),
    dict(key="kmove_fade", grid=dict(k=[2, 3, 4, 6], z=[2.0, 2.5, 3.0]), fn=sig_kmove,
         mech="Long at 1h close when ln(C_t/C_t-{k}) <= -{z}*sigma168*sqrt({k}); short when >= +{z}*sigma168*sqrt({k}).",
         why="Short-horizon overreaction in thin alt perps is partly reversed as market makers inventory-rebalance.",
         prior=6, note="short-term reversal is the best-replicated crypto anomaly class"),
    dict(key="bar_z_fade", grid=dict(W=[72, 168, 336], z=[2.0, 2.5, 3.0]), fn=sig_bar_z,
         mech="Long at 1h close when 1-bar log return <= -{z}*std(r, {W}); short when >= +{z}*std(r, {W}).",
         why="Single-bar liquidation-driven shocks often overshoot and partially retrace within hours.",
         prior=5, note="z-scored single-bar shock fade; fragile to volatility regime"),
    dict(key="gap_fill", grid=dict(A=[14, 48], G=[0.5, 1.0, 1.5]), fn=sig_gap,
         mech="Long at 1h close (for bar t) when (O_t - C_t-1)/ATR{A}_t-1 <= -{G}; short when >= +{G}; fade the open gap.",
         why="Gap-fill is a stock-market behaviour; 24/7 crypto gaps are small and may be filled by continuous trading.",
         prior=3, note="24/7 market means gaps are rare; low prior"),
    dict(key="dip_buy", grid=dict(D=[5, 10, 15], W=[168, 336]), fn=sig_dip,
         mech="Long at 1h close when C_t is >= {D}% below the max high of the last {W} bars AND bar t is green (C>O).",
         why="Buy-the-dip in crypto drawdowns with a green confirmation bar; drawdowns tend to partially recover in bull regimes.",
         prior=6, note="classic drawdown-recovery rule; regime dependent"),
    dict(key="rally_sell", grid=dict(D=[5, 10, 15], W=[168, 336]), fn=sig_rally,
         mech="Short at 1h close when C_t is >= {D}% above the min low of the last {W} bars AND bar t is red (C<O).",
         why="Mirror of dip-buy: sharp rallies off local lows fade in bear-leaning crypto regimes.",
         prior=4, note="mirror control of dip_buy"),
    dict(key="exhaust_fade", grid=dict(N=[4, 6, 8], m=[0, 2]), fn=sig_exhaust,
         mech="Long at 1h close when exactly {N} consecutive down closes end at t and cumulative move <= -{m}*ATR14 (m=0: count only); short symmetric.",
         why="Parabolic runs of same-direction bars in perps exhaust as stop-hunting completes and momentum traders take profit.",
         prior=5, note="exhaustion fade; plausible but many similar runs"),
    dict(key="donchian_atr", grid=dict(N=[12, 24, 48, 96], a=[0.0, 1.0]), fn=sig_donchian_atr,
         mech="Long at 1h close when C_t > max(H[t-{N}..t-1]) + {a}*ATR14; short when C_t < min(L[t-{N}..t-1]) - {a}*ATR14.",
         why="ATR-normalised channel breakouts capture the trend-following premium with volatility-scaled thresholds.",
         prior=6, note="standard trend-following breakout; ATR offset reduces false breaks"),
    dict(key="vol_compr_break", grid=dict(q=[0.6, 0.7, 0.8], N=[12, 24]), fn=sig_vol_compr,
         mech="When ATR14/ATR100 <= {q} (compression), long at 1h close when C_t > max(H[t-{N}..t-1]); short when C_t < min(L[t-{N}..t-1]).",
         why="Volatility compression precedes expansion; breakouts from low-vol ranges in crypto tend to run.",
         prior=6, note="volatility-squeeze breakout is a standard regime idea"),
    dict(key="vol_spike_fade", grid=dict(fast=[12, 24], x=[1.5, 2.0, 2.5]), fn=sig_vol_spike,
         mech="When std(r,{fast}) / std(r,720) >= {x} (vol spike), long at 1h close if r_t<0, short if r_t>0 (fade the last bar).",
         why="Vol spikes in crypto are liquidation-driven; the vol risk premium implies over-reaction is faded.",
         prior=4, note="vol-of-vol fade; direction choice is ad hoc"),
    dict(key="skew_fade", grid=dict(W=[72, 168, 336], s=[0.5, 1.0]), fn=sig_skew,
         mech="Long at 1h close when skew(r, {W}) <= -{s} (negative-skew crash state); short when skew >= +{s}.",
         why="Extreme return skew marks crowded positioning; crowded tails often mean-revert after the crash state.",
         prior=3, note="skew on short windows is noisy"),
    dict(key="vr_trend", grid=dict(W=[168, 336], v=[1.1, 1.25], N=[12, 24]), fn=lambda p, F: sig_vr(p, F, "trend"),
         mech="Long at 1h close when ln(C_t/C_t-{N}) crosses above 0 AND variance ratio VR4 over {W} bars >= {v}; short symmetric.",
         why="Hurst/variance-ratio trendiness gate: momentum signals are only traded where returns are positively autocorrelated.",
         prior=5, note="regime-gated trend; gate may be too rare"),
    dict(key="vr_revert", grid=dict(W=[168, 336], v=[1.1, 1.25], N=[12, 24]), fn=lambda p, F: sig_vr(p, F, "revert"),
         mech="Long at 1h close when ln(C_t/C_t-{N}) crosses below 0 AND VR4 over {W} bars <= 1/{v}; short symmetric.",
         why="Variance-ratio mean-reversion gate: contrarian signals only where returns are negatively autocorrelated.",
         prior=5, note="mirror gate of vr_trend"),
    dict(key="utc_slot_seasonal", grid=dict(h=[0, 4, 8, 12, 16, 20], D=[20]), fn=sig_utc_slot,
         mech="At UTC hour {h} bar open, long if mean 4-bar return from the same UTC hour over the last {D} days > 0, short if < 0 (hold 24 bars).",
         why="Intraday UTC session seasonality from Asia/EU/US open timing in a 24/7 market.",
         prior=2, note="24/7 crypto has weak clock effects; shared 24-bar exit is mismatched"),
    dict(key="volume_regime_mom", grid=dict(regime=["hi", "lo"], N=[12, 24]), fn=sig_vol_regime,
         mech="Cross-up/down of ln(C_t/C_t-{N}) through 0, traded only when vol regime VR_v (mean v24/mean v336) is {regime} (>=1.5 for hi, <=0.7 for lo).",
         why="Trend moves on abnormal participation (high turnover) tend to persist, while thin-volume moves revert.",
         prior=4, note="turnover-conditioned momentum"),
    dict(key="volume_climax_fade", grid=dict(W=[168, 336], z=[2.5, 3.5]), fn=sig_vol_climax,
         mech="Long at 1h close when vol z-score (window {W}) >= {z} AND bar is red; short when >= {z} AND bar is green (fade climax bar).",
         why="High-volume capitulation bars in perps often mark short-term exhaustion and absorption.",
         prior=5, note="volume climax reversal"),
    dict(key="nr_breakout", grid=dict(K=[4, 7, 10]), fn=sig_nr,
         mech="When bar t-1 has the narrowest range of last {K} bars (NR{K}), long at 1h close if C_t > H_t-1, short if C_t < L_t-1.",
         why="Narrow-range compression followed by a close outside the prior range is a short-horizon breakout pattern.",
         prior=3, note="classic price-pattern rule; weak in theory"),
    dict(key="ema_dist_revert", grid=dict(N=[20, 50, 100], d=[2.0, 3.0]), fn=sig_ema_dist,
         mech="Long at 1h close when (C_t - EMA{N}_t)/ATR14 <= -{d} (onset); short when >= +{d}.",
         why="ATR-normalised distance from a trend mean: over-stretched prices revert toward the EMA.",
         prior=5, note="standard mean-reversion stretch"),
    dict(key="rsi_extreme", grid=dict(n=[7, 14], thr=[15, 20, 25]), fn=sig_rsi,
         mech="Long at 1h close when RSI{n} crosses to <= {thr}; short when RSI{n} crosses to >= {100-thr}.",
         why="RSI extremes capture short-term oversold/overbought states that revert in liquid perps.",
         prior=4, note="RSI extremes; fires often in trends"),
    dict(key="bb_revert", grid=dict(N=[20, 50], k=[2.0, 2.5, 3.0]), fn=sig_bb,
         mech="Long at 1h close when C_t <= SMA{N} - {k}*std(C,{N}) (onset); short when C_t >= SMA{N} + {k}*std(C,{N}).",
         why="Bollinger-band excursions in perps revert toward the mean in range regimes.",
         prior=4, note="band reversion; fails in trend regimes"),
    dict(key="donchian_close_break", grid=dict(N=[24, 48, 96, 168, 336]), fn=sig_donchian_close,
         mech="Long at 1h close when C_t > max(C[t-{N}..t-1]); short when C_t < min(C[t-{N}..t-1]).",
         why="Close-based channel breakout is a simple trend-following premium test.",
         prior=5, note="close-based version of the breakout family"),
    dict(key="consec_closes", grid=dict(K=[3, 4, 5, 6, 7]), fn=sig_consec,
         mech="Long at 1h close when exactly {K} consecutive down closes end at t; short after exactly {K} consecutive up closes.",
         why="Runs of same-direction closes in perps mark short-term exhaustion before the reversion.",
         prior=4, note="run-length reversal; no volatility normalisation"),
    dict(key="atr_drawdown", grid=dict(W=[168, 720], k=[4.0, 6.0, 8.0]), fn=sig_atr_dd,
         mech="Long at 1h close (onset) when (max H[t-{W}..t] - C_t)/ATR14 >= {k}; short when (C_t - min L[t-{W}..t])/ATR14 >= {k}.",
         why="Volatility-normalised drawdown from the window extreme; buying far-from-high dips in crypto often recovers.",
         prior=5, note="ATR-scaled drawdown-recovery variant"),
    dict(key="funding_contrarian", grid=dict(f=[0.0001, 0.0002, 0.0003, 0.0005]), fn=sig_funding,
         mech="On each funding settlement inside bar t with rate <= -{f}, long at bar t+1 open; rate >= +{f}, short (funding-extreme contrarian, no price structure).",
         why="Crowded perp positioning shows up in funding; extreme funding tends to mean-revert as the crowded side pays. Mirror-adjacent to R13 (overheat), so overlap risk noted.",
         prior=6, note="crypto-specific factor; adjacent to R13 but no OB or breakdown structure"),
    dict(key="xs_momentum", grid=dict(N=list(XS_LOOKBACKS)), fn=lambda p, F: sig_xs(p, F, "mom"),
         mech="Across the 35-symbol panel at each 1h bar: go long when a symbol's ln(C_t/C_t-{N}) rank enters the top 20% (cross-sectional onset), short when it enters the bottom 20%.",
         why="Cross-sectional momentum across crypto coins: relative strength persists as capital rotates between leaders and laggards.",
         prior=7, note="cross-sectional momentum is a widely reported crypto factor"),
    dict(key="xs_reversal", grid=dict(N=list(XS_LOOKBACKS)), fn=lambda p, F: sig_xs(p, F, "rev"),
         mech="Across the 35-symbol panel: go long when a symbol's ln(C_t/C_t-{N}) rank enters the bottom 20%, short when it enters the top 20% (cross-sectional reversal).",
         why="Relative losers over short windows bounce as liquidity providers rotate back into lagging coins.",
         prior=3, note="mirror control of xs_momentum"),
    dict(key="rsi2_pullback", grid=dict(E=[100, 200], thr=[5, 10]), fn=sig_rsi2,
         mech="Long at 1h close when RSI2 <= {thr} AND C_t > EMA{E}; short when RSI2 >= {100-thr} AND C_t < EMA{E} (trend-filtered pullback).",
         why="Pullbacks inside a trend are bought when short-term RSI is extreme; EMA filter keeps the trade with the trend.",
         prior=4, note="trend-filtered RSI2 pullback"),
]

FAMILY_MECH_SUFFIX = " Entry next 1h open; stop 1.5xATR14; target 3.0xATR14; max hold 24 bars; cost 12bp RT."


def expand_ideas():
    ideas = []
    for fam_index, fam in enumerate(FAMILIES):
        keys = list(fam["grid"].keys())
        for values in itertools.product(*fam["grid"].values()):
            p = dict(zip(keys, values))
            ideas.append(dict(family=fam["key"], fam_index=fam_index, params=p,
                              mech=fam["mech"].format(**p, **{"100-thr": 100 - p.get("thr", 0)})
                              + FAMILY_MECH_SUFFIX,
                              why=fam["why"], prior=fam["prior"], note=fam["note"]))
    for i, idea in enumerate(ideas, start=1):
        idea["idea_id"] = f"C{i:03d}"
        suffix = "_".join(f"{k}{v}" for k, v in idea["params"].items())
        idea["name"] = f"{idea['family']}_{suffix}"
    return ideas


# ----------------------------------------------------------------------------
# Data load and cross-sectional panel
# ----------------------------------------------------------------------------
def load_universe():
    syms = {}
    for sym, bars, funding in iter_train_bars(TF):
        bars = [b for b in bars if b.complete]
        if len(bars) < 1000:  # drops ENA/POL/TON (no TRAIN bars) and TIA (142 bars)
            continue
        a = dict(ts=np.array([b.timestamp for b in bars], dtype=np.int64),
                 o=np.array([b.open for b in bars]), h=np.array([b.high for b in bars]),
                 l=np.array([b.low for b in bars]), c=np.array([b.close for b in bars]),
                 v=np.array([b.volume for b in bars]))
        F = base_features(a)
        F["fund_rate_bar"] = funding_bar_rates(a["ts"], funding)
        syms[sym] = F
    return syms


def attach_xs(syms):
    for N in XS_LOOKBACKS:
        mom = pd.DataFrame({s: pd.Series(np.log(F["c"] / F["c"].shift(N)).to_numpy(), index=F["ts"])
                            for s, F in syms.items()}).sort_index()
        mom.index = mom.index.astype(np.int64)
        valid = (mom.notna().sum(axis=1) >= MIN_SYMBOLS).to_numpy()[:, None]
        rk = mom.rank(axis=1, pct=True).to_numpy()
        top = (rk >= 0.8) & valid
        bot = (rk <= 0.2) & valid

        def onset(x):
            prev = np.vstack([np.zeros((1, x.shape[1]), bool), x[:-1]])
            return x & ~prev

        top_on, bot_on = onset(top), onset(bot)
        for s, F in syms.items():
            pos = mom.index.get_indexer(F["ts"])
            j = mom.columns.get_loc(s)
            F.setdefault("xs", {})[N] = (top_on[pos, j], bot_on[pos, j])


# ----------------------------------------------------------------------------
# Trade simulation under the shared exit convention
# ----------------------------------------------------------------------------
def simulate(F, L, S):
    n = F["n"]
    sig = np.flatnonzero(L | S)
    if sig.size == 0:
        return np.array([])
    d = np.where(L[sig], 1, -1)
    e = sig + 1
    atr = F["atr"].to_numpy(float)[sig]
    keep = (e + MAX_HOLD <= n) & np.isfinite(atr) & (atr > 0)
    d, e, atr = d[keep], e[keep], atr[keep]
    if e.size == 0:
        return np.array([])
    o, h, l, c = F["o_np"], F["h_np"], F["l_np"], F["c_np"]
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
    return gross[np.asarray(taken, dtype=int)]


def onset_np(x: np.ndarray) -> np.ndarray:
    prev = np.concatenate([[False], x[:-1]])
    return x & ~prev


def run_idea(idea, fam_fn, syms, years_by_sym):
    per_sym = {}
    for sym, F in syms.items():
        L, S = fam_fn(idea["params"], F)
        L = onset_np(np.asarray(L, dtype=bool))
        S = onset_np(np.asarray(S, dtype=bool))
        g = simulate(F, L, S)
        if g.size:
            per_sym[sym] = g
    return per_sym


def summarize(per_sym, years):
    if not per_sym:
        return dict(n_trades=0, n_symbols_traded=0)
    gross = np.concatenate(list(per_sym.values()))
    net = gross - COST_BPS
    n = net.size
    wins, losses = net[net > 0].sum(), -net[net < 0].sum()
    if losses > 0:
        pf = wins / losses
    else:
        pf = 99.0 if wins > 0 else 0.0
    mean = float(net.mean())
    sd = float(net.std(ddof=1)) if n > 1 else float("nan")
    t_stat = mean / (sd / np.sqrt(n)) if sd and sd > 0 else 0.0
    tpy = n / years
    rough = mean / sd * np.sqrt(tpy) if sd and sd > 0 else float("nan")
    sym_means = [float((g - COST_BPS).mean()) for g in per_sym.values() if g.size >= 5]
    pos_frac = float(np.mean([m > 0 for m in sym_means])) if sym_means else 0.0
    eligible = n >= MIN_TRADES and len(per_sym) >= MIN_SYMBOLS
    composite = t_stat * (0.5 + 0.5 * pos_frac) if eligible else float("nan")
    return dict(n_trades=n, n_symbols_traded=len(per_sym),
                win_rate=float((net > 0).mean()), profit_factor=float(pf),
                expectancy_bps_net=mean, expectancy_bps_gross=float(gross.mean()),
                sd_bps_net=sd, t_stat=float(t_stat), rough_sharpe=float(rough),
                trades_per_year=float(tpy), pos_symbol_frac=pos_frac,
                eligible=bool(eligible), composite_score=float(composite))


def fmt(x, nd=4):
    if isinstance(x, float):
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
    assert len(ideas) == 166, f"expected 166 ideas, got {len(ideas)}"
    syms = load_universe()
    attach_xs(syms)
    years = float(np.mean([(F["ts"][-1] - F["ts"][0]) / (365.25 * 24 * 3_600_000) for F in syms.values()]))
    print(f"loaded {len(syms)} symbols, avg span {years:.2f} years, {time.time()-t0:.1f}s", flush=True)

    fam_fn = {f["key"]: f["fn"] for f in FAMILIES}
    # Qualitative prior rank: higher prior first, then family/grid order.
    prior_order = sorted(ideas, key=lambda x: (-x["prior"], x["fam_index"], x["idea_id"]))
    prior_rank = {x["idea_id"]: i + 1 for i, x in enumerate(prior_order)}

    results = []
    for idea in ideas:
        ts0 = time.time()
        per_sym = run_idea(idea, fam_fn[idea["family"]], syms, years)
        m = summarize(per_sym, years)
        m.update(idea_id=idea["idea_id"], family=idea["family"], name=idea["name"],
                 prior_rank=prior_rank[idea["idea_id"]], prior_score=idea["prior"],
                 elapsed_s=time.time() - ts0)
        results.append(m)

    eligible = [r for r in results if r.get("eligible")]
    eligible.sort(key=lambda r: -r["composite_score"])
    comp_rank = {r["idea_id"]: i + 1 for i, r in enumerate(eligible)}
    for r in results:
        r["composite_rank"] = comp_rank.get(r["idea_id"], "")

    with (HERE / "IDEAS.csv").open("w", newline="", encoding="utf-8") as fh:
        fh.write(f"# {LABEL}\n")
        w = csv.DictWriter(fh, fieldnames=["idea_id", "name", "mechanism_one_liner",
                                           "rationale_one_liner", "prior_rank_note"])
        w.writeheader()
        for idea in ideas:
            w.writerow(dict(idea_id=idea["idea_id"], name=idea["name"],
                            mechanism_one_liner=idea["mech"], rationale_one_liner=idea["why"],
                            prior_rank_note=f"prior_rank={prior_rank[idea['idea_id']]}; "
                                            f"prior_score={idea['prior']}/10; {idea['note']}"))

    res_cols = ["idea_id", "family", "name", "prior_rank", "prior_score", "n_trades", "n_symbols_traded",
                "win_rate", "profit_factor", "expectancy_bps_net", "expectancy_bps_gross", "sd_bps_net",
                "t_stat", "rough_sharpe", "trades_per_year", "pos_symbol_frac", "eligible",
                "composite_score", "composite_rank", "elapsed_s"]
    results.sort(key=lambda r: r["idea_id"])
    write_csv(HERE / "RESULTS.csv", res_cols, results)

    scored = [r for r in results if r["n_trades"] > 0]
    zero = [r["idea_id"] for r in results if r["n_trades"] == 0]
    top20 = eligible[:20]
    lines = [f"# RANKED TOP 20 - EXPLORATORY SCREEN ONLY", "", f"> {LABEL}", "",
             f"Method: {len(syms)} crypto perps (of the 35-symbol universe; ENA, POL, TON have no TRAIN bars and TIA has 142), 1h TRAIN bars (data_access.iter_train_bars), shared exit "
             "(stop 1.5 ATR14, target 3.0 ATR14, 24-bar max hold, 12bp RT cost, one position per symbol). "
             "Ranking = composite_score = t_stat(net bps) x (0.5 + 0.5 x fraction of symbols with positive mean). "
             "Eligibility for the composite: >= 100 pooled trades and >= 10 symbols traded.",
             "",
             f"Scored {len(scored)} of {len(ideas)} ideas with at least one trade; "
             f"{len(eligible)} met eligibility; no-trade ideas: {len(zero)}.", "",
             "| rank | idea_id | name | composite | n_trades | exp net bps | win % | PF | t | pos-sym % | rough Sharpe | prior rank |",
             "|---|---|---|---|---|---|---|---|---|---|---|---|"]
    for i, r in enumerate(top20, start=1):
        lines.append(f"| {i} | {r['idea_id']} | {r['name']} | {r['composite_score']:.2f} | {r['n_trades']} | "
                     f"{r['expectancy_bps_net']:.1f} | {100*r['win_rate']:.1f} | {r['profit_factor']:.2f} | "
                     f"{r['t_stat']:.2f} | {100*r['pos_symbol_frac']:.0f} | {r['rough_sharpe']:.2f} | {r['prior_rank']} |")
    why_by_family = {f["key"]: f["why"] for f in FAMILIES}
    lines += ["", "## Why-notes (top 20)", ""]
    for i, r in enumerate(top20, start=1):
        lines.append(f"{i}. **{r['name']}**: {why_by_family[r['family']]}")
    if len(eligible) >= 3:
        prior_e = pd.Series([r["prior_rank"] for r in eligible])
        emp_e = pd.Series([comp_rank[r["idea_id"]] for r in eligible])
        rho = float(prior_e.corr(emp_e, method="spearman"))
    else:
        rho = float("nan")
    lines += ["", "## Caveats", "",
              "- EXPLORATORY SCREEN ONLY. Not G-eligible, not added to TRAIN_TRIALS.csv or any ledger, not counted toward the 13-round cap.",
              "- No look-ahead-bias audit beyond the construction rules; no walk-forward, no out-of-sample split inside TRAIN.",
              "- No multiple-testing correction across 166 ideas; top t-stats are optimistic and selection-biased.",
              "- Single shared exit for every idea (1.5/3.0 ATR, 24 bars). Families whose edge lives on a different horizon (e.g., 4-bar seasonal, funding-settlement entries) are judged on this exit only, so a low rank is not evidence the underlying idea is dead.",
              "- 1h timeframe only, equal-weight symbols, gaps in bar history not repaired; rough Sharpe scales per-trade stats by pooled trades per year and assumes independence.",
              f"- Spearman rank correlation between the pre-run prior ranking and empirical composite ranking (eligible ideas): {rho:.2f}.",
              "- Promotion to any candidate requires separate formal preregistration, synthetic tests, and a resource-gated TRAIN run."]
    (HERE / "RANKED_TOP20.md").write_text("\n".join(lines) + "\n", encoding="utf-8")

    readme = [f"# EXPLORE500 lane C (factors) - README", "", f"> {LABEL}", "",
              "Files: IDEAS.csv (166 ideas), screen.py (harness; re-run writes all outputs), "
              "RESULTS.csv (per-idea metrics), RANKED_TOP20.md (top 20 and caveats).",
              "CSV files start with a `#` label line; read with `pandas.read_csv(..., comment='#')`.",
              "", "Reproduce: `/opt/anaconda3/bin/python3 screen.py` (about 15 seconds on the TRAIN cache).", "",
              f"Simplifications: 1h timeframe only; {len(syms)} symbols with TRAIN bars from the cache; greedy one-position-per-symbol; "
              "shared exit convention (see screen.py header)."]
    (HERE / "README.md").write_text("\n".join(readme) + "\n", encoding="utf-8")
    print(f"done in {time.time()-t0:.1f}s; scored {len(scored)}/{len(ideas)}; eligible {len(eligible)}", flush=True)
    for i, r in enumerate(top20[:10], start=1):
        print(i, r["idea_id"], r["name"], round(r["composite_score"], 2), r["n_trades"],
              round(r["expectancy_bps_net"], 2))


if __name__ == "__main__":
    main()
