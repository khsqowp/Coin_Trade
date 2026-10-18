"""Selection protocol: IS-only ranking, untouched OOS, folds, cross-model (const-weight) check, neighbours, years."""
from __future__ import annotations
import json, math
import numpy as np, pandas as pd
from app.rs_final_data import load_panel
from app.rs_final_engine import Sim
from app.rs_final_run import SIG, ACCT, KILL, IS, OOS, FOLDS, overlays, full_row, summarise, run_cfg, avg_ret, deflated_sharpe

SCR = "/private/tmp/claude-501/-Users-user-Desktop-CODE-Ochestration/20fd8e9e-6d26-4ff1-a6b5-39a3bd8d3e48/scratchpad"


def r4(x):
    if isinstance(x, dict):
        return {k: r4(v) for k, v in x.items()}
    if isinstance(x, (list, tuple)):
        return [r4(v) for v in x]
    return round(float(x), 4) if isinstance(x, (float, np.floating)) else x


def cal(S, sig, ov, extra=None, acct="ideal"):
    rs = run_cfg(S, sig, ov, acct, extra)
    return summarise(rs, *IS), summarise(rs, *OOS), summarise(rs)


def neighbours(S, sname, oname, ov_all):
    sg = dict(SIG[sname]); o = dict(ov_all[oname])
    out = []
    def add(name, s2=None, o2=None):
        s_ = {**sg, **(s2 or {})}; o_ = {**o, **(o2 or {})}
        i, oo, f = cal(S, s_, o_)
        out.append(dict(n=name, IS=i["calmar"], OOS=oo["calmar"]))
    for dk in (-2, 2):
        if sg["K"] + dk >= 4: add(f"K{sg['K']+dk}", dict(K=sg["K"] + dk))
    for dn in (-1, 1):
        if sg["rebal"] + dn >= 1: add(f"N{sg['rebal']+dn}", dict(rebal=sg["rebal"] + dn))
    if len(sg["lbs"]) == 1:
        add("lb10", dict(lbs=(10,))); add("lb18", dict(lbs=(18,)))
    else:
        add("lbs(10,21)", dict(lbs=(10, 21))); add("lbs(14,21)", dict(lbs=(14, 21)))
    add("band" + str(0 if sg["band"] else 2), dict(band=0 if sg["band"] else 2))
    if "vt" in o:
        for dT in (-0.03, 0.03):
            add(f"T{int((o['vt']+dT)*100)}", None, dict(vt=o["vt"] + dT))
        add("vlb30", None, dict(vlb=30)); 
    if o.get("crash_flat"):
        for thr in (-0.075, -0.125, -0.15):
            add(f"crash{thr}", None, dict(crash_thr=thr))
        for lb in (7, 10, 21):
            add(f"crashlb{lb}", None, dict(crash_lb=lb))
    return out


