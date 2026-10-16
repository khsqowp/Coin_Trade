"""Offline map: broad pass over every (family, tf, params) x construction x K x cadence x cost x sizing.
Selection window only (sim ends before the frozen holdout). Writes a case table (csv.gz in scratch) + prints counts."""
from __future__ import annotations
import itertools, json, os, sys, time, importlib
import numpy as np, pandas as pd
from multiprocessing import Pool
from app.rs_map_off_core import *
from app.rs_map_off_data import load_data, SCRATCH

OUT = os.path.join(SCRATCH, "mapoff")
COSTS = {"c10F": dict(cost=0.001, fund=1), "c04": dict(cost=0.0004, fund=0)}
SIZES = {"x1": dict(vt=0.0), "vt20": dict(vt=0.20, cap=1.5)}
OVL_MODES = ("tilt0.5", "tilt1.0", "agree", "gate")
_G = {}


def registry():
    reg = {}
    for m in ("a", "b", "c"):
        try:
            mod = importlib.import_module(f"app.rs_map_off_fam_{m}")
        except Exception as e:  # noqa
            print("missing/failed family module", m, repr(e)[:200], file=sys.stderr); continue
        for k, v in mod.FAMILIES.items():
            reg[k] = v
    return reg


def grid_points(fam):
    ax = list(fam["grid"].keys())
    for vals in itertools.product(*[fam["grid"][a] for a in ax]):
        yield dict(zip(ax, vals))


def units(reg):
    out = []
    for name, f in reg.items():
        for tf in f["tfs"]:
            for p in grid_points(f):
                out.append((name, tf, p))
    return out


def _init():
    D = load_data(); cx = Ctx(D)
    _G["D"] = D; _G["cx"] = cx; _G["reg"] = registry()
    # warm numba
    sc = rotation_score(cx, (14,)); run_engine(cx, sc, 8, 3, 0, d1=cx.d_hold)


def _row(base, m, m_f, extra):
    r = dict(base); r.update(extra)
    if m is None:
        return None
    r.update(cagr=m["cagr"], mdd=m["mdd"], calmar=m["calmar"], sharpe=m["sharpe"], worst=m["worst"])
    for k, mf in enumerate(m_f):
        r[f"f{k+1}_cagr"] = mf["cagr"] if mf else np.nan
        r[f"f{k+1}_calmar"] = mf["calmar"] if mf else np.nan
    return r


def work(u):
    name, tf, p = u
    cx = _G["cx"]; D = _G["D"]; fam = _G["reg"][name]
    try:
        pos, strength = fam["fn"](D, tf, **p)
    except Exception as e:  # noqa
        return [dict(family=name, tf=tf, params=json.dumps(p, sort_keys=True), cons="ERROR", err=repr(e)[:120])]
    pos = np.asarray(pos, float); strength = np.asarray(strength, float)
    rows = []
    pj = json.dumps(p, sort_keys=True)
    d1 = cx.d_hold
    i0, i1 = cx.d0, d1
    fl_ix = [cx.widx(a, b) for a, b in FOLDS]
    base = dict(family=name, tf=tf, params=pj)
    on_frac = float(np.nanmean(pos[cx.d0:d1] > 0))

    def emit(cons, K, cad, wt, mode, rs_by_cs):
        for cs_id, rs in rs_by_cs.items():
            m = phase_mets(rs, i0, i1)
            mf = [phase_mets(rs, a, b) for a, b in fl_ix]
            r = _row(base, m, mf, dict(cons=cons, K=K, cad=cad, wt=wt, mode=mode, cs=cs_id, on_frac=on_frac))
            if r is not None:
                rows.append(r)

    def run_variants(runner, rebal):
        """runner(phase, cost, fund, vt, cap)->eq. returns {cs_id: [rets per phase]}"""
        out = {}
        for cn, cc in COSTS.items():
            for sn, sz in SIZES.items():
                out[f"{cn}|{sn}"] = [rets(runner(ph, cc["cost"], cc["fund"], sz.get("vt", 0.0), sz.get("cap", 1.5))) for ph in range(rebal)]
        return out

    # (ii) cross-sectional dollar-neutral long-short
    sc = ls_score(cx, strength)
    for K in KS:
        for cad in CADENCES:
            rs = run_variants(lambda ph, c, f, vt, cap: run_engine(cx, sc, K, cad, ph, c, f, vt, cap, 1, None, d1)[0], cad)
            emit("LS", K, cad, "ew", "", rs)
    # (i) per-symbol signals -> long-only equal weight (+ inverse-vol)
    for iv in (False, True):
        W = w_longonly_ew(cx, pos, iv)
        for cad in CADENCES:
            rs = run_variants(lambda ph, c, f, vt, cap: run_w(cx, W, cad, ph, c, f, vt, cap, None, d1), cad)
            emit("LO_EW", 0, cad, "iv" if iv else "ew", "", rs)
    # (iii) top-N concentrated long-only + BTC>SMA200 gate
    for iv in (False, True):
        for K in KS:
            W = w_topn_gate(cx, pos, strength, K, iv, True)
            for cad in CADENCES:
                rs = run_variants(lambda ph, c, f, vt, cap: run_w(cx, W, cad, ph, c, f, vt, cap, None, d1), cad)
                emit("LO_TOPN", K, cad, "iv" if iv else "ew", "", rs)
    # (iv) overlay on live rotation 14d/3d/K8 (model A = live-faithful quantity keeping) incl. live crash filter
    for mode in OVL_MODES:
        if mode == "gate":
            sc2 = rotation_score(cx, (14,)); fl = overlay_flat(cx, pos, mode)
        else:
            sc2 = overlay_score(cx, pos, strength, mode); fl = cx.crash
        rs = run_variants(lambda ph, c, f, vt, cap: run_engine(cx, sc2, 8, 3, ph, c, f, vt, cap, 0, fl, d1)[0], 3)
        emit("OVL", 8, 3, "-", mode, rs)
    return rows


def main(nproc=4, limit=None):
    reg = registry()
    us = units(reg)
    if limit:
        us = us[:limit]
    print("families", len(reg), "units", len(us), flush=True)
    t = time.time(); rows = []
    with Pool(nproc, initializer=_init) as pool:
        for k, r in enumerate(pool.imap_unordered(work, us, chunksize=2)):
            rows.extend(r)
            if k % 100 == 0:
                print(k, len(rows), f"{time.time()-t:.0f}s", flush=True)
    df = pd.DataFrame(rows)
    os.makedirs(OUT, exist_ok=True)
    df.to_csv(os.path.join(OUT, "cases.csv.gz"), index=False)
    print("rows", len(df), f"{time.time()-t:.0f}s")


if __name__ == "__main__":
    lim = int(sys.argv[1]) if len(sys.argv) > 1 else None
    main(3, lim)
