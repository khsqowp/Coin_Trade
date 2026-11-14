"""KR Round 3 preregistered hypotheses (KR-25..KR-36)."""
import numpy as np
import pandas as pd
from lib import features as F, data
from kr.hypotheses2 import _topk, _every, h_ld_rebound


def _ret(P, n):
    with np.errstate(invalid="ignore", divide="ignore"):
        return P.close / F.lag(P.close, n) - 1


def _cool(mask, P, h):
    """Accept eligible finite-return signals; suppress next h signal bars per name."""
    m = np.asarray(mask, dtype=bool) & P.liquid(2e9)
    future = np.full_like(P.close, np.nan)
    if h < len(P.dates):
        future[:-h] = P.close[h:]
    m &= np.isfinite(P.close) & np.isfinite(future)
    out = np.zeros_like(m)
    next_ok = np.zeros(m.shape[1], dtype=np.int64)
    for t in range(m.shape[0]):
        take = m[t] & (t >= next_ok)
        out[t] = take
        next_ok[take] = t + h + 1
    return out


def _event(mask, P, h):
    return _cool(mask, P, h), ("close", 0), ("close", h)


def h25(P, ctx, r=0.15, dry=0.5, h=3):
    ret = _ret(P, 1)
    recent = pd.DataFrame(P.volume).rolling(3, min_periods=3).mean().to_numpy()
    prior = F.lag(pd.DataFrame(P.volume).rolling(20, min_periods=20).mean().to_numpy(), 3)
    m = (_ret(P, 5) <= -r) & (recent < dry * prior) & (ret > -0.03)
    return _event(m, P, h)


def h26(P, ctx, r=0.20, q=0.30, h=3):
    crash = _ret(P, 10) <= -r
    vol = P.volume
    threshold = np.full(vol.shape, np.nan)
    for t in np.nonzero(crash.any(axis=1))[0]:
        for j in np.nonzero(crash[t])[0]:
            hist = vol[max(0, t - 250):t, j]
            hist = hist[np.isfinite(hist)]
            if len(hist) >= 120 and np.isfinite(vol[t, j]):
                threshold[t, j] = np.percentile(hist, 100 * q)
    return _event(crash & (vol <= threshold) & (_ret(P, 1) > -0.03), P, h)


def h27(P, ctx, z=0.05, d=0.15, dry=0.5, h=3):
    low = pd.DataFrame(P.close).rolling(250, min_periods=250).min().to_numpy()
    prior_hi_vol = F.lag(F.rolling_max(P.volume, 5), 1)
    m = (P.close <= (1 + z) * low) & (_ret(P, 20) <= -d)
    m &= (P.volume < dry * prior_hi_vol) & (_ret(P, 1) > -0.03)
    return _event(m, P, h)


def h28(P, ctx, x=20, ma=200, h=5):
    return _event((ctx.rsi(5) < x) & (P.close > ctx.sma(ma)), P, h)


def h29(P, ctx, x=20, ma=200, h=10):
    return h28(P, ctx, x=x, ma=ma, h=h)


def h30(P, ctx, x=20, ma=200, h=20):
    return h28(P, ctx, x=x, ma=ma, h=h)


def _lowdry(P, n, dry, h):
    low = pd.DataFrame(P.close).rolling(n, min_periods=n).min().to_numpy()
    prior = F.lag(pd.DataFrame(P.volume).rolling(n, min_periods=n).mean().to_numpy())
    return _event((P.close <= low) & (P.volume < dry * prior), P, h)


def h31(P, ctx, n=20, dry=0.5, h=5):
    return _lowdry(P, n, dry, h)


def h32(P, ctx, n=20, dry=0.5, h=10):
    return _lowdry(P, n, dry, h)


def _ranked_losers(P, k, lb, top, h):
    ret = _ret(P, 1)
    score = np.where(P.liquid(2e9) & (P.group == "KOSPI")[None, :] & (P.value20 >= 0), _ret(P, lb), np.nan)
    # Restrict the cross-section to the top `top` by value20 at each bar.
    for t in range(len(P.dates)):
        cols = np.flatnonzero(np.isfinite(score[t]))
        if len(cols) > top:
            keep = cols[np.argsort(P.value20[t, cols], kind="stable")[-top:]]
            drop = np.setdiff1d(cols, keep, assume_unique=True)
            score[t, drop] = np.nan
    score[ret <= -0.25] = np.nan
    return _topk(score, _every(P, h), k, True), ("close", 0), ("close", h)


def h33(P, ctx, k=5, lb=5, top=200, h=5):
    return _ranked_losers(P, k, lb, top, h)


def h34(P, ctx, k=5, lb=5, top=200, h=10):
    return _ranked_losers(P, k, lb, top, h)


