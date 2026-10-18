"""Audit driver. Usage: python rs_audit_run.py > out.txt   (local cache only, no network)."""
import sys
import numpy as np
import pandas as pd
import rs_audit_engine as E

rng = np.random.default_rng(20261011)
P = E.load_panel()
D = E.derive(P)
s0 = E.s0_index(P)
T, N = D["R"].shape
dates_ret = P["dates"][s0 + 1:]
print(f"panel days={T} syms={N} first={P['dates'][0].date()} last={P['dates'][-1].date()} s0={P['dates'][s0].date()} "
      f"ret_days={T-1-s0} ({dates_ret[0].date()}..{dates_ret[-1].date()})")

CFGS = {"a": dict(K=8, every=3, band=0), "b": dict(K=12, every=2, band=0), "c": dict(K=8, every=3, band=2)}
COST = 0.001


def fmt(m):
    return f"CAGR {m['cagr']*100:6.1f}% MDD {m['mdd']*100:6.1f}% Sh {m['sharpe']:4.2f} worst {m['worst']*100:5.1f}%"


def run_cfg(name, model, cost=COST, funding=True, D_=None, P_=None, s0_=None, volt=False):
    D_ = D_ or D; P_ = P_ or P; s0_ = s0 if s0_ is None else s0_
    c = CFGS[name]
    outs = []
    for o in range(c["every"]):
        kw = dict(K=c["K"], every=c["every"], off=o, band=c["band"], model=model, cost=cost, funding=funding)
        if volt:
            base = E.simulate(D_, P_, s0_, **kw)["rets"]
            kw["scale_fn"] = E.vol_scale_fn(base, s0=s0_)
        outs.append(E.simulate(D_, P_, s0_, **kw))
    return outs


def summarize(outs):
    ms = [E.metrics(o["rets"]) for o in outs]
    stag = E.metrics(np.mean([o["rets"] for o in outs], axis=0))
    return ms, stag


def row(label, outs):
    ms, stag = summarize(outs)
    offs = " ".join(f"{m['cagr']*100:5.1f}" for m in ms)
    mean = {k: np.mean([m[k] for m in ms]) for k in ms[0]}
    print(f"{label:22s} offs[{offs}] mean: {fmt(mean)} | stag: {fmt(stag)} | "
          f"trades/yr {np.mean([o['trades_yr'] for o in outs]):5.0f} turn/yr {np.mean([o['turnover_yr'] for o in outs]):5.1f} "
          f"fee/yr {np.mean([o['fee_yr'] for o in outs])*100:4.1f}% fund/yr {np.mean([o['fund_yr'] for o in outs])*100:5.2f}%")
    return ms, stag


print("\n=== 1. REPRODUCTION (cost 0.10%/side, funding on, 45 syms) ===")
store = {}
for model in ("cw", "qk"):
    for name in ("a", "b", "c"):
        store[(name, model)] = run_cfg(name, model)
        row(f"{name}-{model}", store[(name, model)])
    store[("d", model)] = run_cfg("a", model, volt=True)
    row(f"d(volt a)-{model}", store[("d", model)])

print("\n=== 1b. GAP DECOMPOSITION for (a), offset-mean / staggered CAGR / MDD ===")
for model in ("cw", "qk"):
    for cost, fu in [(0.0004, False), (0.0004, True), (0.0007, True), (0.001, True), (0.0, False)]:
        outs = run_cfg("a", model, cost=cost, funding=fu)
        ms, st = summarize(outs)
        print(f"{model} cost {cost*100:.2f}% fund {fu!s:5}: offs {[round(m['cagr']*100,1) for m in ms]} "
              f"mean CAGR {np.mean([m['cagr'] for m in ms])*100:5.1f}% MDD {np.mean([m['mdd'] for m in ms])*100:5.1f}% | stag {st['cagr']*100:5.1f}% / {st['mdd']*100:5.1f}%")
# funding timing sensitivity
P_sh = E.load_panel(fund_shift_ms=3600_000)
for model in ("cw", "qk"):
    o = [E.simulate(D, P_sh, s0, K=8, every=3, off=k, model=model, cost=COST) for k in range(3)]
    print(f"funding booked to previous day (shift 1h) {model}: fund/yr {np.mean([x['fund_yr'] for x in o])*100:.2f}% stag CAGR "
          f"{E.metrics(np.mean([x['rets'] for x in o],0))['cagr']*100:.1f}%")
