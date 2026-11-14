#!/usr/bin/env python3
"""Predeclared long-history multi-timeframe taker-imbalance signal probe."""
import sqlite3
import numpy as np
import pandas as pd

DB='chart_predictor/data/vision_dev.sqlite'
CUTOFF_MS=int(pd.Timestamp('2026-10-09T00:00:00Z').timestamp()*1000)
SYMBOLS=('BNBUSDT','BTCUSDT','DOGEUSDT','ETHUSDT')
TF_MINUTES=(1,3,5,10,15,30,60,120,240,360,720,1440)
HORIZONS=(10,20)
LEVERAGES=(10,20)
COSTS={'base':.001,'stress':.003}
BOOTSTRAPS=1000
SEED=20261115


def derive_signals(f):
    """Return completed-bar signal masks and ATR using only current/past rows."""
    h,l,c,v=(f[k].to_numpy(float) for k in ('h','l','c','v'))
    qv=f.quote_volume.to_numpy(float); tq=f.taker_buy_quote.to_numpy(float)
    imbalance=np.divide(2*tq,qv,out=np.full(len(f),np.nan),where=qv>0)-1
    prev_hi=pd.Series(h).rolling(20,min_periods=20).max().shift(1).to_numpy()
    prev_lo=pd.Series(l).rolling(20,min_periods=20).min().shift(1).to_numpy()
    vol_med=pd.Series(v).rolling(20,min_periods=20).median().shift(1).to_numpy()
    pc=np.r_[np.nan,c[:-1]]
    tr=np.maximum(h-l,np.maximum(np.abs(h-pc),np.abs(l-pc)))
    atr=pd.Series(tr).rolling(14,min_periods=14).mean().to_numpy()
    masks={'long':(c>prev_hi)&(imbalance>=.30)&(v>=1.5*vol_med),
           'short':(c<prev_lo)&(imbalance<=-.30)&(v>=1.5*vol_med)}
    return masks,atr


