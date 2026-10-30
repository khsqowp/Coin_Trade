"""BACKTESTER-C runner: executes the pre-registered cells (docs/research/lev_loop/C/prereg.md). Research only.
Writes docs/research/lev_loop/C/results.json (summaries) + results_r.npz (daily log-returns for bootstrap)."""
from __future__ import annotations
import json, os, sys, time
import numpy as np
import pandas as pd
from app.rs_final_data import load_panel
from app.rs_final_engine import window_metrics
from app.rs_lev_c_engine import LSim

OUT = os.path.join(os.path.dirname(os.path.abspath(__file__)), "..", "docs", "research", "lev_loop", "C")
SETS = {"S0": (4.0, 0.95), "S1": (3.0, 1.0), "S2": (3.0, 0.95), "S3": (5.0, 0.95), "S4": (2.5, 1.0)}
LADDER = [1.0, 1.5, 2.0, 2.5, 3.0, 3.5, 4.0, 5.0, 6.0, 8.0]   # x0.95 ; 1.0/1.5 = AMENDMENT-1 (scope extension, labelled)
TOP5 = ("HBAR", "ZEC", "XLM", "TAO", "STX")
NRUN = [0]
MONN = ["tier", "flat3", "gap5", "gap10", "flashF1", "flashF2", "flashF1L"]


def cfgs():
    out = dict(SETS)
    for l in LADDER:
        out[f"L{l:g}x0.95"] = (l, 0.95)
    return out


def summarize(S, res, keep_r=False):
    NRUN[0] += 1
    eq = res["eq"]; d0 = res["d0"]
    e = eq.to_numpy(copy=True)
    nd = len(e)
    seg = e[d0:]
    seg = pd.Series(seg).ffill().fillna(0).to_numpy()   # NaN tail (should not occur) -> hold
    e2 = e.copy(); e2[d0:] = seg
    with np.errstate(divide="ignore", invalid="ignore"):
        r = np.zeros(nd)
        r[d0 + 1:] = np.log(np.where(e2[d0 + 1:] > 0, e2[d0 + 1:], 1e-12) / np.where(e2[d0:-1] > 0, e2[d0:-1], 1e-12))
    r = np.where(np.isfinite(r), r, 0.0)
    oos0 = int(S.days.searchsorted(pd.Timestamp("2024-07-01", tz="UTC")))
    n_is = max(oos0 - 1 - d0, 1); n_oos = nd - oos0
    g_full = 365.0 * r[d0 + 1:].sum() / (nd - 1 - d0)
    g_is = 365.0 * r[d0 + 1:oos0].sum() / n_is
    g_oos = 365.0 * r[oos0:].sum() / n_oos
    wm = window_metrics(res)
    kd = res["kill_day"]
    mon = res["mon"]
    d = dict(g=float(g_full), g_is=float(g_is), g_oos=float(g_oos), tw=float(wm["end"]) if wm else float("nan"),
             cagr=float(wm["cagr"]) if wm else float("nan"), mdd=float(wm["mdd"]) if wm else float("nan"),
             imdd=float(wm["imdd"]) if wm else float("nan"), kills=int(res["kills"]), liq=bool(res["liq"]),
             liq_day=int(res["liq_day"]), skip=float(res["skip"]), att=float(res["att"]), imu=float(res["imu"]),
             flat=float((res["expo"].to_numpy()[d0:] == 0).mean()),
             mon_min=[float(x) for x in mon[:, 0]], mon_first=[int(x) for x in mon[:, 1]], mon_day=[int(x) for x in mon[:, 2]], nev=float(res["nev"]))
    if keep_r:
        d["_r"] = r
    return d


def avg_r(rs):
    return np.mean(np.stack(rs), axis=0)


def boot_diff(Rd, d0, nd, B=2000, block=15, seed=20261030, lo=None, hi=None, oos0=None):
    """annualised mean log-growth diff with moving-block bootstrap over days d0+1..nd-1"""
    d = Rd[d0 + 1:]
    T = len(d)
    rng = np.random.default_rng(seed)
    nb = int(np.ceil(T / block))
    st = rng.integers(0, T - block + 1, size=(B, nb))
    idx = (st[:, :, None] + np.arange(block)[None, None, :]).reshape(B, -1)[:, :T]
    bm = 365.0 * d[idx].mean(axis=1)
    return dict(point=float(365.0 * d.mean()), se=float(bm.std()), lo95=float(np.percentile(bm, 2.5)), hi95=float(np.percentile(bm, 97.5)),
                lo_bonf=float(np.percentile(bm, 0.625)), hi_bonf=float(np.percentile(bm, 99.375)))


def window_g(S, Rd, d0):
    oos0 = int(S.days.searchsorted(pd.Timestamp("2024-07-01", tz="UTC")))
    return dict(full=float(365 * Rd[d0 + 1:].mean()), is_=float(365 * Rd[d0 + 1:oos0].mean()), oos=float(365 * Rd[oos0:].mean()))


