"""Offline map: stage 'select' (reads selection-window case table, freezes finalists) and stage 'eval' (finalists only:
holdout once, null, survivorship, blends, deflated Sharpe). usage: python -m app.rs_map_off_final select|eval"""
from __future__ import annotations
import json, math, os, sys, hashlib, time
import numpy as np, pandas as pd
from statistics import NormalDist
from app.rs_map_off_core import *
from app.rs_map_off_data import load_data, SCRATCH
from app.rs_map_off_run import registry, grid_points, COSTS, SIZES, OVL_MODES

OUT = os.path.join(SCRATCH, "mapoff")
DOCS = os.path.join(os.path.dirname(os.path.dirname(os.path.abspath(__file__))), "docs", "research")
KEY = ["family", "tf", "params", "cons", "K", "cad", "wt", "mode"]
BASE_CS = "c10F|x1"
N_NULL = 300
ND = NormalDist()


def jdump(o, name):
    p = os.path.join(DOCS, name)
    json.dump(o, open(p, "w"), ensure_ascii=False, indent=1, default=float)
    print("wrote", p, os.path.getsize(p) // 1024, "KB")


def baselines(cx):
    ctl = control_runs(cx, d1=cx.d_hold, per_phase=True)   # per-phase metrics averaged = same convention as the case table
    out = {}
    for k, rl in ctl.items():
        out[k] = dict(sel=phase_mets(rl, cx.d0, cx.d_hold), folds=[phase_mets(rl, *cx.widx(a, b)) for a, b in FOLDS])
    return ctl, out


def neighbours(row, lut, axes_vals):
    """one-step neighbours: adjacent value on one param axis, adjacent K, adjacent cadence; same family/tf/cons/wt/mode."""
    p = json.loads(row["params"]); res = []
    for ax, vals in axes_vals[row["family"]].items():
        i = vals.index(p[ax])
        for di in (-1, 1):
            if 0 <= i + di < len(vals):
                q = dict(p); q[ax] = vals[i + di]
                res.append((row["family"], row["tf"], json.dumps(q, sort_keys=True), row["cons"], row["K"], row["cad"], row["wt"], row["mode"]))
    if row["cons"] in ("LS", "LO_TOPN"):
        i = KS.index(row["K"])
        for di in (-1, 1):
            if 0 <= i + di < len(KS):
                res.append((row["family"], row["tf"], row["params"], row["cons"], KS[i + di], row["cad"], row["wt"], row["mode"]))
    if row["cons"] != "OVL":
        i = CADENCES.index(row["cad"])
        for di in (-1, 1):
            if 0 <= i + di < len(CADENCES):
                res.append((row["family"], row["tf"], row["params"], row["cons"], row["K"], CADENCES[i + di], row["wt"], row["mode"]))
    return [lut[k] for k in res if k in lut]


def select():
    D = load_data(); cx = Ctx(D); reg = registry()
    df = pd.read_csv(os.path.join(OUT, "cases.csv.gz"))
    err = df[df.cons == "ERROR"]
    df = df[df.cons != "ERROR"].copy()
    df["mode"] = df["mode"].fillna("").astype(str)
    ctl, bl = baselines(cx)
    blB = bl["rot14/3d/K8+crash|B"]; blA = bl["rot14/3d/K8+crash|A"]
    base = df[df.cs == BASE_CS].copy()
    isA = (base.cons == "OVL").to_numpy()
    def _b(a, b_):
        return np.where(isA, a, b_)
    c_sel = base.calmar.to_numpy() > _b(blA["sel"]["calmar"], blB["sel"]["calmar"])
    ok = c_sel.copy()
    for k in range(3):
        ok &= base[f"f{k+1}_calmar"].to_numpy() > _b(blA["folds"][k]["calmar"], blB["folds"][k]["calmar"])
    base["beat_sel"] = c_sel; base["beat_all"] = ok
    base["robust"] = base[["calmar", "f1_calmar", "f2_calmar", "f3_calmar"]].min(axis=1)
    # neighbours
    axes_vals = {n: {a: list(v) for a, v in f["grid"].items()} for n, f in reg.items()}
    lut = {tuple(r[k] for k in KEY): r["calmar"] for _, r in base[KEY + ["calmar"]].iterrows()}
    cand = base[(base.robust > 0) & (base.mdd <= 0.5) & (base.cagr > 0.05)].sort_values("robust", ascending=False)
    tops = cand.groupby(["family", "cons"]).head(3)
    nb_rate = []
    for _, r in tops.iterrows():
        nb = neighbours(r, lut, axes_vals)
        nb_rate.append(np.mean([x >= 0.8 * r.calmar for x in nb]) if nb else np.nan)
    tops = tops.assign(nb_rate=nb_rate)
    tops["nb_pass"] = tops.nb_rate >= 0.75
    tops = tops.sort_values(["nb_pass", "robust"], ascending=[False, False])
    # best per (family, cons); passing neighbour test first, then fill to 8 with best failing ones (flagged)
    best = tops.groupby(["family", "cons"]).head(1)
    best = best.sort_values(["nb_pass", "robust"], ascending=[False, False])
    fin_parts = []
    for cons_ in ("LS", "LO_EW", "LO_TOPN", "OVL"):
        g = best[best.cons == cons_].sort_values(["nb_pass", "robust"], ascending=[False, False])
        fin_parts.append(g.groupby("family").head(1).head(5))     # <=5 per construction, 1 per family
    fin = pd.concat(fin_parts)
    # walk-forward pick per (family, cons): choose by mean train-fold calmar, test on next fold
    wf = []
    for (fam, cons), g in base.groupby(["family", "cons"]):
        g = g[g.cagr.notna()]
        p1 = g.loc[((g.f1_calmar)).idxmax()]; t1 = p1.f2_calmar
        p2 = g.loc[((g.f1_calmar + g.f2_calmar) / 2).idxmax()]; t2 = p2.f3_calmar
        b = blA if cons == "OVL" else blB
        wf.append(dict(family=fam, cons=cons, wf_test_f2=float(t1), wf_test_f3=float(t2),
                       base_f2=b["folds"][1]["calmar"], base_f3=b["folds"][2]["calmar"],
                       wins=int(t1 > b["folds"][1]["calmar"]) + int(t2 > b["folds"][2]["calmar"])))
    wf = pd.DataFrame(wf)
    summ = base.groupby(["family", "cons"]).agg(n=("calmar", "size"), beat_sel=("beat_sel", "mean"), beat_all=("beat_all", "mean"),
                                                med_calmar=("calmar", "median"), best_calmar=("calmar", "max"),
                                                best_robust=("robust", "max")).reset_index()
    summ.to_csv(os.path.join(OUT, "family_summary.csv"), index=False)
    wf.to_csv(os.path.join(OUT, "wf_pick.csv"), index=False)
    fin_list = []
    for _, r in fin.iterrows():
        fin_list.append({k: (r[k].item() if hasattr(r[k], "item") else r[k]) for k in KEY + ["calmar", "robust", "nb_rate", "nb_pass", "cagr", "mdd"]})
    frozen = dict(frozen_at=time.strftime("%Y-%m-%d %H:%M:%S"), rule="per (family,cons) best min(SEL,F1,F2,F3 Calmar) among cagr>5%,mdd<=50%; neighbours>=0.8xCalmar in >=75% preferred; "
                  "top 5 families per construction (LS, LO_EW, LO_TOPN, OVL)", finalists=fin_list,
                  baseline_A=blA, baseline_B=blB)
    jdump(frozen, "map_off_finalists.json")
    base.to_csv(os.path.join(OUT, "base_cases.csv.gz"), index=False)
    # headline counts
    n_all = len(df); n_units = df.groupby(["family", "tf", "params"]).ngroups
    cnt = dict(total_cases=int(n_all), base_cases=int(len(base)), units=int(n_units), errors=int(len(err)),
               beat_sel=float(base.beat_sel.mean()), beat_all=float(base.beat_all.mean()))
    print(json.dumps(cnt))
    print(summ.sort_values("best_robust", ascending=False).head(30).to_string())
    print(fin[KEY + ["calmar", "robust", "nb_rate", "nb_pass", "cagr", "mdd"]].to_string())
    print(wf.to_string())
    json.dump(cnt, open(os.path.join(OUT, "counts.json"), "w"))


# ------------------------------------------------------------------------------------------------ eval stage
def build(cx, fam, tf, p, cons, K, wt, mode, D, subset=None):
    pos, st = fam["fn"](D, tf, **p)
    pos = np.asarray(pos, float).copy(); st = np.asarray(st, float).copy()
    if subset is not None:
        pos[:, ~subset] = np.nan; st[:, ~subset] = np.nan
    return pos, st


def case_returns(cx, pos, st, cons, K, cad, wt, mode, cost, fund, vt, cap, d1=None):
    """phase-averaged and per-phase return arrays for a case"""
    if cons == "LS":
        sc = ls_score(cx, st)
        fn = lambda ph: run_engine(cx, sc, K, cad, ph, cost, fund, vt, cap, 1, None, d1)[0]
    elif cons == "LO_EW":
        W = w_longonly_ew(cx, pos, wt == "iv")
        fn = lambda ph: run_w(cx, W, cad, ph, cost, fund, vt, cap, None, d1)
    elif cons == "LO_TOPN":
        W = w_topn_gate(cx, pos, st, K, wt == "iv", True)
        fn = lambda ph: run_w(cx, W, cad, ph, cost, fund, vt, cap, None, d1)
    elif cons == "OVL":
        if mode == "gate":
            sc = rotation_score(cx, (14,)); fl = overlay_flat(cx, pos, mode)
        else:
            sc = overlay_score(cx, pos, st, mode); fl = cx.crash
        fn = lambda ph: run_engine(cx, sc, 8, 3, ph, cost, fund, vt, cap, 0, fl, d1)[0]
    else:
        raise ValueError(cons)
    c = 3 if cons == "OVL" else cad
    rs = [rets(fn(p)) for p in range(c)]
    return np.nanmean(np.vstack(rs), axis=0), rs, fn


def yearly(cx, r):
    out = {}
    s = pd.Series(r, index=cx.days)
    for y, g in s.groupby(s.index.year):
        g = g[np.isfinite(g.to_numpy())]
        out[int(y)] = float(np.prod(1 + g.to_numpy()) - 1) if len(g) else None
    return out


def dsr(r, sr_var_daily, n_trials):
    x = r[np.isfinite(r)]
    T = len(x); sr = x.mean() / x.std()
    g = 0.5772156649
    sr0 = math.sqrt(sr_var_daily) * ((1 - g) * ND.inv_cdf(1 - 1 / n_trials) + g * ND.inv_cdf(1 - 1 / (n_trials * math.e)))
    sk = float(pd.Series(x).skew()); ku = float(pd.Series(x).kurt() + 3)
    den = math.sqrt(max(1 - sk * sr + (ku - 1) / 4 * sr * sr, 1e-9))
    return float(ND.cdf((sr - sr0) * math.sqrt(T - 1) / den)), float(sr * math.sqrt(365)), float(sr0 * math.sqrt(365))


def null_draws(cx, pos, st, cons, K, cad, wt, mode, rng, n=N_NULL):
    """matched-turnover null: circularly time-shift the whole signal (score/weights/flags) vs returns by a random lag>=60d."""
    cal, cg = [], []
    lo, hi = 60, cx.nd - 60
    for _ in range(n):
        lag = int(rng.randint(lo, hi))
        p2 = np.roll(pos, lag, axis=0); s2 = np.roll(st, lag, axis=0)
        r, rs, _ = case_returns(cx, p2, s2, cons, K, cad, wt, mode, 0.001, 1, 0.0, 1.5, cx.d_hold)
        m = mets(r, cx.d0, cx.d_hold)
        cal.append(m["calmar"] if m else np.nan); cg.append(m["cagr"] if m else np.nan)
    return np.array(cal), np.array(cg)


def erc_weights(cov, it=200):
    n = cov.shape[0]; w = np.ones(n) / n
    for _ in range(it):
        m = cov @ w; rc = w * m
        w = w * (rc.mean() / np.maximum(rc, 1e-14)) ** 0.5
        w = np.maximum(w, 1e-6); w /= w.sum()
    return w


def blend_series(rot, fins, mode, lb=60):
    """rot, fins: arrays (nd,). returns blended daily returns (sleeves rebalanced daily to target weights, weights lagged 1 day)"""
    X = np.vstack([rot] + list(fins)).T
    nd, k = X.shape
    w = np.full((nd, k), 1.0 / k)
    if mode == "5050":
        pass
    else:
        for i in range(nd):
            lo = max(0, i - (lb if mode == "ivol" else 120)); win = X[lo:i]
            if len(win) < 30 or not np.isfinite(win).all():
                continue
            if mode == "ivol":
                s = win.std(0); iv = 1 / np.maximum(s, 1e-9); w[i] = iv / iv.sum()
            elif mode == "erc" and i % 20 == 0:
                w[i] = erc_weights(np.cov(win.T))
            elif mode == "erc":
                w[i] = w[i - 1]
    return np.nansum(X * w, axis=1) * np.where(np.isfinite(X).all(1), 1.0, np.nan)


def evaluate():
    D = load_data(); cx = Ctx(D); reg = registry()
    fz = json.load(open(os.path.join(DOCS, "map_off_finalists.json")))
    fin = fz["finalists"]
    base = pd.read_csv(os.path.join(OUT, "base_cases.csv.gz"))
    base["mode"] = base["mode"].fillna("").astype(str)
    n_total = int(json.load(open(os.path.join(OUT, "counts.json")))["total_cases"])
    n_units = int(json.load(open(os.path.join(OUT, "counts.json")))["units"])
    sr_var = float((base.sharpe / math.sqrt(365)).var())
    n_trials = len(base)
    ctl = control_runs(cx, d1=None)                       # full period incl. holdout, causal
    rotA = ctl["rot14/3d/K8+crash|A"]; rotB = ctl["rot14/3d/K8+crash|B"]
    ia, ib = cx.d0, cx.d_hold; hd0, hd1 = cx.d_hold, cx.nd
    rng = np.random.RandomState(2026)
    res = []; ret_store = {}
    pre = cx.pre2022
    for f in fin:
        fam = reg[f["family"]]; p = json.loads(f["params"]); tf = f["tf"]
        pos, st = build(cx, fam, tf, p, f["cons"], f["K"], f["wt"], f["mode"], D)
        K, cad, wt, mode, cons = int(f["K"]), int(f["cad"]), f["wt"], (f["mode"] if isinstance(f["mode"], str) else ""), f["cons"]
        if cons == "OVL":
            K, cad = 8, 3
        out = dict(id=f"{f['family']}|{tf}|{cons}|K{K}|c{cad}|{wt}|{mode}|{f['params']}", family=f["family"], tf=tf, cons=cons, K=K, cad=cad, wt=wt, mode=mode, params=p)
        r, rs, _ = case_returns(cx, pos, st, cons, K, cad, wt, mode, 0.001, 1, 0.0, 1.5)
        ret_store[out["id"]] = r
        out["sel"] = mets(r, ia, ib); out["hold"] = mets(r, hd0, hd1)
        out["folds"] = [mets(r, *cx.widx(a, b)) for a, b in FOLDS]
        out["years"] = yearly(cx, np.where(np.arange(cx.nd) < ib, r, np.nan))
        out["hold_total"] = float(np.prod(1 + r[hd0:hd1][np.isfinite(r[hd0:hd1])]) - 1)
        yv = [v for k, v in out["years"].items() if v is not None]
        lg = {k: math.log1p(v) for k, v in out["years"].items() if v is not None}
        tot = sum(lg.values())
        out["top_year_share"] = float(max(lg.values()) / tot) if tot > 0 else None
        out["share_2024"] = float(lg.get(2024, 0) / tot) if tot > 0 else None
        out["ex2024_cagr"] = float(np.expm1((tot - lg.get(2024, 0)) / (len(lg) - 1 if 2024 in lg else len(lg)))) if tot > 0 else None
        # costs / sizing variants (selection window only)
        for tag, (c, fd, vt) in {"c04": (0.0004, 0, 0.0), "vt15": (0.001, 1, 0.15), "vt20": (0.001, 1, 0.20), "vt25": (0.001, 1, 0.25)}.items():
            rv, _, _ = case_returns(cx, pos, st, cons, K, cad, wt, mode, c, fd, vt, 1.5, cx.d_hold)
            out[tag] = mets(rv, ia, ib)
        # survivorship subset (listed before 2022)
        ps, ss = build(cx, fam, tf, p, cons, K, wt, mode, D, subset=pre)
        rsub, _, _ = case_returns(cx, ps, ss, cons, K, cad, wt, mode, 0.001, 1, 0.0, 1.5, cx.d_hold)
        out["pre2022_subset"] = mets(rsub, ia, ib); out["n_pre2022"] = int(pre.sum())
        # null
        t = time.time()
        nc, ng = null_draws(cx, pos, st, cons, K, cad, wt, mode, rng)
        okn = np.isfinite(nc)
        cal = out["sel"]["calmar"]
        nfam = int(((base.family == f["family"]) & (base.cons == cons)).sum())
        mx = np.array([np.nanmax(rng.choice(nc[okn], size=nfam)) for _ in range(2000)])
        out["null"] = dict(n=int(okn.sum()), pct_calmar=float((nc[okn] < cal).mean()), null_med=float(np.median(nc[okn])),
                           null_p95=float(np.percentile(nc[okn], 95)), null_max=float(nc[okn].max()),
                           pct_cagr=float((ng[np.isfinite(ng)] < out["sel"]["cagr"]).mean()),
                           bestofN_p95_calmar=float(np.percentile(mx, 95)), n_family_cases=nfam,
                           beats_bestofN_p95=bool(cal > np.percentile(mx, 95)))
        d, srA, sr0 = dsr(r[ia:ib], sr_var, n_trials); out["dsr_all"] = dict(dsr=d, sr=srA, sr0=sr0)
        d2, _, sr02 = dsr(r[ia:ib], sr_var, max(n_units, 2)); out["dsr_units"] = dict(dsr=d2, sr0=sr02)
        # correlation with live rotation (A), (B)
        for tag, rr in (("A", rotA), ("B", rotB)):
            ok = np.isfinite(r) & np.isfinite(rr)
            sel = ok.copy(); sel[ib:] = False; sel[:ia] = False
            ho = ok.copy(); ho[:hd0] = False
            out[f"corr_{tag}_sel"] = float(np.corrcoef(r[sel], rr[sel])[0, 1])
            out[f"corr_{tag}_hold"] = float(np.corrcoef(r[ho], rr[ho])[0, 1]) if ho.sum() > 20 else None
        # 50/50, inverse-vol blends vs rotation A
        bl = {}
        for mode_b in ("5050", "ivol"):
            bs = blend_series(rotA, [r], mode_b)
            bl[mode_b] = dict(sel=mets(bs, ia, ib), hold=mets(bs, hd0, hd1))
        out["blend"] = bl
        res.append(out)
        print("done", out["id"][:80], "sel calmar %.2f hold cagr %.2f null pct %.2f" % (cal, out["hold"]["cagr"] if out["hold"] else float("nan"), out["null"]["pct_calmar"]), flush=True)
    # multi-sleeve ERC blend: rotation + top-3 finalists by robust
    top3 = [r for r in sorted(res, key=lambda o: -(o["sel"]["calmar"]))[:3]]
    # added AFTER first look: rotation + top-3 distinct NON-overlay sleeves (selection Calmar only; duplicates removed)
    non = []
    for o in sorted([o for o in res if o["cons"] != "OVL"], key=lambda o: -o["sel"]["calmar"]):
        if all(abs(np.nansum(ret_store[o["id"]] - ret_store[q["id"]])) > 1e-6 for q in non):
            non.append(o)
    non3 = non[:3]
    erc = blend_series(rotA, [ret_store[o["id"]] for o in top3], "erc")
    iv3 = blend_series(rotA, [ret_store[o["id"]] for o in top3], "ivol")
    e5 = blend_series(rotA, [ret_store[o["id"]] for o in top3], "5050")
    nerc = blend_series(rotA, [ret_store[o["id"]] for o in non3], "erc")
    niv = blend_series(rotA, [ret_store[o["id"]] for o in non3], "ivol")
    neq = blend_series(rotA, [ret_store[o["id"]] for o in non3], "5050")
    bh = np.nanmean(np.where(np.isfinite(cx.dc[1:]) & np.isfinite(cx.dc[:-1]), cx.dc[1:] / cx.dc[:-1] - 1, np.nan), axis=1)
    bh = np.concatenate([[np.nan], bh])
    btc_r = np.concatenate([[np.nan], cx.dc[1:, cx.btc] / cx.dc[:-1, cx.btc] - 1])
    tot = lambda x, a, b: float(np.prod(1 + x[a:b][np.isfinite(x[a:b])]) - 1)
    multi = dict(members_nonovl=[o["id"] for o in non3],
                 nonovl=dict(erc=dict(sel=mets(nerc, ia, ib), hold=mets(nerc, hd0, hd1), hold_total=tot(nerc, hd0, hd1)),
                             ivol=dict(sel=mets(niv, ia, ib), hold=mets(niv, hd0, hd1), hold_total=tot(niv, hd0, hd1)),
                             eq=dict(sel=mets(neq, ia, ib), hold=mets(neq, hd0, hd1), hold_total=tot(neq, hd0, hd1))),
                 refs=dict(btc_hold_total=tot(btc_r, hd0, hd1), ew_universe_hold_total=tot(bh, hd0, hd1), rotA_hold_total=tot(rotA, hd0, hd1),
                           rotB_hold_total=tot(rotB, hd0, hd1), btc_sel=mets(btc_r, ia, ib), ew_sel=mets(bh, ia, ib)),
                 members=[o["id"] for o in top3],
                 rot_alone=dict(sel=mets(rotA, ia, ib), hold=mets(rotA, hd0, hd1)),
                 erc=dict(sel=mets(erc, ia, ib), hold=mets(erc, hd0, hd1)),
                 ivol=dict(sel=mets(iv3, ia, ib), hold=mets(iv3, hd0, hd1)),
                 eq=dict(sel=mets(e5, ia, ib), hold=mets(e5, hd0, hd1)))
    cm = pd.DataFrame({o["id"][:40]: ret_store[o["id"]] for o in res}); cm["ROT_A"] = rotA
    corr = cm.iloc[ia:ib].corr().round(2)
    corr.to_csv(os.path.join(OUT, "corr_matrix.csv"))
    rot = dict(A=dict(sel=mets(rotA, ia, ib), hold=mets(rotA, hd0, hd1), years=yearly(cx, np.where(np.arange(cx.nd) < ib, rotA, np.nan))),
               B=dict(sel=mets(rotB, ia, ib), hold=mets(rotB, hd0, hd1)),
               controls={k: dict(sel=mets(v, ia, ib), hold=mets(v, hd0, hd1)) for k, v in ctl.items()})
    jdump(dict(n_total_cases=n_total, n_trials_base=n_trials, n_units=n_units, windows=dict(sel=[SEL_A, SEL_B], hold=[HOLD_A, str(cx.days[-1].date())]),
               rotation=rot, finalists=res, multi_blend=multi), "map_off_finalists_eval.json")
    print(corr.to_string())


if __name__ == "__main__":
    {"select": select, "eval": evaluate}[sys.argv[1]]()
