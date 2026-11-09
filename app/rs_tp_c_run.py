"""BACKTESTER-C runner: executes the pre-registered plan in docs/research/tp_loop/C/prereg.md. Offline only."""
from __future__ import annotations
import sys, json, time
sys.dont_write_bytecode = True
import numpy as np
import pandas as pd
from app.rs_final_data import load_panel
from app.rs_tp_c_engine import TPSim, xparams

OUT = "docs/research/tp_loop/C/results.json"
BASES = {"LIVE": dict(lev=4.0, deploy=0.95), "RESEARCH": dict(lev=2.0, deploy=1.0)}
CFGS = {
    "A1": dict(xp=(3, 3.0, 0, 0)), "A2": dict(xp=(1, 3.0, 0, 0)), "A3": dict(xp=(2, 3.0, 0, 0)),
    "A4": dict(xp=(3, 2.5, 0, 0)), "A5": dict(xp=(3, 4.0, 0, 0)), "A6": dict(xp=(4, 3.0, 0, 0)),
    "B1": dict(xp=(0, 3.0, 4, 0)), "B2": dict(xp=(0, 3.0, 2, 0)),
    "R1": dict(rebal=1), "R2": dict(rebal=2),
    "C1": dict(xp=(3, 3.0, 0, 1)), "C2": dict(xp=(0, 3.0, 4, 1)),
}
NEIGH = {  # +-25% neighbours (not headline)
    "A1": [dict(xp=(3, 2.25, 0, 0)), dict(xp=(3, 3.75, 0, 0))], "A2": [dict(xp=(1, 2.25, 0, 0)), dict(xp=(1, 3.75, 0, 0))],
    "A3": [dict(xp=(2, 2.25, 0, 0)), dict(xp=(2, 3.75, 0, 0))], "A4": [dict(xp=(3, 1.875, 0, 0)), dict(xp=(3, 3.125, 0, 0))],
    "A5": [dict(xp=(3, 3.0, 0, 0)), dict(xp=(3, 5.0, 0, 0))], "A6": [dict(xp=(4, 2.25, 0, 0)), dict(xp=(4, 3.75, 0, 0))],
    "B1": [dict(xp=(0, 3.0, 3, 0)), dict(xp=(0, 3.0, 5, 0))], "B2": [dict(xp=(0, 3.0, 1, 0)), dict(xp=(0, 3.0, 3, 0))],
    "C1": [dict(xp=(3, 2.25, 0, 1)), dict(xp=(3, 3.75, 0, 1))], "C2": [dict(xp=(0, 3.0, 3, 1)), dict(xp=(0, 3.0, 5, 1))],
    "R1": [dict(rebal=2)], "R2": [dict(rebal=1), dict(rebal=3)],
}
HEAD = list(CFGS)
IS_END = pd.Timestamp("2024-06-30", tz="UTC"); OOS_START = pd.Timestamp("2024-07-01", tz="UTC")
STRESS = {"2022H1": ("2022-01-01", "2022-06-30"), "FTX2022-11": ("2022-11-01", "2022-11-30"), "2024-08": ("2024-08-01", "2024-08-31"),
          "2025Q4": ("2025-10-01", "2025-12-31"), "2026": ("2026-01-01", "2026-12-31")}
NB = 5000; BLK = 15; SEED = 7


def phases_of(c):
    return list(range(c.get("rebal", 3)))


def run_cfg(sim, base, c, cost=0.001, Z=None, plc=None, U=None):
    out = []
    for ph in phases_of(c):
        xp = c.get("xp", (0, 3.0, 0, 0))
        if plc is not None:
            xpv = xparams(0, 3.0, 0, xp[3], 1, plc[ph][0], plc[ph][1])
        else:
            xpv = xparams(*xp)
        out.append(sim.run(rebal=c.get("rebal", 3), phase=ph, xp=xpv, cost=cost, Z=Z, U=U, **base))
    return out


def rets(res, d0):
    e = res["eq"].to_numpy().copy()
    e[np.isnan(e)] = 0.0
    r = np.full(len(e), np.nan)
    prev = e[:-1]
    with np.errstate(divide="ignore", invalid="ignore"):
        rr = np.where(prev > 0, e[1:] / prev - 1, 0.0)
    r[1:] = rr
    r[:d0 + 1] = np.nan
    return r


def calmar_cagr_mdd(r):
    r = r[np.isfinite(r)]
    if len(r) < 30:
        return (np.nan, np.nan, np.nan)
    eq = np.cumprod(1 + r)
    end = eq[-1]
    cagr = end ** (365.0 / len(r)) - 1 if end > 0 else -1.0
    hw = np.maximum.accumulate(np.r_[1.0, eq])[1:]
    mdd = float(np.max(1 - eq / hw))
    return (cagr / mdd if mdd > 0 else 0.0, cagr, mdd)


