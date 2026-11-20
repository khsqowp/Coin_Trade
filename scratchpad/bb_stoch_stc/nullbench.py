"""Seeded random-entry benchmark using production OHLC execution.

For each series, candidate entry bars are drawn uniformly without replacement,
sorted into chronological order, and simulated one at a time. A candidate is
accepted only after the prior trade's actual exit bar. Direction quotas use
largest-remainder allocation from the observed long/short mix. Thus the null
matches exact count and direction mix when enough non-overlapping candidates
exist; otherwise it uses the maximum feasible prefix of that quota schedule.
"""
from multiprocessing import Pool
import numpy as np
import pandas as pd
from strategy import simulate

_CTX = None
_SIMULATE_ORIGINAL = simulate

def _init_null(ctx):
    global _CTX
    _CTX = ctx

def _random_trade(frame, entry, management, direction, mid, av):
    """Execute one isolated random entry with strategy.simulate fill ordering."""
    o=frame.open.to_numpy(float);h=frame.high.to_numpy(float);l=frame.low.to_numpy(float);c=frame.close.to_numpy(float)
    pos=int(direction);slip=.0002;fee=.0004;capital=10000.;base=1000.
    px=o[entry]*(1+pos*slip);qty=base/px;avg=px;entry_cost=px*qty*fee;lastfill=px;adds=0;entry_atr=av[entry-1]
    def close(i,fill):
        exitpx=fill*(1-slip if pos>0 else 1+slip)
        return ( (exitpx-avg)*qty*pos-(entry_cost+exitpx*qty*fee) )/capital*100, i
    atr_mult=management.get('atr_mult');stopdist=management.get('sl_pct')/100 if management.get('sl_pct') is not None else (atr_mult*entry_atr/avg if atr_mult is not None and np.isfinite(entry_atr) else 999)
    stop=avg*(1-pos*stopdist);tp=avg*(1+pos*management['tp_pct']/100) if management.get('tp_pct') else None
    if (l[entry]<=stop if pos>0 else h[entry]>=stop):return close(entry,o[entry] if (o[entry]<stop if pos>0 else o[entry]>stop) else stop)
    if tp is not None and (h[entry]>=tp if pos>0 else l[entry]<=tp):return close(entry,o[entry] if (o[entry]>tp if pos>0 else o[entry]<tp) else tp)
    if adds<management.get('n_adds',0):
        level=lastfill*(1-pos*management.get('add_spacing_pct',0)/100)
        if (l[entry]<=level if pos>0 else h[entry]>=level):
            addpx=o[entry] if (o[entry]<level if pos>0 else o[entry]>level) else level;addpx*=1+pos*slip
            aq=base*management.get('add_size_mult',1)/addpx;avg=(avg*qty+addpx*aq)/(qty+aq);qty+=aq;entry_cost+=addpx*aq*fee;lastfill=addpx;adds+=1
    for i in range(entry+1,len(frame)):
        stopdist=management.get('sl_pct')/100 if management.get('sl_pct') is not None else (atr_mult*entry_atr/avg if atr_mult is not None and np.isfinite(entry_atr) else 999)
        stop=avg*(1-pos*stopdist);tp=avg*(1+pos*management['tp_pct']/100) if management.get('tp_pct') else None
        if (l[i]<=stop if pos>0 else h[i]>=stop):return close(i,o[i] if (o[i]<stop if pos>0 else o[i]>stop) else stop)
        if tp is not None and (h[i]>=tp if pos>0 else l[i]<=tp):return close(i,o[i] if (o[i]>tp if pos>0 else o[i]<tp) else tp)
        if management.get('max_hold_bars') and i-entry>=management['max_hold_bars']:return close(i,c[i])
        if management.get('bb_mid_exit') and ((pos>0 and h[i]>=mid[i]) or (pos<0 and l[i]<=mid[i])):return close(i,mid[i])
        if adds<management.get('n_adds',0):
            level=lastfill*(1-pos*management.get('add_spacing_pct',0)/100)
            if (l[i]<=level if pos>0 else h[i]>=level):
                addpx=o[i] if (o[i]<level if pos>0 else o[i]>level) else level;addpx*=1+pos*slip
                aq=base*management.get('add_size_mult',1)/addpx;avg=(avg*qty+addpx*aq)/(qty+aq);qty+=aq;entry_cost+=addpx*aq*fee;lastfill=addpx;adds+=1
    return close(len(frame)-1,c[-1])

