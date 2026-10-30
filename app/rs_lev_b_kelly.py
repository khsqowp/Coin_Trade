"""BACKTESTER-B analysis A (Kelly / growth-optimal exposure) + no-kill realised growth vs leverage. Offline research only."""
import os, sys, pickle, json
sys.dont_write_bytecode = True
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
import numpy as np, pandas as pd
import app.rs_lev_b_run as R
from app.rs_lev_b_engine import pbvec

ctx = R.Ctx()
F = np.arange(0.5, 12.01, 0.25)
rng = np.random.default_rng(777)
lines = []
res = {}

def unit_series(win):
    a, b = ctx.W[win]
    out = []
    hl = 0.0
    for ph in range(3):
        r = ctx.base.run_b(a, b, phase=ph, lev=1.0, deploy=1.0, kill=1.0, cool=0, pb=pbvec(intra=0, norm=1, mbreak=1))
        e = r["eq"][a:b]
        out.append(np.diff(e) / e[:-1]); hl = max(hl, r["hloss"])
    return np.vstack(out), hl

def g_curve(r):
    return np.array([365.0 * np.mean(np.log1p(np.clip(f * r, -0.999999, None))) for f in F])

def stat_idx(n, B, mean_block=20):
    p = 1.0 / mean_block
    idx = np.empty((B, n), np.int64)
    for b in range(B):
        i = rng.integers(n)
        for t in range(n):
            idx[b, t] = i
            i = rng.integers(n) if rng.random() < p else (i + 1) % n
    return idx

for win in ("IS", "OOS", "FULL"):
    r, hl = unit_series(win)
    n = r.shape[1]
    mu = r.mean() * 365; var = r.var() * 365
    g = g_curve(r)
    fs = F[np.argmax(g)]
    idx = stat_idx(n, 2000)
    fstars = []; g4 = []; g6 = []
    for b in range(2000):
        rb = r[:, idx[b]]
        gb = g_curve(rb)
        fstars.append(F[np.argmax(gb)]); g4.append(gb[list(F).index(4.0)]); g6.append(gb[list(F).index(6.0)])
    fs_ci = np.percentile(fstars, [5, 50, 95])
    f_cont = mu / var
    f_liq = 1.0 / (hl + 0.03)
    res[win] = dict(mu=mu, sigma=np.sqrt(var), f_cont=f_cont, fstar=float(fs), fstar_ci=fs_ci.tolist(), hl_unit=hl, f_liq=f_liq,
                    g_at={float(f): float(g[list(F).index(f)]) for f in (1, 2, 3, 4, 5, 6, 8)}, g4_ci=np.percentile(g4, [5, 50, 95]).tolist())
    lines.append(f"{win}: unit(1x) mu={mu:.3f}/yr sigma={np.sqrt(var):.3f}/yr  Sharpe={mu/np.sqrt(var):.2f}  f_cont=mu/var={f_cont:.2f}  grid f*={fs:.2f}  "
                 f"f* boot[5,50,95]={fs_ci.round(2).tolist()}  max 1h worst-case loss (unit)={hl:.3f} -> f_liq(gap)={f_liq:.1f}")
    lines.append("   g(f) [ann. log growth, daily-rebalanced fixed fraction, no kill]: " + ", ".join(f"f={f:g}:{g[list(F).index(f)]:+.2f}" for f in (1, 2, 3, 4, 5, 6, 8, 10)))
    lines.append(f"   g(4) boot [5,50,95] = {np.percentile(g4,[5,50,95]).round(2).tolist()};  g(6) boot = {np.percentile(g6,[5,50,95]).round(2).tolist()}")

# realised growth vs leverage: no kill vs blunt kill (T0, T2, T1), 120 paths
lines.append("\nREALISED (engine, 120 jittered paths) median ann. log-growth by lev x deploy .95; columns: no-kill | kill35 T0 | kill35 T2 | kill35 T1 ; liq paths (no-kill)")
for win in ("IS", "OOS"):
    lines.append(f"[{win}]")
    for lev in (1.0, 2.0, 3.0, 4.0, 5.0, 6.0, 8.0):
        row = []
        for tag, kw in (("nokill", dict(kill=1.0, cool=0, trig=0)), ("T0", dict(kill=0.35, cool=14, trig=0)), ("T2", dict(kill=0.35, cool=14, trig=2)), ("T1", dict(kill=0.35, cool=14, trig=1))):
            des = R.D(lev=lev, kill=kw["kill"], cool=kw["cool"])
            c = R.run_cell(ctx, des, kw["trig"], win, "sc1")
            rr = c["rows"]
            row.append((float(rr.logg.median()), int((rr.liq_f > 0).sum())))
        lines.append(f"  lev {lev:g}: " + " | ".join(f"{g:+.2f} (liq {l})" for g, l in row))
print("\n".join(lines))
json.dump(res, open(os.path.join(os.path.dirname(os.path.abspath(__file__)), "..", "docs/research/lev_loop/B/kelly.json"), "w"), indent=1, default=float)