def windows(sim):
    d = sim.days
    return {"full": np.ones(len(d), bool), "IS": np.asarray(d <= IS_END), "OOS": np.asarray(d >= OOS_START)}


def wstats(runs, sim, w):
    """per phase calmar/cagr/mdd on a window mask; returns arrays."""
    res = []
    for r in runs:
        x = rets(r, sim.d0)
        x = np.where(w, x, np.nan)
        res.append(calmar_cagr_mdd(x))
    return np.array(res)


def blend(runs, sim):
    return np.nanmean(np.vstack([rets(r, sim.d0) for r in runs]), axis=0) if len(runs) > 1 else rets(runs[0], sim.d0)


def delta_calmar(sim, v0, var, win="full"):
    w = windows(sim)[win]
    a = wstats(v0, sim, w); b = wstats(var, sim, w)
    return float(np.nanmean(b[:, 0]) - np.nanmean(a[:, 0])), a, b


def regimes(sim):
    c = sim.btc; sma = sim.sma200
    nd = len(c)
    d = np.where(np.isfinite(sma), c / sma - 1, np.nan)
    r = np.r_[np.nan, c[1:] / c[:-1] - 1]
    vol = pd.Series(r).rolling(30, min_periods=30).std().to_numpy()
    trend = np.full(nd, -1); volb = np.full(nd, -1)
    for t in range(1, nd):
        dd = d[t - 1]
        if np.isfinite(dd):
            trend[t] = 2 if dd >= 0.10 else (0 if dd <= -0.10 else 1)  # 2 bull, 0 bear, 1 chop
        past = vol[:t][np.isfinite(vol[:t])]
        if len(past) >= 120 and np.isfinite(vol[t - 1]):
            pr = (past < vol[t - 1]).mean()
            volb[t] = 0 if pr < 1 / 3 else (1 if pr < 2 / 3 else 2)
    return trend, volb


def regime_table(sim, bv0, bvar, trend, volb):
    lg = np.log1p(bvar) - np.log1p(bv0)
    ok = np.arange(len(lg)) > sim.d0
    out = {}
    for nm, arr, lab in (("trend", trend, ("bear", "chop", "bull")), ("vol", volb, ("lowvol", "midvol", "highvol"))):
        for k in range(3):
            m = ok & (arr == k) & np.isfinite(lg)
            out[lab[k]] = dict(days=int(m.sum()), dlog=float(lg[m].sum()))
    return out


def stress_table(sim, bv0, bvar):
    out = {}
    for k, (a, b) in STRESS.items():
        m = (sim.days >= pd.Timestamp(a, tz="UTC")) & (sim.days <= pd.Timestamp(b, tz="UTC")) & np.isfinite(bv0)
        if m.sum() < 5:
            out[k] = None; continue
        x0 = np.prod(1 + bv0[m]) - 1; x1 = np.prod(1 + bvar[m]) - 1
        out[k] = dict(v0=float(x0), var=float(x1), diff=float(x1 - x0), days=int(m.sum()))
    return out


def boot_idx(T):
    rng = np.random.default_rng(SEED)
    nbk = int(np.ceil(T / BLK))
    st = rng.integers(0, T, size=(NB, nbk))
    return ((st[:, :, None] + np.arange(BLK)[None, None, :]) % T).reshape(NB, -1)[:, :T]


def calmar_batch(R):
    L = np.cumsum(np.log1p(np.clip(R, -0.999999, None)), axis=1)
    T = R.shape[1]
    cagr = np.exp(L[:, -1] * 365.0 / T) - 1
    hw = np.maximum.accumulate(np.concatenate([np.zeros((R.shape[0], 1)), L], axis=1), axis=1)[:, 1:]
    mdd = (1 - np.exp(L - hw)).max(axis=1)
    return np.where(mdd > 0, cagr / np.maximum(mdd, 1e-12), 0.0)


_IDX = {}


def bootstrap(b0, bv, idx=None):
    Tn = int(np.isfinite(b0).sum())
    if Tn not in _IDX:
        _IDX[Tn] = boot_idx(Tn)
    idx = _IDX[Tn]
    m = np.isfinite(b0) & np.isfinite(bv)
    a = np.where(m, b0, np.nan)[np.isfinite(b0)]; v = bv[np.isfinite(b0)]
    d = np.empty(NB)
    for s in range(0, NB, 1000):
        ii = idx[s:s + 1000, :len(a)]
        d[s:s + 1000] = calmar_batch(v[ii]) - calmar_batch(a[ii])
    point = calmar_cagr_mdd(v)[0] - calmar_cagr_mdd(a)[0]
    return d, point


