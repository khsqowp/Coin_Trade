"""Tables from stage1_IS.pkl using the frozen runner functions (admission rule per prereg 6)."""
import sys, os, pickle, json
sys.dont_write_bytecode = True
sys.path.insert(0, os.path.join(os.path.dirname(os.path.abspath(__file__)), "../../../.."))
import numpy as np
from app import rs_lev_r2a_run as R
per = sys.argv[1] if len(sys.argv) > 1 else "IS"
fn = {"IS": "stage1_IS.pkl", "OOS": "oos_OOS.pkl"}[per]
res = pickle.load(open(os.path.join(R.OUT, fn), "rb"))
mde = json.load(open(os.path.join(R.OUT, "stage0_mde.json")))
ctl = res[R.CTL]
cells = [c for c in res if c != R.CTL]
adm = {c: R.admission(res[c], ctl) for c in cells}
print(f"=== period {per} ===")
print("\n## Tail state (pooled over 60 paths, day-close, after caps) p50/p95/p99/max  [kill=daily]")
for c in res:
    S = res[c]["daily"]["S"]
    print(f"{c:16s} gross/eq {np.round(S['gross_q'],2)} | |net|/eq {np.round(S['net_q'],2)} | max-sym/eq {np.round(S['sym_q'],3)}")
for km in R.KMS:
    print(f"\n## kill model {km}: n_unique ctl={ctl[km]['S']['n_unique']} MDE0={mde[km]['mde0']:.2f}/yr")
    print("cell | f*anti med (min) | P anti f=.5/.75/1 | P sync .75 | P hedged .75 | dGross% held | dGross% all | subsets4b worse strict/tol02 | min4b (cell vs ctl) | real cmin min | A1 A2 A3 A4 | kills | n_uniq | episodes(union/path) | blocks15 liq/total")
    for c in res:
        S = res[c][km]["S"]; sub = res[c][km]["sub"]; K = ctl[km]["S"]; kk = ctl[km]["sub"]
        P = S["P"]
        a = adm.get(c, {}).get(km)
        dga = S["gross_mean_all"] / K["gross_mean_all"] - 1
        dgh = S["gross_mean_held"] / K["gross_mean_held"] - 1
        w = int(np.sum(sub["tp1"] < kk["tp1"] - 1e-9)); w2 = int(np.sum(sub["tp1"] < kk["tp1"] - 0.02))
        flags = " ".join("Y" if a[x] else "n" for x in ("c1", "c2", "c3", "c4")) if a else "-"
        print(f"{c:16s} | {np.median(S['fstar']['anti']):.3f} ({S['fstar']['anti'].min():.3f}) | {P[('tier','anti',0.5)]:.3f}/{P[('tier','anti',0.75)]:.3f}/{P[('tier','anti',1.0)]:.3f} | {P[('tier','sync',0.75)]:.3f} | {P[('tier','hedged',0.75)]:.3f} | {dgh*100:+.2f} | {dga*100:+.2f} | {w}/{w2} | {sub['tp1'].min():+.3f} vs {kk['tp1'].min():+.3f} | {sub['real'].min():+.3f} | {flags} | {S['kills'].mean():.1f} | {S['n_unique']} | {S['episodes_union_anti75']}/{S['episodes_per_path_anti75']:.1f} | {S['blocks15_with_liq_anti75']}/{S['blocks15_total']}")
print("\n## P with flat3 MM, f=.75 anti / sync (daily kill model) and f* sync/hedged median")
for c in res:
    S = res[c]["daily"]["S"]; P = S["P"]
    print(f"{c:16s} flat3 anti.75={P[('flat3','anti',0.75)]:.3f} anti1.0={P[('flat3','anti',1.0)]:.3f} | f* sync med {np.median(S['fstar']['sync']):.2f} hedged med {np.median(S['fstar']['hedged']):.2f} | f*anti flat3 {np.median(S['fstar_flat']['anti']):.3f} | turnover(sum trade/eq) caps events g/n/s {S['cnt'].mean(0).round(1)}")
print("\n## Bootstrap CIs (daily kill) for key P and relative drop; growth diffs")
for km in R.KMS:
    print(f"-- {km}")
    for c in cells:
        b = R.boot_P_rel(res[c][km]["S"], ctl[km]["S"])
        g = R.growth_diff(res[c][km]["S"], ctl[km]["S"])
        lab = "uninformative" if mde[km]["mde0"] > R.THR["plausible_growth"] else "informative"
        print(f"{c:16s} P75 cell CI {np.round(b['P_cand_ci'],3)} ctl CI {np.round(b['P_ctl_ci'],3)} reldrop CI {None if b['drop_ci'] is None else np.round(b['drop_ci'],2)} | dg {g['point']:+.3f}/yr SEboot {g['se_boot']:.3f} CI95 {np.round(g['ci95'],3)} Bonf {np.round(g['ci_bonf8'],3)} | path dg {g['path_mean']:+.3f}+-{g['path_sd']:.3f} P(+)={g['path_sign_pos']:.2f} | label {lab} (MDE0 {mde[km]['mde0']:.2f})")
print("\n## ADMISSION (all five kill models required)")
for c in cells:
    ok = all(adm[c][km]["passed"] for km in R.KMS)
    fails = {km: [x for x in ("c1", "c2", "c3", "c4") if not adm[c][km][x]] for km in R.KMS}
    print(f"{c:16s} IS_PASS_ALL5={ok} fails={fails}")
json.dump({c: {km: {k: (v if not isinstance(v, (np.floating, np.integer)) else float(v)) for k, v in adm[c][km].items()} for km in R.KMS} for c in cells},
          open(os.path.join(R.OUT, f"admission_{per}.json"), "w"), indent=1, default=str)
print("\nreal-history (4a) per-cell min over subsets/paths: real cmin ctl", {km: round(float(ctl[km]['S']['real_cmin'].min()),3) for km in R.KMS})
