import csv, json, sys
from collections import Counter
csv.field_size_limit(sys.maxsize)
rows = list(csv.DictReader(open(sys.argv[1], encoding="utf-8")))
def jl(v):
    try: return json.loads(v) if v else None
    except Exception: return None
def fl(v):
    try: return float(v)
    except Exception: return None
def short(r):
    d = jl(r.get("core_gate")) or {}
    return dict(id=r["config_id"], fam=r["family"][:2], tf=r["timeframe"], n=int(float(r["trades"])),
                pf=fl(r["profit_factor"]), exp=fl(r["expectancy_bps"]), wr=fl(r["win_rate"]),
                wil=fl(r["wilson_95_lower"]), be=fl(r["breakeven_win_rate"]), cum=fl(r["cumulative_return"]),
                mdd=fl(r["max_drawdown"]), sh=fl(r["sharpe"]), p=fl(r["one_sided_p"]),
                fails=jl(r["fail_reasons"]) if False else r["fail_reasons"])
fr = Counter()
for r in rows:
    for x in (jl(r.get("fail_reasons")) or []):
        fr[x.split(":")[0]] += 1
print("fail reason counts:", dict(fr))
cfg = json.loads(json.dumps(rows[0]))  # placeholder
print("\nTOP10 by expectancy among trades>=60:")
elig = [r for r in rows if r["status"] == "scored" and int(float(r["trades"])) >= 60 and fl(r["expectancy_bps"]) is not None]
elig.sort(key=lambda r: (-fl(r["expectancy_bps"]), r["config_id"]))
for r in elig[:10]:
    s = short(r); sup = jl(r["supplementary"]) or {}
    print(s["id"], s["fam"], s["tf"], "n", s["n"], "PF", round(s["pf"],3), "exp", round(s["exp"],2),
          "wil", round(s["wil"],3), "be", round(s["be"],3), "cum", round(s["cum"],3), "mdd", round(s["mdd"],3),
          "sh", round(s["sh"],2), "p", s["p"], "| delay", (sup.get("delay_1bar") or {}).get("expectancy_bps"),
          "cost2", (sup.get("cost_2x") or {}).get("expectancy_bps"), "clu_p", (sup.get("cluster_p") or {}).get("p"),
          "yr", (sup.get("yearly") or {}).get("reason"), "top3", (sup.get("top3_excluded") or {}).get("expectancy_bps"))
    print("   fails:", r["fail_reasons"])
print("\nCORE or BONF passers:")
for r in rows:
    if r["passes_core"] == "True" or r["passes_bonferroni"] == "True":
        s = short(r); sup = jl(r["supplementary"]) or {}
        print(s["id"], s["fam"], s["tf"], "n", s["n"], "PF", round(s["pf"],3), "exp", round(s["exp"],2),
              "p", s["p"], "core", r["passes_core"], "bonf", r["passes_bonferroni"],
              "| delay", (sup.get("delay_1bar") or {}).get("expectancy_bps") and round((sup.get("delay_1bar") or {}).get("expectancy_bps"),2),
              "cost2", (sup.get("cost_2x") or {}).get("expectancy_bps") and round((sup.get("cost_2x") or {}).get("expectancy_bps"),2),
              "clu_p", (sup.get("cluster_p") or {}).get("p"), "top3", (sup.get("top3_excluded") or {}).get("expectancy_bps") and round((sup.get("top3_excluded") or {}).get("expectancy_bps"),2))
print("\nD1 detail (all 96): exp sorted top 5 and bottom 3")
d1 = sorted([r for r in rows if r["family"].startswith("D1")], key=lambda r: -fl(r["expectancy_bps"]))
for r in d1[:5] + d1[-3:]:
    s = short(r)
    print(s["id"], s["tf"], "n", s["n"], "exp", round(s["exp"],2), "PF", round(s["pf"],3), "wr", round(s["wr"],3), "be", round(s["be"],3), "cum", round(s["cum"],3), r["config_id"])
import statistics as st
print("D1 median wr", round(st.median(fl(r["win_rate"]) for r in d1),3), "median cost2 exp", round(st.median((jl(r["supplementary"]) or {}).get("cost_2x", {}).get("expectancy_bps") or 0 for r in d1),2))
print("D1 median delay exp", round(st.median((jl(r["supplementary"]) or {}).get("delay_1bar", {}).get("expectancy_bps") or 0 for r in d1),2))