def main():
    S = Sim(load_panel()); ov = overlays()
    # extra overlay variants for O3 robustness live inside neighbours()
    A = {}; B = {}; rets = {}
    for sname, sg in SIG.items():
        for oname, o in ov.items():
            key = f"{sname}|{oname}"
            row, rs = full_row(S, sg, o, "ideal")
            for ac in ("m5", "m20"):
                r2, _ = full_row(S, sg, o, ac)
                row[ac] = dict(cagr=r2["full"]["cagr"], imdd=r2["full"]["imdd"], calmar=r2["full"]["calmar"],
                               skip_rate=r2["skip_rate"], skips=r2["skips"], attempts=r2["attempts"], kills=r2["kills"],
                               flat=r2["flat_frac"], npos=r2["npos"], OOS_cagr=r2["OOS"]["cagr"], OOS_imdd=r2["OOS"]["imdd"])
            A[key] = row
            ret, idx = avg_ret(rs); rets[key] = pd.Series(ret, index=idx)
            i, oo, f = cal(S, sg, o, dict(cw=1))
            B[key] = dict(IS=i, OOS=oo, full=f)
    base, baseB = A["S0|O0"], B["S0|O0"]
    def ok_is(r): return r["IS"]["imdd"] <= 0.25 and r["IS"]["worst_day_min"] > -0.07
    cand = sorted([k for k, r in A.items() if ok_is(r)], key=lambda k: -A[k]["IS"]["calmar"])
    # multiple-testing
    isr = {k: v[(v.index >= pd.Timestamp(IS[0], tz="UTC")) & (v.index <= pd.Timestamp(IS[1], tz="UTC"))] for k, v in rets.items()}
    sr_tr = [float(v.mean() / v.std()) for v in isr.values()]
    dsr = {}
    for k in set(cand[:12]) | {"S0|O0", "S1|O3", "S0|O3"}:
        v = isr[k]; sr = float(v.mean() / v.std())
        sk = float(((v - v.mean()) ** 3).mean() / v.std() ** 3); ku = float(((v - v.mean()) ** 4).mean() / v.std() ** 4)
        p, sr0 = deflated_sharpe(sr, len(v), sr_tr, sk, ku)
        dsr[k] = dict(sr=sr * math.sqrt(365), p=p, sr0=sr0 * math.sqrt(365))
    n = len(A)
    def beats(r, b): return r["IS"]["calmar"] > b["IS"]["calmar"] and r["OOS"]["calmar"] > b["OOS"]["calmar"]
    fr_A = float(np.mean([beats(r, base) for r in A.values()]))
    fr_B = float(np.mean([beats(B[k], baseB) for k in A]))
    fr_both = float(np.mean([beats(A[k], base) and beats(B[k], baseB) for k in A]))
    fr_cagr = float(np.mean([A[k]["IS"]["cagr"] > base["IS"]["cagr"] and A[k]["OOS"]["cagr"] > base["OOS"]["cagr"] for k in A]))
    # consistency screen
    def screen(k):
        r = A[k]
        if not ok_is(r): return False
        if r["OOS"]["imdd"] > 0.30: return False
        if not beats(r, base): return False
        if not beats(B[k], baseB): return False
        fb = [f["calmar"] for f in base["folds"]]
        if any(f["calmar"] < 0.8 * b_ for f, b_ in zip(r["folds"], fb)): return False
        return True
    scr = [k for k in A if screen(k)]
    scr.sort(key=lambda k: -min(A[k]["IS"]["calmar"], A[k]["OOS"]["calmar"]))
    show = []
    for k in list(dict.fromkeys(cand[:5] + scr[:6] + ["S0|O0", "S1|O0"])):
        nb = neighbours(S, *k.split("|"), ov)
        rI = [x["IS"] / A[k]["IS"]["calmar"] for x in nb]; rO = [x["OOS"] / max(A[k]["OOS"]["calmar"], 1e-9) for x in nb]
        show.append(k); A[k]["nb"] = dict(n=len(nb), IS_min=min(rI), IS_med=float(np.median(rI)), IS_frac80=float(np.mean(np.array(rI) >= .8)),
                                          OOS_min=min(rO), OOS_med=float(np.median(rO)), OOS_frac80=float(np.mean(np.array(rO) >= .8)), items=nb)
    out = dict(n_configs=n, n_pass_IS_filter=len(cand), IS_rank=cand, screen_pass=scr, dsr=dsr, sr_trial_sd_ann=float(np.std(sr_tr) * math.sqrt(365)),
               frac_beat_base_calmar_IS_OOS_modelA=fr_A, frac_beat_modelB=fr_B, frac_beat_both_models=fr_both, frac_beat_cagr_and_IS_OOS=fr_cagr,
               table=A, modelB=B)
    json.dump(r4(out), open("docs/research/final_grid.json", "w"), separators=(",", ":"))
    print("n", n, "passIS", len(cand), "fracA", fr_A, "fracB", fr_B, "both", fr_both, "cagr", fr_cagr, "screen", len(scr))
    def f(w): return f"{w['cagr']*100:5.1f}/{w['imdd']*100:4.1f}/{w['calmar']:.2f}"
    def line(k):
        r = A[k]; b = B[k]
        s = f"{k:16s} IS {f(r['IS'])} OOS {f(r['OOS'])} full {f(r['full'])} wpMDD {r['full']['imdd_worst_phase']*100:4.1f} folds " + \
            " ".join(f"{x['calmar']:.2f}" for x in r["folds"]) + f" | modelB IS/OOS Calmar {b['IS']['calmar']:.2f}/{b['OOS']['calmar']:.2f} cagr {b['full']['cagr']*100:.1f}"
        s += f" | m5 skip {r['m5']['skip_rate']*100:.0f}% cagr {r['m5']['cagr']*100:.1f}% imdd {r['m5']['imdd']*100:.1f} flat {r['m5']['flat']*100:.0f}% | m20 skip {r['m20']['skip_rate']*100:.0f}%"
        if k in dsr: s += f" | DSR {dsr[k]['p']:.2f}"
        if "nb" in r: s += f" | nb IS min/med {r['nb']['IS_min']:.2f}/{r['nb']['IS_med']:.2f} OOS min/med {r['nb']['OOS_min']:.2f}/{r['nb']['OOS_med']:.2f}"
        s += " | yrs " + " ".join(f"{y}:{v*100:+.0f}" for y, v in r["years"].items())
        return s
    print("== IS-ranked top 8 (filter passed)")
    for k in cand[:8]: print(line(k))
    print("== consistency-screened")
    for k in scr[:10]: print(line(k))
    print("== refs")
    for k in ("S0|O0", "S1|O0", "S2|O0", "S3|O0", "S4|O0"): print(line(k))


if __name__ == "__main__":
    main()
