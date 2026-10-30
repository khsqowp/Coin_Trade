import sys, os; sys.path.insert(0, os.path.dirname(__file__))
from lib import *
import importlib; pr = importlib.import_module("app.rs_profit_run")
P, CF = load_all(); S = TPSim(P, CF)
days = S.days
masks = {"IS": (days <= pd.Timestamp("2024-06-30", tz="UTC")), "OOS": days >= pd.Timestamp("2024-07-01", tz="UTC")}
masks["full"] = np.ones(len(days), bool)
d0 = S.d_start()
rs = []
for ph in range(3):
    r = S.run(phase=ph, **ENVS["B"])
    n = len(days)
    eq = r["eq"].to_numpy()[d0:]; w = r["worst"].to_numpy()[d0:]
    rs.append(dict(wealth=eq, total_worst=w, eq=eq, expo=r["expo"].to_numpy()[d0:], events=np.zeros(len(eq)), loss=np.zeros(len(eq)), eq0=1.0, days=days[d0:]))
m = {k: v[d0:] for k, v in masks.items()}
out = pr.meanms(rs, m)
for k, v in out.items(): print(k, {a: round(float(b), 4) for a, b in v.items() if a in ("wealth","cagr","dd","idd","dd_wp","wealth_wp","flat")})
