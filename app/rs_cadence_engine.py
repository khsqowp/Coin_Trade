"""Cadence research engine (offline, numba). Signal at close t -> weights set at close t, earn returns from t+1.
Weights are fractions of equity (gross 1.0 at 1x), drift with price between rebalances, fees charged on
|delta w| at the rebalance close. Funding: daily sum of 8h rates settled on date d is charged to weights held
through date d (long pays positive rate). NaN price return while held -> 0 pnl (name is ineligible -> exits)."""
from __future__ import annotations
from dataclasses import dataclass, asdict, replace
import numpy as np
import pandas as pd
from numba import njit

FEE = 0.001  # 0.05% taker + 0.05% slippage per side


@dataclass(frozen=True)
class Cfg:
    mode: str = "fixed"        # fixed | event | vol
    lbs: tuple = (14,)
    k: int = 8
    cadence: int = 3
    offset: int = 0
    band: int = 0              # hysteresis margin m
    frac: float = 1.0          # partial rebalance fraction
    drift: int = 2             # event: #holdings outside band that triggers
    decay: float = 1e9         # event: target-held score gap that triggers
    minimum: int = 1           # event: min days between rebalances
    cap: int = 14              # event: max days between rebalances
    inverse: bool = False      # vol mode: slower when dispersion high


@njit(cache=True)
def _sim(ret, fund, score, elig, volratio, start, end, mode, k, cadence, offset, band, frac,
         drift, decay, minimum, cap, inverse, fee, funding_on, trace):
    n, p = ret.shape
    w = np.zeros(p)
    net = np.zeros(n); fees = np.zeros(n); fpn = np.zeros(n); turn = np.zeros(n)
    trd = np.zeros(n); reb = np.zeros(n)
    hist = np.zeros((n if trace else 1, p))
    last = -10 ** 6
    first = -1
    for t in range(start, end):
        if trace:
            hist[t] = w
        pnl = 0.0; fp = 0.0
        for j in range(p):
            if w[j] != 0.0:
                r = ret[t, j]
                if np.isfinite(r):
                    pnl += w[j] * r
                if funding_on:
                    fp -= w[j] * fund[t, j]
        g = 1.0 + pnl + fp
        fpn[t] = fp
        for j in range(p):
            if w[j] != 0.0:
                r = ret[t, j]
                if not np.isfinite(r):
                    r = 0.0
                w[j] = w[j] * (1.0 + r) / g
        cnt = 0
        for j in range(p):
            if elig[t, j]:
                cnt += 1
        if cnt >= 2 * k:
            if first < 0:
                first = t
            order = np.argsort(-score[t])  # best first; ineligible are -inf (last)
            rank = np.empty(p, np.int64)
            for z in range(p):
                rank[order[z]] = z
            # target with hysteresis
            tgt = np.zeros(p)
            nl = 0; ns = 0
            if band > 0:
                for j in range(p):
                    if elig[t, j]:
                        if w[j] > 1e-12 and rank[j] < k + band and nl < k:
                            tgt[j] = 0.5 / k; nl += 1
                        elif w[j] < -1e-12 and rank[j] >= cnt - k - band and ns < k:
                            tgt[j] = -0.5 / k; ns += 1
            for z in range(cnt):
                if nl >= k:
                    break
                j = order[z]
                if tgt[j] == 0.0:
                    tgt[j] = 0.5 / k; nl += 1
            for z in range(cnt - 1, -1, -1):
                if ns >= k:
                    break
                j = order[z]
                if tgt[j] == 0.0:
                    tgt[j] = -0.5 / k; ns += 1
            due = False
            if mode == 0:
                due = (t - first - offset) >= 0 and (t - first - offset) % cadence == 0
            elif mode == 1:
                gross = 0.0; bad = 0; hv = 0.0; tv = 0.0
                for j in range(p):
                    gross += abs(w[j])
                    if w[j] > 1e-12 and (not elig[t, j] or rank[j] >= k + band):
                        bad += 1
                    if w[j] < -1e-12 and (not elig[t, j] or rank[j] < cnt - k - band):
                        bad += 1
                    if elig[t, j]:
                        hv += w[j] * score[t, j]; tv += tgt[j] * score[t, j]
                el = t - last
                if gross < 1e-9:
                    due = True
                elif el >= minimum:
                    due = bad >= drift or (tv - hv / gross) > decay or el >= cap
            else:
                v = volratio[t]
                if not np.isfinite(v) or v <= 0:
                    v = 1.0
                if inverse:
                    v = 1.0 / v
                iv = int(np.floor(cadence / v + 0.5))
                iv = min(14, max(1, iv))
                due = (t - last) >= iv
            if due:
                tc = 0.0; nt = 0
                dl = np.zeros(p)
                for j in range(p):
                    dl[j] = frac * (tgt[j] - w[j])
                    tc += abs(dl[j])
                    if abs(dl[j]) > 1e-10:
                        nt += 1
                cost = fee * tc
                fees[t] = g * cost; turn[t] = tc; trd[t] = nt; reb[t] = 1.0
                for j in range(p):
                    w[j] = (w[j] + dl[j]) / (1.0 - cost)
                g *= (1.0 - cost)
                last = t
        net[t] = g - 1.0
    return net, fees, fpn, turn, trd, reb, hist


