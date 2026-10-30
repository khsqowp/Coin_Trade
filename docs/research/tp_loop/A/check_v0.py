import sys, os; sys.path.insert(0, os.path.dirname(__file__))
from lib import *
from app.rs_final_engine import Sim as Ref
P, CF = load_all()
S = TPSim(P, CF); R = Ref(P)
for env in ("A", "B", "C"):
    kw = ENVS[env]
    for ph in range(3):
        a = S.run(phase=ph, **kw)
        b = R.run(lbs=(14,), crash_flat=True, phase=ph, **kw)
        ea, eb = a["eq"].to_numpy(), b["eq"].to_numpy()
        assert np.array_equal(ea, eb, equal_nan=True), (env, ph, np.nanmax(abs(ea-eb)))
        assert np.array_equal(a["worst"].to_numpy(), b["worst"].to_numpy(), equal_nan=True)
        assert np.array_equal(a["expo"].to_numpy(), b["expo"].to_numpy())
        print(env, ph, "EXACT", float(np.nanmax(ea)), int(a["kills"]), len(a["trades"]))
