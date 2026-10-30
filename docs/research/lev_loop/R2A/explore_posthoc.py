"""POST-HOC exploratory (NOT part of the pre-registered decision rule): what determines per-day f* in the control book (IS, kill=daily, path 0)?"""
import sys, os
sys.dont_write_bytecode = True
sys.path.insert(0, os.path.join(os.path.dirname(os.path.abspath(__file__)), "../../../.."))
import numpy as np
from app import rs_lev_r2a_run as R, rs_lev_r2a_engine as E
d0, d1 = R.PERIOD["IS"]
for cell in ("C0_control", "G42", "N03", "C1_norm"):
    r = E.run(phase=0, d0=d0, d1=d1, km="daily", **R.CELLS[cell])
    held, c0, eq, b = R.tp_coeffs(r["snapA"], r["eqA"], R.MM_TIER)
    V = r["snapA"][held]; e = r["eqA"][held]
    fs = np.where(b["anti"] > 0, c0 / np.where(b["anti"] > 0, b["anti"], 1), 99)
    gross = np.abs(V).sum(1) / e; net = V.sum(1) / e
    longg = np.where(V > 0, V, 0).sum(1) / e; shortg = -np.where(V < 0, V, 0).sum(1) / e
    L_wick = np.where(V > 0, V, 0) @ (1 - R.rL) / e; S_wick = np.where(V < 0, -V, 0) @ (R.rH - 1) / e
    i = np.argmin(fs)
    print(f"{cell:11s} days {held.sum()} | f* min {fs.min():.3f} p5 {np.percentile(fs,5):.3f} med {np.median(fs):.3f} | corr(f*,1/gross)={np.corrcoef(fs,1/gross)[0,1]:.2f} corr(f*,net)={np.corrcoef(fs,net)[0,1]:.2f}"
          f" | f*xgross med {np.median(fs*gross):.2f} min {np.min(fs*gross):.2f} | worst day: gross {gross[i]:.2f} net {net[i]:+.2f} long {longg[i]:.2f} short {shortg[i]:.2f} long-wick-loss/eq {L_wick[i]:.2f} short-H-loss/eq {S_wick[i]:.2f}")
    if cell == "C0_control":
        idx = np.argsort(fs)[:8]
        print("   8 lowest-f* days (gross, net, longwick):", [(round(gross[k],2), round(net[k],2), round(L_wick[k],2), round(fs[k],3)) for k in idx])
        print("   gross range on those days", gross[idx].min().round(2), gross[idx].max().round(2), "| overall gross p50/p95/max", np.percentile(gross,[50,95,100]).round(2))
        # what gross multiplier would +0.12 need if f* ~ k/gross at the worst day
        k = fs.min() * gross[np.argmin(fs)]
        print(f"   implied: worst-day f*xgross={k:.2f}; to reach f*={fs.min()+0.12:.3f} worst-day gross would have to be {k/(fs.min()+0.12):.2f} (nominal 3.80)")
S = __import__("pickle").load(open(os.path.join(R.OUT, "stage1_IS.pkl"), "rb"))
print("P at f=1.0 (daily kill) hedged / sync / anti, tier:")
for c in S:
    P = S[c]["daily"]["S"]["P"]
    print(f"  {c:16s} hedged {P[('tier','hedged',1.0)]:.3f} sync {P[('tier','sync',1.0)]:.3f} anti {P[('tier','anti',1.0)]:.3f} | f* hedged median {np.median(S[c]['daily']['S']['fstar']['hedged']):.2f}")
