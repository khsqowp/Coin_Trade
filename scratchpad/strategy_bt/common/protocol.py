"""Chronological train/grid selection, frozen test and matched random-entry null."""
import itertools
import numpy as np
import pandas as pd
from .engine import simulate
from .verdict import decide, adjusted_decide

def validate_grid(grid):
    if not isinstance(grid,dict): raise ValueError("PARAM_GRID must be a mapping")
    if len(grid)>3: raise ValueError("PARAM_GRID supports at most 3 axes")
    for key,values in grid.items():
        if not isinstance(values,(list,tuple)) or not 1<=len(values)<=4: raise ValueError(f"PARAM_GRID axis {key} must have 1..4 values")
    return [dict(zip(grid,values)) for values in itertools.product(*grid.values())] or [{}]

def check_no_lookahead(plugin,df,params=None):
    """Assert full-frame signals through each prefix equal independently recomputed prefix signals."""
    params=dict(params or getattr(plugin,"PARAMS",{})); full=plugin.signals(df.copy(),**params)
    if not isinstance(full,pd.DataFrame): raise AssertionError("signals must return DataFrame")
    cols=[c for c in full if c in {"long_entry","short_entry","long_exit","short_exit","stop_pct","atr_stop","tp_pct","max_hold"}]
    n=len(df)
    probes=sorted(set([min(n,5),min(n,17),max(1,n//2),max(1,n-1)]))
    for end in probes:
        if end<=0:continue
        prefix=plugin.signals(df.iloc[:end].copy(),**params)
        pd.testing.assert_frame_equal(full[cols].iloc[:end].reset_index(drop=True),prefix[cols].reset_index(drop=True),check_dtype=False,check_exact=False,rtol=1e-10,atol=1e-12)
    return True

def _summary(frames, plugin, params, side, seed, null_reps=200):
    per={}; alltr=[]
    for key,df in frames.items():
        sig=plugin.signals(df.copy(),**params); trades,m=simulate(df,sig,params,side=side); per[key]=(trades,m,sig); alltr.extend(trades)
    return per,alltr

def _aggregate(per):
    trades=[t for ts,_,_ in per.values() for t in ts]
    return {"return":sum(t["pct"] for t in trades),"pf":sum(t["net"] for t in trades if t["net"]>0)/abs(sum(t["net"] for t in trades if t["net"]<0)) if any(t["net"]<0 for t in trades) else float("inf"),"win_rate":float(np.mean([t["net"]>0 for t in trades])*100) if trades else 0.,"max_dd":min((m["max_dd"] for _,m,_ in per.values()),default=0.),"trades":len(trades)}

def _null(frames,per,plugin,params,side,seed,repetitions=200):
    rng=np.random.default_rng(seed); vals=[]
    for rep in range(repetitions):
        total=0.
        for (key,df),(actual,_,sig) in zip(frames.items(),per.values()):
            n=len(actual)
            if n==0 or len(df)<2:continue
            longs=sum(t["side"]=="long" for t in actual); shorts=n-longs; dirs=np.array(["long"]*longs+["short"]*shorts,dtype=object); rng.shuffle(dirs)
            # Randomized signal bars are generated only in this series' TEST slice by caller.
            starts=np.arange(1,len(df)); rng.shuffle(starts); chosen=np.sort(starts[:min(len(starts),max(n*4,n))])
            r=pd.DataFrame(False,index=df.index,columns=["long_entry","short_entry"])
            for col in ("long_exit","short_exit","stop_pct","atr_stop","tp_pct","max_hold"):
                if col in sig:r[col]=sig[col].to_numpy()
            for j,ix in enumerate(chosen): r.iloc[ix-1,0 if dirs[j%len(dirs)]=="long" else 1]=True
            randomized,_=simulate(df,r,params,side=side)
            total+=sum(t["pct"] for t in randomized[:n])
            # Infeasible remaining trades are simply not fabricated.
        vals.append(total)
    return np.asarray(vals)

def evaluate(plugin, symbols, timeframe, data_dir, *, n_slice_strategies=30, seed=1729, null_repetitions=200, secondary_symbols=()):
    defaults=dict(getattr(plugin,"PARAMS",{})); grid=[{**defaults,**point} for point in validate_grid(getattr(plugin,"PARAM_GRID",{}))]; side=getattr(plugin,"SIDES","both")
    if side not in ("long","short","both"): raise ValueError("SIDES must be long, short, or both")
    def load(universe):
        frames={}
        for symbol in universe:
            path=data_dir/f"{symbol}_{timeframe}.parquet"
            if path.exists(): frames[symbol]=pd.read_parquet(path)
        return frames
    frames=load(symbols)
    if not frames:return {"status":"INELIGIBLE","reason":"NO_DATA","timeframe":timeframe}
    splits={k:int(len(v)*.6) for k,v in frames.items()}; train={k:v.iloc[:splits[k]].reset_index(drop=True) for k,v in frames.items()}; test={k:v.iloc[splits[k]:].reset_index(drop=True) for k,v in frames.items()}
    ranked=[]
    for params in grid:
        per,trades=_summary(train,plugin,params,side,seed)
        ranked.append((_aggregate(per)["return"],params,len(trades),per))
    best=max(ranked,key=lambda x:x[0]); candidates=len(grid)
    if best[2]<30:return {"status":"INELIGIBLE","reason":"TRAIN_TRADES_LT_30","timeframe":timeframe,"train_trades":best[2],"n_candidates_tested":candidates,"grid_points":candidates,"plateau":"NA" if candidates==1 else "FRAGILE"}
    # Plateau: at least 70% of immediately adjacent grid points must be profitable and >=50% of winner.
    neighbor_scores=[]
    if len(grid)==1: plateau="NA"
    else:
        axes=list(getattr(plugin,"PARAM_GRID",{}).keys())
        for score,params,_,_ in ranked:
            changed=[k for k in axes if params.get(k)!=best[1].get(k)]
            if len(changed)!=1:continue
            axis=changed[0]; values=list(getattr(plugin,"PARAM_GRID",{})[axis])
            if abs(values.index(params[axis])-values.index(best[1][axis]))==1:neighbor_scores.append(score)
        positive=sum(s>0 and s>=best[0]*.5 for s in neighbor_scores)
        plateau="ROBUST" if neighbor_scores and positive/len(neighbor_scores)>=.7 else "FRAGILE"
    tp,tt=_summary(test,plugin,best[1],side,seed); actual=_aggregate(tp)
    # Restrict null to test segment; same position management and direction mix.
    nullframes={k:df for k,df in test.items()}; null=_null(nullframes,tp,plugin,best[1],side,seed,null_repetitions)
    percentile=float(100*np.mean(null<=actual["return"])) if len(null) else None
    positive=sum(m["total_return"]>0 for _,m,_ in tp.values())
    raw=decide(percentile,plateau,actual["trades"],actual["return"],positive,len(symbols)); adjusted=adjusted_decide(percentile,plateau,actual["trades"],actual["return"],positive,n_slice_strategies,len(symbols))
    secondary={}
    if secondary_symbols:
        sf=load(secondary_symbols)
        if sf:
            sp,st=_summary(sf,plugin,best[1],side,seed);secondary=_aggregate(sp)
    return {"status":"DONE","timeframe":timeframe,"params":best[1],"n_candidates_tested":candidates,"grid_points":candidates,"plateau":plateau,"train":_aggregate(best[3]),"test":actual,"null_percentile":percentile,"null_returns":null.tolist(),"positive_symbols":positive,"symbols":len(frames),"verdict":raw,"adjusted_verdict":adjusted,"secondary":secondary}
