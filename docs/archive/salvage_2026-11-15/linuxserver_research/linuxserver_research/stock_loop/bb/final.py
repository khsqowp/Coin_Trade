import json, numpy as np
R = json.load(open("results.json")); D = R["dev"]; T = R["test"]
print("coverage", json.dumps(R["coverage"]))
def cells(x): return x["cells"]
def key(c): return (c["dataset"], c["k"], c["exit"], c["stop"], c["fill"], c["filter"])
dev = {key(c["cell"]): c["stats"] for c in cells(D)}; tst = {key(c["cell"]): c["stats"] for c in cells(T)}
f = lambda x: "na" if x is None else f"{x*100:.3f}"
for ds in ["us", "kr", "tick5", "tick1"]:
    bl = T["baselines"].get(ds, {}) if "baselines" in T else {}
    dbl = D["baselines"].get(ds, {})
    for tag in ["primary", "dev_best"]:
        c = dbl.get(tag, {}).get("cell")
        if not c: continue
        k = key(c); s = tst.get(k) or {}; d = dev.get(k) or {}
        print(f"{ds} {tag} cell k{c['k']} {c['exit']} s{c['stop']} {c['fill']} | DEV n={d.get('n')} gross={f(d.get('gross_mean'))} net={f(d.get('net_mean'))} t={d.get('cluster_t'):.2f} | TEST n={s.get('n')} gross={f(s.get('gross_mean'))} net={f(s.get('net_mean'))} t={s.get('cluster_t') and round(s['cluster_t'],2)} win={s.get('win_rate') and round(s['win_rate'],3)} netA={f(s.get('net_A_mean'))} net2x={f(s.get('net_2x_mean'))} BE={f(s.get('break_even_rt_cost'))} cost={f(s.get('avg_cost'))} worst={f(s.get('worst_trade'))}")
        print("   DEV base", json.dumps(dbl[tag]["baselines"]).replace('"draws": 1000, ', ''))
        print("   TEST base", json.dumps(bl.get(tag, {}).get("baselines")).replace('"draws": 1000, ', ''))
# pooled per dataset/fill/filter: mean gross, mean net, number of cells with net>0 (test), dev too
for ph, dd in [("DEV", dev), ("TEST", tst)]:
    print(ph, "pooled over 8 grid cells (trade-weighted):")
    for ds in ["us", "kr", "tick5", "tick1"]:
        for fill in ["base", "opt"]:
            for flt in ["A0", "A1", "A2"]:
                ss = [v for k, v in dd.items() if k[0] == ds and k[4] == fill and k[5] == flt and v.get("n")]
                if not ss: continue
                n = sum(v["n"] for v in ss); g = sum(v["n"] * v["gross_mean"] for v in ss) / n; nt = sum(v["n"] * v["net_mean"] for v in ss) / n
                pos = sum(v["net_mean"] > 0 for v in ss)
                print(f"  {ds:5} {fill:4} {flt} cells={len(ss)} n_tot={n:5d} gross={g*100:6.3f} net={nt*100:6.3f} cells_net>0={pos}  maxnet={max(v['net_mean'] for v in ss)*100:6.3f}")
