import sys, numpy as np
sys.path.insert(0, "/Users/user/CODE/Coin_Trade/scratchpad/strategy_bt/orderblock_loop")
import verify_rb246_independent as V
syms = V.load_universe(); P = V.load_panel(syms); funds = [V.load_funding(s) for s in syms]
D = V.day_count(P)
cfg = {"top_k":3,"rs":84,"reg":100}
def show(name, **kw):
    f = kw.pop("funds", funds)
    tr, info = V.run(P, cfg, f, **kw)
    m = V.metrics(tr, P["t0"], D)
    fund_mean = np.mean([x["fund"] for x in tr])*1e4 if tr else 0
    gross_mean = np.mean([x["gross"] for x in tr])*1e4 if tr else 0
    print(f'{name:28s} n={m["n"]:5d} PF={m["PF"]:.3f} exp={m["exp_bp"]:7.1f} cum={m["cum"]:.3f} mdd={m["mdd"]:.3f} sh={m["sharpe"]:.2f} p={m["p_one"]:.2e} M2={m["M2"]:.2f} gross_bp={gross_mean:.1f} fund_bp={fund_mean:.1f} info={info}', flush=True)
    return tr
show("base literal")
show("no funding", funds=[None]*len(syms))
show("replace mode", mode="replace")
show("replace, no funding", mode="replace", funds=[None]*len(syms))
show("cost 0", cost_rt=0.0)
show("delay 2", delay=2)
show("cost x2", cost_rt=0.0024)
