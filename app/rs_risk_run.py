"""Risk-overlay research runner (offline; reads .rs_cache/vision). python3.12 -m app.rs_risk_run"""
from __future__ import annotations
import itertools, json, sys, time
from dataclasses import asdict, replace
from multiprocessing import Pool
import numpy as np, pandas as pd
from app.rs_risk_engine import Cfg, build_panel, simulate, block_bootstrap
from app.rs_risk_load import load

SIGS = {"base_14_3_8": dict(lookback=14, rebal=3, K=8), "live_14_2_12": dict(lookback=14, rebal=2, K=12)}
_P = None
def _init():
    global _P
    o, f = load()
    _P = build_panel(o, f)
def day_idx(P, ts):
    return int(np.searchsorted(P["days"].values, np.datetime64(pd.Timestamp(ts).tz_localize(None))))
WIN = {"FULL": ("2022-01-01", None), "IS": ("2022-01-01", "2024-07-01"), "OOS": ("2024-07-01", None),
       "F1": ("2022-01-01", "2023-05-01"), "F2": ("2023-05-01", "2024-09-01"), "F3": ("2024-09-01", None)}
def run_raw(cfg, win, off):
    a, b = WIN[win]
    return simulate(_P, cfg, day_idx(_P, a) + off, day_idx(_P, b) if b else None)
def run_one(args):
    """average over rebalance-phase offsets (strategy is phase sensitive); worst-case for risk metrics"""
    cfg, win = args
    ms = [run_raw(cfg, win, off) for off in range(cfg.rebal)]
    for m in ms:
        m.pop("_eq", None); m.pop("_worst", None)
    out = {}
    for k in ("cagr", "mdd", "imdd", "calmar", "sharpe", "worst_day", "worst_week", "longest_uw_days", "final"):
        vals = [m[k] for m in ms if k in m]
        out[k] = float(np.mean(vals)) if k not in ("imdd", "mdd", "longest_uw_days") else float(np.max(vals))
        out[k + "_min"] = float(np.min(vals)); out[k + "_max"] = float(np.max(vals))
    out["min_buffer"] = float(min(m["min_buffer"] for m in ms))
    out["liq"] = any(m["liq"] for m in ms); out["halted"] = any(m["halted"] for m in ms)
    yrs = sorted({y for m in ms for y in m["yearly"]})
    out["yearly"] = {y: float(np.mean([m["yearly"][y] for m in ms if y in m["yearly"]])) for y in yrs}
    out["offsets"] = len(ms)
    return out
def stress(args):
    cfg, = args
    rs, as_ = [], []
    base = replace(cfg, lev=1.0, deploy=1.0, ladder=(), kill_dd=1.0, vol_target=0.0, start_equity=1.0,
                   min_notional=0.0, min_names=())
    for off in range(cfg.rebal):
        m = run_raw(base, "FULL", off)
        eq = m["_eq"].values; w = m["_worst"].values
        r = eq[1:] / eq[:-1] - 1; a = np.minimum(w[1:] / eq[:-1] - 1, r)
        rs.append(r); as_.append(a)
    r = np.concatenate(rs); a = np.concatenate(as_)
    out = {}
    for blk in (10,):
        out[f"1y_block{blk}"] = block_bootstrap(r, a, cfg, n_paths=1000, horizon=365, block=blk, seed=1)
    out["2y_block10"] = block_bootstrap(r, a, cfg, n_paths=1000, horizon=730, block=10, seed=2)
    return out
def grid(sig):
    s = SIGS[sig]; out = {}
    for lev, d in itertools.product([0.5, 0.75, 1, 1.25, 1.5, 2, 2.5, 3, 3.5, 4], [0.6, 0.8, 1.0]):
        out[f"const L{lev} d{d}"] = Cfg(**s, lev=lev, deploy=d)
    lads = {"A.15/.5": ((.15, .5),), "B.20/.5": ((.2, .5),), "C.10/.75,.2/.5,.3/.25": ((.1, .75), (.2, .5), (.3, .25)),
            "D.15/.67,.25/.33": ((.15, .67), (.25, .33))}
    for lev, (ln, lad), hy, mode, ap, kill in itertools.product([1.5, 2, 3, 4], lads.items(), [0.03, 0.08], ["dd", "hwm"],
                                                                 ["rebalance", "daily"], [0.35, 1.0]):
        out[f"lad L{lev} {ln} hy{hy} {mode} {ap} kill{kill}"] = Cfg(**s, lev=lev, deploy=0.8, ladder=lad, hyst=hy,
                                                                 relever_mode=mode, apply=ap, kill_dd=kill)
    for tv, lb, cap in itertools.product([.08, .10, .12, .15, .2, .25, .3, .4], [10, 20, 30, 60], [1.5, 2, 3, 4]):
        out[f"vol T{tv} lb{lb} cap{cap}"] = Cfg(**s, lev=cap, deploy=1.0, vol_target=tv, vol_lb=lb, lev_cap=cap)
    return out
