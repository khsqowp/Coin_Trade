"""v3 report tables built from ledger.jsonl (+ in-process re-runs of decomposition / selected baselines for daily-path moments).
Writes docs/research/sl_loop/v3_tables.md and v3_numbers.json. Run from trading/ with panel env set."""
import os, sys, json, math
from pathlib import Path
ROOT = Path(__file__).resolve().parents[3]
os.environ.setdefault("RS_FINAL_SCRATCH", str(ROOT / ".rs_cache/sl_panel"))
os.environ.setdefault("NUMBA_CACHE_DIR", str(ROOT / ".rs_cache/sl_nbc"))
sys.path.insert(0, str(ROOT))
import numpy as np, pandas as pd
from docs.research.sl_loop.lib import load_all, ENVA
from app.rs_sl_engine import TPSim as SLSim
from app.rs_final_engine import window_metrics

OUT = Path(__file__).resolve().parent
rows = [json.loads(l) for l in open(OUT / "ledger.jsonl") if l.strip()]
V3 = [r for r in rows if r.get("grid_version") == 3]
LEVELS_ALL = None
def key(p):
    return (p["lev"], round(p["sL"], 6), round(p["sS"], 6), p["lock"], p["fill"], p["crash"], round(p.get("kill", .35), 6), p.get("cool", 14), p.get("cost", .001), p.get("fund", 1))
idx = {}
for r in rows:
    p = r["params"]; p = {**dict(kill=.35, cool=14, cost=.001, fund=1), **p}
    idx[key(p)] = r
def get(lev, kill=.35, cool=14, crash=1, s=None, cost=.001, fund=1):
    sv = -1. if s is None else s
    return idx.get((lev, sv, sv, 0, 1, crash, round(kill, 6), cool, cost, fund))
def pc(x, d=1): return f"{x*100:.{d}f}%"
W = ("IS", "OOS", "full")
def yearly(r):
    out = {}
    for y in range(2022, 2027):
        v = [r["phase_results"][str(p)]["years"][str(y)] for p in (0, 1, 2)]
        v = [x["end"] - 1 for x in v if x]
        out[y] = float(np.mean(v)) if v else float("nan")
    return out
def cs(r, w): return f"{pc(r[w]['cagr'],0)}/{pc(r[w]['imdd'],0)}/{r[w]['calmar_i']:.2f}"
lines = []; nums = {}
P, CF = load_all(); sim = SLSim(P, CF)
KW = dict(rebal=3, K=8, deploy=.95, minn=0., eq0=1.)
def run_paths(p):
    res = []
    for ph in (0, 1, 2):
        res.append(sim.run(sl={}, phase=ph, crash_mode=p["crash"], lev=p["lev"], kill=p["kill"], cool=p["cool"], cost=p["cost"], fund=p["fund"], **KW))
    return res
def moments(res, a, b):
    o = []
    for r in res:
        m = window_metrics(r, a, b)
        s = r["eq"].dropna()
        if a: s = s[s.index >= pd.Timestamp(a, tz="UTC")]
        if b: s = s[s.index <= pd.Timestamp(b, tz="UTC")]
        sn = s / s.iloc[0]; ret = sn.pct_change().dropna()
        yrs = len(s) / 365.
        lg = math.log(sn.iloc[-1]) / yrs if sn.iloc[-1] > 0 else float("nan")
        mu, sd = ret.mean() * 365, ret.std() * math.sqrt(365)
        o.append(dict(cagr=m["cagr"], logg=lg, mu=mu, sd=sd, drag=sd ** 2 / 2, sharpe=m["sharpe"], mdd=m["mdd"], imdd=m["imdd"], end=m["end"]))
    return {k: float(np.nanmean([x[k] for x in o])) for k in o[0]}

# ---------------- A decomposition
stages = {0: "(a) no cost/fund/crash/kill", 1: "(b) + funding", 2: "(c) + cost 0.1%/side", 3: "(d) + crash filter", 4: "(e) + kill 35%/14d (live)"}
lines += ["### A. Decomposition ladder (no stops; phase means; IS/OOS/full)", "",
          "mu = annualised arithmetic mean daily return, sigma = annualised daily std, drag = sigma^2/2, logG = ln(end)/years (approx. mu - drag). Sharpe from daily returns*sqrt(365).", "",
          "| lev | stage | win | CAGR | logG | mu | sigma | drag | Sharpe | close MDD | intraday MDD | kills/yr | flat share | liq (3 ph) |", "|---|---|---|---:|---:|---:|---:|---:|---:|---:|---:|---:|---:|---:|"]
