"""Alignment-neutral evaluation: staggered tranches (N equal sub-books, offsets 0..N-1 -> 1/N of the book
re-targeted daily). Return series = mean over offsets of single-offset series (fees per tranche, no
cross-netting => conservative). Also reports per-offset spread."""
from __future__ import annotations
import itertools, json, warnings
import numpy as np, pandas as pd
from dataclasses import asdict, replace
from app.rs_cadence_data import load
from app.rs_cadence_engine import Engine, Cfg
from app.rs_cadence_run import IS, OOS, FOLDS, MULTI, short, ok

warnings.filterwarnings("ignore")

def stag(E, c, cache={}):
    k = (c.lbs, c.k, c.cadence, c.band, c.mode)
    if k in cache: return cache[k]
    rs = [E.run(replace(c, offset=o)) for o in range(c.cadence)]
    out = {f: np.mean([r[f] for r in rs], axis=0) for f in ("net", "fees", "funding", "turn", "trd", "reb")}
    out["start"] = rs[0]["start"]; out["per_offset"] = rs
    cache[k] = out
    return out

def spread(E, c, w):
    ms = [E.metrics(r, *w) for r in stag(E, c)["per_offset"]]
    cal = [m["Calmar"] for m in ms]
    return min(cal), float(np.median(cal)), max(cal)

def main():
    E = Engine(load()); out = {}
    lbsets = [(7,), (14,), (21,), (30,)] + MULTI
    rows = []
    for ls, N, k, band in itertools.product(lbsets, range(1, 11), range(6, 16), [0, 2, 4]):
        c = Cfg(lbs=ls, k=k, cadence=N, band=band)
        m = E.metrics(stag(E, c), *IS)
        if m: rows.append((c, m))
    print("evaluated", len(rows))
    good = sorted([r for r in rows if ok(r[1])], key=lambda r: -r[1]["Calmar"])
    print(len(good), "pass constraints on IS (staggered)")
    base = [("live 14/N2/K12", Cfg(lbs=(14,), k=12, cadence=2)), ("valid 14/N3/K8", Cfg(lbs=(14,), k=8, cadence=3))]
    out["ref"] = {}
    for n, c in base:
        s = stag(E, c)
        out["ref"][n] = {w: E.metrics(s, *wi) for w, wi in [("IS", IS), ("OOS", OOS), ("full", (None, None))]}
        print(f"{n:15} staggered full", short(out["ref"][n]["full"]))
        print(f"{'':15} staggered  OOS", short(out["ref"][n]["OOS"]), " single-offset Calmar min/med/max full", [round(x, 2) for x in spread(E, c, (None, None))])
    out["top"] = []
    seen = set()
    for c, mi in good[:40]:
        s = stag(E, c)
        nb = []
        for d in [dict(k=c.k - 1), dict(k=c.k + 1), dict(cadence=c.cadence - 1), dict(cadence=c.cadence + 1), dict(band=max(0, c.band - 2)), dict(band=c.band + 2)]:
            cc = replace(c, **d)
            if cc.k < 4 or cc.cadence < 1 or cc.band > 6: continue
            m = E.metrics(stag(E, cc), *IS)
            if m: nb.append(m["Calmar"])
        ent = dict(cfg=asdict(c), IS=mi, OOS=E.metrics(s, *OOS), full=E.metrics(s, None, None),
                   folds=[E.metrics(s, *f) for f in FOLDS], nb_min=min(nb), nb_med=float(np.median(nb)),
                   offset_spread_full=spread(E, c, (None, None)))
        out["top"].append(ent)
    out["top"].sort(key=lambda e: -(min(e["OOS"]["Calmar"], e["IS"]["Calmar"]) if e["OOS"] else -9))
    for e in out["top"][:12]:
        c = e["cfg"]
        print(f"L{c['lbs']} K{c['k']} N{c['cadence']} band{c['band']}  nb min/med {e['nb_min']:.2f}/{e['nb_med']:.2f} offset-spread(full Calmar) {[round(x,2) for x in e['offset_spread_full']]}")
        print("   IS  ", short(e["IS"])); print("   OOS ", short(e["OOS"])); print("   full", short(e["full"]))
        for i, f in enumerate(e["folds"]): print(f"   F{i+1}  ", short(f))
    # staggered neighbourhood map: Calmar IS+OOS by N for lb14 K8,K12 and (7,14,30) K15
    print("\n== staggered cadence profile (full period Calmar / CAGR / MDD / fee)")
    out["profile"] = {}
    for name, ls, k, band in [("L14 K8", (14,), 8, 0), ("L14 K12", (14,), 12, 0), ("L14 K12 b2", (14,), 12, 2), ("L(7,14,30) K15 b2", (7, 14, 30), 15, 2), ("L(14,28) K12", (14, 28), 12, 0)]:
        for N in range(1, 15):
            m = E.metrics(stag(E, Cfg(lbs=ls, k=k, cadence=N, band=band)), None, None)
            oo = E.metrics(stag(E, Cfg(lbs=ls, k=k, cadence=N, band=band)), *OOS)
            out["profile"][f"{name}_N{N}"] = dict(full=m, OOS=oo)
            print(f" {name:18} N={N:2d} full Calmar {m['Calmar']:5.2f} CAGR {m['CAGR']*100:+5.1f}% MDD {m['MDD']*100:4.1f}% fee {m['fee_yr']*100:4.1f}% | OOS Calmar {oo['Calmar']:5.2f} CAGR {oo['CAGR']*100:+5.1f}%")
    json.dump(out, open("docs/research/cadence_stagger_results.json", "w"), indent=1, default=str)

if __name__ == "__main__":
    main()
