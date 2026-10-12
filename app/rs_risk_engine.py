"""Research: leverage / risk-overlay engine for the Binance perp momentum rotation (OFFLINE, no network).
Hourly high/low path -> worst-case intraday equity under cross margin, maintenance-margin liquidation test.
Input: hourly OHLC dict base->DataFrame[open,high,low,close] (UTC index) and funding dict base->Series(rate per 8h).
Conventions (mirror live loop): signal at daily close (23:00 bar close), positions executed at that close;
unchanged-side positions keep their quantity (no resize); notional/pos = equity*deploy*lev/(2K);
fees+slippage 0.10% per traded notional; funding applied at 00/08/16 UTC on held notional.
"""
from __future__ import annotations
from dataclasses import dataclass, field, replace
import numpy as np
import pandas as pd


@dataclass(frozen=True)
class Cfg:
    lookback: int = 14
    rebal: int = 3
    K: int = 8
    lev: float = 1.0
    deploy: float = 1.0
    cost: float = 0.0010          # fee 0.05% + slippage 0.05% per side
    mmr: float = 0.005            # maintenance margin rate (tier-1 alt ~0.5%)
    ladder: tuple = ()            # ((dd_threshold, lev_multiplier), ...) ascending dd; e.g. ((.2,.5),)
    hyst: float = 0.05            # re-lever only when dd < thr - hyst
    relever_mode: str = "dd"      # "dd" (hysteresis on drawdown) | "hwm" (only at new high)
    kill_dd: float = 1.0          # >=1 disables
    apply: str = "rebalance"      # when new leverage level is applied: "rebalance" | "daily"
    vol_target: float = 0.0       # annualised target vol of strategy (0 = off)
    vol_lb: int = 30
    lev_cap: float = 4.0
    min_names: tuple = ()         # ((base, min_notional), ...) per-name overrides e.g. (('BTC',100),)
    min_notional: float = 0.0     # per-order min notional (USDT) -> positions below are skipped (live behaviour)
    start_equity: float = 1.0
    funding: bool = True


def build_panel(ohlc: dict, funding: dict | None = None):
    idx = None
    for df in ohlc.values():
        idx = df.index if idx is None else idx.union(df.index)
    idx = pd.date_range(idx.min().floor("D"), idx.max().ceil("D") - pd.Timedelta(hours=1), freq="1h", tz="UTC")
    names = list(ohlc)
    H = np.full((len(idx), len(names)), np.nan); L = H.copy(); C = H.copy()
    for j, b in enumerate(names):
        d = ohlc[b].reindex(idx)
        H[:, j], L[:, j], C[:, j] = d["high"].values, d["low"].values, d["close"].values
    F = np.zeros_like(C)
    if funding:
        for j, b in enumerate(names):
            if b in funding:
                s = funding[b].reindex(idx.union(funding[b].index)).loc[idx]  # exact-hour match only
                F[:, j] = np.nan_to_num(s.values)
    nd = len(idx) // 24
    return dict(names=names, days=idx[::24][:nd], H=H[:nd*24].reshape(nd, 24, -1), L=L[:nd*24].reshape(nd, 24, -1),
                C=C[:nd*24].reshape(nd, 24, -1), F=F[:nd*24].reshape(nd, 24, -1))


def _targets(dclose, i, lookback, K):
    if i < lookback:
        return None
    p, p0 = dclose[i], dclose[i - lookback]
    ok = np.isfinite(p) & np.isfinite(p0) & (p0 > 0)
    if ok.sum() < 2 * K:
        return None
    mom = np.where(ok, p / np.where(p0 > 0, p0, 1) - 1, np.nan)
    order = np.argsort(np.where(ok, mom, -np.inf))  # ascending, invalid first
    valid = order[ok[order]]
    side = np.zeros(len(p))
    side[valid[-K:]] = 1; side[valid[:K]] = -1
    return side


