"""BACKTESTER-A main run (pre-registered grid in prereg.md). Research only, offline."""
import sys, os, json, time, itertools
sys.path.insert(0, os.path.dirname(__file__))
from lib import *
from math import comb
from scipy.stats import norm, skew, kurtosis

OUT = os.path.dirname(os.path.abspath(__file__))
P, CF = load_all(); S = TPSim(P, CF); NAMES = S.names

# ---------------------------------------------------------------- pre-registered grid (see prereg.md)
CFGS = {
 "T01": dict(side="both", frac=1.0, X=.15, lock=0), "T02": dict(side="both", frac=1.0, X=.25, lock=0),
 "T03": dict(side="both", frac=1.0, X=.40, lock=0), "T04": dict(side="both", frac=1.0, X=.60, lock=0),
 "T05": dict(side="both", frac=1.0, X=1.00, lock=0), "T06": dict(side="both", frac=.5, X=.25, lock=0),
 "T07": dict(side="both", frac=.5, X=.40, lock=0), "T08": dict(side="long", frac=1.0, X=.40, lock=0),
 "T09": dict(side="short", frac=1.0, X=.40, lock=0), "T10": dict(side="both", frac=1.0, X=.25, lock=1),
 "T11": dict(side="both", frac=1.0, X=.40, lock=1), "T12": dict(side="both", frac=1.0, X="margin1.0", lock=0),
}
assert len(CFGS) == 12
IDS = list(CFGS)

def tpkw(cid, lev, xs=1.0, fill=0):
    c = CFGS[cid]; X = c["X"]
    X = (1.0 / lev) if isinstance(X, str) else X
    X *= xs
    return dict(XL=X if c["side"] in ("both", "long") else 0.0, XS=X if c["side"] in ("both", "short") else 0.0,
                frac=c["frac"], lockout=c["lock"], fillmode=fill, slipx=0.003)

_cache = {}
def runs(env, cid=None, xs=1.0, cost_mult=1.0, fill=0):
    key = (env, cid, xs, cost_mult, fill)
    if key not in _cache:
        kw = dict(ENVS[env]); kw["cost"] = kw["cost"] * cost_mult
        tp = None if cid is None else tpkw(cid, kw["lev"], xs, fill)
        _cache[key] = [S.run(tp=tp, phase=ph, **kw) for ph in range(3)]
    return _cache[key]

def win(rl, a=None, b=None):
    ms = [window_metrics(r, a, b) for r in rl]
    out = {}
    for k in ("cagr", "mdd", "imdd", "sharpe", "end", "worst_day"):
        out[k] = float(np.mean([m[k] for m in ms]))
    cal_i = [m["cagr"] / m["imdd"] if m["imdd"] > 0 else 0 for m in ms]
    cal_c = [m["cagr"] / m["mdd"] if m["mdd"] > 0 else 0 for m in ms]
    out.update(calmar_i=float(np.mean(cal_i)), calmar_c=float(np.mean(cal_c)), calmar_i_min=float(min(cal_i)),
               imdd_max=float(max(m["imdd"] for m in ms)), cagr_min=float(min(m["cagr"] for m in ms)))
    return out

def passw(t, b):
    return bool(t["calmar_i"] > b["calmar_i"] and t["cagr"] >= b["cagr"] - 0.1 * abs(b["cagr"]))

WINS = {"IS": IS, "OOS": OOS, "full": (None, None), **{f"F{k+1}": f for k, f in enumerate(FOLDS)}}
def allwin(rl): return {w: win(rl, *ab) for w, ab in WINS.items()}

R = {"meta": dict(note="phase-mean metrics; calmar_i=CAGR/intraday MDD", ids=IDS)}
t0 = time.time()
# ---------------------------------------------------------------- V0 replication proof (bit-exact vs rs_final_engine)
from app.rs_final_engine import Sim as Ref
Rf = Ref(P); rep = {}
for env in ("A", "B", "C"):
    ok = True
    for ph in range(3):
        a = runs(env)[ph]; b = Rf.run(lbs=(14,), crash_flat=True, phase=ph, **ENVS[env])
        ok &= np.array_equal(a["eq"].to_numpy(), b["eq"].to_numpy(), equal_nan=True) and np.array_equal(a["worst"].to_numpy(), b["worst"].to_numpy(), equal_nan=True) and np.array_equal(a["expo"].to_numpy(), b["expo"].to_numpy())
    assert ok, env
    rep[env] = "EXACT eq/worst/expo, phases 0-2"
