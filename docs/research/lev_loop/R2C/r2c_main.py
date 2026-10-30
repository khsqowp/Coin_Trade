"""R2C MAIN RESULTS (run only after prereg.md + power.out are hashed). Deterministic (fixed seeds)."""
import os, sys, json, time
sys.path.insert(0, "/Users/user/Desktop/CODE/Ochestration/trading"); sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import numpy as np, pandas as pd
from app import rs_lev_r2c_lib as LIB, rs_lev_r2c_engine as E
import r2c_samples as RS
HERE = os.path.dirname(os.path.abspath(__file__))
cs = LIB.combos(); idx = {c: i for i, c in enumerate(cs)}
CAND = [(lev, k) for lev in (3.5, 4.0, 5.0) for k in LIB.KILLS if (lev, k) != LIB.BASE]
LAMB = (0.15, 0.3)
def col(lev, k, lam): return idx[(lev, k, None)] if k is None else idx[(lev, k, lam)]
def P(*a): print(*a, flush=True)
RES = {}; ARR = {}

def full_table(name, full):
    O = full["O"]; g = full["g"]
    uq = LIB.unique_traj(O); ep = LIB.kill_epochs(full["KD"])
    P(f"\n--- {name} FULL-SAMPLE continuous runs (R={O.shape[1]} jittered reps; g = annualised ln W, mean over reps (sd across reps)); CAGR=exp(g)-1")
    P("lev  kill  lam |   g_mean (sd)    CAGR  | uniq/R  kill-epochs  kills/path | maxgross/eq | ruin reps | reps with liquidation f.5(T/F3) f.75(T/F3) f1(T/F3)   minbuf f.75(T,F3)")
    for c, (lev, k, lam) in enumerate(cs):
        gm, gs = g[c].mean(), g[c].std()
        br = [int((O[c, :, E.O_C0 + m] > 0).sum()) for m in range(6)]
        mb = O[c, :, E.O_B0 + 2].min(), O[c, :, E.O_B0 + 3].min()
        P(f"{lev:3.1f} {('none' if k is None else format(k,'.2f')):>5} {('-' if lam is None else format(lam,'.2f')):>4} | {gm:+.3f} ({gs:.3f}) {np.expm1(gm):+7.1%} | {uq[c]:2d}/{O.shape[1]}  {ep[c]:4d}  {O[c,:,E.O_KILLS].mean():6.1f} | {O[c,:,E.O_MAXGR].max():5.2f} | {int((O[c,:,E.O_RUIN]>0).sum()):3d} | {br[0]}/{br[1]}  {br[2]}/{br[3]}  {br[4]}/{br[5]}   {mb[0]:+.2f},{mb[1]:+.2f}")
    return uq, ep

def cand_tables(name, G, wins, pre="", verbose=True):
    """per candidate x lambda: bootstrap / t CI of window-level paired diff, pos fraction, MDE"""
    nw = len(wins); out = {}
    if verbose:
        P(f"\n--- {name}{pre}: paired window contrasts vs base (4.0,.35) same lambda; n_windows={nw}; d = mean annualised ln W diff")
        P("cand(lev,kill)  lam |  mean     boot95CI            t95CI        | pos/nontied  | SE    MDE_t  delta | Holm-adj p")
    for lam in LAMB:
        fam = []
        for cnd in CAND:
            d = G[:, col(*cnd, lam)] - G[:, col(4.0, 0.35, lam)]
            bs = LIB.boot_stats(d, seed=11); ts = LIB.t_stats(d); pf, nt = LIB.pos_fraction(d)
            out[(cnd, lam)] = dict(boot=bs, t=ts, pf=pf, nt=nt, d=d.tolist()); fam.append(bs["p_le0"])
        hp = LIB.holm(fam)
        for cnd, h in zip(CAND, hp): out[(cnd, lam)]["holm"] = h
        if verbose:
            for cnd in CAND:
                o = out[(cnd, lam)]
                P(f"({cnd[0]},{('none' if cnd[1] is None else cnd[1])})  {lam:4.2f} | {o['boot']['mean']:+.3f} [{o['boot']['lo']:+.3f},{o['boot']['hi']:+.3f}] [{o['t']['lo']:+.3f},{o['t']['hi']:+.3f}] | {('nan' if np.isnan(o['pf']) else format(o['pf'],'.2f'))}/{o['nt']} | {o['t']['se']:.3f} {o['t']['mde']:.3f} {LIB.delta_for(cnd):.2f} | {o['holm']:.3f}")
    return out

