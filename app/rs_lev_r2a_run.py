"""R2-A runner / metrics (research only, offline). Modes: replicate | stage0 | stage1 | oos.
All thresholds are fixed in docs/research/lev_loop/R2A/prereg.md BEFORE running."""
import sys, os, json, pickle, time
sys.dont_write_bytecode = True
sys.path.insert(0, os.path.join(os.path.dirname(os.path.abspath(__file__)), ".."))
import numpy as np, pandas as pd
from app import rs_lev_r2a_engine as E

OUT = os.path.join(os.path.dirname(os.path.abspath(__file__)), "../docs/research/lev_loop/R2A/out")
os.makedirs(OUT, exist_ok=True)
N = E.N; ND = E.ND
IS0, IS1 = E.day_idx("2022-01-01"), E.day_idx("2024-07-01")
OOS0, OOS1 = E.day_idx("2024-07-01"), ND
PERIOD = {"IS": (IS0, IS1), "OOS": (OOS0, OOS1)}
M_PATHS = 60
KMS = list(E.KILLMODELS)
CELLS = {
    "C0_control": dict(norm=0, gcap=0.0, ncap=0.0, scap=0.0),
    "C1_norm": dict(norm=1, gcap=0.0, ncap=0.0, scap=0.0),
    "G42": dict(gcap=4.2), "G46": dict(gcap=4.6),
    "N03": dict(ncap=0.3), "N05": dict(ncap=0.5),
    "S12": dict(scap=0.12),
    "X1_G42_S12": dict(gcap=4.2, scap=0.12),
    "X2_G46_N05_S12": dict(gcap=4.6, ncap=0.5, scap=0.12),
}
CANDS = [c for c in CELLS if c not in ("C0_control",)]
CTL = "C0_control"
FS = (0.5, 0.75, 1.0)
MODELS = ("anti", "sync", "hedged")
# ---- shock bar (2025-10-10 21:00 UTC), relative to previous hour close
_D = E.day_idx("2025-10-10")
_ref = E.C[_D, 20, :]
rL = E.L[_D, 21, :] / _ref; rH = E.H[_D, 21, :] / _ref
rL = np.where(np.isfinite(rL), rL, np.nanmedian(rL)); rH = np.where(np.isfinite(rH), rH, np.nanmedian(rH))
MM_TIER = E.MMR; MM_FLAT = np.full(N, 0.03)

def path_spec(k):
    """k=0: un-jittered baseline; k>=1: random start offset, phase, per-kill cooldown jitter (+-2d) and re-entry delay (0-2d)."""
    if k == 0:
        return dict(off=0, phase=0, cool_j=np.zeros(64, np.int64), delay_j=np.zeros(64, np.int64))
    r = np.random.default_rng(910000 + k)
    return dict(off=int(r.integers(0, 40)), phase=int(r.integers(0, 3)),
                cool_j=r.integers(-2, 3, 64).astype(np.int64), delay_j=r.integers(0, 3, 64).astype(np.int64))
SPECS = [path_spec(k) for k in range(M_PATHS)]

def run_paths(cell, km, per, lev=4.0, dep=0.95):
    d0, d1 = PERIOD[per]
    out = []
    for sp in SPECS:
        out.append(E.run(lev=lev, dep=dep, phase=sp["phase"], d0=d0 + sp["off"], d1=d1, km=km,
                         cool_j=sp["cool_j"], delay_j=sp["delay_j"], **CELLS[cell]))
    return out

