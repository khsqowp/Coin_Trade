import json, numpy as np
r = json.load(open("docs/research/risk_results.json"))
def row(m):
    return (f"CAGR {m['cagr']*100:5.1f}% (ph {m['cagr_min']*100:4.0f}..{m['cagr_max']*100:3.0f}) iMDD {m['imdd']*100:4.1f} "
            f"MDD {m['mdd']*100:4.1f} Cal {m['calmar']:4.2f} Sh {m['sharpe']:4.2f} wd {m['worst_day']*100:5.1f} ww {m['worst_week']*100:5.1f} "
            f"uw {m['longest_uw_days']:3.0f}d buf {m['min_buffer']:5.1f} {'HALT' if m['halted'] else ''}")
for sig in ("base_14_3_8", "live_14_2_12"):
    S = r[sig]; names = list(S["IS"])
    print("=" * 30, sig, "configs", len(names))
    def ok(n, w, lim=0.30): m = S[w][n] if w != "IS" else S["IS"][n]; return m["imdd"] <= lim and not m["liq"] and m["min_buffer"] >= 1.5
    # (a) IS-selected
    cand = sorted([n for n in names if ok(n, "IS")], key=lambda n: -S["IS"][n]["cagr"])
    print("-- (a) IS-selected top3 (IS imdd<=30%)")
    for n in cand[:3]:
        print(n)
        for w in ("IS", "OOS", "F1", "F2", "F3", "FULL"):
            print("   ", w, row(S[w][n] if w != "IS" else S["IS"][n]))
    # (b) robust: imdd<=30 on FULL, OOS and all folds; max min-window CAGR... use FULL cagr
    rob = [n for n in names if all(ok(n, w) for w in ("FULL", "OOS", "F1", "F2", "F3"))]
    rob.sort(key=lambda n: -S["FULL"][n]["cagr"])
    print("-- (b) robust (iMDD<=30% on FULL/OOS/each fold, all phases) top5 by FULL CAGR; count", len(rob))
    for n in rob[:5]:
        print(n)
        for w in ("IS", "OOS", "F1", "F2", "F3", "FULL"):
            print("   ", w, row(S[w][n] if w != "IS" else S["IS"][n]))
    print("-- 1x baseline")
    for w in ("IS", "OOS", "FULL"):
        print("   ", w, row(S[w]["const L1 d1.0"] if w != "IS" else S["IS"]["const L1 d1.0"]))
    # best by family on FULL with imdd<=30
    print("-- best feasible-by-FULL per family")
    for fam in ("const", "lad", "vol"):
        c = [n for n in rob if n.startswith(fam)]
        if c: print(fam, c[0], f"FULL CAGR {S['FULL'][c[0]]['cagr']*100:.1f} OOS {S['OOS'][c[0]]['cagr']*100:.1f}")
    # liquidation / buffer flags
    allm = [(n, S[w][n]) for w in ("FULL",) for n in names]
    print("any liq:", [n for n, m in allm if m["liq"]][:5], "min buffer overall", min(m["min_buffer"] for _, m in allm))
    cl = [n for n in names if n.startswith("const") and "d0.8" in n or n.startswith("const L") and "d1.0" in n]
    print("-- constant leverage ladder (FULL)")
    for n in cl:
        if "d0.8" in n or "d1.0" in n: print(f"   {n:18s}", row(S["FULL"][n]))
    ref = r["refs"][sig]
    print("-- stress 1y block10 (1000 paths) chosen(IS)=", ref["chosen"]); print("   ", ref["stress_chosen"]["1y_block10"])
open("/dev/null", "w")
