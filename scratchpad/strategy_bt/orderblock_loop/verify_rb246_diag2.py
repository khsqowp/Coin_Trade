import sys, numpy as np, pandas as pd
sys.path.insert(0, "/Users/user/CODE/Coin_Trade/scratchpad/strategy_bt/orderblock_loop")
import verify_rb246_independent as V
syms = V.load_universe(); P = V.load_panel(syms); funds = [V.load_funding(s) for s in syms]
D = V.day_count(P)
cfg = {"top_k":3,"rs":84,"reg":100}
def show(name, P_=P, **kw):
    f = kw.pop("funds", funds)
    tr, info = V.run(P_, cfg, f, **kw)
    m = V.metrics(tr, P_["t0"], D)
    print(f'{name:30s} n={m["n"]:5d} PF={m["PF"]:.3f} exp={m["exp_bp"]:7.1f} cum={m["cum"]:.3f} mdd={m["mdd"]:.3f} sh={m["sharpe"]:.2f} p={m["p_one"]:.2e} M2={m["M2"]:.3f} rs={m["reasons"]}', flush=True)
    return tr
# Wilder ATR
tr_ = P["H"]-P["L"]
import copy
PW = dict(P)
C=P["C"]; H=P["H"]; L=P["L"]
prev=np.full_like(C,np.nan); prev[1:]=C[:-1]
TR=np.maximum(H-L,np.maximum(np.abs(H-prev),np.abs(L-prev)))
PW["ATR"]=pd.DataFrame(TR).ewm(alpha=1/14, adjust=False, min_periods=14).mean().to_numpy()
show("Wilder ATR", P_=PW)
show("SMA ATR (base)")
PE=dict(P); PE["ATR"]=pd.DataFrame(TR).ewm(span=14, adjust=False, min_periods=14).mean().to_numpy()
show("EMA14 ATR", P_=PE)
# horizon variants
for hz in [23,25,12,48]:
    show(f"horizon {hz}", horizon=hz)
# warm-up variant: none
V.WARM = 0
show("warm 0")
V.WARM = 500