def holm(p):
    p = np.asarray(p); o = np.argsort(p); m = len(p); adj = np.empty(m); run = 0
    for rank, i in enumerate(o):
        run = max(run, (m - rank) * p[i]); adj[i] = min(1.0, run)
    return adj


def turnover(runs, sim, cost):
    t = []; dr = []
    for r in runs:
        eq = r["eq"].to_numpy(); m = np.isfinite(eq); m[:sim.d0] = False
        yrs = m.sum() / 365.0
        to = r["tn"][m].sum() / np.nanmean(eq[m]) / yrs
        t.append(to); dr.append(to * cost)
    return float(np.mean(t)), float(np.mean(dr))


def summary(runs, sim, cost):
    w = windows(sim)["full"]
    s = wstats(runs, sim, w)
    to, drag = turnover(runs, sim, cost)
    yrs = (sim.nd - sim.d0) / 365.0
    return dict(calmar=float(np.nanmean(s[:, 0])), calmar_worst=float(np.nanmin(s[:, 0])), cagr=float(np.nanmean(s[:, 1])),
                cagr_worst=float(np.nanmin(s[:, 1])), mdd=float(np.nanmean(s[:, 2])), mdd_worst=float(np.nanmax(s[:, 2])),
                kills=float(np.mean([r["kills"] for r in runs])), liq=int(sum(r["liq"] for r in runs)),
                turnover=to, fee_drag=drag, exL_yr=float(np.mean([r["exL"].sum() for r in runs]) / yrs),
                exS_yr=float(np.mean([r["exS"].sum() for r in runs]) / yrs),
                end=[float(r["eq"].dropna().iloc[-1]) for r in runs])