R["v0_replication"] = rep
# T12 == T02 in ENV-A
for ph in range(3):
    assert np.array_equal(runs("A", "T12")[ph]["eq"].to_numpy(), runs("A", "T02")[ph]["eq"].to_numpy(), equal_nan=True)
R["v0_replication"]["T12_eq_T02_envA"] = True

# ---------------------------------------------------------------- main grids
for env in ("A", "B", "C"):
    base = allwin(runs(env)); g = {"V0": base}
    for c in IDS:
        rl = runs(env, c); w = allwin(rl)
        w["ntp_per_year"] = float(np.mean([r["ntp"] for r in rl]) / ((S.nd - S.d_start()) / 365.0))
        w["kills"] = float(np.mean([r["kills"] for r in rl]))
        w["pass"] = {k: passw(w[k], base[k]) for k in WINS}
        g[c] = w
    g["V0"]["kills"] = float(np.mean([r["kills"] for r in runs(env)]))
    R[f"grid_{env}"] = g
gA = R["grid_A"]
REP = max(IDS, key=lambda c: gA[c]["IS"]["calmar_i"])
R["representative"] = REP
R["rep_rule"] = "argmax IS phase-mean Calmar_i among T01..T12, ENV-A"

# ---------------------------------------------------------------- neighbors (X*0.75, X*1.25), cost 2x, fills
nb = {}; 
for c in IDS:
    nb[c] = {}
    for xs in (0.75, 1.25):
        w = allwin(runs("A", c, xs=xs)); nb[c][str(xs)] = dict(IS=w["IS"], OOS=w["OOS"], passIS=passw(w["IS"], gA["V0"]["IS"]), passOOS=passw(w["OOS"], gA["V0"]["OOS"]))
R["neighbors_A"] = nb
st = {}
b2 = allwin(runs("A", None, cost_mult=2.0)); st["V0_cost2x"] = {k: b2[k] for k in ("IS", "OOS", "full")}
for c in IDS:
    w2 = allwin(runs("A", c, cost_mult=2.0))
    e = dict(cost2x=dict(IS=w2["IS"], OOS=w2["OOS"], full=w2["full"], passIS=passw(w2["IS"], b2["IS"]), passOOS=passw(w2["OOS"], b2["OOS"])))
    for fm in (1, 2):
        wf = allwin(runs("A", c, fill=fm))
        e[f"fill{fm}"] = dict(IS=wf["IS"], OOS=wf["OOS"], full=wf["full"], passIS=passw(wf["IS"], gA["V0"]["IS"]), passOOS=passw(wf["OOS"], gA["V0"]["OOS"]))
    wc = allwin(runs("A", c, cost_mult=2.0, fill=1))
    e["cost2x_fill1"] = dict(IS=wc["IS"], OOS=wc["OOS"], passIS=passw(wc["IS"], b2["IS"]), passOOS=passw(wc["OOS"], b2["OOS"]))
    st[c] = e
R["stress_A"] = st

# ---------------------------------------------------------------- walk-forward selection (diagnostic)
wf = []
for k, (a, b) in enumerate(FOLDS):
    tr_end = (pd.Timestamp(a) - pd.Timedelta(days=1)).strftime("%Y-%m-%d")
    tr = {c: win(runs("A", c), "2022-01-01", tr_end)["calmar_i"] for c in IDS}
    trb = win(runs("A"), "2022-01-01", tr_end)["calmar_i"]
    sel = max(IDS, key=lambda c: tr[c])
    te = gA[sel][f"F{k+1}"]; teb = gA["V0"][f"F{k+1}"]
    wf.append(dict(fold=f"F{k+1}", test=[a, b], train_end=tr_end, selected=sel, train_cal_sel=tr[sel], train_cal_v0=trb,
                   test_cal_sel=te["calmar_i"], test_cal_v0=teb["calmar_i"], test_cagr_sel=te["cagr"], test_cagr_v0=teb["cagr"], pass_=passw(te, teb)))
R["wf_selected"] = wf
fold_pass = {c: [gA[c]["pass"][f"F{k+1}"] for k in range(4)] for c in IDS}
R["fold_pass_A"] = fold_pass

