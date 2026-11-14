"""Round 3 study driver (offline, deterministic). Rules: research/PREREG_round3.md. Every selection variant is logged in runs/research/trials.sqlite (study R3)."""
import itertools
import json
import os
import time

import numpy as np

from . import metrics, research, risk, rotation
from .config import DATA, RUNS

OUT = RUNS / "research" / "r3_rotation.json"
PRIMARY = dict(fee=0.0005, slip=0.0002)
COSTS = {"slip0.01": dict(fee=0.0005, slip=0.0001), "slip0.05": dict(fee=0.0005, slip=0.0005), "maker50": dict(fee=0.0005, slip=0.0002, maker_share=0.5, maker_fee=0.0002)}


def variants():
    out = {}
    for clock, n, stop, btc in itertools.product(("1h", "4h", "1d", "ad"), (1, 3), rotation.STOPS, (1, 0)):
        out["c%s_n%d_%s_b%d" % (clock, n, stop, btc)] = dict(kind="rot", clock=clock, n=n, stop=stop, btc=bool(btc))
    out["card_k8"] = dict(kind="card", k=8)
    out["card_k3"] = dict(kind="card", k=3)
    return out


def sr_slice(eq, a, b):
    r = eq[a + 1:b] / eq[a:b - 1] - 1.0
    return float(metrics.sharpe_annual(r, 8760)) if len(r) > 50 else 0.0


def dd_distribution(trades, n_seq=2000, length=100, seed=7):
    x = np.array([t["pnl"] / t["eq0"] for t in trades if t.get("eq0")], float)
    if len(x) < 10:
        return None
    rng = np.random.RandomState(seed)
    mdds = []
    for _ in range(n_seq):
        e = np.cumprod(1.0 + rng.choice(x, size=length, replace=True))
        pk = np.maximum.accumulate(np.r_[1.0, e])[1:]
        mdds.append(float(((pk - e) / pk).max()))
    streak = best = 0
    for v in x:
        streak = streak + 1 if v < 0 else 0
        best = max(best, streak)
    return dict(n_trades=len(x), win_rate=round(float((x > 0).mean()), 3), avg_trade=round(float(x.mean()), 5), worst_trade=round(float(x.min()), 4),
                longest_losing_streak=best, boot_mdd_p50=round(float(np.percentile(mdds, 50)), 3), boot_mdd_p95=round(float(np.percentile(mdds, 95)), 3),
                boot_mdd_p99=round(float(np.percentile(mdds, 99)), 3), boot_mdd_max=round(float(max(mdds)), 3))


def worst_rolling(eq, hours=720):
    if len(eq) <= hours:
        return None
    return round(float((eq[hours:] / eq[:-hours] - 1).min()), 4)


def row(res, mid):
    eq = res["eq"]
    t_in = sum(1 for t in res["trades"] if t["t1"] - rotation.WARMUP < mid)
    return dict(sharpe=round(res["sharpe"], 3), sharpe_h1=round(sr_slice(eq, 0, mid), 3), sharpe_h2=round(sr_slice(eq, mid, len(eq)), 3),
                total_return=round(res["total_return"], 4), mdd=round(res["mdd"], 4), trades=res["n_trades"], trades_h1=t_in, trades_h2=res["n_trades"] - t_in,
                fees=round(res["fees"], 2), slip=round(res["slip"], 2), funding=round(res["funding"], 2), rejects=res["rejects"], rej_top=dict(sorted(res["rej_sym"].items(), key=lambda kv: -kv[1])[:4]), liq=res["liq"],
                exposure=round(res["exposure"], 3), days_gt10_fills=res["days_gt10_fills"], days_loss_gt3=res["days_loss_gt3"], clock_share=res["clock_share"],
                worst_30d=worst_rolling(eq), end_equity=round(float(eq[-1]), 2))


def gate_input(res, mid, bars):
    eq = res["eq"]
    t_in = sum(1 for t in res["trades"] if t["t1"] - rotation.WARMUP < mid)
    return dict(params=dict(fee=PRIMARY["fee"], slippage=PRIMARY["slip"]),
                full=dict(trades=res["n_trades"], mdd=res["mdd"], sharpe=res["sharpe"]),
                in_sample=dict(trades=t_in, sharpe=sr_slice(eq, 0, mid), bars=mid),
                out_of_sample=dict(trades=res["n_trades"] - t_in, sharpe=sr_slice(eq, mid, len(eq)), bars=len(eq) - mid),
                lookahead_check=dict(passed=True, mismatches=0, errors=0))