def h35(P, ctx, k=10, lb=60, ma=200):
    idx = ctx.index("KOSPI").reindex(P.dates).ffill()
    idx_sma = idx.rolling(ma, min_periods=ma).mean()
    score = 0.5 * _ret(P, 20) + 0.5 * _ret(P, lb)
    score = np.where((P.value20 >= 2e10) & (_ret(P, 1) < 0.25), score, np.nan)
    m = _topk(score, _every(P, 20) & (idx.to_numpy() > idx_sma.to_numpy()), k, False)
    return m, ("close", 0), ("close", 20)


def h36(P, ctx, h=3):
    union = np.zeros(P.close.shape, dtype=bool)
    for fn, params in ((h25, dict(r=.15, dry=.5, h=3)), (h26, dict(r=.2, q=.3, h=3)),
                       (h27, dict(z=.05, d=.15, dry=.5, h=3))):
        union |= fn(P, ctx, **params)[0]
    return _event(union, P, h)


def h_kr24(P, ctx, r=0.15, dry=0.5, h=3):
    return h_ld_rebound(P, ctx, r=r, dry=dry, h=h)


H3 = {
    "KR-25": (h25, dict(r=.15, dry=.5, h=3), dict(r=(.12,.15,.20), dry=(.35,.5,.7), h=(2,3,5)), "Crash5 rebound with 3-bar volume dry-up", 5, "5-bar return<=-r; mean volume last 3 bars < dry times prior 20-bar mean; ret_t>-3%; buy close t, sell close t+h."),
    "KR-26": (h26, dict(r=.20, q=.30, h=3), dict(r=(.15,.20,.25), q=(.2,.3,.4), h=(2,3,5)), "Crash10 rebound with own-volume rolling percentile filter", 5, "10-bar return<=-r; volume_t<=q percentile of prior 250 bars (minimum 120); ret_t>-3%; buy close t, sell close t+h."),
    "KR-27": (h27, dict(z=.05,d=.15,dry=.5,h=3), dict(z=(.03,.05,.10),d=(.10,.15,.20),dry=(.35,.5,.7)), "52-week low zone after drawdown with volume dry-up", 5, "Close within z of 250-bar low, 20-bar return<=-d, volume below dry times prior 5-bar maximum, ret_t>-3%; hold 3."),
    "KR-28": (h28, dict(x=20,ma=200,h=5), dict(x=(15,20,25),ma=(100,200,300),h=(3,5,10)), "Oversold bounce in long-term uptrend", 5, "RSI(5)<x and close>SMA(ma); buy close t and hold h."),
    "KR-29": (h29, dict(x=20,ma=200,h=10), dict(x=(15,20,25),ma=(100,200,300),h=(5,10,15)), "Oversold bounce in long-term uptrend", 5, "RSI(5)<x and close>SMA(ma); buy close t and hold h."),
    "KR-30": (h30, dict(x=20,ma=200,h=20), dict(x=(15,20,25),ma=(100,200,300),h=(10,20,30)), "Oversold bounce in long-term uptrend", 5, "RSI(5)<x and close>SMA(ma); buy close t and hold h."),
    "KR-31": (h31, dict(n=20,dry=.5,h=5), dict(n=(10,20,40),dry=(.35,.5,.7),h=(3,5,10)), "20-day low with volume dry-up", 5, "Close equals rolling n-bar low and volume_t<dry times prior n-bar mean; hold h."),
    "KR-32": (h32, dict(n=20,dry=.5,h=10), dict(n=(10,20,40),dry=(.35,.5,.7),h=(5,10,15)), "20-day low with volume dry-up", 5, "Close equals rolling n-bar low and volume_t<dry times prior n-bar mean; hold h."),
    "KR-33": (h33, dict(k=5,lb=5,top=200,h=5), dict(k=(3,5,8),lb=(3,5,10),top=(100,200,300)), "Weekly KOSPI top-value loser reversal", 5, "Every h-th bar, buy k lowest lb-day returns among KOSPI names in top top by value20 and liquid>=2e9; exclude return<=-25%."),
    "KR-34": (h34, dict(k=5,lb=5,top=200,h=10), dict(k=(3,5,8),lb=(3,5,10),top=(100,200,300)), "Biweekly KOSPI top-value loser reversal", 5, "Every h-th bar, buy k lowest lb-day returns among KOSPI names in top top by value20 and liquid>=2e9; exclude return<=-25%."),
    "KR-35": (h35, dict(k=10,lb=60,ma=200), dict(k=(5,10,20),lb=(40,60,90),ma=(100,200,300)), "Monthly momentum with KOSPI index trend filter", 10, "Every 20th bar: if KOSPI index close>SMA(ma), buy top k score=.5*20-day return+.5*lb-day return among value20>=2e10, excluding daily return>=25%; hold 20."),
    "KR-36": (h36, dict(h=3), dict(h=(2,3,5)), "Pooled union of KR-25/26/27 rebound signals", 5, "Union of default KR-25, KR-26, KR-27 signals; per-stock cooldown h; buy close t, sell close t+h."),
}