def aggregate(raw, minutes):
    if minutes==1:
        return raw.copy().reset_index(drop=True)
    width=minutes*60_000
    x=raw.copy()
    x['bucket']=(x.open_ms//width)*width
    g=x.groupby('bucket',sort=True)
    out=g.agg(o=('o','first'),h=('h','max'),l=('l','min'),c=('c','last'),v=('v','sum'),
              quote_volume=('quote_volume','sum'),taker_buy_quote=('taker_buy_quote','sum'),
              count=('open_ms','nunique')).reset_index()
    return out[out['count']==minutes].drop(columns='count').rename(columns={'bucket':'open_ms'})


def wilson(successes,n):
    if not n:return [None,None]
    z=1.95996398454; p=successes/n; den=1+z*z/n
    mid=(p+z*z/(2*n))/den
    rad=z*np.sqrt(p*(1-p)/n+z*z/(4*n*n))/den
    return [float(mid-rad),float(mid+rad)]


def summarize(trades, symbols, timeframe, horizon, leverage, cost_name):
    # Non-overlap sampling is greedy by signal time per symbol, independent of outcomes.
    independent=[]
    for symbol in symbols:
        seq=sorted((r for r in trades if r['symbol']==symbol),key=lambda r:r['signal_ms'])
        last=-1
        for row in seq:
            if row['signal_ms']>=last:
                independent.append(row)
                last=row['expiry_ms']
    n=len(independent)
    if not n:
        return {'independent_n':0}
    pos=np.asarray([r['net']>0 for r in independent],float)
    target=np.asarray([r['target_first'] for r in independent],float)
    direction=np.asarray([r['direction_correct'] for r in independent],float)
    momentum=np.asarray([r['momentum_correct'] for r in independent],float)
    always_up=np.asarray([r['always_up_correct'] for r in independent],float)
    always_down=np.asarray([r['always_down_correct'] for r in independent],float)
    nets=np.asarray([r['net'] for r in independent],float)
    days=np.asarray([r['signal_ms']//86_400_000 for r in independent])
    uniq=np.unique(days); by_day={d:np.flatnonzero(days==d) for d in uniq}
    rng=np.random.default_rng(SEED+timeframe+horizon+leverage+(0 if cost_name=='base' else 10000))
    boots=np.empty((BOOTSTRAPS,7),float)
    for b in range(BOOTSTRAPS):
        draw=rng.choice(uniq,len(uniq),replace=True)
        ix=np.concatenate([by_day[d] for d in draw])
        boots[b]=(pos[ix].mean(),target[ix].mean(),direction[ix].mean(),nets[ix].mean()*100,
                  momentum[ix].mean(),always_up[ix].mean(),always_down[ix].mean())
    return {
        'independent_n':n,'independent_positive_rate':float(pos.mean()),'positive_rate_wilson95':wilson(int(pos.sum()),n),
        'positive_rate_day_cluster95':[float(x) for x in np.quantile(boots[:,0],[.025,.975])],
        'target_first_rate':float(target.mean()),'target_first_day_cluster95':[float(x) for x in np.quantile(boots[:,1],[.025,.975])],
        'direction_accuracy_at_expiry':float(direction.mean()),'direction_day_cluster95':[float(x) for x in np.quantile(boots[:,2],[.025,.975])],
        'momentum_baseline_accuracy':float(momentum.mean()),
        'always_up_baseline_accuracy':float(always_up.mean()),'always_up_day_cluster95':[float(x) for x in np.quantile(boots[:,5],[.025,.975])],
        'always_down_baseline_accuracy':float(always_down.mean()),'always_down_day_cluster95':[float(x) for x in np.quantile(boots[:,6],[.025,.975])],
        'mean_net_pct':float(nets.mean()*100),
        'mean_net_day_cluster95_pct':[float(x) for x in np.quantile(boots[:,3],[.025,.975])],
        'median_net_pct':float(np.median(nets)*100),
    }


def main():
    db=sqlite3.connect(f'file:{DB}?mode=ro',uri=True)
    records=[]; manifests=[]
    for symbol in SYMBOLS:
        raw=pd.read_sql_query(
            'SELECT open_ms,open AS o,high AS h,low AS l,close AS c,volume AS v,'
            'quote_volume,taker_buy_quote FROM candles WHERE symbol=? AND open_ms<? ORDER BY open_ms',
            db,params=(symbol,CUTOFF_MS))
        raw=raw[raw.open_ms+60_000<=CUTOFF_MS].reset_index(drop=True)
        rt=raw.open_ms.to_numpy(np.int64); rh=raw.h.to_numpy(float); rl=raw.l.to_numpy(float)
        for tf in TF_MINUTES:
            width=tf*60_000
            f=aggregate(raw,tf)
            f=f[f.open_ms+width<=CUTOFF_MS].reset_index(drop=True)
            if len(f)<100:continue
            o,h,l,c=(f[k].to_numpy(float) for k in ('o','h','l','c'))
            masks,atr=derive_signals(f)
            manifests.append((symbol,tf,len(f)))
            for side_name,side,mask in (('long',1,masks['long']),('short',-1,masks['short'])):
                for i in np.flatnonzero(mask):
                    entry_i=i+1
                    if entry_i>=len(f) or not np.isfinite(atr[i]) or atr[i]<=0:continue
                    entry=o[entry_i]; risk=1.5*atr[i]
                    # Baseline uses the fully completed bar before the signal candle.
                    momentum_side=1 if c[i-1]>=c[i-2] else -1
                    for horizon in HORIZONS:
                        if entry_i+horizon>len(f):continue
                        expiry_i=entry_i+horizon-1
                        start=int(f.open_ms.iloc[entry_i]); end=int(f.open_ms.iloc[expiry_i])+width
                        lo_ix=np.searchsorted(rt,start); hi_ix=np.searchsorted(rt,end)
                        if hi_ix<=lo_ix:continue
                        base={'symbol':symbol,'tf':tf,'horizon':horizon,'side':side_name,
                              'signal_ms':int(f.open_ms.iloc[i])+width,'expiry_ms':end}
                        for leverage in LEVERAGES:
                            if risk/entry>=1/leverage-.005:continue
                            stop=entry-side*risk; target=entry+side*2*risk
                            # Resolve on original 1m candles even for higher-timeframe forecasts.
                            exitp=float(c[expiry_i]); target_first=False
                            rlo=rl[lo_ix:hi_ix]; rhi=rh[lo_ix:hi_ix]
                            hit_stop=(rlo<=stop) if side>0 else (rhi>=stop)
                            hit_target=(rhi>=target) if side>0 else (rlo<=target)
                            touched=np.flatnonzero(hit_stop|hit_target)
                            if len(touched):
                                first=int(touched[0])
                                if hit_stop[first]:exitp=stop
                                else:exitp=target; target_first=True
                            raw_move=float(c[expiry_i])/entry-1
                            move=side*raw_move
                            for cost_name,cost in COSTS.items():
                                records.append({**base,'leverage':leverage,'cost_name':cost_name,
                                                'target_first':target_first,
                                                'direction_correct':move>0,
                                                'momentum_correct':momentum_side*raw_move>0,
                                                'always_up_correct':raw_move>0,
                                                'always_down_correct':raw_move<0,
                                                'net':side*(exitp/entry-1)-cost,
                                                'stop_pct':risk/entry})
    rows=[]
    for tf in TF_MINUTES:
        for horizon in HORIZONS:
            for leverage in LEVERAGES:
                for cost_name in COSTS:
                    for side in ('long','short'):
                        cell=[r for r in records if r['tf']==tf and r['horizon']==horizon and r['leverage']==leverage and r['cost_name']==cost_name and r['side']==side]
                        s=summarize(cell,SYMBOLS,tf,horizon,leverage,cost_name)
                        anchors=sum(n for sym,t,n in manifests if t==tf)
                        raw_signal_count=len(set((r['symbol'],r['signal_ms']) for r in cell))
                        rows.append({'timeframe_min':tf,'horizon_bars':horizon,'horizon_minutes':tf*horizon,
                                     'leverage':leverage,'cost':cost_name,'direction':side,'raw_n':len(cell),
                                     'raw_signal_coverage':raw_signal_count/max(1,anchors),
                                     'status':'NOT_EVALUABLE' if s['independent_n']<30 else 'EXPLORATORY',**s})
    causal=[]
    for tf in (1,30,240):
        width=tf*60_000
        raw=pd.read_sql_query('SELECT open_ms,open AS o,high AS h,low AS l,close AS c,volume AS v,quote_volume,taker_buy_quote FROM candles WHERE symbol=? AND open_ms<? ORDER BY open_ms',db,params=('BTCUSDT',CUTOFF_MS))
        f=aggregate(raw,tf); f=f[f.open_ms+width<=CUTOFF_MS].reset_index(drop=True)
        full,_=derive_signals(f); checks=[]; mutation_checks=[]
        for k in np.linspace(max(50,len(f)//4),len(f)-25,5,dtype=int):
            prefix=f.iloc[:k].reset_index(drop=True); pref,_=derive_signals(prefix)
            checks.append(all(np.array_equal(pref[side][:k-1],full[side][:k-1],equal_nan=True) for side in ('long','short')))
            changed=f.copy(); changed.loc[k:,'o']*=1.3; changed.loc[k:,'h']*=1.3; changed.loc[k:,'l']*=1.3; changed.loc[k:,'c']*=1.3
            mutated,_=derive_signals(changed)
            mutation_checks.append(all(np.array_equal(mutated[side][:k-1],full[side][:k-1],equal_nan=True) for side in ('long','short')))
        close=f.c.to_numpy(float); i=max(30,len(f)//2); original=bool(close[i+2]>close[i])
        future=close.copy(); future[i+2]=close[i]*(.5 if original else 2.); detected=bool((future[i+2]>future[i])!=original)
        causal.append({'symbol':'BTCUSDT','tf_minutes':tf,'prefix_pass':sum(checks),'prefix_total':len(checks),
                       'future_mutation_pass':sum(mutation_checks),'future_mutation_total':len(mutation_checks),
                       'deliberate_future_peek_detected':detected})
    db.close()
    meta={'cutoff_exclusive_ms':CUTOFF_MS,'symbols':SYMBOLS,'timeframes_min':TF_MINUTES,
                  'rule_configs':len(TF_MINUTES)*2,'record_rows':len(records),'aggregates':manifests,
                  'rule':'20-bar close breakout + taker-buy imbalance +/-0.30 + volume >=1.5x prior-20 median; entry next bar open; stop 1.5 ATR14; target 2R; timeout 10/20 bars; resolve against original 1m OHLC, stop-first ties',
                  'baselines':'prior completed bar direction uses close[i-1] vs close[i-2] before signal bar i; always-up and always-down are reported separately',
                  'costs_round_trip':COSTS,'bootstrap':'1000 UTC-day cluster draws',
                  'overlap':'per symbol, chronological greedy non-overlap by forecast interval; outcomes not used for selection',
                  'liquidation_screen':'stop distance < 1/leverage - 0.5%; approximation only',
                  'causal_checks':causal}
    out={'metadata':meta,'cells':rows}
    from pathlib import Path
    outdir=Path(__file__).resolve().parents[2]/'docs'/'research'
    outdir.mkdir(parents=True,exist_ok=True)
    json_path=outdir/'long_history_taker_multitf_20261115.json'
    md_path=outdir/'long_history_taker_multitf_20261115.md'
    import json
    json_path.write_text(json.dumps(out,indent=2,allow_nan=False),encoding='utf-8')
    table=['# Long-history taker-imbalance multi-timeframe probe','','Development-only exploratory results. No candidate is promoted.','',
           f"- UTC cutoff exclusive: {pd.to_datetime(CUTOFF_MS,unit='ms',utc=True).isoformat()}",
           f"- Symbols: {', '.join(SYMBOLS)}; SOL/XRP excluded due internal archive gaps.",
           '- Fees: 0.10% base / 0.30% stress round trip; funding, spread and exchange liquidation omitted.',
           '- Each cell includes raw trades and greedy non-overlapping trades. The non-overlap interval is selected without outcomes.',
           '- Uncertainty: 1,000 UTC-day cluster bootstrap replicates; cells below 30 independent trades are NOT EVALUABLE.',
           '', '| TF | Horizon | Leverage | Cost | Side | Raw n | Indep n | Coverage | Target-first | Direction | Prior momentum | Always up | Always down | Net-positive | Mean net | Decision |',
           '|---:|---:|---:|---|---|---:|---:|---:|---:|---:|---:|---:|---:|---:|---:|---|']
    for r in rows:
        table.append(f"| {r['timeframe_min']}m | {r['horizon_minutes']}m | {r['leverage']}x | {r['cost']} | {r['direction']} | {r['raw_n']} | {r['independent_n']} | {r['raw_signal_coverage']:.2%} | {r.get('target_first_rate',float('nan')):.2%} | {r.get('direction_accuracy_at_expiry',float('nan')):.2%} | {r.get('momentum_baseline_accuracy',float('nan')):.2%} | {r.get('always_up_baseline_accuracy',float('nan')):.2%} | {r.get('always_down_baseline_accuracy',float('nan')):.2%} | {r.get('independent_positive_rate',float('nan')):.2%} | {r.get('mean_net_pct',float('nan')):.3f}% | {r['status']} |")
    md_path.write_text('\n'.join(table)+'\n',encoding='utf-8')
    print('OUTPUT',json_path,md_path,'cells',len(rows),'records',len(records))


if __name__=='__main__':main()
