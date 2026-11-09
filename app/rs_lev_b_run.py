"""BACKTESTER-B lev_loop: design registry + jittered-start runner (OFFLINE research only).
Usage (venv with numba):  python -I app/rs_lev_b_run.py <outdir> [designs comma-sep] [windows comma-sep]
Protocol: 40 start offsets (0..39 d) x rebalance phases 0..2 = 120 paths per (design, trigger, window, scenario).
Windows: IS = 2022-01-01..2024-06-30, OOS = 2024-07-01..panel end (fresh start with equity 1), FULL = 2022-01-01.. end.
Triggers: 1 = hourly WORST-case equity (PRIMARY, prescribed), 2 = hourly close-mark equity, 0 = daily close (V0 convention).
Scenarios: sc0 base/tiered-MMR, sc1 base/flat-3%, sc2 vol x1.5 (flat), sc3 cost x2 (fees, slippage, funding; flat),
           sc4 adverse-mark execution (trigger 1 only; flat)."""
from __future__ import annotations
import os, pickle, sys, time
sys.dont_write_bytecode = True
import numpy as np
import pandas as pd

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
from app.rs_final_data import load_panel
from app.rs_lev_b_engine import BSim, pbvec

OFFS = range(40)
PHASES = range(3)
BASE = dict(rebal=3, K=8, deploy=0.95, cool=14, kill=0.35, cost=0.001, fund=1)
LA = dict(nr=2, hw=30, rec_frac=0.5)
LB = dict(nr=3, hw=30, rec_frac=0.5)
RD_A, RM_A = [0.15, 0.25, 0, 0], [0.5, 0.25, 1, 1]
RD_B, RM_B = [0.10, 0.20, 0.30, 0], [0.7, 0.4, 0.2, 1]


def D(lev=4.0, kill=0.35, cool=14, pb=None, rd=None, rm=None, desc="", ref=False):
    return dict(lev=lev, kill=kill, cool=cool, pb=pb or {}, rd=rd, rm=rm, desc=desc, ref=ref)


DESIGNS = {
    "D00": D(desc="V0 live: lev4 x.95, kill35 cool14, no norm"),
    "D01": D(pb=dict(norm=1), desc="control: V0 + gross normalisation at each rebalance"),
    "D02": D(lev=5.0, desc="blunt kill, lev5"),
    "D03": D(lev=6.0, desc="blunt kill, lev6"),
    "D04": D(lev=3.0, ref=True, desc="REFERENCE ONLY (lowers leverage, owner-ineligible): lev3"),
    "D05": D(cool=3, desc="V0 cooldown 3d"),
    "D06": D(cool=7, desc="V0 cooldown 7d"),
    "D07": D(pb=dict(norm=1, re_m=0.5, re_days=14), desc="V0 + re-entry at 0.5x size for 14d"),
    "D08": D(kill=0.45, cool=7, pb=dict(norm=1, **LA), rd=RD_A, rm=RM_A, desc="ladder A (15%->.5, 25%->.25, 30d roll HWM), hard kill45 cool7, lev4"),
    "D09": D(kill=0.45, cool=7, pb=dict(norm=1, **LB), rd=RD_B, rm=RM_B, desc="ladder B (10/20/30 -> .7/.4/.2), hard kill45 cool7, lev4"),
    "D10": D(lev=5.0, kill=0.45, cool=7, pb=dict(norm=1, **LA), rd=RD_A, rm=RM_A, desc="ladder A at lev5"),
    "D11": D(lev=6.0, kill=0.45, cool=7, pb=dict(norm=1, **LA), rd=RD_A, rm=RM_A, desc="ladder A at lev6"),
    "D12": D(pb=dict(norm=1, vt=1.25, vcap=5.0), desc="vol target 1.25 (=lev5 at 25% unit vol), cap5"),
    "D13": D(pb=dict(norm=1, vt=1.50, vcap=6.0), desc="vol target 1.50, cap6"),
    "D14": D(pb=dict(norm=1, vt=1.00, vcap=4.0), desc="vol target 1.00, cap4 (pure de-risk)"),
    "D15": D(kill=0.45, cool=7, pb=dict(norm=1, vt=1.25, vcap=5.0, **LA), rd=RD_A, rm=RM_A, desc="vol target1.25 cap5 + ladder A"),
    "D16": D(pb=dict(norm=1, tt=0.45, tw=100000, vcap=6.0), desc="tail target: worst-hour loss <=45% of equity, expanding window, cap6"),
    "D17": D(lev=6.0, pb=dict(norm=1, expx=0.5), desc="lev6 start, sizing base eq^0.5 (partial compounding)"),
    "D18": D(kill=0.50, desc="V0 with deeper kill 50%"),
    "D19": D(kill=0.45, cool=7, pb=dict(norm=1, vt=1.50, vcap=6.0, **LA), rd=RD_A, rm=RM_A, desc="vol target1.50 cap6 + ladder A"),
}

# analysis B (pre-registered lev sweep on the D00 structure; D04=lev3, D00=lev4, D02=lev5, D03=lev6 are in the table above)
for _l in (2.0, 7.0, 8.0):
    DESIGNS[f"B{int(_l)}"] = D(lev=_l, ref=True, desc=f"analysis B: blunt kill lev{_l:g}")


