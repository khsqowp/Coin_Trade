import sys, numpy as np
sys.path.insert(0, "/Users/user/CODE/Coin_Trade/scratchpad/strategy_bt/orderblock_loop")
import verify_rb246_independent as V
syms=V.load_universe(); P=V.load_panel(syms); funds=[V.load_funding(s) for s in syms]; D=V.day_count(P); T=P["T"]
def run_strict(cfg, gap):
    score=V.rs_score(P["C"],P["btc"],cfg["rs"]); reg=V.regime_on(P["C"],P["btc"],cfg["reg"])
    cand=V.base_mask(P)&np.isfinite(score); entry_ok=np.zeros_like(cand); entry_ok[:T-1]=np.isfinite(P["O"][1:]); cand&=entry_ok
    last=np.full(len(syms),-10**9); tr=[]
    for t in range(T-1):
        if not reg[t]: continue
        js=np.nonzero(cand[t])[0]
        if js.size==0: continue
        order=js[np.argsort(-score[t,js],kind="stable")]
        for j in order[:cfg["top_k"]]:
            if t < last[j]+gap: continue
            x=V.sim_trade(P,j,t,t+1,V.COST_RT,funds[j])
            if x is None: continue
            last[j]=x["k"]; tr.append(x)
    return tr
for cfg in [{"top_k":1,"rs":42,"reg":100},{"top_k":3,"rs":84,"reg":100}]:
    for gap in [0,1]:
        tr=run_strict(cfg,gap); m=V.metrics(tr,P["t0"],D)
        print(cfg, "gap",gap, "n",m["n"],"PF",round(m["PF"],3),"exp",round(m["exp_bp"],1),"p",f'{m["p_one"]:.2e}')