# gross exposure for qk
o = E.simulate(D, P, s0, K=8, every=3, off=0, model="qk", cost=COST, full_out=True)
C_ = D["R"]
gross = np.abs(o["W"]).sum(1)
net = o["W"].sum(1)
eqs = np.cumprod(1 + o["rets"])
eq_prev = np.concatenate([[1.0], eqs[:-1]])
print(f"qk (a) off0: mean gross/equity {np.mean(gross/eqs):.2f} p5 {np.percentile(gross/eqs,5):.2f} p95 {np.percentile(gross/eqs,95):.2f} max {np.max(gross/eqs):.2f}; "
      f"mean net/equity {np.mean(net/eqs):+.3f}")
# year-by-year (a) staggered
for model in ("cw", "qk"):
    st = np.mean([x["rets"] for x in store[("a", model)]], 0)
    yrs = pd.Series(st, index=dates_ret).groupby(dates_ret.year).apply(lambda s: (1 + s).prod() - 1)
    print(f"(a) {model} stag by year:", {int(k): round(v * 100, 1) for k, v in yrs.items()})
    h = len(st) // 2
    print(f"   first half {fmt(E.metrics(st[:h]))} | second half {fmt(E.metrics(st[h:]))}")

print("\n=== 2. LOOK-AHEAD AUDIT ===")
fund_off = []
for b in P["bases"]:
    f = pd.read_csv(f"{E.CACHE}/funding/{b}USDT.csv.gz", header=None)
    fund_off.append(((f[0] % (8 * 3600_000)).max(), f[1].nunique(), sorted(f[1].unique())))
print("funding calc_time offset past 8h grid: max ms =", max(x[0] for x in fund_off), "; interval_h values:",
      sorted(set(v for x in fund_off for v in x[2])))
cuts = [s0 + 200, s0 + 600, s0 + 1000, s0 + 1400]
for model, band in [("cw", 0), ("qk", 0), ("qk", 2)]:
    ok = True
    for c in cuts:
        cutms = int(P["idx"][c + 1]) * E.DAY  # everything from day c+1 00:00 on is perturbed
        def kh(b, k, cutms=cutms):
            k = k.copy(); m = k["t"] >= cutms
            k.loc[m, "c"] *= rng.lognormal(0, 0.3, m.sum()); k.loc[m, "qv"] *= rng.lognormal(0, 1, m.sum())
            return k
        def fh(b, f, cutms=cutms):
            f = f.copy(); m = f["t"] >= cutms; f.loc[m, "r"] = rng.normal(0, 0.001, m.sum()); return f
        P2 = E.load_panel(kline_hook=kh, fund_hook=fh)
        D2 = E.derive(P2)
        base = E.simulate(D, P, s0, K=8, every=3, off=0, band=band, model=model, cost=COST, full_out=True)
        pert = E.simulate(D2, P2, s0, K=8, every=3, off=0, band=band, model=model, cost=COST, full_out=True)
        n = c - s0
        d_r = np.abs(base["rets"][:n] - pert["rets"][:n]).max()
        d_w = np.abs(base["W"][:n] - pert["W"][:n]).max()
        d_after = np.abs(base["rets"][n:] - pert["rets"][n:]).max()
        ok &= (d_r < 1e-12 and d_w < 1e-12)
        print(f"  {model} band{band} cut {P['dates'][c].date()}: max|d ret| before cut {d_r:.1e}, max|d W| {d_w:.1e}; after cut {d_after:.3f}")
    print(f"  => {model} band{band} no look-ahead: {ok}")
# listing-history check on selected names
o = E.simulate(D, P, s0, K=8, every=3, off=0, model="cw", cost=COST, full_out=True)
viol = 0; minhist = 10**9
hist = np.arange(T)[:, None] - D["first"][None, :] + 1
for k in range(0, len(o["W"]), 3):
    i = s0 + k
    # W holds the target after day i+1's (unchanged for cw) -> names selected on day i
    sel = np.where(o["W"][k] != 0)[0]
    viol += int((~D["elig"][i, sel]).sum()); minhist = min(minhist, hist[i, sel].min() if len(sel) else 10**9)
print(f"  selected names failing eligibility at rebalance: {viol}; min listing history among selected: {minhist} days")