# ---------------------------------------------------------------- daily-return matrix, DSR, PBO, effective bets
def dret(rl):
    rs = []
    for r in rl:
        s = r["eq"].dropna(); rs.append(s.pct_change().dropna())
    df = pd.concat(rs, axis=1).dropna(); return df.mean(axis=1)
RET = pd.concat({c: dret(runs("A", c)) for c in ["V0"] and []} | {}, axis=1) if False else None
cols = {"V0": dret(runs("A"))}; cols.update({c: dret(runs("A", c)) for c in IDS})
M = pd.concat(cols, axis=1).dropna(); T = len(M)
sr_d = (M.mean() / M.std()); g3 = M.apply(skew); g4 = M.apply(lambda x: kurtosis(x, fisher=False))
def sr0(var_sr, N):
    gam = 0.5772156649
    return np.sqrt(var_sr) * ((1 - gam) * norm.ppf(1 - 1.0 / N) + gam * norm.ppf(1 - 1.0 / (N * np.e)))
corr = M[IDS].corr().to_numpy(); ev = np.linalg.eigvalsh(corr); neff_raw = float(ev.sum() ** 2 / (ev ** 2).sum())
D = M[IDS].sub(M["V0"], axis=0); ev2 = np.linalg.eigvalsh(D.corr().to_numpy()); neff_diff = float(ev2.sum() ** 2 / (ev2 ** 2).sum())
varsr = float(sr_d[IDS].var(ddof=1))
def dsr_for(c, N):
    s0 = sr0(varsr, N); s = sr_d[c]
    z = (s - s0) * np.sqrt(T - 1) / np.sqrt(1 - g3[c] * s + (g4[c] - 1) / 4 * s * s)
    return dict(sr_ann=float(s * np.sqrt(365)), sr0_ann=float(s0 * np.sqrt(365)), haircut_sr_ann=float((s - s0) * np.sqrt(365)), dsr_prob=float(norm.cdf(z)), N=N)
ds = {}
for c in IDS:
    ds[c] = {f"N{N}": dsr_for(c, N) for N in (12, 36, max(2, round(neff_raw)))}
R["dsr"] = dict(T=T, var_sr_daily_trials=varsr, sr_v0_ann=float(sr_d["V0"] * np.sqrt(365)), neff_corr_raw=neff_raw, neff_corr_diff_vs_v0=neff_diff,
                per_config=ds, rep=ds[REP])
