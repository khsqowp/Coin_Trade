"""Cadence research runner (offline; reads .rs_cache/vision via rs_cadence_data)."""
from __future__ import annotations
import itertools, json, warnings, os
import numpy as np, pandas as pd
from dataclasses import asdict, replace
from app.rs_cadence_data import load
from app.rs_cadence_engine import Engine, Cfg, FEE

warnings.filterwarnings("ignore")
IS = ("2022-01-01", "2024-06-30"); OOS = ("2024-07-01", None)
FOLDS = [("2022-01-01", "2023-04-30"), ("2023-05-01", "2024-08-31"), ("2024-09-01", None)]
LBS = [5, 7, 10, 14, 21, 30, 45, 60]
MULTI = [(7, 14, 30), (5, 14, 30, 60), (14, 28), (7, 21), (10, 20, 40)]

def key(c): return json.dumps(asdict(c), sort_keys=True, default=str)

class Ev:
    def __init__(self, E): self.E, self.cache = E, {}
    def res(self, c):
        k = key(c)
        if k not in self.cache: self.cache[k] = self.E.run(c)
        return self.cache[k]
    def m(self, c, w): return self.E.metrics(self.res(c), *w)

def ok(m): return m is not None and m["MDD"] <= 0.25 and m["worst"] > -0.06

def grid():
    g = []
    for N, lb, k in itertools.product(range(1, 15), LBS, range(4, 16)):
        g.append(("A", Cfg(lbs=(lb,), k=k, cadence=N)))
    for N, band, lb, k in itertools.product([1, 2, 3, 5, 7], range(0, 7), [7, 14, 21, 30], [6, 8, 10, 12]):
        g.append(("B", Cfg(lbs=(lb,), k=k, cadence=N, band=band)))
    for lb, k, band, dr, de, cap, mn in itertools.product([14, 21], [8, 12], [0, 2, 4], [1, 2, 3, 4], [0.1, 0.25, 0.5, 1e9], [5, 7, 10, 14], [1, 2, 3]):
        if mn < cap: g.append(("C", Cfg(mode="event", lbs=(lb,), k=k, band=band, drift=dr, decay=de, cap=cap, minimum=mn)))
    for N, inv, lb, k in itertools.product([2, 3, 4, 5, 7], [False, True], [7, 14, 21], [8, 12]):
        g.append(("D", Cfg(mode="vol", lbs=(lb,), k=k, cadence=N, inverse=inv)))
    for f, N, lb, k in itertools.product([0.25, 0.5, 0.75], [1, 2, 3, 5, 7], [7, 14, 21], [8, 12]):
        g.append(("E", Cfg(lbs=(lb,), k=k, cadence=N, frac=f)))
    for ls, N, k, band in itertools.product(MULTI, [1, 2, 3, 5, 7], range(4, 16), [0, 2]):
        g.append(("F", Cfg(lbs=ls, k=k, cadence=N, band=band)))
    return g

def neighbours(c):
    """+-1 step on each ordinal parameter."""
    out = []
    if len(c.lbs) == 1 and c.lbs[0] in LBS:
        i = LBS.index(c.lbs[0])
        for j in (i - 1, i + 1):
            if 0 <= j < len(LBS): out.append(replace(c, lbs=(LBS[j],)))
    out += [replace(c, k=c.k + d) for d in (-1, 1) if 4 <= c.k + d <= 15]
    if c.mode in ("fixed", "vol"):
        out += [replace(c, cadence=c.cadence + d) for d in (-1, 1) if 1 <= c.cadence + d <= 14]
    if c.mode in ("fixed", "event"):
        out += [replace(c, band=c.band + d) for d in (-1, 1) if 0 <= c.band + d <= 6]
    if c.mode == "event":
        out += [replace(c, cap=c.cap + d) for d in (-2, 2) if 3 <= c.cap + d <= 20]
        out += [replace(c, drift=c.drift + d) for d in (-1, 1) if c.drift + d >= 1]
        if c.decay < 1e8: out += [replace(c, decay=c.decay * f) for f in (0.6, 1.6)]
    if c.frac < 1: out += [replace(c, frac=min(1.0, c.frac + d)) for d in (-0.25, 0.25) if 0.25 <= c.frac + d <= 1]
    return out

def short(m):
    if m is None: return "n/a"
    return (f"CAGR {m['CAGR']*100:+6.1f}% MDD {m['MDD']*100:5.1f}% Calmar {m['Calmar']:4.2f} Sh {m['Sharpe']:4.2f} "
            f"worst {m['worst']*100:5.1f}% reb/yr {m['reb_yr']:5.0f} trades/yr {m['trades_yr']:6.0f} fee {m['fee_yr']*100:4.1f}%/yr fund {m['fund_yr']*100:+4.1f}%/yr")