def main():
    t0 = time.time()
    P = load_panel(); full = TPSim(P); sims_h = {1: TPSim(P, zh=1), 3: TPSim(P, zh=3)}
    rng = np.random.default_rng(20261030)
    subsets = [sorted(rng.choice(len(P["names"]), 30, replace=False).tolist()) for _ in range(10)]
    subsims = [TPSim(P, cols=c) for c in subsets]
    trend, volb = regimes(full)
    T = int((full.nd) - full.d0) ; idx = boot_idx(full.nd)
    res = {"meta": dict(nb=NB, blk=BLK, seed=SEED, subsets=[[P["names"][j] for j in c] for c in subsets])}
    for bn, base in BASES.items():
        R = {}
        v0 = run_cfg(full, base, {}); v0_2 = run_cfg(full, base, {}, cost=0.002)
        R["V0"] = summary(v0, full, 0.001); R["V0_2x"] = summary(v0_2, full, 0.002)
        bv0 = blend(v0, full)
        v0_sub = [run_cfg(s, base, {}) for s in subsims]
        pvals = []; cfgres = {}
        for name in HEAD:
            c = CFGS[name]
            var = run_cfg(full, base, c)
            r = dict(summary=summary(var, full, 0.001))
            for win in ("full", "IS", "OOS"):
                dlt, a, b = delta_calmar(full, v0, var, win)
                r[f"d_{win}"] = dlt
                r[f"cagr_{win}"] = [float(np.nanmean(a[:, 1])), float(np.nanmean(b[:, 1]))]
                r[f"mdd_{win}"] = [float(np.nanmean(a[:, 2])), float(np.nanmean(b[:, 2]))]
            # per-phase delta (vs same-index V0 phase, or V0 mean for R)
            _, a, b = delta_calmar(full, v0, var, "full")
            ref = a[:, 0] if len(a) == len(b) else np.full(len(b), np.nanmean(a[:, 0]))
            r["phase_delta"] = (b[:, 0] - ref).tolist()
            r["worst_phase_delta"] = float(np.min(b[:, 0] - ref))
            bvv = blend(var, full)
            r["regimes"] = regime_table(full, bv0, bvv, trend, volb)
            r["stress"] = stress_table(full, bv0, bvv)
            nimp = sum(1 for k, v in r["regimes"].items() if v["dlog"] > 0)
            r["regimes_improved"] = nimp
            # 2x cost
            var2 = run_cfg(full, base, c, cost=0.002)
            r["d_2x"] = delta_calmar(full, v0_2, var2, "full")[0]
            r["summary_2x"] = summary(var2, full, 0.002)
            # subsets
            ds = []
            for s, v0s in zip(subsims, v0_sub):
                vs = run_cfg(s, base, c)
                ds.append(delta_calmar(s, v0s, vs, "full")[0])
            r["subset_d"] = ds; r["subset_pos"] = int(sum(x > 0 for x in ds))
            # neighbours
            nb = []
            for nc in NEIGH.get(name, []):
                nv = run_cfg(full, base, nc)
                nb.append(dict(cfg={k: v for k, v in nc.items()}, d_IS=delta_calmar(full, v0, nv, "IS")[0], d_OOS=delta_calmar(full, v0, nv, "OOS")[0],
                               d_full=delta_calmar(full, v0, nv, "full")[0]))
            r["neighbors"] = nb
            r["neigh_stable"] = bool(nb) and all(x["d_IS"] > 0 and x["d_OOS"] > 0 for x in nb)
            # wide neighbours: horizon 1/3 (informational)
            if name in ("A1", "A2", "A3", "C1"):
                wd = {}
                for h, sh in sims_h.items():
                    nv = run_cfg(full, base, c, Z=sh.Z)
                    wd[h] = delta_calmar(full, v0, nv, "full")[0]
                r["wide_h"] = wd
            # bootstrap
            d, pt = bootstrap(bv0, bvv, idx)
            r["boot"] = dict(point=pt, mean=float(d.mean()), p_one=float((d <= 0).mean()))
            r["boot_ci95"] = [float(np.percentile(d, 2.5)), float(np.percentile(d, 97.5))]
            a_ = 0.05 / len(HEAD)
            r["boot_ci_bonf"] = [float(np.percentile(d, 100 * a_ / 2)), float(np.percentile(d, 100 * (1 - a_ / 2)))]
            r["boot_dcagr"] = float(np.mean([calmar_cagr_mdd(blend(var, full)[np.isfinite(bv0)])[1]]) - calmar_cagr_mdd(bv0[np.isfinite(bv0)])[1])
            pvals.append(max(r["boot"]["p_one"], 1.0 / NB))
            cfgres[name] = r
            print(bn, name, "dCal full %.3f IS %.3f OOS %.3f | reg %d/6 sub %d/10 d2x %.3f nstab %s | %.0fs" % (
                r["d_full"], r["d_IS"], r["d_OOS"], nimp, r["subset_pos"], r["d_2x"], r["neigh_stable"], time.time() - t0), flush=True)
        adj = holm(pvals)
        for nm, pa, pr in zip(HEAD, adj, pvals):
            cfgres[nm]["boot"]["p_holm"] = float(pa)
        # placebos (LIVE and RESEARCH both; cheap)
        for name in HEAD:
            c = CFGS[name]
            if name in ("R1", "R2"):
                cfgres[name]["placebo"] = None; continue
            var = run_cfg(full, base, c)
            real = delta_calmar(full, v0, var, "full")[0]
            haz = {}
            for ph, r_ in enumerate(var):
                eL = r_["pdL"].sum(); eS = r_["pdS"].sum()
                haz[ph] = (r_["exL"].sum() / max(eL, 1), r_["exS"].sum() / max(eS, 1))
            pdist = []
            rg = np.random.default_rng(1000 + HEAD.index(name))
            for s in range(100):
                U = rg.random((full.nd, len(full.names)))
                pv = run_cfg(full, base, c, plc=haz, U=U)
                pdist.append(delta_calmar(full, v0, pv, "full")[0])
            pdist = np.array(pdist)
            pl = dict(real=real, hazard_p95=float(np.percentile(pdist, 95)), hazard_mean=float(pdist.mean()),
                      hazard_p=float((1 + (pdist >= real).sum()) / 101), hazard_pass=bool(real > np.percentile(pdist, 95)))
            if name in ("A1", "A2", "A3", "A4", "A5", "A6", "C1"):
                sd = []
                for s in range(100):
                    sh = int(rg.integers(30, full.nd - 30))
                    Zs = np.ascontiguousarray(np.roll(full.Z, sh, axis=0))
                    sv = run_cfg(full, base, c, Z=Zs)
                    sd.append(delta_calmar(full, v0, sv, "full")[0])
                sd = np.array(sd)
                pl.update(shift_p95=float(np.percentile(sd, 95)), shift_mean=float(sd.mean()), shift_p=float((1 + (sd >= real).sum()) / 101),
                          shift_pass=bool(real > np.percentile(sd, 95)))
            cfgres[name]["placebo"] = pl
            print(bn, name, "placebo", {k: (round(v, 3) if isinstance(v, float) else v) for k, v in pl.items()}, flush=True)
        R["cfg"] = cfgres
        res[bn] = R
        json.dump(res, open(OUT, "w"), indent=1, default=float)
    print("done %.0fs" % (time.time() - t0))


if __name__ == "__main__":
    main()
