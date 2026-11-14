import json, numpy as np, sys
out={}
for m in ("kr","us"):
    r=json.load(open(f"out/results_{m}.json")); C=r["combos"]; md=r["metadata"]
    print("=====",m,{k:md[k] for k in ("universe_names","usable_names","names_with_signals","first_date","last_date","share_names_first_bar_before_2015")})
    print("signals(confirmed) total",sum(md["signals_by_N_R_D_M"].values()), "valid", r["validation"])
    s=r["selected"]; 
    if s:
        print("SELECTED",s["combo"]); 
        for p in ("IS","OOS"): print(p,{k:(round(v,4) if isinstance(v,float) else v) for k,v in s[p].items()})
        c=C[[x["id"] for x in C].index(r["selected"]["combo_id"])]
        print(" rand",{p:(c["random_entry_baseline"][p]["percentile"],c["random_entry_baseline"][p]["p_one_sided"]) for p in ("ALL","IS","OOS")},"bootOOS",c["cluster_bootstrap"]["OOS"],"q",c["bh_q_all"],"bonf",c["bonferroni_p_all"])
        print(" 2x OOS", c["portfolio"]["OOS_2x"]["cagr"], c["portfolio"]["OOS_2x"]["sharpe"])
    mn=np.array([c["trade_stats"]["mean_net"] for c in C if c["trade_stats"]["mean_net"] is not None])
    print("ALL combos mean net trade ret: median %.4f min %.4f max %.4f; frac>0 %.2f"%(np.median(mn),mn.min(),mn.max(),(mn>0).mean()))
    def per(p):
        v=[]
        for c in C:
            rb=c["random_entry_baseline"][p]; 
            if rb.get("percentile") is not None: v.append((rb["percentile"],rb["real_mean_net"]))
        return v
    for p in ("IS","OOS"):
        v=per(p); pc=np.array([x[0] for x in v]); mm=np.array([x[1] for x in v])
        print(p,"combos with data",len(v),"median real mean net %.4f"%np.median(mm),"median rand pct %.3f"%np.median(pc),"n>=95pct",(pc>=.95).sum(),"n<=5pct",(pc<=.05).sum(),"n mean>0",(mm>0).sum())
    ps=[c["cluster_bootstrap"]["ALL"]["p_two_sided"] for c in C]; q=[c["bh_q_all"] for c in C]
    print("ALL: min p %.4f; n p<0.05 %d; n bonf128<0.05 %d; n BH q<0.10 %d"%(min(ps),sum(p<.05 for p in ps),sum(c["bonferroni_p_all"]<.05 for c in C),sum(x<.10 for x in q)))
    oosm=[]
    for c in C:
        pass
    # confirmation ablation
    d=[(c["confirmation_ablation"]["confirmed_mean_net"],c["confirmation_ablation"]["unconditional_mean_net"],c["confirmation_ablation"]["failed_trigger_mean_net"],c["confirmation_ablation"]["confirmed_vs_failed_cluster_bootstrap"]) for c in C]
    cf=np.array([x[0] for x in d if x[0] is not None and x[2] is not None]); ff=np.array([x[2] for x in d if x[0] is not None and x[2] is not None])
    print("confirm ablation: median confirmed %.4f, median failed %.4f, median uncond %.4f; n confirmed>failed %d/%d; n CI excl 0 (conf>fail) %d"%(np.median(cf),np.median(ff),np.median([x[1] for x in d if x[1] is not None]),(cf>ff).sum(),len(cf),sum(1 for x in d if x[3]["ci95"][0] is not None and x[3]["ci95"][0]>0)))
    v0=[(c["trade_stats"]["mean_net"],c["volume_ablation_m0"]["mean_net"],c["volume_ablation_m0"]["mean_net_m3"]) for c in C if "volume_ablation_m0" in c and c["volume_ablation_m0"]["mean_net"] is not None]
    print("vol ablation (M2 / M0 / M3 medians): %.4f %.4f %.4f"%(np.median([x[0] for x in v0]),np.median([x[1] for x in v0]),np.median([x[2] for x in v0 if x[2] is not None])))
    print("index", {k:{p:(round(v["cagr"],3),round(v["sharpe"],2),round(v["max_drawdown"],2)) for p,v in d.items()} for k,d in r["index_buy_hold"].items()})
    print("year median mean-net:", {y:(round(v,4) if v is not None else None) for y,v in r["rolling_year_median_over_combos_mean_net_trade_return"].items()})
    # best/worst by ALL mean
    ordc=sorted(C,key=lambda c:-(c["trade_stats"]["mean_net"] or -9))
    for c in ordc[:3]+ordc[-2:]:
        print(" ",c["combo"],"n",c["trade_stats"]["n"],"mean_net %.4f"%c["trade_stats"]["mean_net"],"IS/OOS sharpe",c["portfolio"]["IS"]["sharpe"],c["portfolio"]["OOS"]["sharpe"])
    # event forward
    ev=[c["event_forward_returns"]["mean_gross_forward"] for c in C]
    print("event fwd gross median over combos:",{k:round(float(np.nanmedian([e[k] for e in ev if e[k] is not None])),4) for k in ("1","3","5","10")})
    # gross vs net median portfolio sharpe
    print("median portfolio net sharpe IS/OOS/ALL:",[round(float(np.nanmedian([c["portfolio"][p]["sharpe"] if c["portfolio"][p]["sharpe"] is not None else np.nan for c in C])),2) for p in ("IS","OOS","ALL")], "2x:",[round(float(np.nanmedian([c["portfolio"][p+"_2x"]["sharpe"] if c["portfolio"][p+"_2x"]["sharpe"] is not None else np.nan for c in C])),2) for p in ("IS","OOS","ALL")])
    print("median trades per combo ALL:", int(np.median([c["trade_stats"]["n"] for c in C])))
