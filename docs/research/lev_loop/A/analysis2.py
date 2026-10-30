"""Stage 2 inference: paired block bootstrap, verdicts, haircuts, DSR, concentration, cushions."""
from summ import *
from statistics import NormalDist
import json, math
ND = NormalDist()
B = 4000; BL = 15; SEED = 20261030
DFS = {w: load(w) for w in ("IS", "OOS", "FULL")}
ADM = {(w, km): admissible(DFS[w], km) for w in DFS for km in (0, 1, 3)}

def lr_series(df, cell, km):
    d = df[(df.cell == cell) & (df.kmode == km) & (df.scen == "BASE")].set_index(["off", "ph"])
    out = {}
    for k, row in d.iterrows():
        e = row["eq"].astype(np.float64)
        if row["ruin"] or len(e) == 0 or (e <= 0).any(): continue
        out[k] = np.diff(np.log(np.r_[1.0, e]))
    return out

def boot(df, cell, ref, km, rng):
    a = lr_series(df, cell, km); b = lr_series(df, ref, km)
    keys = [k for k in a if k in b and len(a[k]) == len(b[k])]
    if not keys: return None
    D = [a[k] - b[k] for k in keys]; n = len(D)
    ar = np.arange(BL)
    stats = np.empty(B)
    for i in range(B):
        p = rng.integers(n); d = D[p]; T = len(d)
        nb = int(np.ceil(T / BL))
        st = rng.integers(T, size=nb)
        idx = ((st[:, None] + ar) % T).ravel()[:T]
        stats[i] = 365.0 * d[idx].mean()
    pm = np.array([365.0 * d.mean() for d in D])   # per-path paired growth difference
    return dict(n=n, point=float(pm.mean()), lo=float(np.percentile(stats, 2.5)), hi=float(np.percentile(stats, 97.5)), se=float(stats.std()),
                path_p10=float(np.percentile(pm, 10)), path_p90=float(np.percentile(pm, 90)), win=float((pm > 0).mean()), n_excl=120 - n)

def verdict(km, cell, bt):
    i, o = bt["IS"], bt["OOS"]
    if i is None or o is None: return "n/a"
    adm_c = ADM[("IS", km)][CURRENT][0] and ADM[("OOS", km)][CURRENT][0]
    adm = ADM[("IS", km)][cell][0] and ADM[("OOS", km)][cell][0]
    if cell == CURRENT: return "REF"
    if i["lo"] > 0 and o["lo"] > 0 and adm: return "BETTER"
    if (i["hi"] < 0 and o["hi"] < 0): return "WORSE"
    if adm_c and not adm: return "WORSE-inadm"
    return "ND"

def emax(N):
    g = 0.5772156649
    return (1 - g) * ND.inv_cdf(1 - 1 / N) + g * ND.inv_cdf(1 - 1 / (N * math.e))

res = {"boot": {}, "verdict": {}}
for km in (3, 1, 0):
    for cell in CELLS:
        bt = {}
        for w in ("IS", "OOS", "FULL"):
            rng = np.random.default_rng(SEED + 1000 * km + hash((cell, w)) % 997)
            bt[w] = boot(DFS[w], cell, CURRENT, km, rng)
        res["boot"][f"{km}|{cell[0]}|{KNAME[cell[1]]}"] = bt
        res["verdict"][f"{km}|{cell[0]}|{KNAME[cell[1]]}"] = verdict(km, cell, bt)
# print verdict grid
for km in (3, 1, 0):
    print(f"\n#### kill_mode {km}: verdict vs CURRENT (4|0.35) ; point diff IS / OOS / FULL in annual log-growth [95% CI IS ; OOS]")
    for cell in CELLS:
        k = f"{km}|{cell[0]}|{KNAME[cell[1]]}"; bt = res["boot"][k]
        f = lambda w: ("%+.2f" % bt[w]["point"]) if bt[w] else "n/a"
        ci = lambda w: ("[%+.2f,%+.2f]" % (bt[w]["lo"], bt[w]["hi"])) if bt[w] else ""
        print(f"  {cell[0]:>3}|{KNAME[cell[1]]:>4}  {res['verdict'][k]:11s} IS {f('IS')} {ci('IS')}  OOS {f('OOS')} {ci('OOS')}  FULL {f('FULL')}  adm IS/OOS/FULL {ADM[('IS',km)][cell][0]}/{ADM[('OOS',km)][cell][0]}/{ADM[('FULL',km)][cell][0]}")
