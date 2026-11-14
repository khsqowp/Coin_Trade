import json, sys
ph = sys.argv[1]
d = json.load(open(f"results_{ph}.json"))
print("trials", d["trial_count"])
f = lambda x: "  na" if x is None else f"{x*100:6.3f}"
for c in d["cells"]:
    k = c["cell"]; s = c["stats"]
    if k["filter"] != "A0" and not (k["k"] == 2.0 and k["exit"] == "upper" and k["stop"] == 0.01):
        continue
    if s.get("n", 0) == 0:
        print(k, "n=0"); continue
    print(f'{k["dataset"]:5} k{k["k"]} {k["exit"][:3]} s{k["stop"]*100:.1f} {k["fill"]:4} {k["filter"]} n={s["n"]:4d} gross={f(s["gross_mean"])} net={f(s["net_mean"])} t={s["cluster_t"]:5.2f} win={s["win_rate"]:.2f} cost={f(s["avg_cost"])} netA={f(s["net_A_mean"])} net2x={f(s["net_2x_mean"])} h1={f(s.get("h1_net_mean"))} h2={f(s.get("h2_net_mean"))} hold={s["avg_hold_bars"]:.1f}')
print(json.dumps(d.get("baselines"))[:3500])