def universe_cell(S, cols, tag, cf, phases=(0, 1, 2), events=None, **kw):
    """5/12 configs x phases on one universe; returns summaries + phase-avg r."""
    out = {}
    for name, (lev, dep) in cf.items():
        runs = []
        for ph in phases:
            res = S.run_c(lev, dep, phase=ph, mm_mode=1, cols=cols, events=events, **kw)
            runs.append(summarize(S, res, keep_r=True))
        rr = avg_r([x.pop("_r") for x in runs])
        out[name] = dict(phases=runs, r=rr)
    return out


def kendall(a, b):
    n = len(a); c = 0; d = 0
    for i in range(n):
        for j in range(i + 1, n):
            s = (a[i] - a[j]) * (b[i] - b[j])
            c += s > 0; d += s < 0
    return (c - d) / (n * (n - 1) / 2)


def agg_phase(u, key):
    return float(np.mean([p[key] for p in u["phases"]]))


def main():
    t0 = time.time()
    S = LSim(load_panel())
    ds = S.d_start()
    n = len(S.names)
    nm = S.nm
    CF = cfgs()
    S5 = {k: SETS[k] for k in SETS}
    R = {"meta": dict(d_start=ds, nd=S.nd, fund_window=[str(S.days[S.fwin[0]].date()), str(S.days[S.fwin[1]].date())],
                      wick_day=str(S.days[S.wick_day].date()), wick=dict(zip(nm, [float(x) for x in S.wick])))}
    rarr = {}

    # ---------------- U1 / U2 / U3 (12 configs so that ladder is covered; verdicts use S0..S4)
    print("U1", flush=True)
    allc = list(range(n))
    U = {}
    U["U1"] = universe_cell(S, allc, "U1", CF)
    ex = [j for j in range(n) if nm[j] not in TOP5]
    U["U2"] = universe_cell(S, ex, "U2", CF)
    rng = np.random.default_rng(20261030)
    subs = [sorted(rng.choice(n, size=30, replace=False).tolist()) for _ in range(30)]
    R["subsets"] = [[nm[j] for j in s] for s in subs]
    for k, cols in enumerate(subs):
        print("U3 subset", k, flush=True)
        U[f"U3_{k:02d}"] = universe_cell(S, cols, f"U3_{k}", CF)
    # ---------------- U4 delisting stress
    for seed in range(1, 21):
        ev = S.make_events(seed, ds)
        U[f"U4_{seed:02d}"] = universe_cell(S, allc, "U4", CF, events=ev)
    print("U done", time.time() - t0, flush=True)
    for uk, uv in U.items():
        for name, x in uv.items():
            rarr[f"{uk}|{name}"] = x["r"].astype(np.float32)
    R["U"] = {uk: {name: dict(phases=x["phases"]) for name, x in uv.items()} for uk, uv in U.items()}

    # ---------------- jitter families
    FAM = {
        "J1": dict(kill_mode=1, mm_mode=1),
        "K1": dict(kill_mode=2, mm_mode=1),
        "K2": dict(kill_mode=3, mm_mode=1),
        "K3": dict(kill_mode=4, mm_mode=1),
        "K5ph": dict(kill_mode=5, mm_mode=1),     # POST-HOC
        "K6ph": dict(kill_mode=6, mm_mode=1),     # POST-HOC
        "L3a": dict(kill_mode=1, mm_mode=1, r1=0.5 / S.cap_a, capj=S.cap_a, cap_on=1),
        "L3b": dict(kill_mode=1, mm_mode=1, r1=0.5 / S.cap_b, capj=S.cap_b, cap_on=1),
        "L4": dict(kill_mode=1, mm_mode=1, minn=5.0, eq0=127.0),
        "L7": dict(kill_mode=1, mm_mode=1, fmult=S.fmult_stress(3.0)),
    }
    J = {}
    for fam, kw in FAM.items():
        J[fam] = {}
        for name, (lev, dep) in CF.items():
            rows = []
            for off in range(40):
                for ph in range(3):
                    res = S.run_c(lev, dep, phase=ph, d0=ds + off, **kw)
                    keep = (off == 0)
                    x = summarize(S, res, keep_r=keep)
                    x["off"] = off; x["ph"] = ph
                    if keep:
                        rarr[f"{fam}|{name}|ph{ph}"] = x.pop("_r").astype(np.float32)
                    rows.append(x)
            J[fam][name] = rows
        print("family", fam, time.time() - t0, flush=True)
    R["J"] = J
    R["trials"] = dict(engine_runs=NRUN[0], configs=len(CF), families=len(FAM))
    with open(os.path.join(OUT, "results.json"), "w") as f:
        json.dump(R, f, default=float)
    np.savez_compressed(os.path.join(OUT, "results_r.npz"), **rarr)
    print("DONE", time.time() - t0, "runs", NRUN[0])


if __name__ == "__main__":
    main()