print("\n=== 3. UNIVERSE / SURVIVORSHIP ===")
first_dates = {b: P["dates"][D["first"][j]].date() for j, b in enumerate(P["bases"])}
print("first-data date (cache begins 2021-06-01, so 2021-06-01 = left-truncated):")
print("  " + ", ".join(f"{b}:{d}" for b, d in sorted(first_dates.items(), key=lambda x: x[1])))
for y in range(2022, 2027):
    i = int(np.where(P["dates"] == pd.Timestamp(f"{y-1}-12-31"))[0][0])
    print(f"  names eligible (>=60d history) for signal at {y-1}-12-31: {int(D['elig'][i].sum())} of {N}")
el = D["elig"][s0:T - 1].sum(1)
print(f"  eligible count over backtest: min {el.min()} median {int(np.median(el))} max {el.max()}")

def sub_run(cols, label):
    Ds = dict(R=D["R"][:, cols], mom=D["mom"][:, cols], elig=D["elig"][:, cols], first=D["first"][cols])
    Ps = dict(P); Ps["fund"] = P["fund"][:, cols]
    for model in ("cw", "qk"):
        outs = [E.simulate(Ds, Ps, s0, K=8, every=3, off=o, model=model, cost=COST) for o in range(3)]
        ms = [E.metrics(x["rets"]) for x in outs]; st = E.metrics(np.mean([x["rets"] for x in outs], 0))
        print(f"  {label:34s} {model}: offs {[round(m['cagr']*100,1) for m in ms]} mean {np.mean([m['cagr'] for m in ms])*100:5.1f}% "
              f"MDD {np.mean([m['mdd'] for m in ms])*100:5.1f}% Sh {np.mean([m['sharpe'] for m in ms]):.2f} | stag {st['cagr']*100:5.1f}%/{st['mdd']*100:5.1f}%")

