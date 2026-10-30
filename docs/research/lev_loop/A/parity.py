"""V0 replication: new engine (kill_mode=0, liq_stop=1) must be BIT-EXACT vs rs_final_engine.Sim.run (crash_flat=True)."""
from common import *
from app.rs_final_engine import Sim, window_metrics
P = load_panel(); S0 = Sim(P); SA = SimA(P)
n = 0
for (lev, dep, kill, cool) in [(4.0, .95, .35, 14), (3.0, 1.0, .35, 14), (6.0, .95, .25, 14), (5.0, .95, 1.0, 14), (4.0, .95, .5, 14), (2.5, .95, .35, 7)]:
    for ph in range(3):
        for (a, b) in [(None, None), (S0.d_start() + 17, None), (None, S0.d_start("2024-07-01"))]:
            kw = dict(d0=a, d1=b)
            r0 = S0.run(crash_flat=True, rebal=3, K=8, lev=lev, deploy=dep, kill=kill, cool=cool, phase=ph, **kw)
            r1 = SA.run_a(lev, dep, kill, cool=cool, kill_mode=0, phase=ph, liq_stop=1, d0=a, d1=b)
            assert np.array_equal(r0["eq"].to_numpy(), r1["eq"], equal_nan=True), (lev, dep, kill, ph)
            assert np.array_equal(r0["worst"].to_numpy(), r1["worst"], equal_nan=True)
            assert r0["kills"] == r1["kills"] and r0["liq"] == bool(r1["st"][4])
            n += 1
r = SA.run_a(4.0, .95, .35, kill_mode=0, phase=0, liq_stop=1)
print("PARITY OK: %d runs bit-exact (eq, worst, kills, liq)." % n)
print("V0 live cell ends (phases 0/1/2):", [round(float(np.nan_to_num(SA.run_a(4.0, .95, .35, kill_mode=0, phase=p, liq_stop=1)["eq"])[-2:].max()), 4) for p in range(3)])
# lev x deploy identity
a = SA.run_a(4.0, .95, .35, kill_mode=1, phase=0); b = SA.run_a(3.8, 1.0, .35, kill_mode=1, phase=0); c = SA.run_a(2.0, 1.9, .35, kill_mode=1, phase=0)
assert np.array_equal(a["eq"], b["eq"], equal_nan=True) and np.array_equal(a["eq"], c["eq"], equal_nan=True)
print("IDENTITY OK: eq path depends on lev*deploy only (4x0.95 == 3.8x1.0 == 2.0x1.9), intraday mode too.")
