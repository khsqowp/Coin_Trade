from summ import *
import json
pd.set_option("display.width", 250); pd.set_option("display.max_columns", 40)
for win in ("OOS", "FULL"):
    df = load(win)
    for km in (3, 1, 0):
        A = agg(df, km)
        adm = admissible(df, km)
        A["adm"] = [adm[c][0] for c in A.index]
        print(f"\n=== {win} kill_mode {km} BASE (120 paths) ===")
        print(A[["g_mean","g_med","cagr_med","w_p10","w_med","w_p90","mdd_med","mddi_med","mddi_p90","kills_mean","liq_tier","liq_flat","cush_flat_min","adm"]].round(3).to_string())
        if km == 3:
            for c in CELLS:
                if not adm[c][0]: print("   inadmissible", c, adm[c][1])
