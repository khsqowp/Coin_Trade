"""KR Round 2 hypotheses (KR-13..KR-24). Defaults fixed in prereg BEFORE any run. Dev data only.

fn(P, ctx, **p) -> (mask[T,N] signal at bar t, entry, exit). Close-entry convention: buy at close t (MOC), signal uses
bars <= t (closing-auction indicative price caveat; survivors get a +1 bar lag robustness check).
"""
import numpy as np
import pandas as pd
from lib import features as F, data
from lib.eventstudy import shift_up


def _idx(P):
    out = {}
    for n in ("KOSPI", "KOSDAQ"):
        d = data.load_index(n).reindex(P.dates).ffill()
        out[n] = d
    isk = (P.group == "KOSPI")[None, :]
    def mat(col):
        return np.where(isk, out["KOSPI"][col].to_numpy()[:, None], out["KOSDAQ"][col].to_numpy()[:, None])
    return out, mat


def _ret(P, k=1):
    return P.close / F.lag(P.close, k) - 1


def h_gd_nopanic(P, ctx, g=0.03, x=0.015):
    """KR-01 + own-market index gap at open > -x (idiosyncratic gap-down only)."""
    _, mat = _idx(P)
    ig = mat("open") / F.lag(mat("close"), 1) - 1
    gap = P.open / F.lag(P.close, 1) - 1
    return (gap <= -g) & (ig > -x), ("open", 0), ("close", 0)


def h_gd_ma50(P, ctx, g=0.03, n=50):
    """KR-01 + own-market index previous close above its SMA(n)."""
    _, mat = _idx(P)
    c = mat("close")
    up = F.lag(c, 1) > F.lag(F.sma(c, n), 1)
    gap = P.open / F.lag(P.close, 1) - 1
    return (gap <= -g) & up, ("open", 0), ("close", 0)


def _kqrel_sig(P, x, n):
    ix, _ = _idx(P)
    kq, ks = ix["KOSDAQ"]["close"], ix["KOSPI"]["close"]
    rel = (kq / kq.shift(n) - 1) - (ks / ks.shift(n) - 1)
    return (rel <= -x), kq


def h_kq_nopanic(P, ctx, x=0.03, n=3, h=3, panic=0.03):
    """KR-12 + exclude days where KOSDAQ falls more than `panic` on the signal day."""
    sig, kq = _kqrel_sig(P, x, n)
    ok = sig & ((kq / kq.shift(1) - 1) > -panic)
    m = np.broadcast_to(ok.to_numpy()[:, None], P.close.shape) & (P.group == "KOSDAQ")[None, :]
    return m, ("open", 1), ("close", h)


def h_kq_ma50(P, ctx, x=0.03, n=3, h=3, ma=50):
    """KR-12 + KOSDAQ close above its SMA(ma) on the signal day."""
    sig, kq = _kqrel_sig(P, x, n)
    ok = sig & (kq > kq.rolling(ma).mean())
    m = np.broadcast_to(ok.to_numpy()[:, None], P.close.shape) & (P.group == "KOSDAQ")[None, :]
    return m, ("open", 1), ("close", h)


def h_fade_spike(P, ctx, r=0.10, d=0.03, h=2):
    """Day s: ret>=r (liquid). Day t=s+1 closes down <= -d (not limit-down locked). Buy close t, hold h bars."""
    ret = _ret(P)
    m = (F.lag(ret, 1) >= r) & (ret <= -d) & (ret > -0.29)
    return m, ("close", 0), ("close", h)


def h_fade_volspike(P, ctx, v=3.0, r=0.05, d=0.02, h=2):
    """Day s: volume>=v*avg20(prev) and ret>=r. Day t=s+1 ret<=-d. Buy close t, hold h."""
    ret = _ret(P)
    v20 = F.lag(ctx.avgvol20(), 1)
    spike = (P.volume >= v * v20) & (ret >= r)
    m = F.lag(spike.astype(float), 1).astype(bool) & (ret <= -d) & (ret > -0.29)
    return m, ("close", 0), ("close", h)


def h_fade_breakout(P, ctx, n=20, v=2.0, d=0.02, h=3):
    """Day s: 20d-high close breakout w/ volume>=v*avg20. Day t=s+1 ret<=-d (failed follow-through). Buy close t, hold h."""
    ret = _ret(P)
    hi = F.lag(F.rolling_max(P.high, n), 1)
    v20 = F.lag(ctx.avgvol20(), 1)
    brk = (P.close > hi) & (P.volume >= v * v20)
    m = F.lag(brk.astype(float), 1).astype(bool) & (ret <= -d) & (ret > -0.29)
    return m, ("close", 0), ("close", h)