deco = {}
for lev in (2., 3., 4.):
    for st in range(5):
        r = next(x for x in V3 if x["params"].get("family") == "decomposition" and x["params"]["lev"] == lev and x["params"]["stage"] == st)
        res = run_paths({**dict(kill=.35, cool=14, cost=.001, fund=1), **r["params"]})
        # sanity: re-run reproduces ledger
        for w, (a, b) in dict(IS=("2022-01-01", "2024-06-30"), OOS=("2024-07-01", None), full=(None, None)).items():
            m = moments(res, a, b)
            assert abs(m["cagr"] - r[w]["cagr"]) < 1e-12, (lev, st, w)
            deco[(lev, st, w)] = m
            fl = r["phase_results"]["0"]["operating"]["flat_share"]
            lines.append(f"| {lev:g}x | {stages[st]} | {w} | {pc(m['cagr'])} | {m['logg']:.3f} | {m['mu']:.3f} | {m['sd']:.3f} | {m['drag']:.3f} | {m['sharpe']:.2f} | {pc(m['mdd'])} | {pc(m['imdd'])} | {r['kills_per_year']:.2f} | {pc(np.mean([r['phase_results'][str(p)]['operating']['flat_share'] for p in (0,1,2)]))} | {r['liquidations']} |")
nums["deco"] = {f"{k[0]:g}|{k[1]}|{k[2]}": v for k, v in deco.items()}
nums["deco_liq"] = {f"{lev:g}|{st}": next(x for x in V3 if x["params"].get("family") == "decomposition" and x["params"]["lev"] == lev and x["params"]["stage"] == st)["liquidations"] for lev in (2., 3., 4.) for st in range(5)}

# ---------------- B kill sweep
lines += ["", "### B. Kill sweep (no stops, crash filter live, costs/funding on). Cells: IS Calmar_i / OOS Calmar_i (full CAGR; kills per year)", "",
          "Cooldown 0 = permanent halt after the first kill (engine semantics). Kill 'off' = kill >= 100% (liquidation logic still active)."]
sel = {}
kills = (.15, .20, .25, .30, .35, .40, .50, .60, .70); cools = (0, 1, 7, 14, 30)
for lev in (2., 3., 4.):
    live = get(lev); off = get(lev, 1., 14)
    lines += ["", f"#### {lev:g}x  (off: IS/OOS Calmar_i {off['IS']['calmar_i']:.2f}/{off['OOS']['calmar_i']:.2f}, full CAGR {pc(off['full']['cagr'],0)}, liq {off['liquidations']} over 3 phases)", "",
              "| kill \\ cooldown | 0d (permanent) | 1d | 7d | 14d | 30d |", "|---:|---:|---:|---:|---:|---:|"]
    cand = []
    for k in kills:
        cells = []
        for c in cools:
            r = get(lev, k, c)
            if r is None: cells.append("-"); continue
            cells.append(f"{r['IS']['calmar_i']:.2f} / {r['OOS']['calmar_i']:.2f} ({pc(r['full']['cagr'],0)}; {r['kills_per_year']:.1f})")
            cand.append((r['IS']['calmar_i'], k, c, r))
        lines.append(f"| {pc(k,0)} | " + " | ".join(cells) + " |")
    elig = [x for x in cand + [(off['IS']['calmar_i'], 1., 14, off)] if x[3]["IS"]["end"] >= .85 * live["IS"]["end"]]
    elig.sort(key=lambda x: -x[0])
    sel[lev] = elig
    nums[f"kill_top5_{lev:g}"] = [dict(kill=x[1], cool=x[2], is_calmar=x[0], oos_calmar=x[3]["OOS"]["calmar_i"], is_cagr=x[3]["IS"]["cagr"], oos_cagr=x[3]["OOS"]["cagr"]) for x in elig[:5]]
lines += ["", "### B2. IS-selected kill setting per leverage vs live and off (eligible = IS end wealth >= 85% of live IS end wealth)", "",
          "| lev | setting | IS CAGR/iMDD/Calmar | OOS CAGR/iMDD/Calmar | full CAGR/iMDD/Calmar | kills/yr | liq | flat share | 2022 | 2023 | 2024 | 2025 | 2026 |", "|---|---|---|---|---|---:|---:|---:|---:|---:|---:|---:|---:|"]
