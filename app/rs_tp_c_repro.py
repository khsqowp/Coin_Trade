"""V0 replication proof: rs_tp_c_engine (exits off) vs rs_final_engine.Sim (original), exact array equality."""
import os, sys, json
sys.dont_write_bytecode = True
import numpy as np
from app.rs_final_data import load_panel
from app.rs_final_engine import Sim as Ref, window_metrics
from app.rs_tp_c_engine import TPSim

CFG = {"LIVE lev4 dep0.95": dict(lev=4.0, deploy=0.95), "RESEARCH lev2 dep1.0": dict(lev=2.0, deploy=1.0)}

def main():
    P = load_panel(); ref = Ref(P); me = TPSim(P)
    out = {}
    for name, c in CFG.items():
        W = []; I = []
        for ph in range(3):
            a = ref.run(lbs=(14,), crash_flat=True, rebal=3, K=8, kill=0.35, cool=14, cost=0.001, fund=1, minn=0.0, eq0=1.0, phase=ph, **c)
            b = me.run(rebal=3, K=8, kill=0.35, cool=14, phase=ph, **c)
            for k in ("eq", "worst", "expo"):
                x = a[k].to_numpy(); y = b[k].to_numpy()
                assert np.array_equal(np.nan_to_num(x, nan=-9), np.nan_to_num(y, nan=-9)), (name, ph, k, np.nanmax(np.abs(x - y)))
            assert a["kills"] == b["kills"] and a["liq"] == b["liq"]
            m = window_metrics(a); W.append(m["end"]); I.append((m["cagr"], m["mdd"], int(a["kills"]), a["liq"]))
        out[name] = dict(end_wealth_by_phase=W, mean_end=float(np.mean(W)), cagr_mdd_kills_liq=I)
        print(name, "EXACT MATCH (eq, worst, expo) 3 phases; mean end wealth %.3f" % np.mean(W), I)
    json.dump(out, open("docs/research/tp_loop/C/v0_replication.json", "w"), indent=1, default=float)
main()

def extra_checks():
    """exit machinery with zero hazard must not change V0; exits never occur on a rebalance day."""
    from app.rs_tp_c_engine import xparams
    P = load_panel(); me = TPSim(P)
    for name, c in CFG.items():
        for ph in range(3):
            a = me.run(rebal=3, phase=ph, **c)
            b = me.run(rebal=3, phase=ph, xp=xparams(0, 3.0, 0, 0, 1, 0.0, 0.0), U=np.random.default_rng(1).random((me.nd, len(me.names))), **c)
            assert np.array_equal(np.nan_to_num(a["eq"].to_numpy(), nan=-9), np.nan_to_num(b["eq"].to_numpy(), nan=-9))
            v = me.run(rebal=3, phase=ph, xp=xparams(3, 3.0), **c)
            ex_days = np.flatnonzero((v["exL"] + v["exS"]) > 0)
            assert len(ex_days) > 0
            # a rebalance day shows traded notional without being an exit day in V0 phase grid: exits only if (i-d0-ph)%3 != 0 while no kill reset
            if v["kills"] == 0:
                assert all(((i - me.d0 - ph) % 3) != 0 for i in ex_days)
    print("extra checks OK (zero-hazard == V0; exits only on non-rebalance days when no kill-reset)")

extra_checks()