def simulate(P: dict, cfg: Cfg, d0: int = 0, d1: int | None = None) -> dict:
    H, L, C, F = P["H"], P["L"], P["C"], P["F"]
    nd, _, n = C.shape
    min_per = np.full(n, cfg.min_notional)
    for nm, mv in cfg.min_names:
        if nm in P['names']:
            min_per[P['names'].index(nm)] = mv
    d1 = nd if d1 is None else d1
    dclose = C[:, -1, :]
    W = cfg.start_equity            # wallet (realised cash)
    q = np.zeros(n); e = np.zeros(n)
    level, halted, hwm = 0, False, W
    eq_close, eq_worst, buf, days, expo = [], [], [], [], []
    strat_ret = []                  # unlevered-ish daily returns for vol target
    last_reb = -10**9
    liq_day = None
    prev_eq = W
    cur_mult = 1.0
    for i in range(d0, d1):
        px = C[i, -1, :]
        eq_now = W + np.nansum(q * (np.where(np.isfinite(px), px, e) - e))
        # --- decisions at the close of day i-1 are made below at the end of loop; here just simulate day i
        # hourly path for day i with positions q held (positions were set at close of i-1)
        if np.any(q != 0):
            held = q != 0
            lo = np.where(q > 0, L[i], H[i])[:, held]            # adverse extreme per coin per hour
            ex = (q[held] * (np.nan_to_num(lo, nan=0.0) - e[held])).sum(1)
            ex = np.where(np.isfinite(lo).all(1), ex, ex)
            fund = 0.0
            if cfg.funding:
                fund = -np.nansum(q[held] * C[i][:, held] * F[i][:, held])
            worst_eq = W + fund + ex.min()
            maint = np.nansum(np.abs(q[held]) * np.fmax(np.nanmax(H[i][:, held], axis=0) if False else np.max(np.where(np.isfinite(H[i][:, held]), H[i][:, held], 0), axis=0), e[held]) * cfg.mmr)
            W += fund
        else:
            worst_eq, maint = W, 0.0
        b = worst_eq / maint if maint > 0 else np.inf
        if worst_eq <= maint and maint > 0:
            liq_day = days[-1] if days else P["days"][i]
            eq_close.append(0.0); eq_worst.append(0.0); buf.append(0.0); days.append(P["days"][i])
            break
        px = np.where(np.isfinite(px), px, e)
        eq = W + (q * (px - e)).sum()
        eq_close.append(eq); eq_worst.append(worst_eq); buf.append(b); days.append(P["days"][i])
        expo.append(np.abs(q * px).sum() / max(eq, 1e-12))
        strat_ret.append(eq / prev_eq - 1.0 if prev_eq > 0 else 0.0)
        prev_eq = eq
        hwm = max(hwm, eq)
        dd = 1 - eq / hwm
        # ---- overlay state at close of day i
        if dd >= cfg.kill_dd and not halted:
            halted = True
            W = eq - np.abs(q * px).sum() * cfg.cost
            q[:] = 0; e[:] = 0
            continue
        if halted:
            continue
        old_level = level
        while level < len(cfg.ladder) and dd >= cfg.ladder[level][0]:
            level += 1
        if level > 0 and level == old_level:
            thr = cfg.ladder[level - 1][0]
            if cfg.relever_mode == "hwm":
                if dd <= 1e-12: level -= 1
            elif dd < thr - cfg.hyst:
                level -= 1
        lad_mult = cfg.ladder[level - 1][1] if level > 0 else 1.0
        lev = cfg.lev * lad_mult
        if cfg.vol_target > 0 and len(strat_ret) >= max(10, cfg.vol_lb // 2):
            r = np.array(strat_ret[-cfg.vol_lb:])
            gross_prev = max(np.mean(expo[-cfg.vol_lb:]), 0.25)
            vol = r.std() * np.sqrt(365) / gross_prev      # per-unit-gross annualised vol
            if vol > 0:
                lev = min(lev, cfg.vol_target / vol, cfg.lev_cap)
        due = (i - last_reb) >= cfg.rebal
        force = cfg.apply == "daily" and (level != old_level)
        if (due or force) and i < d1 - 1:
            side = _targets(dclose, i, cfg.lookback, cfg.K)
            if side is None:
                continue
            tgt_notional = eq * cfg.deploy * lev / (2 * cfg.K)
            cost_paid = 0.0
            cur_side = np.sign(q)
            for j in range(n):
                s = side[j] if not (min_per[j] > 0 and tgt_notional < min_per[j]) else 0.0
                if force and not due:
                    s = cur_side[j]       # resize only, keep same names
                if q[j] != 0 and (s != cur_side[j] or (force and not due) or (cfg.apply == "daily" and due)):
                    if s == cur_side[j] and not (force or cfg.apply == "daily"):
                        continue
                    # close old (resize in daily mode counts as close+reopen of delta only)
                    new_q = s * tgt_notional / px[j] if (s != 0 and np.isfinite(px[j]) and px[j] > 0) else 0.0
                    if s == cur_side[j] and s != 0:       # resize: trade delta only at current px
                        delta = new_q - q[j]
                        W += q[j] * 0  # realised pnl unchanged; keep entry (avg entry approx)
                        e_old = e[j]
                        # realise pnl proportionally to the closed part
                        if abs(new_q) < abs(q[j]):
                            frac = 1 - abs(new_q) / abs(q[j])
                            W += q[j] * frac * (px[j] - e_old)
                        else:
                            tot = abs(new_q)
                            e[j] = (abs(q[j]) * e_old + abs(delta) * px[j]) / tot
                        cost_paid += abs(delta) * px[j] * cfg.cost
                        q[j] = new_q
                        continue
                    W += q[j] * (px[j] - e[j])
                    cost_paid += abs(q[j]) * px[j] * cfg.cost
                    q[j] = 0.0; e[j] = 0.0
                if q[j] == 0 and s != 0 and np.isfinite(px[j]) and px[j] > 0 and not (force and not due):
                    q[j] = s * tgt_notional / px[j]; e[j] = px[j]
                    cost_paid += tgt_notional * cfg.cost
            W -= cost_paid
            if due:
                last_reb = i
    return _metrics(days, eq_close, eq_worst, buf, cfg, liq_day, halted)


def _metrics(days, eqc, eqw, buf, cfg, liq_day, halted) -> dict:
    s = pd.Series(eqc, index=pd.DatetimeIndex(days)) / cfg.start_equity
    if len(s) < 5:
        return {"n": len(s)}
    w = pd.Series(eqw, index=s.index) / cfg.start_equity
    yrs = max((s.index[-1] - s.index[0]).days / 365.25, 1e-9)
    end = s.iloc[-1]
    cagr = (end ** (1 / yrs) - 1) if end > 0 else -1.0
    hw = s.cummax()
    mdd = float(((hw - s) / hw).max())
    prev_hw = hw.shift(1).fillna(1.0).clip(lower=1.0)
    imdd = float(((np.maximum(prev_hw, hw) - np.minimum(w, s)) / np.maximum(prev_hw, hw)).max())
    r = s.pct_change().dropna()
    sharpe = float(r.mean() / r.std() * np.sqrt(365)) if r.std() > 0 else 0.0
    wk = s.resample("W").last().pct_change().dropna()
    under = (s < hw - 1e-12)
    run = best = 0
    for u in under.values:
        run = run + 1 if u else 0
        best = max(best, run)
    yearly = s.groupby(s.index.year).apply(lambda x: x.iloc[-1] / x.iloc[0] - 1).to_dict()
    bf = np.array(buf)
    return dict(cagr=cagr, mdd=mdd, imdd=imdd, calmar=cagr / imdd if imdd > 0 else np.nan, sharpe=sharpe,
                worst_day=float(r.min()), worst_week=float(wk.min()) if len(wk) else np.nan,
                longest_uw_days=int(best), yearly={int(k): float(v) for k, v in yearly.items()},
                min_buffer=float(np.nanmin(bf[np.isfinite(bf)])) if np.isfinite(bf).any() else np.inf,
                liq=liq_day is not None, liq_day=str(liq_day) if liq_day is not None else None,
                halted=halted, final=float(end), n=len(s), _eq=s, _worst=w)


def base_daily(P: dict, cfg: Cfg):
    """unlevered (lev=1, deploy=1, no overlay) daily (close return, adverse intraday return) for bootstrap"""
    c = replace(cfg, lev=1.0, deploy=1.0, ladder=(), kill_dd=1.0, vol_target=0.0)
    # re-simulate manually to harvest series
    m = simulate(P, c)
    return m


def block_bootstrap(r: np.ndarray, a: np.ndarray, cfg: Cfg, n_paths=1000, horizon=365, block=10, seed=0):
    """r: unlevered daily returns, a: unlevered worst intraday adverse return (<=0) per day.
    Daily overlay model with delever ladder/kill/mmr liquidation. Returns P(DD>30/50), P(liq), median etc."""
    rng = np.random.default_rng(seed)
    n = len(r)
    out = dict(dd30=0, dd50=0, liq=0, kill=0, mdds=[], finals=[])
    for _ in range(n_paths):
        idx = np.concatenate([(rng.integers(0, n) + np.arange(block)) % n for _ in range(horizon // block + 1)])[:horizon]
        E, hwm, level, halted, mdd, liq = 1.0, 1.0, 0, False, 0.0, False
        hist = []
        for k in idx:
            if halted:
                break
            lev = cfg.lev * (cfg.ladder[level - 1][1] if level > 0 else 1.0)
            if cfg.vol_target > 0:
                w_ = hist[-cfg.vol_lb:] if len(hist) >= 5 else r[:cfg.vol_lb]
                sd = float(np.std(w_)) * np.sqrt(365)
                lev = min(lev, cfg.lev_cap, cfg.vol_target / sd) if sd > 0 else lev
            lev *= cfg.deploy
            low = E * (1 + lev * a[k])
            if 1 + lev * a[k] <= lev * cfg.mmr:
                liq = True; E = 0.0; mdd = 1.0; break
            mdd = max(mdd, 1 - low / hwm)      # intraday trough vs high-water mark
            E *= max(1 + lev * r[k], 0.0)
            hist.append(r[k])
            hwm = max(hwm, E)
            dd = 1 - E / hwm
            mdd = max(mdd, dd)
            if dd >= cfg.kill_dd:
                halted = True; out["kill"] += 1
            while level < len(cfg.ladder) and dd >= cfg.ladder[level][0]:
                level += 1
            if level > 0 and dd < cfg.ladder[level - 1][0] - cfg.hyst:
                level -= 1
        out["dd30"] += mdd > .30; out["dd50"] += mdd > .50; out["liq"] += liq
        out["mdds"].append(mdd); out["finals"].append(E)
    return dict(P_dd30=out["dd30"] / n_paths, P_dd50=out["dd50"] / n_paths, P_liq=out["liq"] / n_paths,
                P_kill=out["kill"] / n_paths, med_mdd=float(np.median(out["mdds"])),
                p95_mdd=float(np.percentile(out["mdds"], 95)), med_final=float(np.median(out["finals"])),
                p5_final=float(np.percentile(out["finals"], 5)))


def synthetic(n_days=900, n=30, seed=1):
    rng = np.random.default_rng(seed)
    idx = pd.date_range("2022-01-01", periods=n_days * 24, freq="1h", tz="UTC")
    mkt = rng.normal(0, 0.004, len(idx))
    out, fund = {}, {}
    for j in range(n):
        r = mkt * 0.8 + rng.normal(0, 0.008, len(idx))
        c = 100 * np.exp(np.cumsum(r)); o = np.roll(c, 1); o[0] = 100
        rg = np.abs(rng.normal(0, 0.004, len(idx)))
        out[f"S{j}"] = pd.DataFrame({"open": o, "high": np.maximum(o, c) * (1 + rg), "low": np.minimum(o, c) * (1 - rg), "close": c}, index=idx)
        fi = idx[idx.hour % 8 == 0]
        fund[f"S{j}"] = pd.Series(0.0001, index=fi)
    return out, fund


if __name__ == "__main__":
    o, f = synthetic()
    P = build_panel(o, f)
    for lev in (1, 3, 8):
        m = simulate(P, Cfg(lev=lev))
        print(lev, {k: (round(v, 3) if isinstance(v, float) else v) for k, v in m.items() if k != "yearly"})
