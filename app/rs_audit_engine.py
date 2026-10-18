"""Independent audit engine (plain numpy/pandas, no imports from other rs_* modules, no network).

Conventions (all daily indices i refer to UTC day i; close[i] = close of the 23:00 1h bar):
  signal at close i  -> position earns return of day i+1 (close[i+1]/close[i]-1)
  funding of settlement at calc_time (00:00/08:00/16:00 UTC, +few ms) is booked to the UTC
  day containing it (day = calc // 86_400_000); a position held across the settlement pays/receives it.
"""
import ast
import gzip
import os
import numpy as np
import pandas as pd

ROOT = "/Users/user/Desktop/CODE/Ochestration/trading"
CACHE = f"{ROOT}/.rs_cache/vision"
DAY = 86_400_000


def universe():
    src = open(f"{ROOT}/app/momentum_rotation_loop.py").read()
    for node in ast.parse(src).body:
        if isinstance(node, ast.Assign) and getattr(node.targets[0], "id", "") == "UNIVERSE":
            return list(ast.literal_eval(node.value))
    raise RuntimeError("UNIVERSE not found")


def load_panel(bases=None, kline_hook=None, fund_hook=None, fund_shift_ms=0):
    """Returns dict with day index (DatetimeIndex), close, qv (daily quote vol), fund (daily sum of rates).
    kline_hook(base, df)->df and fund_hook(base, df)->df allow perturbation tests."""
    bases = bases or universe()
    closes, qvs, funds = {}, {}, {}
    for b in bases:
        k = pd.read_csv(f"{CACHE}/klines_1h/{b}USDT.csv.gz", header=None, usecols=[0, 4, 7],
                        names=["t", "c", "qv"], dtype={"t": "int64", "c": "float64", "qv": "float64"})
        if kline_hook:
            k = kline_hook(b, k)
        k["d"] = k["t"] // DAY
        g = k.sort_values("t").groupby("d")
        closes[b] = g["c"].last()
        qvs[b] = g["qv"].sum()
        f = pd.read_csv(f"{CACHE}/funding/{b}USDT.csv.gz", header=None, names=["t", "iv", "r"])
        if fund_hook:
            f = fund_hook(b, f)
        f["d"] = (f["t"] - fund_shift_ms) // DAY
        funds[b] = f.groupby("d")["r"].sum()
    # last full day: all 24 bars present for BTC-like check -> use last day whose last bar is 23:00
    c = pd.DataFrame(closes)
    last_bar = pd.read_csv(f"{CACHE}/klines_1h/BTCUSDT.csv.gz", header=None, usecols=[0])[0].iloc[-1]
    last_day = last_bar // DAY if (last_bar % DAY) == 23 * 3600_000 else last_bar // DAY - 1
    idx = np.arange(c.index.min(), last_day + 1)
    c = c.reindex(idx)
    q = pd.DataFrame(qvs).reindex(idx)
    f = pd.DataFrame(funds).reindex(idx).fillna(0.0)
    dates = pd.to_datetime(idx * DAY, unit="ms")
    return dict(dates=dates, close=c.values, qv=q.values, fund=f.values, bases=list(c.columns), idx=idx)


def derive(P, lookback=14, min_hist=60):
    C = P["close"]
    T, N = C.shape
    Cf = pd.DataFrame(C).ffill().values  # gaps inside a listing: return over the gap is realised on first day after it
    R = np.full((T, N), np.nan)
    R[1:] = Cf[1:] / Cf[:-1] - 1.0
    mom = np.full((T, N), np.nan)
    mom[lookback:] = C[lookback:] / C[:-lookback] - 1.0
    valid = ~np.isnan(C)
    first = np.where(valid.any(0), valid.argmax(0), T)
    hist = np.arange(T)[:, None] - first[None, :] + 1  # number of daily closes available incl. today
    elig = valid & (hist >= min_hist) & ~np.isnan(mom)
    return dict(R=R, mom=mom, elig=elig, first=first)


def metrics(r, ann=365):
    r = np.asarray(r, float)
    r = np.nan_to_num(r)
    eq = np.cumprod(1 + r)
    yrs = len(r) / ann
    cagr = eq[-1] ** (1 / yrs) - 1 if eq[-1] > 0 else -1.0
    peak = np.maximum.accumulate(np.concatenate([[1.0], eq]))[1:]
    mdd = ((eq / peak) - 1).min()
    sd = r.std(ddof=1)
    sh = r.mean() / sd * np.sqrt(ann) if sd > 0 else 0.0
    return dict(cagr=cagr, mdd=mdd, sharpe=sh, worst=r.min(), calmar=(cagr / abs(mdd) if mdd < 0 else np.nan),
                vol=sd * np.sqrt(ann))


def _targets(mom_row, elig_row, K, band, held_long, held_short):
    """Return (long_idx, short_idx) arrays; hysteresis band (0 = none)."""
    ids = np.where(elig_row)[0]
    if len(ids) < 2 * K:
        return None
    order = ids[np.argsort(-mom_row[ids], kind="stable")]  # best first
    rank = {j: n + 1 for n, j in enumerate(order)}
    nn = len(order)
    L = [j for j in held_long if j in rank and rank[j] <= K + band] if band else []
    S = [j for j in held_short if j in rank and (nn - rank[j] + 1) <= K + band] if band else []
    L = [j for j in L if j not in S]
    L = L[:K]
    for j in order:
        if len(L) >= K:
            break
        if j not in L and j not in S:
            L.append(j)
    for j in order[::-1]:
        if len(S) >= K:
            break
        if j not in S and j not in L:
            S.append(j)
    return np.array(L, int), np.array(S, int)


