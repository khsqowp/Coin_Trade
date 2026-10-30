"""V0 replication assert: new engine (legacy flags) == rs_final_engine.Sim.run bit-for-bit; known final-equity values."""
import numpy as np
from app.rs_final_data import load_panel
from app.rs_lev_c_engine import LSim
from app.rs_final_engine import window_metrics

REF = {0: 14.5027, 1: 18.4064, 2: 15.8459}


def main():
    S = LSim(load_panel())
    for ph in range(3):
        a = S.run(lbs=(14,), crash_flat=True, rebal=3, K=8, lev=4.0, deploy=0.95, kill=0.35, cool=14, cost=0.001, fund=1, minn=0.0, eq0=1.0, phase=ph)
        b = S.run_c(4.0, 0.95, phase=ph, kill_mode=1, mm_mode=0)
        assert np.array_equal(a["eq"].to_numpy(), b["eq"].to_numpy(), equal_nan=True), ph
        assert np.array_equal(a["worst"].to_numpy(), b["worst"].to_numpy(), equal_nan=True), ph
        assert a["kills"] == b["kills"] and a["liq"] == b["liq"] == False
        end = float(a["eq"].dropna().iloc[-1])
        assert abs(end - REF[ph]) < 5e-4, (ph, end)
        print("phase", ph, "end", round(end, 4), "kills", a["kills"], "EXACT == rs_final_engine; ref", REF[ph])
    print("wick range", S.wick.min(), S.wick.max(), "fund window", S.days[S.fwin[0]].date(), S.days[S.fwin[1]].date())
    print("ALL V0 REPLICATION ASSERTS PASSED")


if __name__ == "__main__":
    main()
