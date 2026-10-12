"""Deep-dive on final candidates: small-account with K-shrink, survivorship ablation, rolling-window ranges."""
from __future__ import annotations
import json
import numpy as np, pandas as pd
from app.rs_final_data import load_panel
from app.rs_final_engine import Sim, window_metrics, yearly_returns
from app.rs_final_run import SIG, IS, OOS, KILL, summarise

CANDS = {
    "BASE S0|O0 (14/3/K8 1x)": (SIG["S0"], {}),
    "C1 S0|O3 (14/3/K8 + BTC14d<-10% flat)": (SIG["S0"], dict(crash_flat=True)),
    "C2 S1|O3 (14/2/K12 + crash flat)": (SIG["S1"], dict(crash_flat=True)),
    "C3 S0|O1 T18 cap1.5 (vol target)": (SIG["S0"], dict(vt=0.18, cap=1.5, lev=1.5)),
    "C4 S0|O4 T18 cap1.5 (IS top1)": (SIG["S0"], dict(vt=0.18, cap=1.5, lev=1.5, regime_b=True)),
}


def runs(S, sg, ov, **extra):
    kw = {**sg, **ov, **KILL, **extra}
    return [S.run(phase=p, **kw) for p in range(kw["rebal"])]


def rolling(rs, w):
    r = np.mean([x["eq"].dropna().pct_change().fillna(0).to_numpy() for x in rs], axis=0)
    eq = np.cumprod(1 + r)
    ret = eq[w:] / eq[:-w] - 1
    mdd = []
    for i in range(0, len(eq) - w, 5):
        seg = eq[i:i + w + 1]; mdd.append((1 - seg / np.maximum.accumulate(seg)).max())
    q = lambda a, p: float(np.percentile(a, p))
    return dict(ret_p5=q(ret, 5), ret_p25=q(ret, 25), ret_med=q(ret, 50), ret_p75=q(ret, 75), ret_p95=q(ret, 95),
                mdd_med=q(mdd, 50), mdd_p90=q(mdd, 90), mdd_p99=q(mdd, 99), p_neg=float((ret < 0).mean()), sd_daily=float(r.std()))


def main():
    S = Sim(load_panel())
    c = S.C[:, -1, :]; first = np.argmax(np.isfinite(c), axis=0)
    keep = [j for j, n in enumerate(S.names) if S.days[first[j]] < pd.Timestamp("2023-01-01", tz="UTC")]
    Sk = Sim(dict(names=[S.names[j] for j in keep], days=S.days, H=S.H[:, :, keep], L=S.L[:, :, keep], C=S.C[:, :, keep], FD=S.FD[:, keep]))
    out = {}
    f = lambda w: f"{w['cagr']*100:5.1f}%/{w['imdd']*100:4.1f}%/{w['calmar']:.2f}"
    for nm, (sg, ov) in CANDS.items():
        o = {}
        print("\n###", nm)
        rs = runs(S, sg, ov)
        o["ideal"] = dict(IS=summarise(rs, *IS), OOS=summarise(rs, *OOS), full=summarise(rs))
        print("  ideal  IS", f(o["ideal"]["IS"]), "OOS", f(o["ideal"]["OOS"]), "full", f(o["ideal"]["full"]), "wpMDD %.1f" % (o["ideal"]["full"]["imdd_worst_phase"] * 100),
              "worstday %.1f%%" % (o["ideal"]["full"]["worst_day_min"] * 100))
        rb = runs(S, sg, ov, cw=1)
        o["modelB"] = dict(IS=summarise(rb, *IS), OOS=summarise(rb, *OOS), full=summarise(rb))
        print("  modelB IS", f(o["modelB"]["IS"]), "OOS", f(o["modelB"]["OOS"]), "full", f(o["modelB"]["full"]))
        for tag, SS in (("ex-late", Sk),):
            ra = runs(SS, sg, ov); rbb = runs(SS, sg, ov, cw=1)
            o[tag + "_A"] = dict(IS=summarise(ra, *IS), OOS=summarise(ra, *OOS), full=summarise(ra))
            o[tag + "_B"] = dict(full=summarise(rbb))
            print(f"  {tag} A IS", f(o[tag + '_A']['IS']), "OOS", f(o[tag + '_A']['OOS']), "full", f(o[tag + '_A']['full']), "| B full", f(o[tag + '_B']['full']))
        for acct, mn in (("m5", 5.0), ("m20", 20.0)):
            for dn, ex in (("plain", {}), ("Kshrink", dict(design=3, dlv=9.0, rlv=9.0, rearm=5))):
                rr = runs(S, sg, ov, minn=mn, eq0=142.0, **ex)
                sm = summarise(rr)
                skip = np.mean([x["skip"] / max(x["att"], 1) for x in rr]); npos = np.mean([x["npos"] for x in rr])
                flat = np.mean([(x["expo"].loc[x["eq"].dropna().index] == 0).mean() for x in rr])
                o[f"{acct}_{dn}"] = dict(full=sm, skip_rate=float(skip), npos=float(npos), flat=float(flat), end_usdt=float(np.mean([x['eq'].dropna().iloc[-1] for x in rr])),
                                         OOS=summarise(rr, *OOS))
                print(f"  {acct} {dn:8s} full {f(sm)} OOS {f(o[f'{acct}_{dn}']['OOS'])} skip {skip*100:4.1f}% avg#pos {npos:4.1f} flat {flat*100:3.0f}% end {o[f'{acct}_{dn}']['end_usdt']:.0f} USDT")
        o["roll60"] = rolling(rs, 60); o["roll90"] = rolling(rs, 90)
        print("  roll60", {k: round(v, 3) for k, v in o["roll60"].items()})
        print("  roll90", {k: round(v, 3) for k, v in o["roll90"].items()})
        ys = [yearly_returns(r) for r in rs]
        o["years"] = {y: float(np.mean([d[y] for d in ys])) for y in ys[0]}
        print("  years", {y: round(v * 100, 1) for y, v in o["years"].items()}, "kills", np.mean([r["kills"] for r in rs]))
        out[nm] = o
    json.dump(out, open("docs/research/final_candidates.json", "w"), default=float, separators=(",", ":"))


if __name__ == "__main__":
    main()