def simulate(D, P, s0, K=8, every=3, off=0, band=0, model="cw", cost=0.001, funding=True,
             scale_fn=None, ann_start=None, full_out=False):
    """Sequential simulation. s0 = first signal day index (initial entry). Returns dict with daily net returns for
    return days s0+1..T-1 and stats. scale_fn(i, hist_rets)->gross scale at rebalance day i (None => 1)."""
    R, mom, elig, F = D["R"], D["mom"], D["elig"], P["fund"]
    T, N = R.shape
    n_days = T - 1 - s0
    rets = np.zeros(n_days)
    costs = np.zeros(n_days)
    fund_pnl = np.zeros(n_days)
    trades = 0
    turnover = 0.0
    w = np.zeros(N)        # cw: target weights ; qk: notionals (fraction of initial equity)
    E = 1.0
    scale = 1.0
    held_L, held_S = [], []
    W_hist = [] if full_out else None
    for i in range(s0, T - 1):
        k = i - s0
        pend_cost = 0.0
        if k == 0 or (k % every == off):
            sc = scale_fn(i, rets[:k]) if scale_fn else 1.0
            tg = _targets(mom[i], elig[i], K, band, held_L, held_S)
            if tg is None:
                new_w = np.zeros(N)
                held_L, held_S = [], []
                tgL = tgS = np.array([], int)
            else:
                tgL, tgS = tg
            if model == "cw":
                new_w = np.zeros(N)
                new_w[tgL] = sc / (2 * K)
                new_w[tgS] = -sc / (2 * K)
                dw = np.abs(new_w - w)
                pend_cost = dw.sum() * cost
                turnover += dw.sum()
                trades += int((dw > 1e-12).sum())
                w = new_w
            else:  # quantity-keeping: w holds notional in units of equity-at-start (E tracked)
                new_n = np.zeros(N)
                ratio = sc / scale if scale > 0 else 1.0
                for j in tgL:
                    new_n[j] = w[j] * ratio if w[j] > 0 else sc * E / (2 * K)
                for j in tgS:
                    new_n[j] = w[j] * ratio if w[j] < 0 else -sc * E / (2 * K)
                dn = np.abs(new_n - w)
                pend_cost = dn.sum() * cost
                turnover += dn.sum() / E
                trades += int((dn > 1e-12).sum())
                w = new_n
            scale = sc
            held_L, held_S = list(tgL), list(tgS)
        r = np.nan_to_num(R[i + 1])
        fr = F[i + 1] if funding else 0.0
        if model == "cw":
            g = w @ r
            fp = -(w @ fr) if funding else 0.0
            net = g + fp - pend_cost
            rets[k] = net
            costs[k] = pend_cost
            fund_pnl[k] = fp
        else:
            E0 = E
            g = w @ r
            fp = -(w @ fr) if funding else 0.0
            E = E0 - pend_cost + g + fp
            rets[k] = E / E0 - 1.0
            costs[k] = pend_cost / E0
            fund_pnl[k] = fp / E0
            w = w * (1 + r)
        if W_hist is not None:
            W_hist.append(w.copy())
    yrs = n_days / 365.0
    out = dict(rets=rets, trades_yr=trades / yrs, turnover_yr=turnover / yrs, fee_yr=costs.sum() / yrs,
               fund_yr=fund_pnl.sum() / yrs)
    if full_out:
        out["W"] = np.array(W_hist)
    return out


def vol_scale_fn(base_rets, target=0.15, window=60, cap=1.5, s0=0):
    """base_rets: unscaled strategy net daily returns indexed by k (return day s0+1+k). At rebalance on day i
    (k=i-s0) returns up to day i are known: base_rets[:k]."""
    def fn(i, _hist):
        k = i - s0
        if k < window:
            return 1.0
        h = base_rets[k - window:k]
        v = h.std(ddof=1) * np.sqrt(365)
        return float(np.clip(target / v, 0, cap)) if v > 0 else cap
    return fn


def run_all_offsets(D, P, s0, every, **kw):
    outs = [simulate(D, P, s0, every=every, off=o, **kw) for o in range(every)]
    mean_ret = np.mean([o["rets"] for o in outs], axis=0)
    return outs, mean_ret


def s0_index(P, date="2021-12-31"):
    return int(np.where(P["dates"] == pd.Timestamp(date))[0][0])


def fast_cw(mom, elig, R, F, s0, K, every, off, cost=0.001, funding=True):
    """Vectorised constant-weight, no hysteresis, no vol-target. Parity-tested vs simulate()."""
    T, N = R.shape
    m = np.where(elig, mom, np.nan)
    ok = elig.sum(1) >= 2 * K
    rk = np.argsort(np.argsort(-np.where(np.isnan(m), -np.inf, m), axis=1, kind="stable"), axis=1, kind="stable")
    n_el = elig.sum(1)[:, None]
    longm = (rk < K) & elig
    shortm = (rk >= n_el - K) & elig
    Wd = (longm.astype(float) - shortm.astype(float)) / (2 * K)
    Wd[~ok] = 0.0
    days = np.arange(s0, T - 1)
    k = days - s0
    reb = (k == 0) | (k % every == off)
    last = np.maximum.accumulate(np.where(reb, days, -1))
    W = Wd[last]
    Rn = np.nan_to_num(R[days + 1])
    g = (W * Rn).sum(1)
    fp = -(W * F[days + 1]).sum(1) if funding else 0.0
    prevW = np.vstack([np.zeros((1, N)), W[:-1]])
    turn = np.abs(W - prevW).sum(1)
    return g + fp - turn * cost, turn