def _every(P, k):
    return (np.arange(len(P.dates)) % k) == (k - 1)


def _topk(score, rows_ok, k, ascending):
    """mask of k best finite scores per row (rows where rows_ok)."""
    T, N = score.shape
    m = np.zeros((T, N), bool)
    s = np.where(np.isfinite(score), score, np.nan)
    for t in np.nonzero(rows_ok)[0]:
        row = s[t]
        idx = np.nonzero(np.isfinite(row))[0]
        if len(idx) < k:
            continue
        o = idx[np.argsort(row[idx] if ascending else -row[idx], kind="stable")[:k]]
        m[t, o] = True
    return m


def h_top3_loser(P, ctx, k=3, lb=5, h=5, thr=2e10):
    """Every h-th bar: buy the k liquid names (20d value>=thr) with the lowest lb-day return, at close; hold h bars. Max k concurrent."""
    ret = _ret(P)
    score = np.where(P.liquid(thr) & (ret > -0.25), P.close / F.lag(P.close, lb) - 1, np.nan)
    return _topk(score, _every(P, h), k, True), ("close", 0), ("close", h)


def h_top3_winner(P, ctx, k=3, lb=20, h=5, thr=2e10):
    """Every h-th bar: buy the k liquid names with the highest lb-day return (not locked limit-up), at close; hold h bars."""
    ret = _ret(P)
    score = np.where(P.liquid(thr) & (ret < 0.25), P.close / F.lag(P.close, lb) - 1, np.nan)
    return _topk(score, _every(P, h), k, False), ("close", 0), ("close", h)


def h_pullback(P, ctx, fast=5, mid=20, slow=60, h=3):
    """Uptrend (SMA mid > SMA slow, SMA mid rising over 5 bars), pullback: close<SMA fast, close>=SMA mid, down day. Buy close, hold h."""
    f, m_, s = ctx.sma(fast), ctx.sma(mid), ctx.sma(slow)
    m = (m_ > s) & (m_ > F.lag(m_, 5)) & (P.close < f) & (P.close >= m_) & (_ret(P) < 0)
    return m, ("close", 0), ("close", h)


def h_nr7(P, ctx, n=7, ma=20, h=3):
    """Range compression: (H-L)/C is the minimum of the last n bars and close>SMA(ma). Buy close, hold h."""
    rg = pd.DataFrame((P.high - P.low) / P.close)
    trend = (P.close > ctx.sma(ma)) if ma else np.ones(P.close.shape, bool)
    m = (rg.to_numpy() <= rg.rolling(n, min_periods=n).min().to_numpy()) & trend
    return m, ("close", 0), ("close", h)


def h_ld_rebound(P, ctx, r=0.15, dry=0.5, h=3):
    """Day s=t-1 ret<=-r (liquid); day t volume < dry*volume_s (dry-up) and not another >3% drop. Buy close t, hold h."""
    ret = _ret(P)
    m = (F.lag(ret, 1) <= -r) & (P.volume < dry * F.lag(P.volume, 1)) & (ret > -0.03)
    return m, ("close", 0), ("close", h)


