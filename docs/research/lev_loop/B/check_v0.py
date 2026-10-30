"""V0 replication proof: rs_lev_b_engine (all new features off) vs rs_final_engine.Sim.run, bit-exact."""
import sys; sys.dont_write_bytecode=True; sys.path.insert(0,"/Users/user/Desktop/CODE/Ochestration/trading")
import numpy as np
from app.rs_final_data import load_panel
from app.rs_final_engine import window_metrics
from app.rs_lev_b_engine import BSim, pbvec
P=load_panel(); S=BSim(P)
d0=S.d_start(); n_ok=0
for off in (0,7,20,39):
  for ph in range(3):
    for (a,b) in ((d0+off,S.nd),(d0+off,S.days.searchsorted(__import__("pandas").Timestamp("2024-07-01",tz="UTC")))):
        r0=S.run(crash_flat=True,rebal=3,K=8,lev=4.0,deploy=.95,kill=.35,cool=14,phase=ph,d0=a,d1=b)
        r1=S.run_b(a,b,phase=ph,lev=4.0,deploy=.95,pb=pbvec(intra=0))
        e0=r0["eq"].to_numpy(); e1=r1["eq"]
        assert np.array_equal(e0,e1,equal_nan=True), (off,ph,a,b)
        assert np.array_equal(r0["worst"].to_numpy(),r1["worst"],equal_nan=True)
        assert r0["kills"]==r1["kills"]
        n_ok+=1
print("EXACT match (eq_close, eq_worst, kills) on",n_ok,"runs")
for ph in range(3):
    r1=S.run_b(d0,S.nd,phase=ph,lev=4.0,deploy=.95,pb=pbvec(intra=0)); e=r1["eq"][d0:S.nd-0]
    print("phase",ph,"final",round(float(r1["eq"][S.nd-1]),4),"kills",r1["kills"],"liq_t/liq_f",r1["liq_t"],r1["liq_f"])