# PBO (CSCV), metric Sharpe, S=10
def pbo(Mx, S_=10):
    n = len(Mx); blocks = np.array_split(np.arange(n), S_); X = Mx.to_numpy(); logits = []
    for comb_ in itertools.combinations(range(S_), S_ // 2):
        tr = np.concatenate([blocks[b] for b in comb_]); te = np.concatenate([blocks[b] for b in range(S_) if b not in comb_])
        srt = X[tr].mean(0) / X[tr].std(0); srv = X[te].mean(0) / X[te].std(0)
        best = int(np.argmax(srt)); rk = (srv < srv[best]).sum() + 1; w = rk / (len(srv) + 1)
        logits.append(np.log(w / (1 - w)))
    logits = np.array(logits); return float((logits <= 0).mean()), len(logits)
R["pbo_13"], R["pbo_nsplits"] = pbo(M)
R["pbo_12tp_only"], _ = pbo(M[IDS])

# ---------------------------------------------------------------- block bootstrap of paired difference (rep vs V0)
rng = np.random.default_rng(12345)
def cal_from(ret):
    eq = np.cumprod(1 + ret); yrs = len(ret) / 365; cagr = eq[-1] ** (1 / yrs) - 1; hw = np.maximum.accumulate(eq)
    return cagr, cagr / max((1 - eq / hw).max(), 1e-9)
bs = {}
for wn, (a, b) in (("IS", IS), ("OOS", OOS), ("full", (None, None))):
    sub = M[["V0", REP]]
    if a: sub = sub[sub.index >= pd.Timestamp(a, tz="UTC")]
    if b: sub = sub[sub.index <= pd.Timestamp(b, tz="UTC")]
    X = sub.to_numpy(); n = len(X); bl = 10; d = []; dc = []
    for _ in range(2000):
        idx = np.concatenate([np.arange(s, s + bl) % n for s in rng.integers(0, n, n // bl + 1)])[:n]
        c0 = cal_from(X[idx, 0]); c1 = cal_from(X[idx, 1]); d.append(c1[1] - c0[1]); dc.append(c1[0] - c0[0])
    d = np.array(d); dc = np.array(dc)
    bs[wn] = dict(p_calmar_better=float((d > 0).mean()), dcalmar_ci=[float(np.percentile(d, 5)), float(np.percentile(d, 95))],
                  p_cagr_better=float((dc > 0).mean()), dcagr_ci=[float(np.percentile(dc, 5)), float(np.percentile(dc, 95))])
R["bootstrap_rep_vs_v0"] = bs

# ---------------------------------------------------------------- attribution
def attrib(rl):
    out = []
    for r in rl:
        tr = r["trades"]; ret = tr[:, 5] / tr[:, 6]; sym = tr[:, 0].astype(int); tot = ret.sum()
        o = np.sort(ret)[::-1]; k5 = max(1, int(np.ceil(0.05 * len(ret))))
        bysym = pd.Series(ret).groupby(sym).sum().sort_values(ascending=False)
        out.append(dict(n=len(ret), total=float(tot), top5_trades=float(o[:5].sum() / tot), top5pct_trades=float(o[:k5].sum() / tot),
                        top5_symbols=float(bysym.iloc[:5].sum() / tot), mean_ret=float(ret.mean()), win=float((ret > 0).mean()),
                        best=float(o[0]), top_syms=[NAMES[i] for i in bysym.index[:5]]))
    return {k: (float(np.mean([o[k] for o in out])) if k != "top_syms" else out[0][k]) for k in out[0]}
A = {"V0": attrib(runs("A")), REP: attrib(runs("A", REP))}
# right-tail cut: post-TP 3d continuation
C23 = S.C[:, 23, :]
post = []
for r in runs("A", REP):
    tr = r["trades"]; m = tr[:, 4] == 1
    for row in tr[m]:
        j = int(row[0]); xd = int(row[3]); d2 = min(xd + 3, S.nd - 1)
        if np.isfinite(C23[d2, j]): post.append(row[1] * (C23[d2, j] / row[9] - 1))
post = np.array(post)
A["post_tp_3d"] = dict(n=int(len(post)), mean=float(post.mean()) if len(post) else None, frac_positive=float((post > 0).mean()) if len(post) else None)
# TP trade stats by symbol-side and by year
tl = np.vstack([r["trades"] for r in runs("A", REP)])
A["rep_tp_count_by_side"] = dict(long=int(((tl[:, 4] == 1) & (tl[:, 1] > 0)).sum()), short=int(((tl[:, 4] == 1) & (tl[:, 1] < 0)).sum()))
R["attribution_A"] = A

# ---------------------------------------------------------------- extended attribution (all configs), ENV-B neighbors/stress, criteria table
ext = {}
C23 = S.C[:, 23, :]
for c in IDS:
    rl = runs("A", c); a = attrib(rl); pl, ps = [], []
    for r in rl:
        tr = r["trades"]
        for row in tr[np.isin(tr[:, 4], (1, 2))]:
            j = int(row[0]); d2 = min(int(row[3]) + 3, S.nd - 1)
            if np.isfinite(C23[d2, j]):
                (pl if row[1] > 0 else ps).append(row[1] * (C23[d2, j] / row[9] - 1))
    a["post_tp_3d_long"] = dict(n=len(pl), mean=float(np.mean(pl)) if pl else None, frac_pos=float(np.mean(np.array(pl) > 0)) if pl else None)
    a["post_tp_3d_short"] = dict(n=len(ps), mean=float(np.mean(ps)) if ps else None, frac_pos=float(np.mean(np.array(ps) > 0)) if ps else None)
    ext[c] = a
R["attribution_all_A"] = ext
nbB = {}; stB = {}
bB = allwin(runs("B")); bB2 = allwin(runs("B", None, cost_mult=2.0))
for c in IDS:
    nbB[c] = {}
    for xs in (0.75, 1.25):
        w = allwin(runs("B", c, xs=xs)); nbB[c][str(xs)] = dict(passIS=passw(w["IS"], bB["IS"]), passOOS=passw(w["OOS"], bB["OOS"]), calIS=w["IS"]["calmar_i"], calOOS=w["OOS"]["calmar_i"])
    w2 = allwin(runs("B", c, cost_mult=2.0)); wf2 = allwin(runs("B", c, fill=2))
    stB[c] = dict(c2_IS=passw(w2["IS"], bB2["IS"]), c2_OOS=passw(w2["OOS"], bB2["OOS"]), f2_IS=passw(wf2["IS"], bB["IS"]), f2_OOS=passw(wf2["OOS"], bB["OOS"]))
R["neighbors_B"] = nbB; R["stress_B"] = stB
# criteria table for every config (ENV-A verdict basis)
def sr_ann_hair(c): return R["dsr"]["per_config"][c]["N12"]["haircut_sr_ann"]
crit = {}
for c in IDS:
    k = {}
    k["1_IS"] = gA[c]["pass"]["IS"]; k["2_OOS"] = gA[c]["pass"]["OOS"]
    k["3_folds"] = sum(fold_pass[c]) >= 3
    k["4_neighbors"] = all(nb[c][x]["passIS"] and nb[c][x]["passOOS"] for x in nb[c])
    k["5_cost2x_fill2"] = st[c]["cost2x"]["passIS"] and st[c]["cost2x"]["passOOS"] and st[c]["fill2"]["passIS"] and st[c]["fill2"]["passOOS"]
    k["6_dsr_gt_v0"] = bool(sr_ann_hair(c) > R["dsr"]["sr_v0_ann"])
    k["7_envB_IS_OOS"] = gB_pass = bool(R["grid_B"][c]["pass"]["IS"] and R["grid_B"][c]["pass"]["OOS"])
    k["HELPS"] = all(k.values())
    crit[c] = k
R["criteria_A"] = crit
nIS = sum(gA[c]["pass"]["IS"] for c in IDS); nOOS = sum(gA[c]["pass"]["OOS"] for c in IDS)
lowboth = sum((gA[c]["IS"]["calmar_i"] < gA["V0"]["IS"]["calmar_i"]) and (gA[c]["OOS"]["calmar_i"] < gA["V0"]["OOS"]["calmar_i"]) for c in IDS)
Rpass = gA[REP]["pass"]
hurts = (gA[REP]["IS"]["calmar_i"] <= gA["V0"]["IS"]["calmar_i"]) and (gA[REP]["OOS"]["calmar_i"] <= gA["V0"]["OOS"]["calmar_i"]) and lowboth >= 0.7 * 12
R["verdict"] = dict(rep=REP, helps=crit[REP]["HELPS"], hurts=bool(hurts), label="helps" if crit[REP]["HELPS"] else ("hurts" if hurts else "noise"),
                    n_cfg_pass_IS=int(nIS), n_cfg_pass_OOS=int(nOOS), n_cfg_calmar_lower_both=int(lowboth), n_cfg_helps=int(sum(crit[c]["HELPS"] for c in IDS)))
# OOS/IS drawdown + CAGR tradeoff summary
R["tradeoff_A"] = {c: dict(d_imdd_IS=gA[c]["IS"]["imdd"] - gA["V0"]["IS"]["imdd"], d_imdd_OOS=gA[c]["OOS"]["imdd"] - gA["V0"]["OOS"]["imdd"],
                           rel_cagr_IS=gA[c]["IS"]["cagr"] / gA["V0"]["IS"]["cagr"] - 1, rel_cagr_OOS=gA[c]["OOS"]["cagr"] / gA["V0"]["OOS"]["cagr"] - 1) for c in IDS}
# phase synchronisation / independence evidence
R["phase_sync_A"] = {w: [window_metrics(r, *WINS[w])["cagr"] for r in runs("A")] for w in ("IS", "OOS")}
R["phase_sync_A_T09"] = {w: [window_metrics(r, *WINS[w])["cagr"] for r in runs("A", "T09")] for w in ("IS", "OOS")}
# EXPLORATORY (excluded from conclusions): plain de-leveraging of V0
expl = {}
for lv in (2.0, 2.5, 3.0, 4.0):
    for dp in (0.95,):
        kw = dict(ENVS["A"]); kw["lev"] = lv; kw["deploy"] = dp
        rl = [S.run(phase=ph, **kw) for ph in range(3)]
        expl[f"V0 lev{lv} dep{dp}"] = {w: win(rl, *WINS[w]) for w in ("IS", "OOS", "full")}
R["EXPLORATORY_deleverage_v0"] = expl

R["elapsed_s"] = time.time() - t0
json.dump(R, open(os.path.join(OUT, "results.json"), "w"), default=float, indent=1)
print("done", R["elapsed_s"], "REP", REP)