def setrow(lev, label, r):
    y = yearly(r); fl = np.mean([r['phase_results'][str(p)]['operating']['flat_share'] for p in (0, 1, 2)])
    return f"| {lev:g}x | {label} | {cs(r,'IS')} | {cs(r,'OOS')} | {cs(r,'full')} | {r['kills_per_year']:.2f} | {r['liquidations']} | {pc(fl,0)} | " + " | ".join(pc(y[k], 0) for k in range(2022, 2027)) + " |"
selected_cells = {}
for lev in (2., 3., 4.):
    live = get(lev); off = get(lev, 1., 14); top = sel[lev][0]; sr = top[3]
    selected_cells[lev] = sr
    lines += [setrow(lev, "live 35%/14d", live), setrow(lev, f"IS-selected {pc(top[1],0)}/{top[2]}d" if top[1] < 1 else "IS-selected kill off", sr), setrow(lev, "off", off)]
    if len(sel[lev]) > 1:
        t2 = sel[lev][1]; lines.append(setrow(lev, f"2nd-best {pc(t2[1],0)}/{t2[2]}d" if t2[1] < 1 else "2nd-best off", t2[3]))
lines += ["(per-year columns: calendar-year return, phase mean; 2026 is partial to 10-09)"]
# concentration: selected vs live daily log-return differences
lines += ["", "#### B3. Concentration of the selected-vs-live difference", "", "| lev | selected | full log-wealth gain vs live (phase mean) | top-5 days' share of positive daily log-return differences | top-5 days' dates (phase 0) |", "|---|---|---:|---:|---|"]
for lev in (2., 3., 4.):
    sr = selected_cells[lev]; p = {**dict(kill=.35, cool=14, cost=.001, fund=1), **sr["params"]}
    if (p["kill"], p["cool"]) == (.35, 14): continue
    ra = run_paths(p); rb = run_paths({**p, "kill": .35, "cool": 14})
    sh = []; gain = []; dts = None
    for a, b in zip(ra, rb):
        sa, sb = a["eq"].dropna(), b["eq"].dropna()
        la, lb = np.log(sa.clip(lower=1e-12)).diff().dropna(), np.log(sb.clip(lower=1e-12)).diff().dropna()
        d = (la - lb).dropna(); gain.append(d.sum())
        pos = d[d > 0].sort_values(ascending=False)
        sh.append(pos.iloc[:5].sum() / d[d > 0].sum() if len(pos) else float("nan"))
        if dts is None: dts = [str(x.date()) for x in pos.index[:5]]
    lines.append(f"| {lev:g}x | {pc(p['kill'],0)}/{p['cool']}d | {np.mean(gain):.2f} | {pc(np.nanmean(sh),0)} | {', '.join(dts)} |")
    nums[f"conc_{lev:g}"] = dict(gain=float(np.mean(gain)), top5=float(np.nanmean(sh)), dates=dts)

# ---------------- C / D stop curves
def label_levels(levels, rowsby, base):
    out = {}
    for i, s in enumerate(levels):
        grp = levels[max(0, i - 2): i + 3]; imp = hur = 0
        for t in grp:
            r = rowsby[t]
            ok = all(r[w]["calmar_i"] > base[w]["calmar_i"] and r[w]["cagr"] >= .9 * base[w]["cagr"] for w in ("IS", "OOS"))
            bad = all(r[w]["calmar_i"] < base[w]["calmar_i"] for w in ("IS", "OOS"))
            imp += ok; hur += bad
        n = len(grp)
        out[s] = "helps" if imp / n >= .8 else ("hurts" if hur / n >= .8 else "noise")
    return out