def run_sample(name, S, seed):
    t0 = time.time(); st = LIB.first_active_day(S)
    P(f"\n==================== {name}: first active {S.P['days'][st].date()} .. {S.P['days'][S.b-1].date()} ({(S.b-st)/365:.2f}y), cols {S.n}")
    G, U, wins, KL = LIB.window_matrix(S, 24, seed)
    full = LIB.full_runs(S, 48, seed + 4)
    uq, ep = full_table(name, full)
    P(f"--- {name} window-level mean annualised ln W per combo (n_win={len(wins)}; unique finals/24 averaged over windows)")
    for c, (lev, k, lam) in enumerate(cs):
        P(f"{lev:3.1f} {('none' if k is None else format(k,'.2f')):>5} {('-' if lam is None else format(lam,'.2f')):>4} | G {G[:,c].mean():+.3f}  win-sd {G[:,c].std(ddof=1):.3f} | uniq {U[:,c].mean():4.1f}/24 | kills/win {KL[:,c].mean():.2f}")
    ct = cand_tables(name, G, wins)
    ARR[name] = dict(G=G, U=U, KL=KL, wins=np.array(wins), g=full["g"], O=full["O"])
    P(f"[{name} done {time.time()-t0:.0f}s]")
    return dict(S=S, G=G, wins=wins, full=full, ct=ct, uq=uq, ep=ep)

def hazard():
    d = pd.read_csv(os.path.join(HERE, "data/daily_1d.csv.gz"), parse_dates=["date"]); last = d.groupby("sym").date.max()
    m = pd.read_csv(os.path.join(HERE, "data/pit_membership.csv.gz"))
    members = set(m.sym); dead = [s for s in members if last[s] < pd.Timestamp("2026-08-31")]
    return len(dead) / (len(m) / 12.0), len(dead), len(members), len(m) / 12.0

