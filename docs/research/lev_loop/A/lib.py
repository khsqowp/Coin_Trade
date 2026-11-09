"""BACKTESTER-A runner library (implements prereg.md)."""
from common import *
import itertools, json
from multiprocessing import Pool
from app.rs_lev_a_engine import S_KILL, S_LIQ_TIER, S_LIQ_FLAT, S_CUSH_TIER, S_CUSH_FLAT, S_RUIN, S_MDDI

LEVS = [2.5, 3.0, 3.5, 4.0, 5.0, 6.0]
KILLS = [0.25, 0.35, 0.5, 1.0]          # 1.0 == none
KNAME = {0.25: "0.25", 0.35: "0.35", 0.5: "0.5", 1.0: "none"}
DEPLOY = 0.95
CELLS = [(l, k) for l in LEVS for k in KILLS]
CURRENT = (4.0, 0.35)
OFFS = list(range(40)); PHASES = [0, 1, 2]
PATHS = [(o, p) for o in OFFS for p in PHASES]
SCEN = {"BASE": (1.0, 0.001), "VOL": (1.5, 0.001), "COST": (1.0, 0.002), "COMB": (1.5, 0.002)}

_P = None; _SIMS = {}

def init():
    global _P, _SIMS
    _P = load_panel()
    _SIMS = {1.0: SimA(_P), 1.5: SimA(stress_panel(_P, 1.5))}
    return _SIMS

def window_idx(win, off):
    S = _SIMS[1.0]
    if win == "IS":
        return S.d_start("2022-01-01") + off, S.d_start("2024-07-01")
    if win == "OOS":
        return S.d_start("2024-07-01") + off, S.nd
    return S.d_start("2022-01-01") + off, S.nd

def one(args):
    cell, win, scen, kmode, off, ph, keep = args
    lev, kill = cell
    vol, cost = SCEN[scen]
    S = _SIMS[vol]
    d0, d1 = window_idx(win, off)
    r = S.run_a(lev, DEPLOY, kill, cool=int(os.environ.get('LEV_COOL', '14')), kill_mode=kmode, cost=cost, phase=ph, d0=d0, d1=d1)
    eq = r["eq"][d0:d1]; fin = np.isfinite(eq)
    eqf = eq[fin]
    ruin = bool(r["st"][S_RUIN]) or len(eqf) == 0 or eqf[-1] <= 0
    wend = 0.0 if ruin else float(eqf[-1])
    days = int(fin.sum())
    g = float(np.log(wend) / (days / 365.0)) if wend > 0 else -np.inf
    # closing MDD
    hw = np.maximum.accumulate(np.r_[1.0, eqf])[1:]
    mdd = float(np.max(1 - eqf / hw)) if len(eqf) else 1.0
    st = r["st"]
    out = dict(cell=cell, win=win, scen=scen, kmode=kmode, off=off, ph=ph, wend=wend, g=g, days=days, mdd=mdd,
               mddi=float(st[S_MDDI]), kills=int(st[S_KILL]), liq_tier=int(st[S_LIQ_TIER] >= 0), liq_flat=int(st[S_LIQ_FLAT] >= 0),
               cush_tier=float(st[S_CUSH_TIER]), cush_flat=float(st[S_CUSH_FLAT]), ruin=ruin,
               liq_flat_day=int(st[S_LIQ_FLAT]))
    # concentration
    if keep:
        gain = wend - 1.0
        tp = r["tr_pnl"]; ts = r["tr_sym"]
        sp = np.bincount(ts, weights=tp, minlength=len(S.names)) + r["sym_fund"]
        top5t = float(np.sort(tp)[-5:].sum()) if len(tp) >= 5 else float(tp.sum())
        top5s = float(np.sort(sp)[-5:].sum())
        out.update(gain=gain, top5_trades=top5t, top5_syms=top5s, ntr=len(tp),
                   top_syms=[S.names[j] for j in np.argsort(-sp)[:5]])
        out["eq"] = eqf.astype(np.float32)
    return out

def run_batch(tasks, procs=10):
    init()
    with Pool(procs, initializer=init) as pool:
        return pool.map(one, tasks, chunksize=8)
