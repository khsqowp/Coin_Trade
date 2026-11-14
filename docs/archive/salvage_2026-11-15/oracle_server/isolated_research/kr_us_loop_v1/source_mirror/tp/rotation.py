"""Small-capital long-only ROTATION simulator (backtest / forward PAPER only, no order code, no exchange keys).

Hourly bar engine over a universe of USDT-M perpetuals. Decisions are taken at the CLOSE of a clock bar (1h / 4h / 1d / adaptive), orders fill at the NEXT 1h open
(taker fee + slippage on the fill, real funding every 8h). Exchange filters (minNotional, stepSize, minQty) are applied to every order: a violating order is
REJECTED (stay in cash). Isolated margin with liquidation for leverage > 1. Rules are fixed in research/PREREG_round3.md; nothing here is fitted."""
import math

import numpy as np
import pandas as pd

from . import futbt, regime_det, store

H7, H14, H30, H50 = 168, 336, 720, 1200
WARMUP = 1300                       # common start so that every variant and benchmark covers the same bars
CLOCK_H = {"1h": 1, "4h": 4, "1d": 24}
STOPS = ("trail10", "atr3", "down4", "loss7")
SRC = "binanceusdm"


class Data:
    """Aligned hourly arrays (time x symbol). NaN before a symbol exists."""

    def __init__(self, frames, filters, funding):
        self.syms = sorted(frames)
        idx = sorted(set().union(*[set(f.index) for f in frames.values()]))
        self.index = pd.DatetimeIndex(idx)
        n, m = len(self.index), len(self.syms)
        self.O, self.H, self.L, self.C, self.V = (np.full((n, m), np.nan) for _ in range(5))
        for j, s in enumerate(self.syms):
            f = frames[s].reindex(self.index)
            self.O[:, j], self.H[:, j], self.L[:, j], self.C[:, j], self.V[:, j] = (f[k].values for k in ("open", "high", "low", "close", "volume"))
        self.filters = filters
        self.first = np.array([int(np.argmax(np.isfinite(self.C[:, j]))) for j in range(m)])
        self.fund = np.zeros((n, m))
        for j, s in enumerate(self.syms):
            ts, rate = funding.get(s, (np.array([], "int64"), np.array([])))
            if len(ts):
                self.fund[:, j] = futbt.funding_per_bar(self.index, 3600_000, ts, rate)
        dv = np.nan_to_num(self.C * self.V)
        cs = np.vstack([np.zeros((1, m)), np.cumsum(dv, axis=0)])
        self.dv30 = np.full((n, m), np.nan)
        self.dv30[H30:] = cs[H30 + 1:] - cs[1:n - H30 + 1]
        c = pd.DataFrame(self.C)
        self.r7 = (c / c.shift(H7) - 1).values
        self.r14 = (c / c.shift(H14) - 1).values
        b = self.syms.index("BTCUSDT")
        self.b = b
        self.btc_ok = self.C[:, b] > pd.Series(self.C[:, b]).rolling(H50).mean().values
        self.btc_r14 = self.r14[:, b]
        tr = np.fmax(self.H - self.L, np.fmax(np.abs(self.H - np.vstack([self.C[:1], self.C[:-1]])), np.abs(self.L - np.vstack([self.C[:1], self.C[:-1]]))))
        self.atr = {}
        for k, h in CLOCK_H.items():
            self.atr[k] = pd.DataFrame(tr).rolling(14 * h, min_periods=14 * h).mean().values * math.sqrt(h)
        self.close_hour = (self.index.hour.values + 1) % 24
        self.adapt = self._adaptive_clock()

    def _adaptive_clock(self):
        """Hours of the active clock at each bar, from the deterministic BTC 4h regime (high_vol->1h, trend->4h, range/unknown->1d)."""
        b = pd.DataFrame({"open": self.O[:, self.b], "high": self.H[:, self.b], "low": self.L[:, self.b], "close": self.C[:, self.b], "volume": self.V[:, self.b]},
                         index=self.index).dropna()
        d4 = b.resample("4h", closed="left", label="left").agg({"open": "first", "high": "max", "low": "min", "close": "last", "volume": "sum"}).dropna()
        d4 = d4[d4.index + pd.Timedelta(hours=4) <= self.index[-1] + pd.Timedelta(hours=1)]
        lab = regime_det.classify_series(d4)
        mapc = {"high_vol": 1, "trend_up": 4, "trend_down": 4, "range": 24, "unknown": 24}
        ends = d4.index + pd.Timedelta(hours=4)              # label known when the 4h bar has closed
        v = np.array([mapc.get(x, 24) for x in lab.values])
        pos = np.searchsorted(ends.values.astype("datetime64[ns]"), (self.index + pd.Timedelta(hours=1)).values.astype("datetime64[ns]"), side="right") - 1
        return np.where(pos >= 0, v[np.clip(pos, 0, len(v) - 1)], 24)