class Engine:
    def __init__(self, data, sim_start="2022-01-01", ffill_limit=3):
        c = data["close"].sort_index()
        c.index = pd.to_datetime(c.index, utc=True).normalize()
        c = c.reindex(pd.date_range(c.index.min(), c.index.max(), freq="D", tz="UTC"))
        c = c.where(c > 0).ffill(limit=ffill_limit)
        self.close = c; self.dates = c.index; self.syms = list(c.columns)
        self.px = c.to_numpy(float)
        self.ret = np.full_like(self.px, np.nan)
        self.ret[1:] = self.px[1:] / self.px[:-1] - 1
        f = data["funding"].copy(); f.index = pd.to_datetime(f.index, utc=True)
        f = f.reindex(columns=c.columns)
        d = f.groupby(f.index.floor("D")).sum(min_count=1).reindex(self.dates)
        cnt = f.notna().groupby(f.index.floor("D")).sum().reindex(self.dates).fillna(0)
        self.fund = d.fillna(0).to_numpy(float)
        self.fund_cov = float(np.mean(cnt.to_numpy()[self.dates >= pd.Timestamp(sim_start, tz="UTC")] >= 2))
        disp = pd.Series(np.nanstd(self.ret, axis=1), index=self.dates).rolling(20, min_periods=20).mean()
        med = disp.rolling(365, min_periods=90).median()
        self.volratio = (disp / med).to_numpy()  # causal
        self.start = int(self.dates.searchsorted(pd.Timestamp(sim_start, tz="UTC")))
        self._sig = {}

    def signal(self, lbs):
        lbs = tuple(lbs)
        if lbs not in self._sig:
            sc, el = [], np.ones(self.px.shape, bool)
            for lb in lbs:
                m = np.full_like(self.px, np.nan)
                m[lb:] = self.px[lb:] / self.px[:-lb] - 1
                ok = np.isfinite(m)
                r = pd.DataFrame(m).rank(axis=1).to_numpy()
                cnt = ok.sum(axis=1, keepdims=True)
                z = (r - (cnt + 1) / 2) / np.sqrt(np.maximum((cnt * cnt - 1) / 12, 1))
                sc.append(z); el &= ok
            s = np.mean(sc, axis=0)
            s[~el] = -np.inf
            self._sig[lbs] = (s, el)
        return self._sig[lbs]

    def run(self, c: Cfg, fee=FEE, funding=True, trace=False, end=None, start=None):
        s, el = self.signal(c.lbs)
        mode = {"fixed": 0, "event": 1, "vol": 2}[c.mode]
        e = len(self.dates) if end is None else end
        st = self.start if start is None else start
        net, fees, fp, turn, trd, reb, hist = _sim(
            self.ret, self.fund, s, el, self.volratio, st, e, mode, c.k, c.cadence, c.offset, c.band,
            c.frac, c.drift, c.decay, c.minimum, c.cap, c.inverse, fee, funding, trace)
        return dict(net=net, fees=fees, funding=fp, turn=turn, trd=trd, reb=reb, hist=hist, start=st)

    def metrics(self, res, b=None, e=None):
        d = self.dates
        m = np.zeros(len(d), bool); m[res["start"]:] = True
        if b: m &= d >= pd.Timestamp(b, tz="UTC")
        if e: m &= d <= pd.Timestamp(e, tz="UTC")
        m &= np.arange(len(d)) < len(res["net"])
        if m.sum() < 30:
            return None
        r = res["net"][m]; yrs = m.sum() / 365.0
        eq = np.cumprod(1 + r); pk = np.maximum.accumulate(np.r_[1.0, eq])[1:]
        mdd = float((1 - eq / pk).max()); cagr = float(eq[-1] ** (1 / yrs) - 1)
        sd = r.std(ddof=1)
        yrsr = d[m].year
        return dict(CAGR=cagr, MDD=mdd, Calmar=cagr / mdd if mdd > 0 else 0.0,
                    Sharpe=float(r.mean() / sd * np.sqrt(365)) if sd > 0 else 0.0, worst=float(r.min()),
                    yearly={int(y): float(np.prod(1 + r[yrsr == y]) - 1) for y in np.unique(yrsr)},
                    reb_yr=float(res["reb"][m].sum() / yrs), trades_yr=float(res["trd"][m].sum() / yrs),
                    turn_yr=float(res["turn"][m].sum() / yrs), fee_yr=float(res["fees"][m].sum() / yrs),
                    fund_yr=float(res["funding"][m].sum() / yrs), days=int(m.sum()))