# id: (fn, defaults, grid(<=3 params x 3 values), idea, N concurrent slots, signal text)
H2 = {
 "KR-13": (h_gd_nopanic, dict(g=0.03, x=0.015), dict(g=(0.02, 0.03, 0.05), x=(0.01, 0.015, 0.02)),
           "KR-01 gap-down fade (buy open/sell close) excluding market-panic opens (own index gap <= -1.5%)", 5,
           "gap=open_t/close_{t-1}-1<=-3% AND own-market index (KOSPI for KOSPI names, KOSDAQ for KOSDAQ) open_t/close_{t-1}-1 > -1.5%. Buy open t, sell close t."),
 "KR-14": (h_gd_ma50, dict(g=0.03, n=50), dict(g=(0.02, 0.03, 0.05), n=(20, 50, 100)),
           "KR-01 gap-down fade only when own-market index prior close > SMA50", 5,
           "gap<=-3% AND own-market index close_{t-1} > its SMA50_{t-1}. Buy open t, sell close t."),
 "KR-15": (h_kq_nopanic, dict(x=0.03, n=3, h=3, panic=0.03), dict(x=(0.02, 0.03, 0.04), h=(2, 3, 5), panic=(0.02, 0.03, 0.05)),
           "KR-12 KOSDAQ-lags-KOSPI rebound excluding KOSDAQ panic days (signal-day KOSDAQ ret <= -3%)", 5,
           "KR-12 signal (3d KOSDAQ minus KOSPI <= -3%) AND KOSDAQ ret_t > -3%. Buy liquid KOSDAQ names open t+1, sell close t+3."),
 "KR-16": (h_kq_ma50, dict(x=0.03, n=3, h=3, ma=50), dict(x=(0.02, 0.03, 0.04), h=(2, 3, 5), ma=(20, 50, 100)),
           "KR-12 KOSDAQ-lags-KOSPI rebound only when KOSDAQ close > SMA50", 5,
           "KR-12 signal AND KOSDAQ close_t > SMA50_t. Buy liquid KOSDAQ names open t+1, sell close t+3."),
 "KR-17": (h_fade_spike, dict(r=0.10, d=0.03, h=2), dict(r=(0.07, 0.10, 0.15), d=(0.02, 0.03, 0.05), h=(1, 2, 3)),
           "long-only fade proxy: after a >=+10% spike day, buy the close of the next day if it fell >=3%, hold 2", 5,
           "ret_{t-1}>=10% AND ret_t<=-3% (and > -29%, i.e. not locked limit-down). Buy close t (MOC), sell close t+2."),
 "KR-18": (h_fade_volspike, dict(v=3.0, r=0.05, d=0.02, h=2), dict(v=(2.0, 3.0, 4.0), r=(0.03, 0.05, 0.08), h=(1, 2, 3)),
           "long-only fade proxy: after volume>=3x & ret>=+5% day, buy next-day close if it fell >=2%, hold 2", 5,
           "day t-1: volume>=3x avg20 and ret>=5%; day t: ret<=-2% (and > -29%). Buy close t, sell close t+2."),
 "KR-19": (h_fade_breakout, dict(n=20, v=2.0, d=0.02, h=3), dict(n=(20, 40, 60), d=(0.01, 0.02, 0.03), h=(2, 3, 5)),
           "long-only fade proxy: after 20d-high volume breakout, buy next-day close if it fell >=2% (failed follow-through), hold 3", 5,
           "day t-1: close>max high(t-21..t-2) & volume>=2x avg20; day t: ret<=-2%. Buy close t, sell close t+3."),
 "KR-20": (h_top3_loser, dict(k=3, lb=5, h=5, thr=2e10), dict(k=(2, 3, 4), lb=(3, 5, 10), h=(3, 5, 7)),
           "concentrated weekly reversal: every 5th bar buy the 3 worst 5d performers among liquid (>=2e10) names, hold 5", 3,
           "Bars with index%5==4: rank liquid(20d value>=2e10) names by 5d return ascending (exclude ret_t<=-25%); buy lowest 3 at close t, sell close t+5."),
 "KR-21": (h_top3_winner, dict(k=3, lb=20, h=5, thr=2e10), dict(k=(2, 3, 4), lb=(10, 20, 40), h=(3, 5, 7)),
           "concentrated weekly momentum: every 5th bar buy the 3 best 20d performers among liquid names, hold 5", 3,
           "Bars with index%5==4: rank liquid names by 20d return descending (exclude ret_t>=25%); buy top 3 at close t, sell close t+5."),
 "KR-22": (h_pullback, dict(fast=5, mid=20, slow=60, h=3), dict(fast=(3, 5, 10), slow=(40, 60, 120), h=(2, 3, 5)),
           "MA5/MA20 pullback in uptrend (SMA20>SMA60, SMA20 rising), close<SMA5 & >=SMA20 on down day; buy close, hold 3", 5,
           "SMA20>SMA60 AND SMA20_t>SMA20_{t-5} AND close<SMA5 AND close>=SMA20 AND ret_t<0. Buy close t, sell close t+3."),
 "KR-23": (h_nr7, dict(n=7, ma=20, h=3), dict(n=(5, 7, 10), ma=(0, 20, 50), h=(2, 3, 5)),
           "range compression NR7 in uptrend (close>SMA20), buy close, hold 3 (expansion)", 5,
           "(H-L)/C_t is the minimum of last 7 bars AND close_t>SMA20. Buy close t, sell close t+3."),
 "KR-24": (h_ld_rebound, dict(r=0.15, dry=0.5, h=3), dict(r=(0.10, 0.15, 0.20), dry=(0.3, 0.5, 0.7), h=(2, 3, 5)),
           "post-crash rebound with volume dry-up: day t-1 ret<=-15%, day t volume<0.5x that day, buy close t, hold 3", 5,
           "ret_{t-1}<=-15% AND volume_t<0.5*volume_{t-1} AND ret_t>-3%. Buy close t, sell close t+3."),
}
