import json, sys
from pathlib import Path
KR = Path(sys.argv[1] if len(sys.argv) > 1 else ".")
d = json.load(open(KR / "results_main.json"))
R = d["results"]
print("pick", d["is_pick"]); print("coverage", json.dumps(d["coverage"]))
f = "{:<22}" + "{:>8}" * 15
print(f.format("name", "IS_SR", "IS_ret", "IS_MDD", "OOS_SR", "OOSret", "OOSMDD", "F_SR", "F_CAGR", "F_MDD", "dsr17", "dsr233", "RT", "win", "cost", "top10"))
for k, v in R.items():
    I, O, F = v["IS"], v["OOS"], v["FULL"]
    g = lambda x, k2: x.get(k2, "")
    print(f.format(k[:22], g(I, "sharpe"), g(I, "total_return"), g(I, "mdd"), g(O, "sharpe"), round(g(O, "total_return"), 2) if O else "", g(O, "mdd"),
                   g(F, "sharpe"), g(F, "cagr"), g(F, "mdd"), g(F, "dsr_N17"), g(F, "dsr_N233"), str(v.get("round_trips", "")), str(v.get("win_rate", "")),
                   str(v.get("cost_drag_per_yr", "")), str(v.get("top10_pnl_share", ""))))
print("sr0 FULL N17/N233/N1000:", R["V1_XS_MOM12_1"]["FULL"]["sr0_N17"], R["V1_XS_MOM12_1"]["FULL"]["sr0_N233"], R["V1_XS_MOM12_1"]["FULL"]["sr0_N1000"])
for k, v in R.items():
    print(k, "PRE2018", v["PRE2018"].get("sharpe"), "POST2018", v["POST2018"].get("sharpe"), "| OOS exc vs B1", v.get("oos_excess_vs_B1_ci90_ann"),
          "vs B4", v.get("oos_excess_vs_B4_ci90_ann"), "| part100M p95/max", v.get("participation_100M_p95"), v.get("participation_100M_max"),
          "| time_in_mkt", v["FULL"].get("time_in_market"))
for k, v in R.items():
    if "regime_types" not in v:
        continue
    t = v["regime_types"]
    print("TYPES %-22s" % k, " ".join("%s SR %+.2f/%+.2f ret %+.2f/%+.2f" % (x, t[x]["strat"]["sharpe"], t[x]["B1"]["sharpe"], t[x]["strat"]["total_return"], t[x]["B1"]["total_return"]) for x in t))
for k, v in R.items():
    if "regimes" not in v:
        continue
    print("REG", k[:22], " | ".join("%s %+.3f" % (w["label"][:14], w["strat"]["total_return"]) for w in v["regimes"]))
print("REG B1", " | ".join("%s %+.3f" % (w["label"][:14], w["B1"]["total_return"]) for w in R["V1_XS_MOM12_1"]["regimes"]))
for k in R:
    print("TOP10", k, R[k].get("top10_names"))