def chain_metrics(E, parts):
    """parts: list of (net_slice, dates_slice) concatenated -> metrics dict."""
    r = np.concatenate([a for a, _ in parts]); d = np.concatenate([b for _, b in parts])
    yrs = len(r) / 365.0; eq = np.cumprod(1 + r); pk = np.maximum.accumulate(np.r_[1.0, eq])[1:]
    mdd = float((1 - eq / pk).max()); cagr = float(eq[-1] ** (1 / yrs) - 1)
    sd = r.std(ddof=1)
    return dict(CAGR=cagr, MDD=mdd, Calmar=cagr / mdd if mdd > 0 else 0.0, Sharpe=float(r.mean() / sd * np.sqrt(365)),
                worst=float(r.min()), days=len(r))

def walk_forward(E, ev, rows, label_filter=None):
    """Expanding-window: every 6 months from 2023-01 pick best train Calmar (constraints), trade next 6 months."""
    cuts = pd.date_range("2023-01-01", "2026-07-01", freq="6MS", tz="UTC")
    cuts = list(cuts) + [pd.Timestamp("2026-10-10", tz="UTC")]
    parts, picks = [], []
    cand = [r for r in rows if label_filter is None or r[0] in label_filter]
    for a, b in zip(cuts[:-1], cuts[1:]):
        best, bm = None, -9
        for fam, c, _ in cand:
            m = ev.E.metrics(ev.res(c), "2022-01-01", str((a - pd.Timedelta(days=1)).date()))
            if m and ok(m) and m["Calmar"] > bm: best, bm = (fam, c), m["Calmar"]
        fam, c = best
        res = ev.res(c)
        mask = (E.dates >= a) & (E.dates < b)
        parts.append((res["net"][mask], E.dates[mask]))
        picks.append(dict(test_from=str(a.date()), fam=fam, cfg=dict(L=c.lbs, K=c.k, N=c.cadence, band=c.band, mode=c.mode, frac=c.frac), train_calmar=bm))
    return chain_metrics(E, parts), picks

def lookahead_test(E):
    c = Cfg(lbs=(14,), k=8, cadence=3)
    r1 = E.run(c, trace=True)
    T = int(E.dates.searchsorted(pd.Timestamp("2024-03-01", tz="UTC")))
    px = E.px.copy(); rng = np.random.default_rng(0)
    E2 = Engine.__new__(Engine); E2.__dict__.update(E.__dict__)
    E2.px = px.copy(); E2.px[T + 1:] *= rng.uniform(.5, 1.5, px[T + 1:].shape)
    E2.ret = np.full_like(E2.px, np.nan); E2.ret[1:] = E2.px[1:] / E2.px[:-1] - 1
    E2._sig = {}
    r2 = E2.run(c, trace=True)
    same = np.allclose(r1["hist"][:T + 1], r2["hist"][:T + 1]) and np.allclose(r1["net"][:T + 1], r2["net"][:T + 1])
    return bool(same)