# ---- date-shift (transplanted bar) closed-form cushions: c(f) = (c0 - f*b)/eq, adjusted-price maintenance notional
def tp_coeffs(snap, eq, mmv):
    held = (np.abs(snap).sum(1) > 0) & np.isfinite(eq) & (eq > 0)
    V = snap[held]; e = eq[held]; AV = np.abs(V); LG = np.where(V > 0, AV, 0.0); SH = np.where(V < 0, AV, 0.0)
    M0 = AV @ mmv; c0 = e - M0
    res = {}
    A = LG @ (1 - rL) + SH @ (rH - 1); M1 = LG @ ((rL - 1) * mmv) + SH @ ((rH - 1) * mmv); res["anti"] = A + M1
    A = LG @ (1 - rL) - SH @ (1 - rL); M1 = AV @ ((rL - 1) * mmv); res["hedged"] = A + M1
    A = LG @ (1 - rH) + SH @ (rH - 1); M1 = AV @ ((rH - 1) * mmv); res["allH"] = A + M1
    return held, c0, e, res

def tp_cushion(snap, eq, mmv):
    """returns dict model -> (days_idx, {f: cushion array}, fstar array)"""
    held, c0, e, b = tp_coeffs(snap, eq, mmv)
    days = np.where(held)[0]
    def cu(bb, f): return (c0 - f * bb) / e
    def fs(bb): return np.where(c0 <= 0, 0.0, np.where(bb > 0, c0 / np.where(bb > 0, bb, 1), 99.0))
    out = {}
    out["anti"] = ({f: cu(b["anti"], f) for f in FS}, fs(b["anti"]))
    out["hedged"] = ({f: cu(b["hedged"], f) for f in FS}, fs(b["hedged"]))
    out["sync"] = ({f: np.minimum(cu(b["hedged"], f), cu(b["allH"], f)) for f in FS}, np.minimum(fs(b["hedged"]), fs(b["allH"])))
    return days, out

def review_style(snapB, eqB, f, flat):
    """review/event_shift.py convention (unshocked MM notional, day-close pre-action book) -- replication of control only."""
    held = (np.abs(snapB).sum(1) > 0) & np.isfinite(eqB) & (eqB > 0)
    V = snapB[held]; e = eqB[held]; AV = np.abs(V); LG = np.where(V > 0, AV, 0.0); SH = np.where(V < 0, AV, 0.0)
    rLf = 1 + f * (rL - 1); rHf = 1 + f * (rH - 1)
    loss = LG @ (1 - rLf) + SH @ (rHf - 1)
    mm = AV @ MM_FLAT if flat else AV @ MM_TIER
    return float(np.mean(((e - loss - mm) / e) <= 0)), int(held.sum())

# ---- trajectories / effective sample
def n_unique_traj(runs):
    d1 = runs[0]["d1"]; d0 = max(r["d0"] for r in runs)
    w0 = max(d0 + 30, d1 - 365 - 1); w1 = d1 - 1
    eqs = [np.clip(r["eqs"][w0:w1], 1e-12, None) for r in runs]
    leaders = []
    for q in eqs:
        for l in leaders:
            ok = np.isfinite(q) & np.isfinite(l)
            if ok.sum() == 0: continue
            rr = q[ok] / l[ok]
            if np.max(np.abs(rr / rr[-1] - 1)) < 1e-6: break
        else:
            leaders.append(q)
    return len(leaders)

def episodes(daylist, gap=15):
    d = np.sort(np.unique(daylist))
    if len(d) == 0: return 0
    return int(1 + np.sum(np.diff(d) > gap))