def _one_rep(rep):
    frames, split_bounds, management, counts, seed, _ = _CTX
    total = 0.0
    for si, (key, df) in enumerate(frames.items()):
        start, stop = split_bounds[key]
        n = max(0, int(counts[key].get('trades', 0)))
        if n == 0 or stop - start < 2:
            continue
        long_n = int(counts[key].get('long', 0)); short_n = int(counts[key].get('short', 0))
        rng = np.random.RandomState(seed + si + int(rep) * 1000003)
        # Largest remainder keeps the requested total and closest direction mix.
        exact_long = n * long_n / max(1, long_n + short_n)
        desired_long = int(np.floor(exact_long + .5))
        dirs = np.array([1] * desired_long + [-1] * (n-desired_long), dtype=int)
        rng.shuffle(dirs)
        # Randomize the candidate set itself. Sorting a full permutation was a
        # no-op: it always restored every bar to chronological order, so the
        # first n feasible entries were identical in every repetition.
        available = np.arange(start + 1, min(stop, len(df)))
        sample_size = min(len(available), max(n * 20, n))
        candidates = np.sort(rng.choice(available, size=sample_size, replace=False))
        local = df.iloc[start:stop].reset_index(drop=True)
        mid = np.asarray(counts[key].get('bb_mid', np.zeros(len(df))), float)[start:stop]
        av = np.asarray(counts[key].get('atr', np.full(len(df), np.nan)), float)[start:stop]
        last_exit = -1; accepted = 0
        for absolute_bar in candidates:
            if accepted >= n:
                break
            local_entry = int(absolute_bar - start)
            if local_entry <= last_exit:
                continue
            # Preserve the simulator seam for callers/tests that inject a substitute.
            if simulate is not _SIMULATE_ORIGINAL:
                begin=max(0,local_entry-1);d=local.iloc[begin:]
                sig=pd.DataFrame({'long':np.zeros(len(d),bool),'short':np.zeros(len(d),bool),'bb_mid':mid[begin:],'atr':av[begin:]})
                sig.iloc[local_entry-begin-1,0 if dirs[accepted]>0 else 1]=True
                result=simulate(d,sig,management,'combined',include_trade_details=True)
                if not result['trade_details']:continue
                trade=result['trade_details'][0];trade_return=float(trade['return']);trade_exit=begin+int(trade['exit'])
            else:
                # Run exactly one trade from the candidate entry and stop at its actual exit.
                trade_return,trade_exit=_random_trade(local,local_entry,management,dirs[accepted],mid,av)
            total += trade_return
            last_exit = trade_exit
            accepted += 1
    return float(total)

def _indexed_rep(rep):
    return int(rep), _one_rep(int(rep))

def run_null(frames, split_bounds, management, strategy_counts, seed=1, repetitions=200, workers=6, progress=None, checkpoint=None):
    """Return pooled per-repetition returns; count rows need trades/long/short."""
    ctx=(frames,split_bounds,management,strategy_counts,int(seed),0)
    with Pool(processes=workers, initializer=_init_null, initargs=(ctx,)) as pool:
        vals=[]; started=__import__('time').monotonic()
        import json, os
        saved={}
        if checkpoint and os.path.exists(checkpoint):
            try:saved={int(x['rep']):float(x['value']) for x in map(json.loads,open(checkpoint))}
            except Exception:saved={}
        todo=[i for i in range(repetitions) if i not in saved]
        current=dict(saved)
        for rep,value in pool.imap_unordered(_indexed_rep, todo,chunksize=1):
            current[int(rep)]=float(value)
            if checkpoint:
                with open(checkpoint,'a') as f:f.write(json.dumps({'rep':int(rep),'value':float(value)})+'\n')
            i=len(current)
            if progress and (i==1 or i%max(1,repetitions//20)==0 or i==repetitions):
                elapsed=__import__('time').monotonic()-started;progress(f'null reps {i}/{repetitions} elapsed={elapsed:.1f}s ETA={elapsed/max(1,i-len(saved))*(repetitions-i):.1f}s')
    return np.asarray([current[i] for i in range(repetitions)],float)

def percentile_of(strategy_return, null_returns):
    a=np.asarray(null_returns,float)
    return float(100*np.mean(a <= strategy_return)) if a.size else float('nan')

def null_summary(null_returns):
    a=np.asarray(null_returns,float)
    return {'null_p50':float(np.percentile(a,50)),'null_p90':float(np.percentile(a,90))}

def verdict(strategy_test_return, null_p90, fragile_flag, pooled_test_trades):
    gates={'beats_p90':bool(strategy_test_return>null_p90),'not_fragile':not bool(fragile_flag),'at_least_30_trades':int(pooled_test_trades)>=30}
    return all(gates.values()), '; '.join(f'{k}={v}' for k,v in gates.items())
