"""V0 replication assert: rs_tp_b_engine mode 0 == rs_final_engine.Sim.run (eq, worst, expo), all phases, both configs."""
import numpy as np
from app.rs_final_data import load_panel
from app.rs_tp_b_engine import TPSim

def main():
    S = TPSim(load_panel())
    out = []
    for lev, dep in ((4.0, 0.95), (2.0, 1.0)):
        for ph in range(3):
            r0 = S.run(lbs=(14,), crash_flat=True, rebal=3, K=8, lev=lev, deploy=dep, kill=0.35, cool=14, cost=0.001,
                       fund=1, minn=0.0, eq0=1.0, phase=ph)
            r1 = S.run_tp(lev=lev, deploy=dep, phase=ph)
            a = r0["eq"].to_numpy(); b = r1["eq"].to_numpy()
            ok = np.array_equal(np.nan_to_num(a, nan=-1), np.nan_to_num(b, nan=-1)) and \
                 np.array_equal(np.nan_to_num(r0["worst"].to_numpy(), nan=-1), np.nan_to_num(r1["worst"].to_numpy(), nan=-1)) and \
                 np.array_equal(r0["expo"].to_numpy(), r1["expo"].to_numpy())
            md = np.nanmax(np.abs(a - b))
            print(f"lev{lev} dep{dep} phase{ph}: exact={ok} maxabs={md:.3e} end_eq={np.nanstd(a) and a[~np.isnan(a)][-1]:.4f} kills={r0['kills']} liq={r0['liq']} nreb={r0['nreb']}")
            assert ok, "V0 mismatch"
            assert (r0["kills"], r0["nreb"], r0["att"], r0["skip"]) == (r1["stats"][2], r1["stats"][3], r1["stats"][0], r1["stats"][1])
    print("V0 REPLICATION ASSERT PASSED")
    # overlay with unreachable thresholds must also be bit-identical (no side effects of the exit code path)
    from app.rs_tp_b_engine import tp_params
    for mode in (1, 2, 3):
        for ph in range(3):
            r0 = S.run_tp(phase=ph); r1 = S.run_tp(tp_params(mode, 1e9, 1e8), phase=ph)
            assert np.array_equal(np.nan_to_num(r0["eq"].to_numpy(), nan=-1), np.nan_to_num(r1["eq"].to_numpy(), nan=-1)), mode
            assert len(r1["events"]) == 0
    print("NO-TRIGGER OVERLAY (modes 1-3, k=1e9) == V0: PASSED")
    # every logged exit must lie inside the hourly H/L range of its bar (intrabar fills) or be the bar close (next-bar)
    for mode, a, b in ((1, 3.0, 0), (2, 6.0, 3.0), (3, 6.0, 0)):
        r = S.run_tp(tp_params(mode, a, b, slip=0.0), phase=0)
        for (i, h, j, sd, pr_, ty, fr) in r["events"]:
            i, h, j = int(i), int(h), int(j)
            hi, lo = S.H[i, h, j], S.L[i, h, j]
            assert lo * (1 - 1e-12) <= pr_ <= hi * (1 + 1e-12), (mode, i, h, j, lo, pr_, hi)
        print(f"mode {mode}: {len(r['events'])} exit events all inside their hourly [L,H]")
if __name__ == "__main__":
    main()