def run_study(part="main", log=print):
    os.nice(19)
    u = json.loads((DATA / "research" / "rot_universe.json").read_text())
    D = rotation.load_data(u, log=log)
    n_t = len(D.index)
    V = variants()
    nbars = n_t - rotation.WARMUP
    mid = nbars // 2
    res = {"universe": D.syms, "n_hours": nbars, "first": str(D.index[rotation.WARMUP]), "last": str(D.index[-1]), "capital": 128.88}
    t0 = time.time()
    if part == "main":
        con = research.tcon()
        main, causal = {}, {}
        half_end = rotation.WARMUP + nbars // 2
        for k, v in V.items():
            r = rotation.run(D, v, PRIMARY)
            main[k] = r
            h = rotation.run(D, v, PRIMARY, end=half_end)                      # causality: a run that stops at the midpoint must reproduce the full run's first half
            causal[k] = bool(np.allclose(h["eq"], r["eq"][:len(h["eq"])], rtol=1e-9, atol=1e-9))
            research.log_trial(con, "R3", "rot", "long", "UNIV", "1h", k, "primary", r["r"], 8760, selection=1)
        con.commit()
        srs = np.array([r["sharpe"] for r in main.values()])
        bt = rotation.bench_hold(D, "BTCUSDT", PRIMARY)
        eth = rotation.bench_hold(D, "ETHUSDT", PRIMARY)
        ew = rotation.bench_ew(D, PRIMARY)
        res["benchmarks"] = {n: dict(sharpe=round(b["sharpe"], 3), sharpe_h1=round(sr_slice(b["eq"], 0, mid), 3), sharpe_h2=round(sr_slice(b["eq"], mid, len(b["eq"])), 3),
                                     total_return=round(b["total_return"], 4), mdd=round(b["mdd"], 4), worst_30d=worst_rolling(b["eq"]))
                             for n, b in (("btc_hold", bt), ("eth_hold", eth), ("universe_ew_daily", ew))}
        rows, gates = {}, {}
        cfg = risk.PROFILES["crypto_small_rotation"]
        for k, r in main.items():
            d = row(r, mid)
            ds = research.dsr_ann(r["r"], 8760, srs)
            d.update(dsr=round(float(ds[0]), 3), dsr_sr0_ann=round(float(ds[1]), 2), dsr_emp=round(float(ds[2]), 3), causal_ok=causal[k])
            g = risk.gate_numeric(gate_input(r, mid, nbars), "BTC/USDT", "skip", cfg)
            d["gate_pass"] = bool(g.allowed and causal[k])
            d["gate_reasons"] = [x.split(":")[0] for x in g.reasons]
            rows[k] = d
        res["variants"] = rows
        res["n_selection_trials"] = len(rows)
        # strict OOS: pick on the first half, evaluate on the second
        for n in (1, 3):
            ks = [k for k in rows if k.startswith("c") and "_n%d_" % n in k]
            best = max(ks, key=lambda k: rows[k]["sharpe_h1"])
            res["oos_pick_n%d" % n] = dict(variant=best, sharpe_h1=rows[best]["sharpe_h1"], sharpe_h2=rows[best]["sharpe_h2"],
                                           hindsight_best_h2=max(ks, key=lambda k: rows[k]["sharpe_h2"]), hindsight_h2=max(rows[k]["sharpe_h2"] for k in ks))
        # drawdown distribution for: first-half pick (n=1, n=3) and median-Sharpe variant of each n
        dd = {}
        for n in (1, 3):
            ks = sorted([k for k in rows if k.startswith("c") and "_n%d_" % n in k], key=lambda k: rows[k]["sharpe"])
            for tag, k in (("pick_h1", res["oos_pick_n%d" % n]["variant"]), ("median", ks[len(ks) // 2]), ("worst_sharpe", ks[0])):
                dd["n%d_%s:%s" % (n, tag, k)] = dd_distribution(main[k]["trades"])
        res["drawdown_distribution"] = dd
        res["fixed_vs_adaptive"] = {}
        for clock in ("1h", "4h", "1d", "ad"):
            ks = [k for k in rows if k.startswith("c%s_" % clock)]
            res["fixed_vs_adaptive"][clock] = dict(median_sharpe=round(float(np.median([rows[k]["sharpe"] for k in ks])), 3), best_sharpe=round(max(rows[k]["sharpe"] for k in ks), 3),
                                                   median_trades=int(np.median([rows[k]["trades"] for k in ks])), median_fees=round(float(np.median([rows[k]["fees"] for k in ks])), 2), median_slip=round(float(np.median([rows[k]["slip"] for k in ks])), 2),
                                                   median_funding_paid=round(float(np.median([rows[k]["funding"] for k in ks])), 2), share_ret_pos=round(float(np.mean([rows[k]["total_return"] > 0 for k in ks])), 2),
                                                   median_mdd=round(float(np.median([rows[k]["mdd"] for k in ks])), 3))
    else:
        base = {k: v for k, v in V.items() if v["kind"] == "rot"}
        sens = {}
        if part == "cost":
            for name, c in COSTS.items():
                sens[name] = {k: row(rotation.run(D, v, c), mid) for k, v in V.items()}
        elif part == "lev":
            for lev in (2.0, 3.0, 4.0):
                sens["lev%d" % lev] = {k: row(rotation.run(D, v, PRIMARY, lev=lev), mid) for k, v in base.items()}
        elif part == "phase":
            for k, v in base.items():
                if v["clock"] in ("4h", "1d"):
                    sens[k] = row(rotation.run(D, v, PRIMARY, phase=2 if v["clock"] == "4h" else 12), mid)
        elif part == "filters":
            relaxed = {s: dict(f, minNotional=0.0, minQty=0.0, stepSize=1e-9) for s, f in D.filters.items()}
            D2 = rotation.Data.__new__(rotation.Data)
            D2.__dict__.update(D.__dict__)
            D2.filters = relaxed
            sens = {k: row(rotation.run(D2, v, PRIMARY), mid) for k, v in V.items()}
        res["sens_" + part] = sens
    res["seconds"] = round(time.time() - t0, 1)
    out = OUT.with_name("r3_rotation_%s.json" % part)
    out.parent.mkdir(parents=True, exist_ok=True)
    out.write_text(json.dumps(res, indent=1, default=str))
    return {"part": part, "seconds": res["seconds"], "file": str(out)}
