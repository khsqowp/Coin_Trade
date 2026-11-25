#!/usr/bin/env python3
"""EXPLORATORY SCREEN ONLY — not part of the 13-round preregistered G-gate track,
not added to TRAIN_TRIALS.csv, no promotion without separate formal preregistration
+ synthetic tests + resource-gated TRAIN run.

Lane B (crypto cross-asset / cross-sectional / calendar / regime overlays).

Writes into this directory: IDEAS.csv, RESULTS.csv, RANKED_TOP20.md.
Reads only: data_access.iter_train_bars("1h") (TRAIN window, 35 perps, funding).

Shared conventions (documented once, used by every idea):
  * Bars: 1h, complete bars only, TRAIN window (first 60% per symbol).
  * Signals use only data up to and including bar t close.
  * Entry = open of bar t+1. Exit = close of bar t+H (fixed hold H, per idea).
    No stop/target in this lane (the lane is about relationships, not zones).
  * Costs: 12bp round trip per unit of gross notional traded. Basket weights are
    scaled so sum|w| = 1 when active, so each active rebalance costs 12bp.
    Per-trade events cost 12bp per trade.
  * Cross-sectional baskets: rebalance every H bars, long top-5 / short bottom-5
    (equal weight, dollar neutral, 0.5 gross each leg). Needs >= 10 valid names.
  * Overlays gate a base basket at its rebalance bar (flat when gate is False).
  * Per-symbol event ideas: one position per symbol at a time (no overlap).
  * Metrics: n (active periods/trades), win_rate, profit_factor, expectancy_bps,
    rough_sharpe = mean/std of all periods (flat = 0) * sqrt(periods per year).
    Basket periods per year = 8760/H; event periods per year = trades/years.
  * composite_score = clip(rough_sharpe,-3,3) * sqrt(min(n,200)/200), halved when
    the sign of the Sharpe in the first and second half of TRAIN disagrees.
    Ideas with n < 30 get no score ("insufficient_trades").
  * No look-ahead audit beyond the causal construction above, no multiple-testing
    correction, no walk-forward. Not G-eligible.
"""
from __future__ import annotations

import csv
import sys
from pathlib import Path

import numpy as np
import pandas as pd

HERE = Path(__file__).resolve().parent
sys.path.insert(0, str(HERE.parent))  # orderblock_loop (for data_access / crypto imports)
import data_access  # noqa: E402  read-only loader

LABEL = ("EXPLORATORY SCREEN ONLY — not part of the 13-round preregistered G-gate track, "
         "not added to TRAIN_TRIALS.csv, no promotion without separate formal preregistration "
         "+ synthetic tests + resource-gated TRAIN run.")
FEE = 0.0012
K = 5
WARM = 1000
BTC, ETH = "BTCUSDT", "ETHUSDT"
BAR_MS = 3_600_000
DAY_MS = 86_400_000
HOURS_PER_YEAR = 8760.0


# ---------------------------------------------------------------- panel
def _on_grid(grid: pd.Index, vals: dict) -> tuple[pd.Series, pd.Series]:
    """Return (ffilled rate on grid, rate only on settlement bars)."""
    if not vals:
        nan = pd.Series(np.nan, index=grid)
        return nan, nan.copy()
    s = pd.Series(vals, dtype=float).sort_index()
    s.index = s.index.astype("int64")
    ffilled = s.reindex(grid.union(s.index)).ffill().reindex(grid)
    settle = s.reindex(grid)
    return ffilled, settle