def main():
    data = load(); E = Engine(data); ev = Ev(E)
    out = {"assumptions": dict(fee_per_side=FEE, funding_coverage_days_ge2of3=E.fund_cov, universe=len(E.syms),
                               last_date=str(E.dates[-1].date()), sim_start=str(E.dates[E.start].date()))}
    print("assumptions", out["assumptions"])
    la = lookahead_test(E); out["lookahead_test_passed"] = la; print("lookahead test passed:", la)
    ref = {"live 14/N2/K12": Cfg(lbs=(14,), k=12, cadence=2), "valid 14/N3/K8": Cfg(lbs=(14,), k=8, cadence=3)}
    out["reference"] = {}
    for n, c in ref.items():
        out["reference"][n] = {w: ev.m(c, wi) for w, wi in [("IS", IS), ("OOS", OOS), ("full", (None, None))]}
        for w in ("IS", "OOS", "full"): print(f"{n:16} {w:4}", short(out["reference"][n][w]))
    rows = []
    for fam, c in grid():
        mi = ev.m(c, IS)
        if mi is None: continue
        rows.append((fam, c, mi))
    print("evaluated", len(rows))
    out["families"] = {}
    chosen = []
    for fam in "ABCDEF":
        fr = [r for r in rows if r[0] == fam]
        good = sorted([r for r in fr if ok(r[2])], key=lambda r: -r[2]["Calmar"])
        print(f"\n== Family {fam}: {len(fr)} configs, {len(good)} pass constraints (IS)")
        out["families"][fam] = []
        for _, c, mi in good[:3]:
            nb = neighbours(c)
            nc = [ev.m(x, IS)["Calmar"] for x in nb if ev.m(x, IS)]
            rob = dict(n=len(nc), min=float(min(nc)) if nc else None, median=float(np.median(nc)) if nc else None,
                       robust=bool(nc and min(nc) >= 0.8 * mi["Calmar"]), robust_median=bool(nc and np.median(nc) >= 0.8 * mi["Calmar"]))
            ent = dict(cfg=asdict(c), IS=mi, OOS=ev.m(c, OOS), full=ev.m(c, (None, None)),
                       folds=[ev.m(c, f) for f in FOLDS], robustness=rob)
            out["families"][fam].append(ent)
            print(f" {asdict(c)}\n   IS  {short(mi)}\n   OOS {short(ent['OOS'])}\n   rob {rob}")
            for i, f in enumerate(ent["folds"]): print(f"   F{i+1}  {short(f)}")
        if good: chosen.append((fam, good[0][1]))
    # robust selection: maximise worst-of-two IS halves
    H1, H2 = ("2022-01-01", "2023-03-31"), ("2023-04-01", "2024-06-30")
    out["robust_sel"] = {}
    print("\n== robust selection (max min Calmar over IS halves, constraints on IS)")
    for fam in "ABCDEF":
        sc = []
        for f, c, mi in rows:
            if f != fam or not ok(mi): continue
            a, b = ev.m(c, H1), ev.m(c, H2)
            if a and b: sc.append((min(a["Calmar"], b["Calmar"]), c, mi))
        sc.sort(key=lambda x: -x[0]); out["robust_sel"][fam] = []
        for v, c, mi in sc[:2]:
            nc = [ev.m(x, IS)["Calmar"] for x in neighbours(c) if ev.m(x, IS)]
            ent = dict(cfg=asdict(c), minhalf=v, IS=mi, OOS=ev.m(c, OOS), full=ev.m(c, (None, None)), folds=[ev.m(c, f) for f in FOLDS],
                       nb_min=float(min(nc)) if nc else None, nb_med=float(np.median(nc)) if nc else None)
            out["robust_sel"][fam].append(ent)
            print(f" {fam} L{c.lbs} K{c.k} N{c.cadence} band{c.band} frac{c.frac} {c.mode} drift{c.drift} decay{c.decay} cap{c.cap} min{c.minimum} inv{c.inverse} | minhalf {v:.2f}")
            print("   IS ", short(mi)); print("   OOS", short(ent["OOS"])); print("   nb", ent["nb_min"], ent["nb_med"])
            for i, f in enumerate(ent["folds"]): print(f"   F{i+1}", short(f))
    print("\n== expanding walk-forward, 6-month steps from 2023-01 (re-pick by train Calmar w/ constraints)")
    out["walk_forward"] = {}
    for lab, filt in [("all", None), ("A", "A"), ("B", "B"), ("C", "C"), ("D", "D"), ("E", "E"), ("F", "F")]:
        m, picks = walk_forward(E, ev, rows, filt)
        out["walk_forward"][lab] = dict(metrics=m, picks=picks)
        print(f" {lab}: CAGR {m['CAGR']*100:+.1f}% MDD {m['MDD']*100:.1f}% Calmar {m['Calmar']:.2f} Sh {m['Sharpe']:.2f} worst {m['worst']*100:.1f}%")
    # same window for baseline configs
    for n, c in ref.items():
        cuts0 = E.dates >= pd.Timestamp("2023-01-01", tz="UTC")
        m = chain_metrics(E, [(ev.res(c)["net"][cuts0], E.dates[cuts0])])
        print(f" ref {n} same window: CAGR {m['CAGR']*100:+.1f}% MDD {m['MDD']*100:.1f}% Calmar {m['Calmar']:.2f}")
        out["walk_forward"]["ref_"+n] = m
    # alignment: fixed cadence start offsets, k=8 lb=14
    out["alignment"] = {}
    print("\n== alignment (lb14,K8): Calmar/CAGR across start offsets, full-period, new costs")
    for N in [2, 3, 4, 5, 7]:
        cs, cg = [], []
        for off in range(N):
            m = ev.m(Cfg(lbs=(14,), k=8, cadence=N, offset=off), (None, None))
            cs.append(m["Calmar"]); cg.append(m["CAGR"])
        out["alignment"][N] = dict(calmar=cs, cagr=cg)
        print(f" N={N}: Calmar min/med/max {min(cs):.2f}/{np.median(cs):.2f}/{max(cs):.2f}  CAGR {min(cg)*100:.1f}/{np.median(cg)*100:.1f}/{max(cg)*100:.1f}%")
    # UTC daily-bar offset (1h data available)
    out["utc_offset"] = {}
    print("\n== UTC daily bar offset (hours): lb14,K8")
    for hh in [0, 4, 8, 12, 16, 20]:
        Eh = Engine(load(offset_hours=hh), sim_start="2022-01-01")
        for N in (2, 3):
            m = Eh.metrics(Eh.run(Cfg(lbs=(14,), k=8, cadence=N)), None, None)
            out["utc_offset"][f"{hh}h_N{N}"] = m
            print(f" +{hh:2d}h N={N}: {short(m)}")
    # cadence profile table (lb14, K8 / K12)
    print("\n== fixed cadence table lb14 full period")
    out["cadence_table"] = {}
    for k in (8, 12):
        for N in range(1, 15):
            m = ev.m(Cfg(lbs=(14,), k=k, cadence=N), (None, None))
            out["cadence_table"][f"K{k}_N{N}"] = m
            print(f" K{k} N={N:2d}: {short(m)}")
    # fee sensitivity for finalists
    out["fee_sens"] = {}
    for fam, c in chosen:
        for fee in (0.0005, 0.001, 0.0015, 0.002):
            m = E.metrics(E.run(c, fee=fee), None, None)
            out["fee_sens"][f"{fam}_{fee}"] = m
    os.makedirs("docs/research", exist_ok=True)
    json.dump(out, open("docs/research/cadence_results.json", "w"), indent=1, default=str)

if __name__ == "__main__":
    main()