def main():
    os.environ.setdefault("PYTHONHASHSEED", "0")
    R_ = {}
    R_["OLD"] = run_sample("OLD", RS.old(), 20261101)
    R_["NEW"] = run_sample("NEW", RS.new(), 20261102)
    R_["OLDPIT"] = run_sample("OLDPIT", RS.old_pit(), 20261103)
    # ---- IS / OOS split of OLD windows
    S = R_["OLD"]["S"]; oos0 = S.P["days"].searchsorted(pd.Timestamp("2024-07-01", tz="UTC"))
    isw = [i for i, (a, b) in enumerate(R_["OLD"]["wins"]) if a < oos0]; osw = [i for i, (a, b) in enumerate(R_["OLD"]["wins"]) if a >= oos0]
    G = R_["OLD"]["G"]; P(f"\n--- OLD IS ({len(isw)} windows) vs OOS ({len(osw)} windows): boot95 lower/upper of paired diff")
    split = {}
    for lam in LAMB:
        for cnd in CAND:
            r = []
            for nm, ws in (("IS", isw), ("OOS", osw)):
                d = G[ws][:, col(*cnd, lam)] - G[ws][:, col(4.0, 0.35, lam)]; b = LIB.boot_stats(d, seed=13); r.append(b)
            split[(cnd, lam)] = r
            P(f"({cnd[0]},{('none' if cnd[1] is None else cnd[1])}) lam {lam:4.2f} | IS {r[0]['mean']:+.3f} [{r[0]['lo']:+.3f},{r[0]['hi']:+.3f}] | OOS {r[1]['mean']:+.3f} [{r[1]['lo']:+.3f},{r[1]['hi']:+.3f}]")
    # ---- stress on OLD
    So = R_["OLD"]["S"]; full0 = R_["OLD"]["full"]; n = So.n
    ps = full0["PS"][idx[(4.0, 0.35, 0.15)]].mean(axis=0); win5 = list(np.argsort(-ps)[:5])
    P(f"\n--- STRESS S1 top-5 contributors removed (baseline l.15 PnL-attribution, mean over reps): {[So.P['names'][j] for j in win5]}; shares of total {[round(float(ps[j]/ps.sum()),2) for j in win5]}")
    cm = np.ones(n, np.uint8); cm[win5] = 0
    s1 = LIB.full_runs(So, 24, 20261110, colmask=cm)
    uq1, ep1 = full_table("OLD-S1(no top5)", s1)
    # S2 subsets
    rng = np.random.default_rng(20261120); halves = []; blocks = []
    for _ in range(6):
        pm = rng.permutation(n); halves += [pm[:22], pm[22:44]]
    for _ in range(4):
        pm = rng.permutation(n); b = [pm[:15], pm[15:30], pm[30:45]]
        blocks += [np.concatenate([b[0], b[1]]), np.concatenate([b[0], b[2]]), np.concatenate([b[1], b[2]])]
    def subset_diffs(subs, tag):
        dd = {lam: {cnd: [] for cnd in CAND} for lam in LAMB}; gb = {lam: [] for lam in LAMB}
        for k, sub in enumerate(subs):
            cm = np.zeros(n, np.uint8); cm[sub] = 1
            f = LIB.full_runs(So, 8, 20261130, colmask=cm)
            for lam in LAMB:
                base = f["g"][col(4.0, 0.35, lam)]
                gb[lam].append(base.mean())
                for cnd in CAND: dd[lam][cnd].append(float((f["g"][col(*cnd, lam)] - base).mean()))
        return dd
    P("\n--- STRESS S2a symbol-disjoint halves (6 partitions x 2 x 22 symbols, R=8 each): positive fraction of candidate-minus-base mean diffs")
    dh = subset_diffs(halves, "halves")
    P("--- STRESS S2b 30-of-45 block unions (4 partitions x 3, pairwise overlap exactly 50% within partition)")
    db = subset_diffs(blocks, "blocks")
    for lam in LAMB:
        for cnd in CAND:
            a = np.array(dh[lam][cnd]); b = np.array(db[lam][cnd])
            P(f"({cnd[0]},{('none' if cnd[1] is None else cnd[1])}) lam {lam:4.2f} | halves: mean {a.mean():+.3f} pos {(a>1e-12).sum()}/{(np.abs(a)>1e-12).sum()} | blocks: mean {b.mean():+.3f} pos {(b>1e-12).sum()}/{(np.abs(b)>1e-12).sum()}")
    # S3 delisting stress
    h, nd_, nm_, sy = hazard(); yrs = (So.b - LIB.first_active_day(So)) / 365.0
    P(f"\n--- STRESS S3 delisting: empirical PIT delist hazard {h:.3f}/symbol-yr ({nd_} dead of {nm_} members, {sy:.0f} symbol-yrs); applied to OLD 45 syms, adverse gap long x0.1 / short x2.0, R=24")
    rg = np.random.default_rng(20261140); R3 = 24
    evd = -np.ones((R3, n), np.int64); st = LIB.first_active_day(So)
    for r in range(R3):
        hit = rg.random(n) < 1 - np.exp(-h * yrs)
        evd[r, hit] = rg.integers(st + 30, So.b - 1, size=hit.sum())
    s3 = LIB.full_runs(So, R3, 20261150, ev=(evd, np.full((R3, n), 0.1), np.full((R3, n), 2.0)))
    P(f"    mean delist events per path {float((evd>=0).sum(1).mean()):.1f}")
    uq3, ep3 = full_table("OLD-S3(delist stress)", s3)
    # ---- verdicts
    P("\n==================== VERDICTS (prereg section 5)")
    ver = {}
    rows = []
    for cnd in CAND:
        why = []; harm = False; mde_ok = True; liq_ok = True; ci_ok = True; cons_ok = True; hs_ok = True
        for nm in ("OLD", "NEW"):
            for lam in LAMB:
                o = R_[nm]["ct"][(cnd, lam)]
                if not (o["boot"]["lo"] > 0 and o["t"]["lo"] > 0): ci_ok = False
                if o["boot"]["hi"] < 0: harm = True
                if not (o["nt"] >= 5 and o["pf"] >= 0.70): cons_ok = False
                if not (o["t"]["mde"] <= LIB.delta_for(cnd)): mde_ok = False
            O = R_[nm]["full"]["O"]
            for lam in (0.0, 0.15, 0.3):
                c = col(*cnd, lam)
                if O[c, :, E.O_C0:E.O_C0 + 4].sum() > 0: liq_ok = False
        for lam in LAMB:
            a = np.array(dh[lam][cnd]); nt = (np.abs(a) > 1e-12).sum()
            if not (nt >= 5 and (a > 1e-12).sum() / max(nt, 1) >= 0.70): hs_ok = False
        allok = ci_ok and cons_ok and hs_ok and liq_ok and mde_ok
        if allok: v = "supported"
        elif not liq_ok: v = "unsupported(liquidation)"
        elif harm: v = "unsupported(harm)"
        elif not mde_ok: v = "uninformative"
        else: v = "unsupported(no benefit at adequate power)"
        holm_ok = all(R_[nm]["ct"][(cnd, lam)]["holm"] < 0.05 for nm in ("OLD", "NEW") for lam in LAMB)
        pit_sign = all(R_["OLDPIT"]["ct"][(cnd, lam)]["boot"]["mean"] > 0 for lam in LAMB)
        ver[cnd] = v
        P(f"cand ({cnd[0]},{('none' if cnd[1] is None else cnd[1])}){' [lower lev: owner-excluded]' if cnd[0] < 4 else ''}: {v} | CI {ci_ok} cons {cons_ok} halves {hs_ok} liq0 {liq_ok} MDE {mde_ok} | HolmOK {holm_ok} OLDPIT-sign+ {pit_sign}")
    json.dump({str(k): v for k, v in ver.items()}, open(os.path.join(HERE, "verdicts.json"), "w"), indent=1)
    np.savez_compressed(os.path.join(HERE, "results_arrays.npz"), **{f"{k}_{kk}": vv for k, v in ARR.items() for kk, vv in v.items()})
if __name__ == "__main__":
    main()