def load_data(universe, log=print):
    frames, funding = {}, {}
    from . import deriv
    con = deriv.db()
    for s, v in universe["symbols"].items():
        try:
            frames[s] = store.get_ohlcv("%s/USDT" % v["base"], "1h", source=SRC)
        except KeyError:
            log("missing dataset %s" % s)
            continue
        funding[s] = futbt.load_funding(s)
    filt = {s: universe["symbols"][s] for s in frames}
    return Data(frames, filt, funding)


# ------------------------------------------------------------------ simulator
def _floor_step(q, step):
    return math.floor(q / step + 1e-9) * step


def is_decision(D, t, clock, phase):
    h = D.adapt[t] if clock == "ad" else CLOCK_H[clock]
    return (D.close_hour[t] - phase) % h == 0


def run(D, v, cost, lev=1.0, phase=0, end=None, capital=128.88, mmr=0.005):
    """Simulate one variant. v = {kind:'rot', clock, n, stop, btc} or {kind:'card', k}. cost = dict(fee, slip, maker_share, maker_fee).
    Returns dict(eq: np.array from WARMUP, trades: list, stats...)."""
    n_t, m = D.C.shape
    end = n_t if end is None else end
    fee = cost["fee"] * (1 - cost.get("maker_share", 0.0)) + cost.get("maker_fee", 0.0002) * cost.get("maker_share", 0.0)
    slip = cost["slip"]
    cash = capital
    pos = {}                               # j -> dict(qty, entry, margin, peak, t0, eq0)
    cool = np.zeros(m, dtype=int)
    pending_sell, pending_buy = [], 0
    eq = np.empty(end - WARMUP)
    trades, st = [], dict(fees=0.0, slip=0.0, funding=0.0, rejects=0, rej_sym={}, liq=0, fills=0, exposure=0, clock_hours={1: 0, 4: 0, 24: 0})
    fills_day = {}
    kind = v["kind"]
    npos = v["n"] if kind == "rot" else v["k"]
    for t in range(WARMUP, end):
        o = D.O[t]
        # 1. execute orders decided at the previous close
        if pending_sell or pending_buy:
            for j in pending_sell:
                p = pos.pop(j)
                px = o[j] * (1 - slip)
                notional = p["qty"] * px
                cash += p["margin"] + p["qty"] * (px - p["entry"]) - fee * notional
                st["fees"] += fee * notional
                st["slip"] += p["qty"] * o[j] * slip
                st["fills"] += 1
                fills_day[D.index[t].date()] = fills_day.get(D.index[t].date(), 0) + 1
                trades.append(dict(sym=D.syms[j], t0=p["t0"], t1=t, pnl=p["qty"] * (px - p["entry"]) - fee * notional - p["fee_in"],
                                   eq0=p["eq0"], reason=p.get("why", "")))
            pending_sell = []
            if pending_buy:
                want = pending_buy                      # list of symbol indices ranked best first
                pending_buy = 0
                alloc = cash / len(want)
                eq_now = cash + sum(q["margin"] + q["qty"] * (o[jj] - q["entry"]) for jj, q in pos.items())
                for j in want:
                    f = D.filters[D.syms[j]]
                    px = o[j] * (1 + slip)
                    if not np.isfinite(px):
                        st["rejects"] += 1
                        st["rej_sym"]["(no price)"] = st["rej_sym"].get("(no price)", 0) + 1
                        continue
                    q = _floor_step(alloc / (px * (1.0 / lev + fee)), f["stepSize"])
                    if q <= 0 or q < f["minQty"] or q * px < f["minNotional"] or q * px > 1e12:
                        st["rejects"] += 1
                        st["rej_sym"][D.syms[j]] = st["rej_sym"].get(D.syms[j], 0) + 1
                        continue
                    notional = q * px
                    margin = notional / lev
                    cash -= margin + fee * notional
                    st["fees"] += fee * notional
                    st["slip"] += q * o[j] * slip
                    st["fills"] += 1
                    fills_day[D.index[t].date()] = fills_day.get(D.index[t].date(), 0) + 1
                    pos[j] = dict(qty=q, entry=px, margin=margin, peak=D.C[t - 1, j] if np.isfinite(D.C[t - 1, j]) else px, t0=t, eq0=eq_now, fee_in=fee * notional)
        # 2. funding, liquidation, mark
        for j in list(pos):
            p = pos[j]
            fr = D.fund[t, j]
            if fr:
                cash -= p["qty"] * D.C[t, j] * fr
                st["funding"] += p["qty"] * D.C[t, j] * fr
            if lev > 1 and D.L[t, j] <= p["entry"] * (1 - 1.0 / lev + mmr):
                st["liq"] += 1
                trades.append(dict(sym=D.syms[j], t0=p["t0"], t1=t, pnl=-p["margin"] - p["fee_in"], eq0=p["eq0"], reason="liquidated"))
                del pos[j]
                cool[j] = t + 24
                continue
            if D.C[t, j] > p["peak"]:
                p["peak"] = D.C[t, j]
        val = cash + sum(p["margin"] + p["qty"] * (D.C[t, j] - p["entry"]) for j, p in pos.items())
        eq[t - WARMUP] = val
        if pos:
            st["exposure"] += 1
        if t == end - 1:
            break
        # 3. decision at the close of bar t
        if kind == "rot":
            if not is_decision(D, t, v["clock"], phase):
                continue
            h = int(D.adapt[t]) if v["clock"] == "ad" else CLOCK_H[v["clock"]]
            st["clock_hours"][h] += 1
            ck = {1: "1h", 4: "4h", 24: "1d"}[h]
            filt_off = v["btc"] and not D.btc_ok[t]
            sells = []
            for j, p in pos.items():
                c = D.C[t, j]
                why = None
                if filt_off:
                    why = "btc_filter"
                elif v["stop"] == "trail10" and c <= 0.90 * p["peak"]:
                    why = "stop"
                elif v["stop"] == "atr3" and np.isfinite(D.atr[ck][t, j]) and c <= p["peak"] - 3 * D.atr[ck][t, j]:
                    why = "stop"
                elif v["stop"] == "loss7" and c <= 0.93 * p["entry"]:
                    why = "stop"
                elif v["stop"] == "down4" and t - 4 * h >= 0:
                    cs = [D.C[t - i * h, j] for i in range(5)]
                    if all(cs[i] < cs[i + 1] for i in range(4)) and c < p["entry"]:
                        why = "stop"
                if why:
                    p["why"] = why
                    sells.append(j)
                    if why == "stop":
                        cool[j] = t + 24
            free = npos - (len(pos) - len(sells))
            buys = []
            if free > 0 and not filt_off:
                buys = _candidates(D, t, set(pos), cool, free, key=D.r7, need_pos=True)
            pending_sell, pending_buy = sells, (buys or 0)
        else:                                         # reference rule: top-K by 14d return, rebalance every 72h, BTC 14d < -10% -> cash
            if (t - WARMUP) % 72 != 71:
                continue
            crash = np.isfinite(D.btc_r14[t]) and D.btc_r14[t] < -0.10
            tgt = [] if crash else _candidates(D, t, set(), cool, npos, key=D.r14, need_pos=False)
            pending_sell = [j for j in pos if j not in tgt]
            for j in pending_sell:
                pos[j]["why"] = "rebalance"
            new = [j for j in tgt if j not in pos]
            pending_buy = new if new else 0
    return _stats(D, eq, trades, st, fills_day)


