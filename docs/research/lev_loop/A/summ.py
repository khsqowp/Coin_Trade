"""Aggregation helpers."""
import pickle, numpy as np, pandas as pd
from lib import CELLS, CURRENT, LEVS, KILLS, KNAME, PATHS

def load(win):
    df = pd.DataFrame(pickle.load(open(f"res_{win}.pkl", "rb")))
    df["lev"] = df["cell"].map(lambda c: c[0]); df["kill"] = df["cell"].map(lambda c: c[1])
    return df

def agg(df, kmode, scen="BASE"):
    d = df[(df.kmode == kmode) & (df.scen == scen)]
    rows = []
    for cell, g in d.groupby("cell"):
        fin = g[np.isfinite(g.g)]
        rows.append(dict(cell=cell, lev=cell[0], kill=cell[1], n=len(g),
                         g_mean=(fin.g.sum() / len(g)) if len(fin) == len(g) else -np.inf, g_med=g.g.median(),
                         cagr_med=np.exp(g.g.median()) - 1, w_med=g.wend.median(), w_p10=g.wend.quantile(.1), w_p90=g.wend.quantile(.9),
                         mdd_med=g.mdd.median(), mdd_p90=g.mdd.quantile(.9), mdd_max=g.mdd.max(),
                         mddi_med=g.mddi.median(), mddi_p90=g.mddi.quantile(.9), mddi_max=g.mddi.max(),
                         kills_mean=g.kills.mean(), kills_p90=g.kills.quantile(.9),
                         liq_tier=int(g.liq_tier.sum()), liq_flat=int(g.liq_flat.sum()), ruin=int(g.ruin.sum()),
                         cush_tier_min=g.cush_tier.min(), cush_flat_min=g.cush_flat.min(), cush_flat_p10=g.cush_flat.quantile(.1)))
    return pd.DataFrame(rows).set_index("cell")

def admissible(df, kmode):
    out = {}
    for cell in CELLS:
        ok = True; det = {}
        for sc in ("BASE", "VOL", "COST", "COMB"):
            g = df[(df.cell == cell) & (df.kmode == kmode) & (df.scen == sc)]
            lt, lf = int(g.liq_tier.sum()), int(g.liq_flat.sum()); det[sc] = (lt, lf)
            if sc != "COMB" and (lt > 0 or lf > 0 or g.ruin.any()):
                ok = False
        out[cell] = (ok, det)
    return out

def neighbors(cell):
    l, k = cell; li = LEVS.index(l); ki = KILLS.index(k); nb = []
    for dl in (-1, 1):
        if 0 <= li + dl < len(LEVS): nb.append((LEVS[li + dl], k))
    for dk in (-1, 1):
        if 0 <= ki + dk < len(KILLS): nb.append((l, KILLS[ki + dk]))
    return nb

def select(df, kmode):
    A = agg(df, kmode); adm = admissible(df, kmode)
    cands = [c for c in CELLS if c[0] >= 4.0 and adm[c][0]]
    order = sorted(cands, key=lambda c: -A.loc[[c]].g_mean.iloc[0] if False else -A.loc[[c], "g_mean"].iloc[0]) if False else sorted(cands, key=lambda c: -A.g_mean[c])
    trail = []
    for c in order:
        gs = A.g_mean[c]
        nb = {n: A.g_mean[n] for n in neighbors(c)}
        ok = all(v >= 0.75 * gs for v in nb.values())
        trail.append(dict(cell=list(c), g=float(gs), plateau=bool(ok), neighbors={f"{n[0]}|{KNAME[n[1]]}": float(v) for n, v in nb.items()},
                          cliff=[f"{n[0]}|{KNAME[n[1]]}" for n in nb if not adm[n][0]]))
        if ok:
            return dict(kmode=kmode, selected=list(c), trail=trail, n_cands=len(cands)), A, adm
    allad = [c for c in CELLS if adm[c][0]]
    best_any = max(allad, key=lambda c: A.g_mean[c]) if allad else None
    return dict(kmode=kmode, selected=None, trail=trail, n_cands=len(cands), best_any=list(best_any) if best_any else None), A, adm