allc = np.arange(N)
sub_run(allc, "full 45")
pre = np.array([j for j in range(N) if P["dates"][D["first"][j]] < pd.Timestamp("2022-01-01")])
sub_run(pre, f"listed before 2022 ({len(pre)} names)")
# trailing-quote-volume PIT universe
def topn_run(topn, win=30):
    qv = pd.DataFrame(P["qv"]).rolling(win, min_periods=win // 2).sum().values
    el2 = D["elig"].copy()
    for i in range(T):
        ids = np.where(D["elig"][i])[0]
        if len(ids) > topn:
            keep = ids[np.argsort(-np.nan_to_num(qv[i, ids]), kind="stable")[:topn]]
            m = np.zeros(N, bool); m[keep] = True; el2[i] = m
    Dn = dict(D); Dn["elig"] = el2
    for model in ("cw", "qk"):
        outs = [E.simulate(Dn, P, s0, K=8, every=3, off=o, model=model, cost=COST) for o in range(3)]
        ms = [E.metrics(x["rets"]) for x in outs]; st = E.metrics(np.mean([x["rets"] for x in outs], 0))
        print(f"  PIT top-{topn} by trailing {win}d quote vol {model}: offs {[round(m['cagr']*100,1) for m in ms]} mean "
              f"{np.mean([m['cagr'] for m in ms])*100:5.1f}% MDD {np.mean([m['mdd'] for m in ms])*100:5.1f}% | stag {st['cagr']*100:5.1f}%/{st['mdd']*100:5.1f}%")
for tn in (20, 30):
    topn_run(tn)
# ex-post best 5
bh = np.nan_to_num(np.nanprod(1 + D["R"][s0 + 1:], axis=0) - 1)
best_bh = np.argsort(-bh)[:5]
print("  ex-post best 5 by buy&hold:", [P["bases"][j] for j in best_bh], [round(bh[j], 1) for j in best_bh])
o = [E.simulate(D, P, s0, K=8, every=3, off=k, model="cw", cost=COST, full_out=True) for k in range(3)]
contrib = np.mean([(x["W"] * np.nan_to_num(D["R"][s0 + 1:])).sum(0) for x in o], axis=0)
best_ct = np.argsort(-contrib)[:5]
print("  ex-post best 5 by strategy P&L contribution (cw):", [P["bases"][j] for j in best_ct], [round(contrib[j], 2) for j in best_ct])
sub_run(np.array([j for j in allc if j not in best_bh]), "minus 5 best buy&hold")
sub_run(np.array([j for j in allc if j not in best_ct]), "minus 5 best strategy contributors")
worst_ct = np.argsort(contrib)[:5]
print("  (for reference) 5 worst contributors:", [P["bases"][j] for j in worst_ct], [round(contrib[j], 2) for j in worst_ct])

print("\n=== 4. MULTIPLE TESTING NULLS (cw model; 3-offset staggered mean series; cost 0.10%, funding on) ===")
def stag_cw(mom, elig, R, F, s0_, K=8, every=3):
    rs, tu = zip(*[E.fast_cw(mom, elig, R, F, s0_, K, every, o, COST) for o in range(every)])
    return np.mean(rs, 0), np.mean([t.mean() for t in tu])
base_ret, base_turn = stag_cw(D["mom"], D["elig"], D["R"], P["fund"], s0)
bm = E.metrics(base_ret)
print(f"baseline stag: {fmt(bm)} Calmar {bm['calmar']:.2f}; mean per-day turnover {base_turn:.3f}")
# Null A: persistent random scores, calibrated rho to match turnover
def null_scores(rho, g):
    Z = np.zeros((T, N)); z = g.standard_normal(N)
    eps = g.standard_normal((T, N))
    for t in range(T):
        z = rho * z + np.sqrt(1 - rho ** 2) * eps[t]
        Z[t] = z
    return Z
def mean_turn(rho, g):
    return stag_cw(null_scores(rho, g), D["elig"], D["R"], P["fund"], s0)[1]
lo, hi = 0.0, 0.999
g0 = np.random.default_rng(1)
# turnover is measured only on rebalance days via fast_cw diff (zero otherwise), compare consistently
for _ in range(14):
    mid = (lo + hi) / 2
    if mean_turn(mid, np.random.default_rng(1)) > base_turn: lo = mid
    else: hi = mid
rho = (lo + hi) / 2
print(f"calibrated AR(1) rho of random scores = {rho:.3f} (turnover {mean_turn(rho, np.random.default_rng(1)):.3f} vs {base_turn:.3f})")
nA = []
for d in range(500):
    g = np.random.default_rng(1000 + d)
    r, _ = stag_cw(null_scores(rho, g), D["elig"], D["R"], P["fund"], s0)
    m = E.metrics(r); nA.append((m["sharpe"], m["calmar"], m["cagr"], m["mdd"]))
nA = np.array(nA)
def pct(x, v): return (x < v).mean() * 100
print(f"Null A (random persistent scores, 500 draws): Sharpe mean {nA[:,0].mean():+.2f} sd {nA[:,0].std():.2f} p95 {np.percentile(nA[:,0],95):.2f} max {nA[:,0].max():.2f}; "
      f"Calmar mean {np.nanmean(nA[:,1]):+.2f} p95 {np.nanpercentile(nA[:,1],95):.2f} max {np.nanmax(nA[:,1]):.2f}; P(Calmar>2) {(nA[:,1]>2).mean():.3f}")
print(f"  baseline percentile in Null A: Sharpe {pct(nA[:,0], bm['sharpe']):.1f}  Calmar {pct(np.nan_to_num(nA[:,1],nan=-9), bm['calmar']):.1f}  CAGR {pct(nA[:,2], bm['cagr']):.1f}")
from math import sqrt
for ntr in (100, 1000, 7000):
    from statistics import NormalDist
    z = NormalDist().inv_cdf(1 - 1 / ntr)  # approx expected max z
    emax = nA[:,0].mean() + nA[:,0].std() * (z + 0.5772 / (z if z else 1) * 0.0 )
    print(f"  expected best Sharpe out of {ntr} independent null configs ~ {emax:.2f} (Gaussian fit; real configs are highly correlated so effective N is far smaller)")
# Null B: time-permuted joint returns, names present at cache start (full histories)
full = np.array([j for j in range(N) if D["first"][j] == 0])
Rf = np.nan_to_num(D["R"][:, full]); Ff = P["fund"][:, full]
nB = []; nBq = []
for d in range(500):
    g = np.random.default_rng(5000 + d)
    perm = np.concatenate([[0], 1 + g.permutation(T - 1)])
    Rp = Rf[perm]; Rp[0] = np.nan
    Cp = np.cumprod(1 + np.nan_to_num(Rp), axis=0)
    mom = np.full_like(Cp, np.nan); mom[14:] = Cp[14:] / Cp[:-14] - 1
    el = np.zeros_like(Cp, bool); el[60:] = True; el &= ~np.isnan(mom)
    Dp = dict(R=Rp, mom=mom, elig=el, first=np.zeros(len(full), int)); Pp = dict(fund=Ff[perm])
    r = np.mean([E.simulate(Dp, Pp, s0, K=8, every=3, off=o, model="cw", cost=COST)["rets"] for o in range(3)], 0)
    m = E.metrics(r); row_ = [m["sharpe"], m["calmar"], m["cagr"]]
    if d < 200:
        rq = np.mean([E.simulate(Dp, Pp, s0, K=8, every=3, off=o, model="qk", cost=COST)["rets"] for o in range(3)], 0)
        mq = E.metrics(rq); row_ += [mq["sharpe"], mq["calmar"], mq["cagr"]]
    nB.append(row_)
cw_b = np.array([x[:3] for x in nB]); qk_b = np.array([x[3:] for x in nB if len(x) > 3])
Dsub = dict(R=D["R"][:, full], mom=D["mom"][:, full], elig=D["elig"][:, full], first=D["first"][full]); Psub = dict(fund=P["fund"][:, full])
bsub = {}
for model in ("cw", "qk"):
    bsub[model] = E.metrics(np.mean([E.simulate(Dsub, Psub, s0, K=8, every=3, off=o, model=model, cost=COST)["rets"] for o in range(3)], 0))
print(f"Null B (days permuted jointly, {len(full)} full-history names): cw Sharpe mean {cw_b[:,0].mean():+.2f} sd {cw_b[:,0].std():.2f} p95 {np.percentile(cw_b[:,0],95):.2f} max {cw_b[:,0].max():.2f}; "
      f"CAGR mean {cw_b[:,2].mean()*100:+.1f}%; P(Calmar>2) {(cw_b[:,1]>2).mean():.3f}")
print(f"   qk (200 draws): Sharpe mean {qk_b[:,0].mean():+.2f} sd {qk_b[:,0].std():.2f} p95 {np.percentile(qk_b[:,0],95):.2f} max {qk_b[:,0].max():.2f}; CAGR mean {qk_b[:,2].mean()*100:+.1f}%")
print(f"   same-universe real baseline: cw {fmt(bsub['cw'])} Calmar {bsub['cw']['calmar']:.2f} -> pctile Sharpe {pct(cw_b[:,0], bsub['cw']['sharpe']):.1f}, Calmar {pct(cw_b[:,1], bsub['cw']['calmar']):.1f}")
print(f"                              qk {fmt(bsub['qk'])} Calmar {bsub['qk']['calmar']:.2f} -> pctile Sharpe {pct(qk_b[:,0], bsub['qk']['sharpe']):.1f}, Calmar {pct(qk_b[:,1], bsub['qk']['calmar']):.1f}")
print("   (Null B permutes time so momentum/reversal autocorrelation is destroyed but cross-section, vol, funding kept.)")

print("\n=== 5. BLOCK BOOTSTRAP (circular, block 10d, 2000 draws) ===")
def boot(r, B=2000, blk=10, seed=7):
    g = np.random.default_rng(seed); n = len(r); nb = int(np.ceil(n / blk))
    out = np.empty((B, 2))
    for b in range(B):
        st = g.integers(0, n, nb)
        ix = ((st[:, None] + np.arange(blk)[None, :]) % n).ravel()[:n]
        m = E.metrics(r[ix]); out[b] = (m["cagr"], m["sharpe"])
    return out
for name in ("a", "c", "d"):
    for model in ("cw", "qk"):
        outs = store[(name, model)]
        for lab, r in (("stag", np.mean([x["rets"] for x in outs], 0)), ("off0", outs[0]["rets"])):
            bsr = boot(r); m = E.metrics(r)
            lo_c, hi_c = np.percentile(bsr[:, 0], [2.5, 97.5]); lo_s, hi_s = np.percentile(bsr[:, 1], [2.5, 97.5])
            yrs = len(r) / 365
            se = np.sqrt((1 + 0.5 * m['sharpe'] ** 2) / yrs)
            print(f"({name}) {model} {lab}: CAGR {m['cagr']*100:5.1f}% [{lo_c*100:5.1f},{hi_c*100:5.1f}] Sharpe {m['sharpe']:.2f} [{lo_s:.2f},{hi_s:.2f}] "
                  f"P(Sh>0.5) {(bsr[:,1]>0.5).mean():.3f} P(Sh>0) {(bsr[:,1]>0).mean():.3f} P(CAGR>0) {(bsr[:,0]>0).mean():.3f}; analytic SE(Sh)={se:.2f}")