def _candidates(D, t, held, cool, k, key, need_pos):
    """Point-in-time eligible symbols ranked by `key` (descending). Eligible = 30 days of own history, top-20 by trailing 30d dollar volume, not held, not in cooldown."""
    ok = np.isfinite(D.dv30[t]) & ((t - D.first) >= H30) & np.isfinite(key[t]) & np.isfinite(D.C[t])
    if not ok.any():
        return []
    dv = np.where(ok, D.dv30[t], -1.0)
    liquid = np.zeros(len(dv), bool)
    liquid[np.argsort(-dv)[:20]] = True
    cand = [j for j in np.flatnonzero(ok & liquid) if j not in held and cool[j] <= t and (not need_pos or key[t, j] > 0)]
    cand.sort(key=lambda j: -key[t, j])
    return cand[:k]


def _stats(D, eq, trades, st, fills_day):
    from . import metrics
    r = eq[1:] / eq[:-1] - 1.0
    days = pd.Series(eq, index=D.index[WARMUP:WARMUP + len(eq)]).resample("1D").last().dropna()
    dr = days.pct_change().dropna()
    return dict(eq=eq, r=r, trades=trades, sharpe=float(metrics.sharpe_annual(r, 8760)), mdd=float(metrics.max_drawdown(r)),
                total_return=float(eq[-1] / eq[0] - 1), n_trades=len(trades), fees=st["fees"], slip=st["slip"], funding=st["funding"],
                rejects=st["rejects"], rej_sym=st["rej_sym"], liq=st["liq"], exposure=st["exposure"] / max(len(eq), 1), fills=st["fills"],
                days_gt10_fills=int(sum(1 for x in fills_day.values() if x > 10)), days_loss_gt3=int((dr < -0.03).sum()),
                clock_share={k: round(v / max(1, sum(st["clock_hours"].values())), 3) for k, v in st["clock_hours"].items()})


