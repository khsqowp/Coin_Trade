from summ import *
import json
df = load("IS")
out = {}
pd.set_option("display.width", 250); pd.set_option("display.max_columns", 40)
for km in (1, 3, 0):
    A = agg(df, km)
    print(f"\n=== IS kill_mode {km} BASE (120 paths) ===")
    t = A[["g_mean","g_med","cagr_med","w_p10","w_med","w_p90","mdd_med","mddi_med","mddi_p90","kills_mean","liq_tier","liq_flat","cush_flat_min"]].round(3)
    print(t.to_string())
    if km in (1, 3):
        sel, A, adm = select(df, km)
        out[f"S_kmode{km}"] = sel
        print("admissibility (liq tier,flat counts BASE/VOL/COST/COMB):")
        for c in CELLS: print("  ", c, "ADM" if adm[c][0] else "no ", adm[c][1])
        print(json.dumps(sel, indent=1))
json.dump(out, open("selection.json", "w"), indent=1)