def windows(S):
    d0 = S.d_start("2022-01-01")
    isend = int(S.days.searchsorted(pd.Timestamp("2024-07-01", tz="UTC")))
    return dict(IS=(d0, isend), OOS=(isend, S.nd), FULL=(d0, S.nd))


def path_metrics(r):
    d0, d1 = r["d0"], r["d1"]
    eq = np.nan_to_num(r["eq"][d0:d1], nan=0.0)
    w = np.nan_to_num(r["worst"][d0:d1], nan=0.0)
    if r["liq_day"] >= 0:
        k = int(r["liq_day"]) - d0
        eq[k:] = 0.0; w[k:] = 0.0
    term = float(eq[-1])
    yrs = (d1 - d0) / 365.0
    logg = float(np.log(max(term, 1e-6)) / yrs)
    hw = np.maximum.accumulate(eq)
    mdd = float(np.max((hw - eq) / np.maximum(hw, 1e-12)))
    prev = np.r_[1.0, hw[:-1]]
    prev = np.maximum(prev, 1.0)
    top = np.maximum(prev, hw)
    imdd = float(np.max((top - np.minimum(w, eq)) / top))
    ex = r["expo"][d0:d1]
    inv = ex > 0
    return dict(term=term, logg=logg, mdd=mdd, imdd=imdd, kills=r["kills"], dlv=r["dlv"], liq_t=r["liq_t"], liq_f=r["liq_f"],
                liq_day=r["liq_day"], mr_t=r["mr_t"], mr_f=r["mr_f"], avg_g=r["avg_g"], max_g=r["max_g"], hloss=r["hloss"],
                halt_days=r["halt_days"], inv_frac=float(inv.mean()), ntr=r["ntr"])


class Ctx:
    def __init__(self):
        P = load_panel()
        self.base = BSim(P)
        self.vol = BSim(P, m_vol=1.5)
        self.cost2 = BSim(P, fund_mult=2.0)
        self.W = windows(self.base)


def run_cell(ctx, des, trig, win, sc, keep_eq=False):
    S = {"sc0": ctx.base, "sc1": ctx.base, "sc2": ctx.vol, "sc3": ctx.cost2, "sc4": ctx.base}[sc]
    a, b = ctx.W[win]
    pbk = dict(des["pb"]); pbk["intra"] = trig
    pbk["mbreak"] = 0 if sc == "sc0" else 1
    if sc == "sc4":
        pbk["exec_"] = 1
    cost = 0.002 if sc == "sc3" else 0.001
    if sc == "sc3":
        pbk["slip"] = 0.004
    pb = pbvec(**pbk)
    rd = des["rd"]; rm = des["rm"]
    rows = []; eqs = []; contrib = np.zeros(len(ctx.base.names)); trp = []
    for off in OFFS:
        for ph in PHASES:
            if win == "OOS":
                d0 = a + off
            else:
                d0 = a + off
            r = S.run_b(d0, b, phase=ph, lev=des["lev"], deploy=BASE["deploy"], kill=des["kill"], cool=des["cool"],
                        cost=cost, pb=pb, rd=rd, rm=rm)
            m = path_metrics(r); m["off"] = off; m["ph"] = ph
            rows.append(m)
            if keep_eq:
                e = np.nan_to_num(r["eq"], nan=0.0)
                if r["liq_day"] >= 0:
                    e[int(r["liq_day"]):] = 0.0
                eqs.append(e[a + max(OFFS):b].astype(np.float64))
                contrib += r["contrib"]
                trp.append(r["trp"])
    out = dict(rows=pd.DataFrame(rows))
    if keep_eq:
        out["eq"] = np.vstack(eqs)       # calendar-aligned from day a+39 (all paths started)
        out["contrib"] = contrib / len(rows)
        out["trp"] = np.concatenate(trp)
    return out


def task(args):
    did, trig, win = args
    des = DESIGNS[did]
    res = {}
    scs = ["sc0", "sc1", "sc2", "sc3"] + (["sc4"] if trig == 1 else [])
    for sc in scs:
        res[sc] = run_cell(_CTX, des, trig, win, sc, keep_eq=(sc == "sc0"))
    return (did, trig, win), res


_CTX = None


def main():
    global _CTX
    outdir = sys.argv[1]
    dsel = sys.argv[2].split(",") if len(sys.argv) > 2 and sys.argv[2] != "all" else list(DESIGNS)
    wsel = sys.argv[3].split(",") if len(sys.argv) > 3 else ["IS", "OOS", "FULL"]
    os.makedirs(outdir, exist_ok=True)
    _CTX = Ctx()
    tasks = [(d, t, w) for d in dsel for t in (1, 2, 0) for w in wsel]
    import multiprocessing as mp
    t0 = time.time()
    with mp.get_context("fork").Pool(min(10, os.cpu_count() or 4)) as pool:
        for k, (key, res) in enumerate(pool.imap_unordered(task, tasks)):
            d, t, w = key
            with open(os.path.join(outdir, f"{d}_T{t}_{w}.pkl"), "wb") as f:
                pickle.dump(res, f)
            if k % 20 == 0:
                print(k, len(tasks), key, round(time.time() - t0, 1), flush=True)
    print("done", round(time.time() - t0, 1))


if __name__ == "__main__":
    main()
