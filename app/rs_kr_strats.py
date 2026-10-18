"""KR 포팅 전략의 신호/목표비중 생성기 (코인 전략 -> 국내주식 일봉)."""
from __future__ import annotations

import numpy as np
import pandas as pd


def _df(a, P):
    return pd.DataFrame(a, index=P.dates, columns=P.syms)


def prep(P):
    """공통 지표 패널. 종가는 ffill(상장 전은 NaN 유지)."""
    c = _df(P.c, P).ffill()
    ind = {"c": c}
    for n in (9, 21):
        ind[f"ema{n}"] = c.ewm(span=n, adjust=False).mean()
    ind["sma200"] = c.rolling(200, min_periods=200).mean()
    ret1 = c.pct_change(fill_method=None).where(P.elig)
    idx_ret = ret1.mean(axis=1).fillna(0.0)          # 시장 프록시 = 유니버스 균등가중 일수익률
    ind["mkt"] = (1 + idx_ret).cumprod()
    return ind


def crash_state(mkt: pd.Series, thr=-0.10, look=14, rec=0.0):
    """S2: 14일 -10% 이상 하락이면 현금, 14일 수익률이 rec 이상 회복되면 해제."""
    r = (mkt / mkt.shift(look) - 1).to_numpy()
    st = np.zeros(len(r), bool); on = False
    for i, x in enumerate(r):
        if np.isnan(x):
            continue
        if not on and x <= thr:
            on = True
        elif on and x >= rec:
            on = False
        st[i] = on
    return st


def momentum_target(P, ind, L, K, R, filt="none", short=False, start=0):
    T, N = P.c.shape
    ret = (ind["c"] / ind["c"].shift(L) - 1).to_numpy()
    ret = np.where(P.elig & ~np.isnan(ret), ret, np.nan)
    mkt = ind["mkt"]
    bad = np.zeros(T, bool)
    if filt in ("crash", "both"):
        bad |= crash_state(mkt)
    if filt in ("sma200", "both"):
        bad |= (mkt < mkt.rolling(200, min_periods=200).mean()).to_numpy()
    tgt = np.full((T, N), np.nan)
    last_bad = False; since = 0
    for t in range(start, T):
        force = last_bad and not bad[t]
        due = ((t - start) % R == 0) or force
        if bad[t]:
            tgt[t] = 0.0       # 매일 현금 유지 지시
        elif due:
            row = ret[t]; ok = ~np.isnan(row)
            w = np.zeros(N)
            if ok.sum() >= K:
                order = np.argsort(-np.where(ok, row, -np.inf))
                top = order[:K]
                if short:
                    w[top] = 0.5 / K
                    bot = np.argsort(np.where(ok, row, np.inf))[:K]
                    w[bot] = -0.5 / K
                else:
                    w[top] = 1.0 / K
            tgt[t] = w
        last_bad = bad[t]
    return tgt


def ew_target(P, R=21, top_by_value=None, start=0):
    T, N = P.c.shape
    tgt = np.full((T, N), np.nan)
    val = _df(P.c * P.v, P).rolling(60, min_periods=30).median().to_numpy()
    for t in range(start, T, 1):
        if (t - start) % R:
            continue
        el = P.elig[t]
        if top_by_value:
            m = np.where(el, val[t], -1)
            idx = np.argsort(-m)[:top_by_value]
            idx = idx[m[idx] > 0]
            w = np.zeros(N); w[idx] = 1 / max(len(idx), 1)
        else:
            w = el / max(el.sum(), 1)
        tgt[t] = w
    return tgt


def buyhold_target(P, j, start):
    tgt = np.full(P.c.shape, np.nan); w = np.zeros(P.c.shape[1]); w[j] = 1
    tgt[start] = w
    return tgt


def cross(a, b):
    up = (a > b) & ~(a.shift(1) > b.shift(1))
    dn = (a < b) & ~(a.shift(1) < b.shift(1))
    return up.fillna(False).to_numpy(), dn.fillna(False).to_numpy()


def sig_trx(P, ind):   # S3 EMA9/21 골든->진입, 데드->청산
    up, dn = cross(ind["ema9"], ind["ema21"])
    return up, dn, np.zeros(up.shape)


def sig_swing6(P, ind):  # S4
    up, dn = cross(ind["ema9"], ind["ema21"])
    above = (ind["c"] > ind["sma200"]).fillna(False).to_numpy()
    score = ((ind["c"] - ind["sma200"]) / ind["sma200"]).to_numpy()
    return up & above, dn, score


def sig_mach7(P, ind, fast=10, mid=50, slow=200, win=10, exit_ema=50, rs=90):
    c = ind["c"]; lo = _df(P.l, P).ffill(); hi = _df(P.h, P).ffill()
    ef, em, es, ex = (c.ewm(span=n, adjust=False).mean() for n in (fast, mid, slow, exit_ema))
    aligned = (ef > em) & (em > es)
    dipped = (lo <= ef).rolling(win, min_periods=1).max().astype(bool)
    reclaim = (c > ef) & (c > hi.shift(1))
    ent = (aligned & dipped & reclaim).fillna(False).to_numpy()
    ex_sig = (c < ex).fillna(False).to_numpy()
    return ent, ex_sig, (c / c.shift(rs) - 1).to_numpy()


def sig_squeeze(P, ind, rs=90):
    c = ind["c"]; s20 = c.rolling(20, min_periods=20).mean(); s200 = ind["sma200"]
    gap = (s20 - s200).abs() / s200 * 100
    sq = (gap <= 3.0).rolling(10, min_periods=1).max().astype(bool)
    cr = ((s20 > s200) != (s20 > s200).shift(1)).rolling(20, min_periods=1).sum() > 3
    ab = c > s20
    cu = ab & ~ab.shift(1).fillna(False).astype(bool)
    ent = (cu & (c > s200) & sq & ~cr).fillna(False).to_numpy()
    return ent, (~ab).to_numpy(), (c / c.shift(rs) - 1).to_numpy()


def sig_pullback(P, ind, ma=10, vol_filter=True):
    c = ind["c"]; sma = c.rolling(ma, min_periods=ma).mean()
    to = _df(P.c * P.v, P)
    ratio = to / to.rolling(60, min_periods=20).mean()
    ab = c > sma
    cu = ab & ~ab.shift(1).fillna(False).astype(bool)
    ent = cu & (ratio >= 1.5) if vol_filter else cu
    return ent.fillna(False).to_numpy(), (~ab).to_numpy(), (c / c.shift(20) - 1).to_numpy()
