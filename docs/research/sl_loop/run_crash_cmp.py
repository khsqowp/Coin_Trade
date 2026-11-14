"""Round crash_cmp: crash-filter comparison on the live config. Run from trading/: python docs/research/sl_loop/run_crash_cmp.py"""
import sys, json, hashlib
from pathlib import Path
ROOT = Path(__file__).resolve().parents[3]; sys.path.insert(0, str(ROOT))
from docs.research.sl_loop.lib import load_all, ENVA
import numpy as np, pandas as pd
from app.rs_sl_engine import TPSim
from app.rs_final_engine import window_metrics, btc_flags

OUT = Path(__file__).resolve().parent
WIN = {"IS": ("2022-01-01", "2024-06-30"), "OOS": ("2024-07-01", None), "full": (None, None)}
VARIANTS = [("A_live_-10", 1, -.10, .35), ("B_off", 0, -.10, .35), ("C_longs_only_-10", 2, -.10, .35), ("D_off_nokill", 0, -.10, 1.0),
            ("A_-7", 1, -.07, .35), ("A_-15", 1, -.15, .35), ("A_-20", 1, -.20, .35)]

def monthly_worst(eq, a, b):
    s = eq.dropna()
    if a: s = s[s.index >= pd.Timestamp(a, tz="UTC")]
    if b: s = s[s.index <= pd.Timestamp(b, tz="UTC")]
    me = s.groupby([s.index.year, s.index.month]).last()
    prev = pd.concat([pd.Series([s.iloc[0]]), me.iloc[:-1]]).to_numpy()
    r = me.to_numpy() / prev - 1
    return float(r.min())

def main():
    P, CF = load_all(); sim = TPSim(P, CF); d0 = sim.d_start()
    flags = {t: btc_flags(P, t, 14)[1] for t in (-.07, -.10, -.15, -.20)}
    res = {}; rows = []
    for lev in (4., 3., 2.):
        for name, mode, thr, kill in VARIANTS:
            sim.crash = flags[thr]
            kw = dict(ENVA); kw.update(lev=lev, kill=kill)
            runs = [sim.run(sl={}, phase=p, crash_mode=mode, **kw) for p in (0, 1, 2)]
            res[(lev, name)] = runs
            params = dict(lev=lev, crash=mode, thr=thr, kill=kill, cool=14, cost=.001, fund=1, sL=-1., sS=-1., variant=name)
            cid = hashlib.sha1(("crash_cmp" + json.dumps(params, sort_keys=True)).encode()).hexdigest()[:12]
            row = {"id": cid, "round": "crash_cmp", "params": params}
            yrs = np.mean([len(r["eq"].dropna()) for r in runs]) / 365.
            for w, (a, b) in WIN.items():
                ms = [window_metrics(r, a, b) for r in runs]
                d = {k: float(np.mean([m[k] for m in ms])) for k in ("cagr", "mdd", "imdd", "sharpe", "end")}
                d["calmar_i"] = float(np.mean([m["cagr"] / m["imdd"] if m["imdd"] > 0 else 0 for m in ms]))
                d["worst_month"] = float(np.mean([monthly_worst(r["eq"], a, b) for r in runs]))
                sl_ = lambda r: r["eq"].dropna()
                def cut(r):
                    s = r["expo"].reindex(sl_(r).index)
                    if a: s = s[s.index >= pd.Timestamp(a, tz="UTC")]
                    if b: s = s[s.index <= pd.Timestamp(b, tz="UTC")]
                    return s
                d["time_in_market"] = float(np.mean([(cut(r) > 0).mean() for r in runs]))
                d["mean_expo"] = float(np.mean([cut(r).replace([np.inf], np.nan).mean() for r in runs]))
                row[w] = d
            row["kills_per_year"] = float(np.mean([r["kills"] for r in runs]) / yrs)
            row["kills_mean"] = float(np.mean([r["kills"] for r in runs]))
            row["liquidations"] = int(sum(r["liq"] for r in runs))
            rows.append(row)
    # episodes (-10% flag), A vs B, per leverage
    flag = flags[-.10]; ids = np.flatnonzero(flag[d0:]) + d0; groups = []
    for ix in ids:
        if not groups or ix != groups[-1][-1] + 1: groups.append([int(ix)])
        else: groups[-1].append(int(ix))
    eps = {}
    for lev in (4., 3., 2.):
        L = []
        for n, g in enumerate(groups, 1):
            first, last = g[0], g[-1]; ch = {"A": [], "B": []}
            for key, nm in (("A", "A_live_-10"), ("B", "B_off")):
                for r in res[(lev, nm)]:
                    e = r["eq"].to_numpy()
                    ch[key].append(float(e[last] / e[first - 1] - 1) if np.isfinite(e[first-1]) and np.isfinite(e[last]) and e[first-1] > 0 else np.nan)
            L.append({"episode": n, "start": str(P["days"][first].date()), "end": str(P["days"][last].date()), "days": len(g),
                      "A": float(np.nanmean(ch["A"])), "B": float(np.nanmean(ch["B"]))})
        eps[str(int(lev))] = L
    # liquidation check B 4x
    liq = {}
    for nm in ("B_off", "A_live_-10", "D_off_nokill"):
        out = []
        for r in res[(4., nm)]:
            eq = r["eq"]; w = r["worst"]; prev = eq.shift(1)
            ratio = (w / prev).replace([np.inf, -np.inf], np.nan)
            ex = r["expo"].replace([np.inf, -np.inf], np.nan)
            out.append(dict(liq=bool(r["liq"]), min_worst_over_prev_close=float(ratio.min()), argmin=str(ratio.idxmin().date()),
                            worst_day_close=float((eq.pct_change()).min()), peak_expo=float(ex.max()), kills=int(r["kills"])))
        liq[nm] = out
    with (OUT / "ledger.jsonl").open("a") as f:
        for r in rows: f.write(json.dumps(r, separators=(",", ":")) + "\n")
    json.dump({"rows": rows, "episodes": eps, "liq": liq}, open(OUT / "crash_cmp_numbers.json", "w"), indent=1)
    print("done", len(rows))

if __name__ == "__main__": main()
