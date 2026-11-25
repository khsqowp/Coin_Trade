import sys, numpy as np
sys.path.insert(0, "/Users/user/CODE/Coin_Trade/scratchpad/strategy_bt/orderblock_loop")
import verify_rb246_independent as V
syms = V.load_universe(); P = V.load_panel(syms); funds = [V.load_funding(s) for s in syms]
D = V.day_count(P)
cfg = {"top_k":3,"rs":84,"reg":100}
def sim_variant(P, j, t, mode, cost_rt, fund_j, horizon=24):
    O,H,Lo,C = P["O"][:,j],P["H"][:,j],P["L"][:,j],P["C"][:,j]
    T=P["T"]; d=2.0*P["ATR"][t,j]
    if mode=="close_entry":
        entry=C[t]; start=t+1
    else:
        entry=O[t+1]; start=t+1
    stop, tgt = entry-d, entry+2*d
    k=None; reason=None; px=None
    rng = range(t, t+horizon) if mode=="include_signal_bar" else range(start, start+horizon)
    for jj in rng:
        if jj>=T: return None
        if jj==t and mode=="include_signal_bar":
            # signal bar's own range (lookahead) checked against stop/target from close entry
            if Lo[jj]<=stop: k,reason,px=jj,"stop",stop; break
            if H[jj]>=tgt: k,reason,px=jj,"target",tgt; break
            continue
        if O[jj]<=stop: k,reason,px=jj,"stop",O[jj]; break
        if Lo[jj]<=stop: k,reason,px=jj,"stop",stop; break
        if O[jj]>=tgt: k,reason,px=jj,"target",O[jj]; break
        if H[jj]>=tgt: k,reason,px=jj,"target",tgt; break
    if k is None:
        k=start+horizon
        if k>=T: return None
        px,reason=O[k],"time"
    gross=px/entry-1
    tin,tout=int(P["grid"][start]),int(P["grid"][k])
    fp,_=V.funding_pay(fund_j,tin,tout)
    return {"net":gross-cost_rt-fp,"gross":gross,"reason":reason,"fund":fp,"tin":tin,"tout":tout,"k":k}
def run_variant(mode, cost_rt=0.0012):
    T=P["T"]; score=V.rs_score(P["C"],P["btc"],cfg["rs"]); reg=V.regime_on(P["C"],P["btc"],cfg["reg"])
    base=V.base_mask(P); cand=base&np.isfinite(score)
    last=np.full(P["C"].shape[1],-1); trades=[]
    for t in range(T-1):
        if not reg[t]: continue
        js=np.nonzero(cand[t])[0]
        if js.size==0: continue
        order=js[np.argsort(-score[t,js],kind="stable")]
        for j in order[:cfg["top_k"]]:
            if t<last[j]: continue
            tr=sim_variant(P,j,t,mode,cost_rt,funds[j])
            if tr is None: continue
            last[j]=tr["k"]; trades.append(tr)
    m=V.metrics(trades,P["t0"],D)
    print(f'{mode:22s} cost={cost_rt} n={m["n"]} PF={m["PF"]:.3f} exp={m["exp_bp"]:.1f} gross_bp={np.mean([x["gross"] for x in trades])*1e4:.1f} fund_bp={np.mean([x["fund"] for x in trades])*1e4:.1f} M2={m["M2"]:.3f} p={m["p_one"]:.2e}', flush=True)
run_variant("next_open")
run_variant("close_entry")
run_variant("include_signal_bar")
run_variant("next_open", cost_rt=0.0)