def curve_tables(title, lev, fam, setting_filter, kill, cool, crash, base, tag):
    rs = [r for r in V3 if r["params"].get("family") == fam and r["params"]["lev"] == lev and r["params"]["kill"] == kill and r["params"]["cool"] == cool and r["params"]["crash"] == crash and (setting_filter is None or r["params"].get("setting") == setting_filter)]
    by = {round(r["params"]["s"], 6): r for r in rs}
    levels = sorted(by)
    lab = label_levels(levels, by, base)
    lines.extend(["", f"#### {title}", "", f"No-stop baseline: IS {cs(base,'IS')}, OOS {cs(base,'OOS')}, full {cs(base,'full')}, kills/yr {base['kills_per_year']:.2f}, liq {base['liquidations']}. († = at/after liquidation-equivalent {pc(1/lev,1)})", "",
                  "| s | IS CAGR/iMDD/Calmar | OOS CAGR/iMDD/Calmar | full CAGR/iMDD/Calmar | stops/yr (L/S) | kills/yr | liq | label |", "|---:|---|---|---|---:|---:|---:|---|"])
    for s in levels:
        r = by[s]; dg = "†" if s >= 1 / lev - 1e-9 else ""
        lines.append(f"| {s*100:g}%{dg} | {cs(r,'IS')} | {cs(r,'OOS')} | {cs(r,'full')} | {r['stops_per_year']['long']:.0f}/{r['stops_per_year']['short']:.0f} | {r['kills_per_year']:.2f} | {r['liquidations']} | {lab[s]} |")
    # IS-selected stop
    elig = [s for s in levels if by[s]["IS"]["end"] >= .85 * base["IS"]["end"]]
    best = max(elig, key=lambda s: by[s]["IS"]["calmar_i"]) if elig else None
    both = [s for s in levels if all(by[s][w]["calmar_i"] > base[w]["calmar_i"] and by[s][w]["cagr"] >= .9 * base[w]["cagr"] for w in ("IS", "OOS"))]
    nums[tag] = dict(best_is=best, best_is_row={w: by[best][w] for w in ("IS", "OOS")} if best is not None else None, n_levels=len(levels), both_improve=both,
                     helps=[s for s in levels if lab[s] == "helps"], hurts_n=sum(lab[s] == "hurts" for s in levels), base={w: base[w] for w in ("IS", "OOS", "full")},
                     fullpeak=max(levels, key=lambda s: by[s]["full"]["calmar_i"]), full_calmar_peak=max(by[s]["full"]["calmar_i"] for s in levels))
    lines.append(f"\nIS-selected stop: {('none eligible' if best is None else pc(best,1)+' -> IS/OOS Calmar_i %.2f/%.2f vs baseline %.2f/%.2f' % (by[best]['IS']['calmar_i'], by[best]['OOS']['calmar_i'], base['IS']['calmar_i'], base['OOS']['calmar_i']))}; levels improving Calmar_i in BOTH IS and OOS with CAGR>=0.9x base: {[pc(s,1) for s in both] or 'none'}; 'helps' levels: {[pc(s,1) for s in levels if lab[s]=='helps'] or 'none'}.")
lines += ["", "### C. Extended stop curves (both sides, reentry, fill mode 1, crash filter live)"]
for lev in (2., 3., 4.):
    sr = selected_cells[lev]
    for setting, kill, cool in (("live", .35, 14), ("off", 1., 14), ("selected", sr["params"]["kill"], sr["params"]["cool"])):
        base = get(lev, kill, cool)
        curve_tables(f"{lev:g}x, kill setting '{setting}' ({'off' if kill>=1 else pc(kill,0)+'/'+str(cool)+'d'})", lev, "stop_curve", setting, kill, cool, 1, base, f"C|{lev:g}|{setting}")
lines += ["", "### D. Crash filter OFF (BTC filter disabled) stop curves for the three IS-best (lev, kill) pairs", ""]
pairs = sorted({(r["params"]["lev"], r["params"]["kill"], r["params"]["cool"]) for r in V3 if r["params"].get("family") == "crash_off_curve"})
for lev, kill, cool in pairs:
    base = get(lev, kill, cool, crash=0); on = get(lev, kill, cool, crash=1)
    lines.append(f"{lev:g}x {pc(kill,0)}/{cool}d: baseline crash-ON IS/OOS Calmar_i {on['IS']['calmar_i']:.2f}/{on['OOS']['calmar_i']:.2f}; crash-OFF {base['IS']['calmar_i']:.2f}/{base['OOS']['calmar_i']:.2f} (full CAGR {pc(on['full']['cagr'],0)} vs {pc(base['full']['cagr'],0)}).")
    curve_tables(f"crash OFF, {lev:g}x, kill {pc(kill,0)}/{cool}d", lev, "crash_off_curve", None, kill, cool, 0, base, f"D|{lev:g}|{kill}|{cool}")
(OUT / "v3_tables.md").write_text("\n".join(lines) + "\n")
(OUT / "v3_numbers.json").write_text(json.dumps(nums, indent=1, default=float))
print("done", len(lines))