# ------------------------------------------------------------------ benchmarks
def bench_hold(D, sym, cost, capital=128.88):
    j = D.syms.index(sym)
    c = D.C[WARMUP - 1:, j]
    r = c[1:] / c[:-1] - 1.0 - D.fund[WARMUP:, j]
    r = r.copy()
    r[0] -= cost["fee"] + cost["slip"]
    eq = capital * np.r_[1.0, np.cumprod(1 + r)]
    return _bench(D, eq)


def bench_ew(D, cost, capital=128.88):
    """Equal weight of the point-in-time eligible set (30d history, top-20 liquidity), rebalanced daily, fees+slippage on turnover (idealised: no minNotional)."""
    n_t = len(D.index)
    w = np.zeros(D.C.shape[1])
    rets = np.empty(n_t - WARMUP)
    for t in range(WARMUP, n_t):
        j_ret = D.C[t] / D.C[t - 1] - 1.0 - D.fund[t]
        j_ret = np.nan_to_num(j_ret)
        r = float((w * j_ret).sum())
        w = w * (1 + j_ret)
        w = w / w.sum() if w.sum() > 0 else w
        if D.close_hour[t] == 0 and t < n_t - 1:
            cand = _candidates(D, t, set(), np.zeros(D.C.shape[1], int), 20, key=D.r7, need_pos=False)
            nw = np.zeros_like(w)
            if cand:
                nw[cand] = 1.0 / len(cand)
            r -= float(np.abs(nw - w).sum()) * (cost["fee"] + cost["slip"])
            w = nw
        rets[t - WARMUP] = r
    eq = capital * np.r_[1.0, np.cumprod(1 + rets)]
    return _bench(D, eq)


def _bench(D, eq):
    from . import metrics
    r = eq[1:] / eq[:-1] - 1.0
    return dict(eq=eq, r=r, sharpe=float(metrics.sharpe_annual(r, 8760)), mdd=float(metrics.max_drawdown(r)), total_return=float(eq[-1] / eq[0] - 1))