# ---- summarise one (cell, km, period)
def summarise(runs, per, mmv=MM_TIER):
    d0, d1 = PERIOD[per]
    yrs = np.array([(r["d1"] - 1 - r["d0"] + 1) / 365.0 for r in runs])
    fin = np.array([r["final"] for r in runs])
    g = np.log(np.clip(fin, 1e-9, None)) / yrs
    S = dict(per=per, g=g, final=fin, kills=np.array([r["kills"] for r in runs]), yrs=yrs, n_unique=n_unique_traj(runs),
             cnt=np.array([r["cnt"] for r in runs]), dead=int(sum(r["dead"] for r in runs)))
    gc = np.concatenate([r["gcl"][np.isfinite(r["gcl"])] for r in runs])
    nc = np.abs(np.concatenate([r["ncl"][np.isfinite(r["ncl"])] for r in runs]))
    sc_ = np.concatenate([r["scl"][np.isfinite(r["scl"])] for r in runs])
    S["gross_mean_held"] = float(np.mean([np.nanmean(r["gcl"]) for r in runs]))
    S["gross_mean_all"] = float(np.mean([np.nansum(r["gcl"]) / (r["d1"] - r["d0"]) for r in runs]))
    S["gross_q"] = [float(np.percentile(gc, p)) for p in (50, 95, 99)] + [float(gc.max())]
    S["net_q"] = [float(np.percentile(nc, p)) for p in (50, 95, 99)] + [float(nc.max())]
    S["sym_q"] = [float(np.percentile(sc_, p)) for p in (50, 95, 99)] + [float(sc_.max())]
    S["real_cmin"] = np.array([r["cmin"] for r in runs]); S["real_liq_hours"] = int(sum(r["liq_hours"] for r in runs))
    # date-shifted
    nblk = int(np.ceil((d1 - d0) / 15.0))
    flags = {}; fstar = {m: [] for m in MODELS}; fstar_flat = {m: [] for m in MODELS}
    P = {}; blk = {}
    pathdays = {}
    for mmname, mmv_ in (("tier", MM_TIER), ("flat3", MM_FLAT)):
        for k, r in enumerate(runs):
            days, o = tp_cushion(r["snapA"], r["eqA"], mmv_)
            for m in MODELS:
                cs, fsd = o[m]
                if mmname == "tier": fstar[m].append(fsd.min() if len(fsd) else np.nan)
                else: fstar_flat[m].append(fsd.min() if len(fsd) else np.nan)
                for f in FS:
                    key = (mmname, m, f)
                    if key not in blk:
                        blk[key] = [np.zeros(nblk), np.zeros(nblk)]
                    b = np.minimum(((days - d0) // 15), nblk - 1)
                    liq = (cs[f] <= 0).astype(float)
                    np.add.at(blk[key][0], b, liq); np.add.at(blk[key][1], b, 1.0)
                    if mmname == "tier" and f == 0.75 and m == "anti":
                        pathdays[k] = days[cs[f] <= 0]
    S["fstar"] = {m: np.array(fstar[m]) for m in MODELS}; S["fstar_flat"] = {m: np.array(fstar_flat[m]) for m in MODELS}
    S["blk"] = blk
    S["P"] = {k: float(v[0].sum() / max(v[1].sum(), 1)) for k, v in blk.items()}
    S["held_days_total"] = float(blk[("tier", "anti", 0.75)][1].sum())
    S["liq_days_total_anti75"] = float(blk[("tier", "anti", 0.75)][0].sum())
    S["episodes_union_anti75"] = episodes(np.concatenate([v for v in pathdays.values()] + [np.array([], int)]))
    S["episodes_per_path_anti75"] = float(np.mean([episodes(v) for v in pathdays.values()]))
    S["blocks15_with_liq_anti75"] = int((blk[("tier", "anti", 0.75)][0] > 0).sum()); S["blocks15_total"] = nblk
    # daily log-return matrix for paired growth bootstrap
    lr = np.zeros((len(runs), ND))
    for k, r in enumerate(runs):
        eq = np.clip(r["eqs"], 1e-12, None)
        x = np.log(eq); d = np.zeros(ND); d[1:] = x[1:] - x[:-1]
        d[r["d0"]] = x[r["d0"]]
        d[~np.isfinite(d)] = 0.0
        lr[k] = d
    S["lr_mean_blocks"] = np.array([lr[:, d0 + 15 * b: min(d0 + 15 * (b + 1), d1)].sum(axis=1).mean() for b in range(nblk)])
    S["lr_blocks_by_path"] = np.array([[lr[k, d0 + 15 * b: min(d0 + 15 * (b + 1), d1)].sum() for b in range(nblk)] for k in range(len(runs))])
    return S

def subset_set():
    rng = np.random.default_rng(20261030)
    return [sorted(rng.choice(N, size=30, replace=False).tolist()) for _ in range(30)]

def run_subsets(cell, km, per):
    d0, d1 = PERIOD[per]; subs = subset_set(); real = []; tp1 = []; tp75 = []
    for cols in subs:
        r = E.run(cols=cols, phase=0, d0=d0, d1=d1, km=km, **CELLS[cell])
        real.append(r["cmin"])
        days, o = tp_cushion(r["snapA"], r["eqA"], MM_TIER)
        cs = o["anti"][0]
        tp1.append(float(cs[1.0].min()) if len(days) else np.nan); tp75.append(float(cs[0.75].min()) if len(days) else np.nan)
    return dict(real=np.array(real), tp1=np.array(tp1), tp75=np.array(tp75))

def boot_P_rel(Sc, Sk, key=("tier", "anti", 0.75), B=2000, seed=11):
    """paired block bootstrap (15d blocks) of relative drop 1-P_cand/P_ctl and each P."""
    r = np.random.default_rng(seed); n = len(Sc["blk"][key][0])
    idx = r.integers(0, n, size=(B, n))
    lc, hc = Sc["blk"][key]; lk, hk = Sk["blk"][key]
    pc = lc[idx].sum(1) / np.maximum(hc[idx].sum(1), 1); pk = lk[idx].sum(1) / np.maximum(hk[idx].sum(1), 1)
    ok = pk > 0
    drop = 1 - pc[ok] / pk[ok]
    return dict(P_cand_ci=[float(np.percentile(pc, 2.5)), float(np.percentile(pc, 97.5))],
                P_ctl_ci=[float(np.percentile(pk, 2.5)), float(np.percentile(pk, 97.5))],
                drop_ci=[float(np.percentile(drop, 2.5)), float(np.percentile(drop, 97.5))] if ok.sum() > 50 else None)

def growth_diff(Sc, Sk, B=4000, seed=7):
    """paired: path-averaged per-block log-growth differences, 15d block bootstrap; also path-level paired diffs."""
    yrs = float(np.mean(Sk["yrs"]))
    d = Sc["lr_mean_blocks"] - Sk["lr_mean_blocks"]
    r = np.random.default_rng(seed); n = len(d)
    idx = r.integers(0, n, size=(B, n)); bs = d[idx].sum(1) / yrs
    pd_ = Sc["g"] - Sk["g"]
    return dict(point=float(d.sum() / yrs), se_boot=float(bs.std()), ci95=[float(np.percentile(bs, 2.5)), float(np.percentile(bs, 97.5))],
                ci_bonf8=[float(np.percentile(bs, 0.3125)), float(np.percentile(bs, 99.6875))],
                path_mean=float(pd_.mean()), path_sd=float(pd_.std()), path_sign_pos=float(np.mean(pd_ > 0)))

def mde_from_control(Sk):
    """stage-0 MDE using ONLY control runs: chaos (path sd / sqrt(n_unique)) and block-bootstrap SE of path-mean growth."""
    yrs = float(np.mean(Sk["yrs"])); n = len(Sk["lr_mean_blocks"])
    r = np.random.default_rng(3); idx = r.integers(0, n, size=(4000, n))
    se_boot = float((Sk["lr_mean_blocks"][idx].sum(1) / yrs).std())
    sd = float(Sk["g"].std()); nu = max(Sk["n_unique"], 1)
    mde_chaos = 2.8 * np.sqrt(2) * sd / np.sqrt(nu); mde_boot = 2.8 * np.sqrt(2) * se_boot
    return dict(sd_g=sd, n_unique=nu, se_boot=se_boot, mde_chaos=float(mde_chaos), mde_boot=float(mde_boot), mde0=float(max(mde_chaos, mde_boot)))

THR = dict(fstar_gain=0.12, p_rel_drop=0.50, gross_min=-0.03, plausible_growth=0.05)

def admission(cell_res, ctl_res):
    """cell_res[km] = dict(S=..., sub=...). Returns per-km criteria. Fixed in prereg."""
    out = {}
    for km in KMS:
        Sc, Sk = cell_res[km]["S"], ctl_res[km]["S"]
        f_c = float(np.median(Sc["fstar"]["anti"])); f_k = float(np.median(Sk["fstar"]["anti"]))
        Pc = Sc["P"][("tier", "anti", 0.75)]; Pk = Sk["P"][("tier", "anti", 0.75)]
        dg = Sc["gross_mean_held"] / Sk["gross_mean_held"] - 1
        sc, sk = cell_res[km]["sub"], ctl_res[km]["sub"]
        worse = int(np.sum(sc["tp1"] < sk["tp1"] - 1e-9))
        c1 = (f_c - f_k) >= THR["fstar_gain"] - 1e-12
        c2 = (Pk > 0) and (Pc <= (1 - THR["p_rel_drop"]) * Pk)
        c3 = dg >= THR["gross_min"]
        c4 = worse == 0
        out[km] = dict(fstar_ctl=f_k, fstar_cell=f_c, d_fstar=f_c - f_k, P_ctl=Pk, P_cell=Pc, rel_drop=(1 - Pc / Pk) if Pk > 0 else None,
                       dgross=dg, subsets_worse_strict=worse, subsets_worse_tol02=int(np.sum(sc["tp1"] < sk["tp1"] - 0.02)),
                       c1=bool(c1), c2=bool(c2), c3=bool(c3), c4=bool(c4), passed=bool(c1 and c2 and c3 and c4))
    return out

def do_cells(cells, per, tag, with_sub=True):
    res = {}
    for cell in cells:
        res[cell] = {}
        for km in KMS:
            t = time.time()
            runs = run_paths(cell, km, per)
            S = summarise(runs, per)
            sub = run_subsets(cell, km, per) if with_sub else None
            res[cell][km] = dict(S=S, sub=sub)
            print(f"[{tag}] {per} {cell:16s} {km:7s} done {time.time()-t:5.1f}s", flush=True)
    return res

def replicate():
    # control cell vs published review numbers (assert-only)
    r = E.run(phase=0, km="daily", record=None) if False else E.run(phase=0, km="daily")
    exp = {(1.0, False): 0.639, (1.0, True): 0.727, (0.75, False): 0.166, (0.75, True): 0.308}
    for (f, flat), v in exp.items():
        p, n = review_style(r["snapB"], r["eqB"], f, flat)
        assert n == 1423, f"held days {n}"
        assert abs(p - v) < 0.0015, f"review-style P(f={f},flat={flat}) {p} vs {v}"
        print(f"PASS date-shift replication P(anti,f={f},{'flat3' if flat else 'tier'})={p:.3f} (review {v}) over {n} held days")
    print("REPLICATE_OK")

if __name__ == "__main__":
    mode = sys.argv[1]
    if mode == "replicate":
        replicate()
    elif mode == "stage0":
        res = do_cells([CTL], "IS", "stage0", with_sub=False)
        m0 = {km: mde_from_control(res[CTL][km]["S"]) for km in KMS}
        json.dump(m0, open(os.path.join(OUT, "stage0_mde.json"), "w"), indent=1)
        pickle.dump(res, open(os.path.join(OUT, "stage0_ctl_IS.pkl"), "wb"))
        print("STAGE0 written")
    elif mode in ("stage1", "oos"):
        per = "IS" if mode == "stage1" else "OOS"
        cells = list(CELLS) if mode == "stage1" else [CTL] + (sys.argv[2].split(",") if len(sys.argv) > 2 else [])
        res = do_cells(cells, per, mode)
        pickle.dump(res, open(os.path.join(OUT, f"{mode}_{per}.pkl"), "wb"))
        print("WRITTEN", mode)