def build_panel() -> dict:
    closes, opens, vols, ffl, stl = {}, {}, {}, {}, {}
    for sym, bars, fund in data_access.iter_train_bars("1h"):
        bars = [b for b in bars if b.complete]
        if len(bars) < 2000:
            continue
        ts = pd.Index([b.timestamp for b in bars], dtype="int64")
        closes[sym] = pd.Series([b.close for b in bars], index=ts)
        opens[sym] = pd.Series([b.open for b in bars], index=ts)
        vols[sym] = pd.Series([b.volume for b in bars], index=ts)
        ffl[sym] = {k: v.rate for k, v in fund.items()}
    C = pd.DataFrame(closes).sort_index()
    grid = C.index
    O = pd.DataFrame(opens).reindex(grid)
    V = pd.DataFrame(vols).reindex(grid)
    F_fill, F_set = {}, {}
    for sym in C.columns:
        F_fill[sym], F_set[sym] = _on_grid(grid, ffl[sym])
    F = pd.DataFrame(F_fill)[C.columns]
    Fset = pd.DataFrame(F_set)[C.columns]
    lc = np.log(C)
    r = lc.diff()
    dt = pd.to_datetime(grid.values, unit="ms", utc=True)
    ts = grid.values.astype("int64")
    P = dict(C=C, O=O, V=V, F=F, Fset=Fset, lc=lc, r=r, ts=ts,
             hour=(ts // BAR_MS) % 24, dow=((ts // DAY_MS) + 3) % 7,
             month_end=np.asarray(dt.is_month_end), month_start=np.asarray(dt.is_month_start),
             dom=np.asarray(dt.day))
    return P


def rolling_beta(P: dict, against: str, w: int = 720) -> pd.DataFrame:
    r = P["r"]
    b = r[against]
    mrb = r.mul(b, axis=0).rolling(w, min_periods=w // 2).mean()
    mr = r.rolling(w, min_periods=w // 2).mean()
    mb = b.rolling(w, min_periods=w // 2).mean()
    vb = b.rolling(w, min_periods=w // 2).var()
    cov = mrb - mr.mul(mb, axis=0)
    return cov.div(vb, axis=0)


def gates(P: dict) -> dict:
    C, r = P["C"], P["r"]
    G = {}
    G["O1"] = C[BTC] > C[BTC].rolling(720, min_periods=500).mean()
    mkt = r.mean(axis=1)
    corr = pd.DataFrame({c: r[c].rolling(168, min_periods=100).corr(mkt) for c in r.columns})
    avg_corr = corr.mean(axis=1)
    G["O2a"] = avg_corr < 0.5
    G["O2b"] = avg_corr < 0.7
    rv = r[BTC].rolling(168, min_periods=100).std()
    pct = rv.rolling(2160, min_periods=500).rank(pct=True)
    G["O3a"] = pct <= 0.5
    G["O3b"] = pct <= 0.8
    breadth = (C > C.rolling(100, min_periods=100).mean()).where(C.notna()).sum(axis=1) / C.notna().sum(axis=1)
    G["O4"] = (breadth >= 0.3) & (breadth <= 0.7)
    G["_breadth"] = breadth
    return G


# ---------------------------------------------------------------- basket engine
def rank_weights(S: pd.DataFrame, k: int = K, min_n: int = 10) -> pd.DataFrame:
    R = S.rank(axis=1, method="first").values
    n = S.notna().sum(axis=1).values
    W = np.zeros(R.shape)
    W[R > (n - k)[:, None]] = 0.5 / k
    W[R <= k] = -0.5 / k
    W[n < min_n] = 0.0
    return pd.DataFrame(W, index=S.index, columns=S.columns)


def basket_returns(Wr: pd.DataFrame, H: int, P: dict):
    fwd = (P["C"].shift(-H) / P["O"].shift(-1) - 1).reindex(Wr.index).fillna(0.0)
    gross = Wr.abs().sum(axis=1)
    rets = (Wr * fwd).sum(axis=1) - FEE * gross
    return rets.values, (gross > 0).values


def weights_for(spec: dict, P: dict, G: dict) -> pd.DataFrame:
    """Rebalance-row weights for a basket spec (before overlay gating)."""
    H = spec["H"]
    T = len(P["C"])
    pos = np.arange(WARM, T - H - 1, H)
    C, lc, r, V, F = P["C"], P["lc"], P["r"], P["V"], P["F"]
    kind = spec["kind"]
    at = lambda df: df.iloc[pos]  # noqa: E731
    if kind == "csmom":
        Wr = rank_weights(at(lc.diff(spec["L"])))
    elif kind == "rev":
        Wr = rank_weights(at(-lc.diff(spec["L"])))
    elif kind == "lowvol":
        Wr = rank_weights(at(-r.rolling(spec["L"], min_periods=int(spec["L"] * 0.8)).std()))
    elif kind == "idiovol":
        beta = rolling_beta(P, BTC, 720)
        resid = r.sub(beta.mul(r[BTC], axis=0))
        Wr = rank_weights(at(-resid.rolling(720, min_periods=500).std()))
    elif kind == "volmom":
        ret24 = lc.diff(24)
        vz = V.rolling(24).sum() / (V.rolling(168).mean() * 24)
        S = ret24 * np.log(vz.where(vz > 0))
        Wr = rank_weights(at(S * spec["sgn"]))
    elif kind == "fund":
        S = F * (-1.0 if spec["sgn"] < 0 else 1.0)
        Wr = rank_weights(at(S))
    elif kind == "beta":
        beta = rolling_beta(P, BTC, 720)
        base = rank_weights(at(beta))
        sgn = np.sign(lc[BTC].diff(spec["R"])).iloc[pos].fillna(0.0)
        Wr = base.mul(sgn, axis=0)
    elif kind == "relbtc":
        # beta-adjusted residual momentum. (Plain alt-minus-BTC ranking is identical to
        # CSMOM cross-sectionally, since BTC return is common to all names; beta removes that.)
        ret = lc.diff(spec["L"])
        beta = rolling_beta(P, BTC, 720)
        Wr = rank_weights(at(ret.sub(beta.mul(ret[BTC], axis=0))))
    elif kind == "ratio":
        alt = [c for c in C.columns if c != BTC]
        ratio = (r[alt].mean(axis=1) - r[BTC]).cumsum()
        W_ = spec["W"]
        z = (ratio - ratio.rolling(W_, min_periods=W_ // 2).mean()) / ratio.rolling(W_, min_periods=W_ // 2).std()
        zr = z.iloc[pos].values
        sgn = np.where(zr > 2, 1.0, np.where(zr < -2, -1.0, 0.0))
        valid = C.iloc[pos][alt].notna().values.astype(float)
        nalt = np.maximum(valid.sum(axis=1), 1.0)
        Wr = pd.DataFrame(0.0, index=C.index[pos], columns=C.columns)
        Wr[BTC] = 0.5 * sgn
        Wr[alt] = (-0.5 * sgn)[:, None] * valid / nalt[:, None]
    elif kind == "breadth":
        br = G["_breadth"].iloc[pos].values
        if spec["side"] == "low":
            sgn = np.where(br < 0.2, 1.0, 0.0)
        else:
            sgn = np.where(br > 0.8, -1.0, 0.0)
        Wr = pd.DataFrame(0.0, index=C.index[pos], columns=C.columns)
        Wr[BTC] = sgn
    elif kind == "dd":
        mret = lc.diff(72).mean(axis=1)
        hit = (mret.iloc[pos] < -spec["X"]).values
        valid = C.iloc[pos].notna().values.astype(float)
        nv = np.maximum(valid.sum(axis=1), 1.0)
        Wr = pd.DataFrame((hit[:, None] * valid) / nv[:, None], index=C.index[pos], columns=C.columns)
    elif kind == "skew":
        Wr = rank_weights(at(-r.rolling(spec["L"], min_periods=spec["L"]).skew()))
    else:
        raise ValueError(kind)
    if spec.get("ov"):
        gate = G[spec["ov"]].iloc[pos].astype(float).values
        Wr = Wr.mul(gate, axis=0)
    return Wr.fillna(0.0)


# ---------------------------------------------------------------- event engine
def event_masks(spec: dict, P: dict) -> tuple[pd.DataFrame, pd.DataFrame]:
    C, lc, r = P["C"], P["lc"], P["r"]
    kind = spec["kind"]
    cols = C.columns
    hour, dow = P["hour"], P["dow"]

    def bc(mask) -> pd.DataFrame:
        m = np.asarray(mask, dtype=bool)
        return pd.DataFrame(np.repeat(m[:, None], len(cols), axis=1), index=C.index, columns=cols)

    if kind == "leadlag":
        L = spec["L"]
        bsig = r[BTC].rolling(720, min_periods=300).std()
        bret = lc[BTC].diff(L)
        z = (bret / (bsig * np.sqrt(L))).values
        aret = lc.diff(L).values
        bv = bret.values[:, None]
        Ld = pd.DataFrame((z[:, None] > 1.5) & (aret < bv), index=C.index, columns=cols)
        Sd = pd.DataFrame((z[:, None] < -1.5) & (aret > bv), index=C.index, columns=cols)
        Ld[BTC] = False
        Sd[BTC] = False
        return Ld, Sd
    if kind == "resid":
        partner, L = spec["partner"], spec["L"]
        beta = rolling_beta(P, partner, 720)
        ret = lc.diff(L)
        resid = ret.sub(beta.mul(ret[partner], axis=0))
        z = resid / resid.rolling(720, min_periods=300).std()
        Ld = z < -2
        Sd = z > 2
        Ld[partner] = False
        Sd[partner] = False
        return Ld, Sd
    if kind == "ratio_brk":
        rat = lc.sub(lc[BTC], axis=0)
        N = spec["N"]
        hi = rat >= rat.shift(1).rolling(N, min_periods=N).max()
        lo = rat <= rat.shift(1).rolling(N, min_periods=N).min()
        if spec["dir"] == "long":
            Ld, Sd = hi, lo & False
        else:
            Ld, Sd = hi & False, lo
        Ld = Ld.fillna(False).astype(bool)
        Sd = Sd.fillna(False).astype(bool)
        Ld[BTC] = False
        Sd[BTC] = False
        return Ld, Sd
    if kind == "hour":
        return bc((hour == spec["h"])), bc(np.zeros(len(hour), bool))
    if kind == "dow":
        return bc((hour == 0) & (dow == spec["d"])), bc(np.zeros(len(hour), bool))
    if kind == "weekend":
        m = bc((dow == 4) & (hour == 20))
        z = bc(np.zeros(len(hour), bool))
        return (m, z) if spec["dir"] == "long" else (z, m)
    if kind == "month":
        m = P["month_end"] if spec["which"] == "end" else P["month_start"]
        return bc(m & (hour == 0)), bc(np.zeros(len(hour), bool))
    if kind == "fundev":
        Fs = P["Fset"]
        th = spec["th"]
        hot = (Fs > th).fillna(False).astype(bool)
        cold = (Fs < -th).fillna(False).astype(bool)
        zeros = bc(np.zeros(len(hot), bool))
        if spec["dir"] == "short":
            return zeros, hot  # overheated funding -> short
        return cold, zeros  # negative funding -> long
    if kind == "session":
        s = spec["s"]
        sess = (lc.shift(1) - lc.shift(9))
        m = (hour == s)
        pos_ = sess > 0
        neg_ = sess < 0
        mask_m = bc(m) & (pos_ | neg_)
        if spec["mode"] == "mom":
            Ld = mask_m & pos_
            Sd = mask_m & neg_
        else:
            Ld = mask_m & neg_
            Sd = mask_m & pos_
        return Ld.fillna(False), Sd.fillna(False)
    raise ValueError(kind)


def event_trades(Ld: pd.DataFrame, Sd: pd.DataFrame, H: int, P: dict):
    Cv, Ov = P["C"].values, P["O"].values
    T, N = Cv.shape
    pnl, tidx = [], []
    Lv, Sv = Ld.values.astype(bool), Sd.values.astype(bool)
    for j in range(N):
        lsig, ssig = Lv[:, j], Sv[:, j]
        cand = np.flatnonzero(lsig ^ ssig)
        nxt = WARM
        for t in cand:
            if t < nxt or t + H + 1 >= T:
                continue
            e, x = Ov[t + 1, j], Cv[t + H, j]
            if not (np.isfinite(e) and np.isfinite(x)) or e <= 0:
                continue
            d = 1.0 if lsig[t] else -1.0
            pnl.append(d * (x / e - 1.0) - FEE)
            tidx.append(t)
            nxt = t + H + 1
    return np.asarray(pnl), np.asarray(tidx, dtype=int)


# ---------------------------------------------------------------- metrics
def _sh(x: np.ndarray, ppy: float) -> float:
    if len(x) < 5:
        return 0.0
    sd = x.std(ddof=1)
    if not np.isfinite(sd) or sd == 0:
        return 0.0
    return float(x.mean() / sd * np.sqrt(ppy))


def summarize(rets: np.ndarray, active: np.ndarray, half: np.ndarray, ppy: float,
              trade_rets: np.ndarray | None = None, n_comp: int | None = None) -> dict:
    """Basket: rets are per-period (flat=0), active marks live periods.
    Event: rets are per-entry-bar equal-weight periods (Sharpe), trade_rets are
    per-trade pnl (win rate / PF / expectancy); n_comp = number of periods."""
    ra = rets[active] if trade_rets is None else np.asarray(trade_rets, float)
    n = int(len(ra))
    n_c = n if n_comp is None else int(n_comp)
    out = dict(n_trades=n, exposure=float(active.mean()))
    if n == 0:
        out.update(win_rate=np.nan, profit_factor=np.nan, expectancy_bps=np.nan,
                   rough_sharpe=0.0, sharpe_h1=0.0, sharpe_h2=0.0, composite_score=np.nan,
                   note="no_trades")
        return out
    pos, neg = ra[ra > 0].sum(), -ra[ra <= 0].sum()
    pf = float(min(pos / neg, 99.0)) if neg > 0 else 99.0
    sh = _sh(rets, ppy)
    h1 = _sh(rets[half == 1], ppy)
    h2 = _sh(rets[half == 2], ppy)
    out.update(win_rate=float((ra > 0).mean()), profit_factor=pf,
               expectancy_bps=float(ra.mean() * 1e4), rough_sharpe=sh,
               sharpe_h1=h1, sharpe_h2=h2, n_periods=n_c)
    if n_c < 30:
        out.update(composite_score=np.nan, note="insufficient_trades")
    else:
        base = float(np.clip(sh, -3, 3)) * np.sqrt(min(n_c, 200) / 200.0)
        if np.sign(h1) != np.sign(h2):
            base *= 0.5
        out.update(composite_score=base, note="")
    return out


# ---------------------------------------------------------------- ideas
def make_ideas() -> list[dict]:
    rows: list[dict] = []

    def add(**kw):
        kw.setdefault("status", "screenable")
        kw.setdefault("ov", None)
        rows.append(kw)

    # --- basket family (53)
    for L in [24, 72, 168, 336, 720]:
        for H in [24, 168]:
            add(kind="csmom", L=L, H=H, fam="CSMOM", prior=6,
                name=f"CS momentum {L}h lookback, {H}h hold",
                mech=f"Each {H}h rebalance, rank the 35 perps by {L}-bar log return; long top-5, short bottom-5, equal weight, dollar-neutral.",
                rat="Winners keep attracting flow over multi-day horizons in crypto majors; the best-documented cross-section, but 12bp per rebalance bites at short holds.")
    for L in [6, 12, 24]:
        for H in [6, 24]:
            add(kind="rev", L=L, H=H, fam="REV", prior=5,
                name=f"CS short-term reversal {L}h, {H}h hold",
                mech=f"Each {H}h rebalance, rank by -{L}-bar return; long the 5 biggest recent losers, short the 5 biggest winners.",
                rat="Perp liquidity-provision overreaction reverses over hours; gross edge is real but short holds pay the most cost.")
    for L in [168, 720]:
        for H in [168, 336]:
            add(kind="lowvol", L=L, H=H, fam="LOWVOL", prior=5,
                name=f"CS low-volatility ({L}h window), {H}h hold",
                mech=f"Rank by -realized vol over {L} bars; long 5 calmest, short 5 most volatile, hold {H} bars.",
                rat="Low-vol anomaly from lottery-demand for high-vol coins should carry into crypto.")
    for H in [168, 336]:
        add(kind="idiovol", H=H, fam="IDIOVOL", prior=4,
            name=f"CS idiosyncratic-vol (vs BTC residual), {H}h hold",
            mech=f"Residual = r_i - beta_i*r_BTC over 720 bars; long 5 lowest residual-vol coins, short 5 highest; hold {H}h.",
            rat="High idiosyncratic-risk coins are speculative and overpriced; BTC-residual vol is a noisy proxy.")
    for sgn in [1, -1]:
        for H in [24, 72]:
            tag = "momentum" if sgn > 0 else "reversal"
            add(kind="volmom", sgn=sgn, H=H, fam="VOLMOM", prior=4,
                name=f"CS volume-confirmed {tag} (24h ret x log volume surge), {H}h hold",
                mech=f"Score = 24-bar log return x log(24-bar volume / 168-bar mean); {'long top' if sgn>0 else 'long bottom'} 5 / short opposite 5; hold {H}h.",
                rat="Abnormal-volume moves reflect informed flow (momentum) or exhaustion (reversal); sign is untested here.")
    for sgn, Hs in [(-1, [8, 24]), (1, [24, 72])]:
        for H in Hs:
            tag = "reversal (long lowest funding)" if sgn < 0 else "momentum (long highest funding)"
            add(kind="fund", sgn=sgn, H=H, fam="FUND", prior=6 if sgn < 0 else 3,
                name=f"CS funding {tag}, {H}h hold",
                mech=f"Each {H}h rebalance, rank by last settled funding rate (ffilled); {'long lowest / short highest' if sgn<0 else 'long highest / short lowest'} 5 each leg.",
                rat=("Positive funding marks long-crowded perps that unwind; contrarian side is the crowding-unwind thesis." if sgn < 0
                     else "Momentum in funding-rate ranks would mean crowding keeps getting paid; weaker prior."))
    for H in [24, 72]:
        for R in [24, 168]:
            add(kind="beta", H=H, R=R, fam="BETAROT", prior=4,
                name=f"BTC-regime beta rotation (BTC {R}h sign), {H}h hold",
                mech=f"Rank by 720-bar beta to BTC; when BTC {R}-bar return > 0 long top-5 beta / short bottom-5, flip when BTC {R}-bar return < 0; hold {H}h.",
                rat="High-beta alts amplify BTC trends, so rotating by beta with the BTC trend harvests levered beta.")
    for L in [72, 168, 336]:
        for H in [24, 168]:
            add(kind="relbtc", L=L, H=H, fam="RESMOM", prior=5,
                name=f"CS beta-residual momentum vs BTC {L}h, {H}h hold",
                mech=f"Rank by residual {L}-bar log return = alt return - beta_720 x BTC return; long top 5 residual, short bottom 5, equal weight; hold {H}h.",
                rat="Stripping the BTC-beta component leaves the coin-specific trend; prior 5/10 because residual signals are noisier.")
    for W_ in [168, 720]:
        for H in [24, 72]:
            add(kind="ratio", W=W_, H=H, fam="RATIOZ", prior=4,
                name=f"Alt-basket vs BTC log-ratio z reversion (z window {W_}h), {H}h hold",
                mech=f"Ratio = cumsum(mean alt return - BTC return); z vs trailing {W_}-bar mean/std; z>2 long BTC 0.5 / short alt basket 0.5; z<-2 reverse; flat otherwise; hold {H}h.",
                rat="Extreme alt/BTC dominance swings mean-revert as flows reverse, but trend regimes can persist.")
    for side, pr in [("low", 5), ("high", 4)]:
        for H in [48, 168]:
            add(kind="breadth", side=side, H=H, fam="BREADTH", prior=pr,
                name=f"BTC breadth-{'capitulation long' if side=='low' else 'overheat short'} (share above 100h SMA {'<0.2' if side=='low' else '>0.8'}), {H}h hold",
                mech=f"Breadth = share of 35 perps closing above their 100-bar SMA; {'breadth < 0.2 -> long BTC 1.0' if side=='low' else 'breadth > 0.8 -> short BTC 1.0'}; hold {H}h, else flat.",
                rat=("Breadth capitulation with coins all below trend tends to mean-revert in BTC." if side == "low"
                     else "Overheated breadth is a late-cycle fade, but momentum can keep it extreme."))
    for X in [0.05, 0.08, 0.12]:
        add(kind="dd", X=X, H=72, fam="DDREV", prior=5,
            name=f"EW-35 basket drawdown reversal (72h return < -{int(X*100)}%)",
            mech=f"If 72-bar equal-weight 35-perp log return < -{int(X*100)}%, long all valid perps equal weight (gross 1) for 72 bars; flat otherwise.",
            rat="Liquidation-driven market-wide overshoots partially retrace; it is a crash-beta bet.")
    for L in [168, 720]:
        add(kind="skew", L=L, H=168, fam="SKEW", prior=3,
            name=f"CS lottery-skew ({L}h window), 168h hold",
            mech=f"Rank by -{L}-bar return skewness; long 5 lowest-skew, short 5 highest-skew; hold 168h.",
            rat="Lottery demand makes positively skewed coins overpriced; weak prior after costs.")

    # --- overlays on 8 bases x 6 gates (48)
    bases = [
        dict(kind="csmom", L=168, H=24), dict(kind="csmom", L=336, H=168),
        dict(kind="rev", L=12, H=24), dict(kind="lowvol", L=720, H=168),
        dict(kind="relbtc", L=168, H=24), dict(kind="volmom", sgn=1, H=24),
        dict(kind="fund", sgn=-1, H=24), dict(kind="beta", H=24, R=168),
    ]
    gate_desc = {
        "O1": ("BTC above its 720-bar SMA", "O1"),
        "O2a": ("market avg 168-bar corr to EW basket < 0.5", "O2a"),
        "O2b": ("market avg 168-bar corr to EW basket < 0.7", "O2b"),
        "O3a": ("BTC 168-bar realized vol at or below its trailing-2160-bar median", "O3a"),
        "O3b": ("BTC 168-bar realized vol at or below its trailing-2160-bar 80th pct", "O3b"),
        "O4": ("breadth (share of perps above 100-bar SMA) between 0.3 and 0.7", "O4"),
    }
    for b in bases:
        base_name = {
            "csmom": f"CSMOM {b.get('L')}h/{b['H']}h",
            "rev": f"REV {b.get('L')}h/{b['H']}h",
            "lowvol": f"LOWVOL {b.get('L')}h/{b['H']}h",
            "relbtc": f"RESMOM {b.get('L')}h/{b['H']}h",
            "volmom": f"VOLMOM mom/{b['H']}h",
            "fund": f"FUND rev/{b['H']}h",
            "beta": f"BETAROT R{b.get('R')}/{b['H']}h",
        }[b["kind"]]
        for gk, (gd, _) in gate_desc.items():
            add(**b, ov=gk, fam="OVERLAY", prior=max(b_prior(b) - 1, 1),
                name=f"Overlay [{gk}] on {base_name}",
                mech=f"Base {base_name} basket, traded only when {gd}; flat otherwise.",
                rat="A regime gate may remove drawdown-prone periods of the base, at the cost of sample size.",
                base_name=base_name)

    # --- event (per-symbol) family (49)
    for L in [2, 4, 8]:
        for H in [4, 8]:
            add(kind="leadlag", L=L, H=H, fam="LEADLAG", prior=6,
                name=f"BTC-lead alt catch-up ({L}h move, z>1.5), {H}h hold",
                mech=f"If BTC {L}-bar log move z-scored vs 720-bar 1h vol exceeds +/-1.5 and the alt lagged (led) that move, enter next bar in the BTC direction; hold {H}h.",
                rat="Alts lag BTC by hours as liquidity follows; prior is moderate because the lag is short.")
    for partner, L, H in [(BTC, 24, 12), (BTC, 24, 48), (BTC, 96, 12), (BTC, 96, 48), (ETH, 24, 12), (ETH, 96, 48)]:
        add(kind="resid", partner=partner, L=L, H=H, fam="RESID", prior=5,
            name=f"Beta-residual reversion vs {partner.replace('USDT','')} ({L}h), {H}h hold",
            mech=f"Residual = alt {L}-bar log return - beta_720 x {partner.replace('USDT','')} {L}-bar return; z = residual / trailing 720-bar std; short z>2, long z<-2; hold {H}h.",
            rat="Co-movement overshoots relative to the anchor coin mean-revert within hours.")
    for dr, N, H in [("long", 168, 24), ("long", 168, 72), ("long", 336, 24), ("long", 336, 72),
                     ("short", 168, 24), ("short", 168, 72)]:
        add(kind="ratio_brk", dir=dr, N=N, H=H, fam="RATIOBRK", prior=4,
            name=f"Alt/BTC ratio {'breakout' if dr=='long' else 'breakdown'} ({N}h), {H}h hold",
            mech=f"Enter next bar when alt/BTC log ratio makes a new {N}-bar {'high' if dr=='long' else 'low'} (vs prior bars); {'long' if dr=='long' else 'short'} alt; hold {H}h.",
            rat="Relative-strength breaks vs BTC persist while rotation lasts.")
    for h in [0, 4, 8, 12, 16, 20]:
        add(kind="hour", h=h, H=4, fam="HOUR", prior=2,
            name=f"Hour-of-day long {h:02d}:00 UTC, 4h hold",
            mech=f"Long each perp at the open of the {h:02d}:00 UTC bar; exit after 4 bars.",
            rat="Session-open flow clusters could add a small drift; likely noise after 12bp.")
    dnames = ["Mon", "Tue", "Wed", "Thu", "Fri", "Sat", "Sun"]
    for d in range(7):
        add(kind="dow", d=d, H=24, fam="DOW", prior=2,
            name=f"Weekday long {dnames[d]} 00:00 UTC, 24h hold",
            mech=f"Long each perp at the 00:00 UTC bar on {dnames[d]}; exit after 24 bars.",
            rat="Weekday seasonality in crypto is documented but weak and unstable.")
    for dr in ["long", "short"]:
        add(kind="weekend", dir=dr, H=48, fam="WEEKEND", prior=2,
            name=f"Weekend {dr} Fri 20:00 UTC -> Sun 20:00 UTC",
            mech=f"{dr.capitalize()} each perp at Fri 20:00 UTC; exit after 48 bars.",
            rat="Weekend liquidity thinning may bias moves; sign is a guess.")
    for which, H in [("end", 24), ("end", 48), ("start", 24), ("start", 48)]:
        add(kind="month", which=which, H=H, fam="MONTH", prior=2,
            name=f"Month-{which} long 00:00 UTC, {H}h hold",
            mech=f"Long each perp at 00:00 UTC on the {'last calendar day' if which=='end' else 'first day'} of the month; hold {H}h.",
            rat="Rebalancing and month-end flows are a classic calendar effect; weak in crypto so far.")
    for th, H in [(0.0005, 8), (0.0005, 24), (0.001, 8), (0.001, 24)]:
        add(kind="fundev", th=th, dir="short", H=H, fam="FUNDEV", prior=5,
            name=f"Per-symbol funding overheat short (>{th*1e4:.0f}bp/8h), {H}h hold",
            mech=f"At each settlement where funding > +{th*1e4:.0f}bp per 8h, short the perp at next open; hold {H}h.",
            rat="Extreme positive funding marks crowded longs that unwind; per-symbol form of the basket idea.")
    for H in [8, 24]:
        add(kind="fundev", th=0.0005, dir="long", H=H, fam="FUNDEV", prior=5,
            name=f"Per-symbol funding overheat long (< -5bp/8h), {H}h hold",
            mech=f"At each settlement where funding < -5bp per 8h, long the perp at next open; hold {H}h.",
            rat="Negative funding marks crowded shorts; mirror of the overheat short.")
    for s in [0, 8, 16]:
        for mode in ["mom", "rev"]:
            add(kind="session", s=s, mode=mode, H=8, fam="SESSION", prior=3,
                name=f"8h-session {'momentum' if mode=='mom' else 'reversal'} at {s:02d}:00 UTC, 8h hold",
                mech=f"At {s:02d}:00 UTC, trade the sign of the prior 8-bar return ({'same' if mode=='mom' else 'opposite'} direction), hold 8 bars.",
                rat="Session-to-session flow persistence or reversal in 24/7 markets; weak prior.")

    # --- data-blocked (17): listed, not scored
    blocked = [
        ("Open-interest divergence basket", "Long perps with rising price and falling OI, short the opposite.", "Needs OI history; not in local screen dataset.", 4),
        ("Liquidation-cluster fade", "Fade moves toward dense liquidation levels.", "Needs liquidation feed; not in local dataset.", 4),
        ("Spot-perp basis carry", "Long spot / short perp when basis is high.", "Needs spot series; not in local dataset.", 4),
        ("Dated-futures term-structure basis", "Trade quarterly basis vs perp.", "Needs dated futures; not in local dataset.", 3),
        ("BTC-dominance (market-cap) rotation", "Rotate by market-cap share of BTC.", "Needs market-cap series; not in local dataset.", 4),
        ("Stablecoin net-issuance regime", "Long alts when stablecoin supply expands.", "Needs stablecoin supply data.", 4),
        ("Exchange netflow / whale-transfer overlay", "Short when exchange inflows spike.", "Needs on-chain flow data.", 3),
        ("Coinbase-premium lead-lag", "Follow US-spot premium into perps.", "Needs Coinbase spot series.", 4),
        ("Token-unlock calendar short", "Short tokens 7 days before large unlocks.", "Needs unlock schedule.", 3),
        ("ETF-flow regime", "Long BTC when ETF flows positive.", "Needs ETF flow data.", 3),
        ("KR post-earnings-announcement drift", "Long positive-surprise KR stocks for 60 days.", "Equity: KR disclosures lack PIT/delisting license; blocked per STATUS.md.", 4),
        ("US PEAD SUE decile", "Long top SUE decile, short bottom.", "Equity: no PIT fundamentals; blocked per STATUS.md.", 4),
        ("KR 52-week-high momentum", "Long KR stocks at 52-week highs.", "Equity: delisting-PIT missing; blocked.", 3),
        ("US sector-ETF rotation", "Rotate sector ETFs by 6-month momentum.", "Equity: PIT/delisting blocked per STATUS.md.", 3),
        ("KR short-interest squeeze", "Long KR names with high short interest.", "Equity: no KRX short-interest feed locally.", 3),
        ("US index-reconstitution front-run", "Buy additions before index rebalance.", "Equity: PIT constituents not licensed.", 3),
        ("KR dividend-record-date capture", "Buy before record date, sell after.", "Equity: no PIT corporate-action data.", 2),
    ]
    for name, mech, note, pr in blocked:
        add(kind="blocked", fam="BLOCKED", prior=pr, name=name, mech=mech, rat=note,
            status="data-blocked")
    return rows


def b_prior(b: dict) -> int:
    return {"csmom": 6, "rev": 5, "lowvol": 5, "relbtc": 5, "volmom": 4, "fund": 6, "beta": 4}[b["kind"]]


def assign_ids(rows: list[dict]) -> list[dict]:
    for i, r in enumerate(rows, 1):
        r["idea_id"] = f"XB{i:03d}"
    # prior rank: higher prior score first, ties keep definition order
    order = sorted(range(len(rows)), key=lambda i: (-rows[i]["prior"], i))
    for rank, i in enumerate(order, 1):
        rows[i]["prior_rank"] = rank
    return rows


def spec_key(r: dict) -> str:
    return f"{r['kind']}|{r.get('L')}|{r.get('H')}|{r.get('R')}|{r.get('W')}|{r.get('sgn')}|{r.get('side')}|{r.get('X')}|{r.get('ov')}|{r.get('dir')}"


# ---------------------------------------------------------------- run
def evaluate(rows: list[dict], P: dict, G: dict) -> list[dict]:
    res = []
    ts = P["ts"]
    T = len(ts)
    half_rows = (np.arange(T) >= T // 2).astype(int) + 1
    years = (ts[-1] - ts[0]) / (365.25 * DAY_MS)
    for r in rows:
        if r["status"] != "screenable":
            res.append({"idea_id": r["idea_id"], "status": r["status"]})
            continue
        if r["kind"] in ("ratio", "breadth", "dd", "csmom", "rev", "lowvol", "idiovol", "volmom",
                         "fund", "beta", "relbtc", "skew"):
            Wr = weights_for(r, P, G)
            rets, active = basket_returns(Wr, r["H"], P)
            pos_idx = np.searchsorted(ts, Wr.index.values)
            half = np.where(pos_idx < T // 2, 1, 2)
            ppy = HOURS_PER_YEAR / r["H"]
            m = summarize(rets, active, half, ppy)
            m["exposure"] = float(active.mean())
        else:
            Ld, Sd = event_masks(r, P)
            pnl, tidx = event_trades(Ld, Sd, r["H"], P)
            # one period per entry bar: equal-weight average of symbols entering that bar
            per = pd.Series(pnl).groupby(tidx).mean()
            pr, pt = per.values, per.index.values
            half = np.where(pt < T // 2, 1, 2)
            ppy = len(pr) / years if years > 0 else 1.0
            m = summarize(pr, np.ones(len(pr), bool), half, ppy, trade_rets=pnl, n_comp=len(pr))
            m["exposure"] = float(len(pnl) * r["H"] / (T * P["C"].shape[1]))
        res.append({"idea_id": r["idea_id"], "status": "screenable", **m})
        print(f"{r['idea_id']} n={m['n_trades']:6d} sh={m['rough_sharpe']:+.2f} "
              f"comp={m['composite_score'] if m['composite_score']==m['composite_score'] else float('nan'):+.3f} {r['name'][:70]}",
              flush=True)
    return res


def write_outputs(rows: list[dict], res: list[dict]) -> None:
    by = {r["idea_id"]: r for r in res}
    with open(HERE / "IDEAS.csv", "w", newline="", encoding="utf-8") as f:
        f.write(f"# {LABEL}\n")
        w = csv.writer(f)
        w.writerow(["idea_id", "name", "mechanism_one_liner", "rationale_one_liner",
                    "prior_rank_note", "data_status"])
        for r in rows:
            note = f"prior_rank={r['prior_rank']} (prior {r['prior']}/10): {r['rat'] if r['status']=='data-blocked' else 'qualitative prior before any run'}"
            w.writerow([r["idea_id"], r["name"], r["mech"], r["rat"], note, r["status"]])

    cols = ["idea_id", "name", "family", "data_status", "prior_rank", "n_trades", "n_periods", "exposure",
            "win_rate", "profit_factor", "expectancy_bps", "rough_sharpe", "sharpe_h1",
            "sharpe_h2", "composite_score", "note"]
    out = []
    for r in rows:
        m = by[r["idea_id"]]
        rec = {"idea_id": r["idea_id"], "name": r["name"], "family": r["fam"],
               "data_status": r["status"], "prior_rank": r["prior_rank"]}
        if r["status"] == "screenable":
            rec.update({k: m.get(k) for k in cols if k in m})
        else:
            rec["note"] = "data-blocked: not scored"
        out.append(rec)
    out.sort(key=lambda d: (d["data_status"] != "screenable",
                            -(d.get("composite_score") if isinstance(d.get("composite_score"), float) and d.get("composite_score") == d.get("composite_score") else -1e9)))
    with open(HERE / "RESULTS.csv", "w", newline="", encoding="utf-8") as f:
        f.write(f"# {LABEL}\n")
        w = csv.DictWriter(f, fieldnames=cols, extrasaction="ignore")
        w.writeheader()
        for rec in out:
            w.writerow({k: (round(v, 4) if isinstance(v, float) else v) for k, v in rec.items()})
    return out


def write_top20(rows: list[dict], out: list[dict]) -> None:
    scored = [d for d in out if d["data_status"] == "screenable" and isinstance(d.get("composite_score"), float)
              and d["composite_score"] == d["composite_score"]]
    scored.sort(key=lambda d: -d["composite_score"])
    top = scored[:20]
    byid = {r["idea_id"]: r for r in rows}
    # Spearman between prior rank and empirical rank among scored ideas
    pr = np.array([d["prior_rank"] for d in scored], float)
    emp = np.arange(1, len(scored) + 1, dtype=float)
    rho = float(pd.Series(pr).corr(pd.Series(emp), method="spearman")) if len(scored) > 3 else float("nan")
    lines = [f"# RANKED TOP 20 — Lane B (crypto cross-asset / cross-sectional / calendar / regime)", "",
             f"> **{LABEL}**", "",
             "Caveats: exploratory screen only. No look-ahead-bias audit beyond causal construction, no multiple-testing correction "
             "(about 150 ideas scored, so expect false positives), no walk-forward, TRAIN window only, 1h bars, "
             "30 usable perps (POLUSDT and TONUSDT have no TRAIN bars; TIAUSDT and SEIUSDT dropped for <2000 TRAIN bars). "
             "Long-only alt-vs-BTC ideas carry raw alt beta during the in-sample trend and are not beta-neutralized. "
             "Not G-eligible. Not added to any real ledger. Ranking is by composite_score, which is a rough_sharpe shrunk by trade count and "
             "halved when the first- and second-half TRAIN Sharpe disagree.", "",
             f"Scored ideas: {len(scored)} of {sum(1 for r in rows if r['status']=='screenable')} screenable proposed; "
             f"{sum(1 for r in rows if r['status']=='data-blocked')} data-blocked (listed, not scored). "
             f"Zero-trade ideas (gate never fires in TRAIN, e.g. overlay O2a): {sum(1 for d in out if d.get('n_trades')==0)}. "
             f"Spearman(prior_rank, empirical rank) over scored ideas = {rho:.2f} (positive rho means the qualitative prior ranks the scored set in the same order, not that the prior is good).", "",
             "Shared conventions: entry = next 1h open, exit = close after H bars, 12bp per active rebalance/trade, one position per symbol for event ideas.", "",
             "| # | idea | composite | n | win% | PF | exp bp | rough Sharpe | H1 / H2 Sharpe | why |",
             "|---|---|---|---|---|---|---|---|---|---|"]
    for i, d in enumerate(top, 1):
        r = byid[d["idea_id"]]
        stable = "same sign in both TRAIN halves" if np.sign(d["sharpe_h1"]) == np.sign(d["sharpe_h2"]) else "UNSTABLE across TRAIN halves"
        why = f"{r['mech']} ({stable}.)"
        lines.append(f"| {i} | {d['idea_id']} {d['name']} | {d['composite_score']:+.3f} | {d['n_trades']} | "
                     f"{100*d['win_rate']:.1f} | {d['profit_factor']:.2f} | {d['expectancy_bps']:+.1f} | "
                     f"{d['rough_sharpe']:+.2f} | {d['sharpe_h1']:+.2f} / {d['sharpe_h2']:+.2f} | {why} |")
    lines += ["", "Top 10 summary (composite score, one-line mechanism):"]
    for i, d in enumerate(scored[:10], 1):
        lines.append(f"{i}. {d['idea_id']} {d['name']} — composite {d['composite_score']:+.3f}; {byid[d['idea_id']]['mech']}")
    (HERE / "RANKED_TOP20.md").write_text("\n".join(lines) + "\n", encoding="utf-8")
    print(f"Spearman prior vs empirical = {rho:.3f}; scored={len(scored)}")


def main() -> None:
    rows = assign_ids(make_ideas())
    print(f"proposed={len(rows)} screenable={sum(r['status']=='screenable' for r in rows)} "
          f"blocked={sum(r['status']=='data-blocked' for r in rows)}", flush=True)
    P = build_panel()
    print(f"panel: {P['C'].shape[1]} symbols x {P['C'].shape[0]} hourly rows", flush=True)
    G = gates(P)
    res = evaluate(rows, P, G)
    out = write_outputs(rows, res)
    write_top20(rows, out)


if __name__ == "__main__":
    main()