# region counts
print("\n#### region verdict counts (per lev row; per kill column)")
for km in (3, 1, 0):
    for l in LEVS:
        vs = [res["verdict"][f"{km}|{l}|{KNAME[k]}"] for k in KILLS]
        print(f"  mode{km} lev {l}: ", {v: vs.count(v) for v in set(vs)})
    for k in KILLS:
        vs = [res["verdict"][f"{km}|{l}|{KNAME[k]}"] for l in LEVS]
        print(f"  mode{km} kill {KNAME[k]}: ", {v: vs.count(v) for v in set(vs)})
# cushions under stress
print("\n#### min flat3 cushion over 120 paths (p10 in brackets), kill_mode 3, by scenario; FULL window")
for cell in CELLS:
    row = []
    for sc in ("BASE", "VOL", "COST", "COMB"):
        g = DFS["FULL"][(DFS["FULL"].cell == cell) & (DFS["FULL"].kmode == 3) & (DFS["FULL"].scen == sc)]
        row.append(f"{sc} {g.cush_flat.min():+.2f}({g.cush_flat.quantile(.1):+.2f}) liq {int(g.liq_flat.sum()):3d}")
    print(f"  {cell[0]:>3}|{KNAME[cell[1]]:>4} ", " | ".join(row))
# liquidation share by lev (aggregate across kills, FULL, mode 3)
# concentration
print("\n#### concentration (kill_mode 3 BASE): top5 symbols share of net gain / top5 trades share; median [p90] over paths with gain>0")
conc = {}
for w in ("IS", "OOS", "FULL"):
    for cell in (CURRENT, (4.0, 1.0), (5.0, 1.0), (5.0, 0.5), (3.0, 1.0)):
        g = DFS[w][(DFS[w].cell == cell) & (DFS[w].kmode == 3) & (DFS[w].scen == "BASE")]
        g = g[g.gain > 0]
        s5 = (g.top5_syms / g.gain); t5 = (g.top5_trades / g.gain)
        mw = g.iloc[(g.wend - g.wend.median()).abs().argsort().iloc[0]]
        conc[f"{w}|{cell}"] = dict(sym_med=float(s5.median()), sym_p90=float(s5.quantile(.9)), tr_med=float(t5.median()), tr_p90=float(t5.quantile(.9)), top_syms=mw["top_syms"], n=len(g))
        print(f"  {w:4s} {cell}: syms {s5.median():.2f} [{s5.quantile(.9):.2f}]  trades {t5.median():.2f} [{t5.quantile(.9):.2f}]  n={len(g)} median-path top syms {mw['top_syms']}")
res["conc"] = conc
# DSR / haircut for S3=(5,none)
S = (5.0, 1.0)
print("\n#### multiple-testing for S3 =", S)
for w in ("IS", "OOS"):
    bt = res["boot"][f"3|5.0|none"][w]
    for N in (24, 150):
        hc = bt["se"] * emax(N)
        print(f"  {w}: point diff vs current {bt['point']:+.3f}/yr, SE_boot {bt['se']:.3f}, E[max_{N}]={emax(N):.2f} -> haircut {hc:.3f} -> adj {bt['point']-hc:+.3f}")
    # DSR
    df = DFS[w]
    srs = {}
    for cell in CELLS:
        g = df[(df.cell == cell) & (df.kmode == 3) & (df.scen == "BASE")]
        r = np.array([np.diff(np.log(np.r_[1.0, e.astype(np.float64)])) for e in g['eq'] if (e > 0).all()], dtype=object)
        srs[cell] = np.mean([x.mean() / x.std() for x in r])
    V = np.var(list(srs.values()), ddof=1)
    g = df[(df.cell == S) & (df.kmode == 3) & (df.scen == "BASE")]
    e = g.iloc[(g.wend - g.wend.median()).abs().argsort().iloc[0]]["eq"].astype(np.float64)
    r = np.diff(np.log(np.r_[1.0, e])); r = np.exp(r) - 1
    T = len(r); sr = r.mean() / r.std(); sk = float(pd.Series(r).skew()); ku = float(pd.Series(r).kurt() + 3)
    for N in (24, 150):
        sr0 = math.sqrt(V) * emax(N)
        dsr = ND.cdf((sr - sr0) * math.sqrt(T - 1) / math.sqrt(1 - sk * sr + (ku - 1) / 4 * sr ** 2))
        print(f"  {w}: DSR(N={N}) = {dsr:.3f}  (daily SR {sr:.3f} ann {sr*math.sqrt(365):.2f}, SR0 {sr0:.3f} ann {sr0*math.sqrt(365):.2f}, skew {sk:.2f}, kurt {ku:.1f}, T {T})")
json.dump(res, open("analysis2.json", "w"), default=float, indent=1)