def f(m, k):
    v = m.get(k); return "nan" if v is None else f"{v:.3f}" if isinstance(v, float) else str(v)

def main():
    t0 = time.time()
    _init()
    P = _P
    print("panel", P["C"].shape, P["days"][0], P["days"][-1], "coins", len(P["names"]), flush=True)
    res = {}
    with Pool(8, initializer=_init) as pool:
        # 1. validation
        v = Cfg(**SIGS["base_14_3_8"], lev=1, cost=0.0004, funding=False)
        res["validation_1x_fee0.04_nofund"] = pool.apply(run_one, ((v, "FULL"),))
        print("VALID", {k: x for k, x in res["validation_1x_fee0.04_nofund"].items() if k != "yearly"}, flush=True)
        for sig in SIGS:
            G = grid(sig)
            names = list(G)
            r_is = pool.map(run_one, [(G[n], "IS") for n in names], chunksize=4)
            res[sig] = {"IS": dict(zip(names, r_is))}
            ok = [(n, m) for n, m in zip(names, r_is) if m.get("imdd", 9) <= 0.30 and not m["liq"] and m["min_buffer"] >= 1.5]
            ok.sort(key=lambda t: -t[1]["cagr"])
            res[sig]["top"] = [n for n, _ in ok[:8]]
            print(sig, "feasible", len(ok), "of", len(names), "time", round(time.time() - t0), flush=True)
            for w in ("FULL", "OOS", "F1", "F2", "F3"):
                rr = pool.map(run_one, [(G[n], w) for n in names], chunksize=4)
                res[sig][w] = dict(zip(names, rr))
            res[sig]["cfgs"] = {n: asdict(G[n]) for n in names}
        # reference + stress
        refs = {}
        for sig in SIGS:
            G = grid(sig); sel = res[sig]["top"][0] if res[sig]["top"] else "const L1 d1.0"
            refs[sig] = {"chosen": sel, "chosen_cfg": asdict(G[sel]),
                         "stress_chosen": pool.apply(stress, ((G[sel],),)),
                         "stress_1x": pool.apply(stress, ((G["const L1 d1.0"],),))}
            for nm, c in {"live4x_d0.8_nolad": replace(G["const L4 d0.8"]), "live4x_d0.8_lad.2/.25_kill.35":
                          replace(G["const L4 d0.8"], ladder=((.2, .25),), hyst=0.0, kill_dd=0.35),
                          "L3_d0.8_lad.2/.5_kill.35": replace(G["const L3 d0.8"], ladder=((.2, .5),), hyst=0.05, kill_dd=0.35)}.items():
                refs[sig][nm] = {w: pool.apply(run_one, ((c, w),)) for w in ("FULL", "IS", "OOS")}
                refs[sig][nm + "_stress"] = pool.apply(stress, ((c,),))
        res["refs"] = refs
        # live config (142 USDT, min notional scenarios)
        live = {}
        base = dict(lookback=14, rebal=2, K=12, lev=4, deploy=0.8, ladder=((.2, .25),), hyst=0.0, kill_dd=0.35,
                   start_equity=142.0)
        scen = {"live_minN5": dict(min_notional=5.0), "live_minN5_BTC100_ETH20": dict(min_notional=5.0, min_names=(("BTC", 100.), ("ETH", 20.))),
                "live_minN20": dict(min_notional=20.0), "live_noMinN(ideal)": dict()}
        for k, kw in scen.items():
            cfg = Cfg(**base, **kw)
            for w in ("FULL", "IS", "OOS"):
                live.setdefault(k, {})[w] = pool.apply(run_one, ((cfg, w),))
        for k in ("L4_d0.8_K12_nodelever", "L3_d0.8_K12_ladder.2/.5", "L2_d0.8_K12"):
            pass
        res["live"] = live
    for k, v in res["live"].items():
        print("LIVE", k, {w: {x: v[w].get(x) for x in ("cagr", "imdd", "liq", "min_buffer", "halted", "final")} for w in v})
    json.dump(res, open("docs/research/risk_results.json", "w"), default=str, indent=1)
    print("done", round(time.time() - t0), "s")

if __name__ == "__main__":
    main()
