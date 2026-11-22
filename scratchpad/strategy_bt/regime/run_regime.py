"""Regime-switching study runner. Execute from strategy_bt with python -m regime.run_regime."""
from __future__ import annotations
import argparse, importlib.util, itertools, json, math, time, traceback
from pathlib import Path
import numpy as np
import pandas as pd

ROOT=Path(__file__).resolve().parents[1]
SYMBOLS=('BTCUSDT','ETHUSDT','BNBUSDT','XRPUSDT')
KS=(2,3,5,7)
FINALISTS={'jesse_simple_bollinger','btc-macd-15-41-12','turtle-system-2','btc-bollinger-37-16','btc-roc-36-9pct'}
EDGES={2:[0.],3:[-1.,1.],5:[-3.,-1.,1.,3.],7:[-3.,-1.,1.,3.]}

def adx14(high,low,close):
    """Wilder ADX with arithmetic-seeded Wilder smoothing; warmup is NaN."""
    h,l,c=map(lambda x:np.asarray(x,dtype=float),(high,low,close)); n=len(c)
    out=np.full(n,np.nan)
    if n<28:return out
    up=h[1:]-h[:-1]; dn=l[:-1]-l[1:]
    plus=np.where((up>dn)&(up>0),up,0.); minus=np.where((dn>up)&(dn>0),dn,0.)
    tr=np.maximum.reduce((h[1:]-l[1:],np.abs(h[1:]-c[:-1]),np.abs(l[1:]-c[:-1])))
    def wilder(x):
        z=np.full(len(x),np.nan)
        if len(x)>=14:
            z[13]=np.sum(x[:14]);
            for j in range(14,len(x)):z[j]=z[j-1]-z[j-1]/14+x[j]
        return z
    st,sp,sm=map(wilder,(tr,plus,minus))
    p=100*sp/st; m=100*sm/st; dx=100*np.abs(p-m)/(p+m)
    # First ADX averages DX indices 13..26 (bar indices 14..27).
    if len(dx)>=27:
        ad=np.full(len(dx),np.nan); ad[26]=np.nanmean(dx[13:27])
        for j in range(27,len(dx)):ad[j]=(ad[j-1]*13+dx[j])/14
        out[1:]=ad
    return out

def trend_score(daily_df):
    c=daily_df.close.astype(float); sma=c.rolling(200,min_periods=200).mean()
    S=(c/sma-1)/.10+(sma/sma.shift(20)-1)/.05
    return S.to_numpy(float),adx14(daily_df.high,daily_df.low,c)

def labels(S,ADX,K):
    s=np.asarray(S,float); a=np.asarray(ADX,float); b=np.searchsorted(np.asarray(EDGES[K]),s,side='right').astype(float)
    b[~(np.isfinite(s)&np.isfinite(a))]=np.nan
    if K==7:
        # Ordered: strong down, down strong/weak, side, up weak/strong, strong up.
        base=np.searchsorted(np.asarray(EDGES[5]),s,side='right')
        for i in range(len(b)):
            if not np.isfinite(b[i]):continue
            if base[i]==0:b[i]=0
            elif base[i]==1:b[i]=1 if a[i]>=25 else 2
            elif base[i]==2:b[i]=3
            elif base[i]==3:b[i]=4 if a[i]<25 else 5
            else:b[i]=6
    return b

def ambiguous(S,ADX,K):
    s=np.asarray(S,float); a=np.asarray(ADX,float); edges=EDGES[5] if K==7 else EDGES[K]
    out=(np.min(np.abs(s[:,None]-np.asarray(edges)),axis=1)<.25)|(a<15)
    if K==7:
        base=np.searchsorted(np.asarray(EDGES[5]),s,side='right')
        split=(base==1)|(base==3)
        out |= split&(np.abs(a-25)<2)
    out[~(np.isfinite(s)&np.isfinite(a))]=True
    return out

def up_set(K): return {1} if K==2 else ({2} if K==3 else ({3,4} if K==5 else {4,5,6}))
def down_set(K): return {0} if K in (2,3) else ({0,1} if K==5 else {0,1,2})

def _regime_lut(K, side):
    size={2:2,3:3,5:5,7:7}[K]
    allowed=up_set(K) if side=='long' else down_set(K)
    return np.isin(np.arange(size), list(allowed))

def lookup_labels(timestamps, daily_index, L):
    di=pd.DatetimeIndex(daily_index).floor('D'); ti=pd.DatetimeIndex(timestamps).floor('D')-pd.Timedelta(days=1)
    ix=di.get_indexer(ti); out=np.full(len(ix),np.nan); ok=ix>=0; out[ok]=np.asarray(L)[ix[ok]]; return out

def resample_4h(df):
    d=df.copy(); d.index=pd.DatetimeIndex(d.index); groups=d.index.floor('4h')
    cnt=pd.Series(1,index=d.index).groupby(groups).sum(); complete=cnt[cnt==4].index
    return d.groupby(groups).agg({'open':'first','high':'max','low':'min','close':'last','volume':'sum'}).loc[complete]

def _load(path):
    spec=importlib.util.spec_from_file_location('regime_plugin_'+Path(path).stem,path)
    mod=importlib.util.module_from_spec(spec); spec.loader.exec_module(mod); return mod

def discover_candidates(quick=False):
    rows=[]; skipped_15m=0
    for f in sorted((ROOT/'results').glob('slice_*/summary.csv')):
        try: tab=pd.read_csv(f)
        except Exception:continue
        for _,r in tab.iterrows():
            if str(r.get('status','')).upper()!='DONE':continue
            try:p=json.loads(r['params']) if isinstance(r['params'],str) else r['params']
            except Exception:continue
            sid=str(r.get('strategy_id',r.get('spec_id',''))); tf=str(r.get('timeframe',''))
            if tf=='15m': skipped_15m+=1; continue
            matches=[]
            for pf in (ROOT/'plugins'/f.parent.name).glob('*.py'):
                if pf.name.startswith('_'):continue
                try:
                    mod=_load(pf)
                    if getattr(mod,'SPEC_ID',None)==sid:matches.append((pf,mod))
                except Exception:pass
            if matches:rows.append(dict(strategy_id=sid,timeframe=tf,train_return=float(r.get('train_return',0)),params=p,plugin_path=str(matches[0][0]),sides=getattr(matches[0][1],'SIDES','both'),finalist=sid in FINALISTS))
    discover_candidates.skipped_15m=skipped_15m
    if not rows:return []
    df=pd.DataFrame(rows).sort_values('train_return',ascending=False).drop_duplicates(['strategy_id','timeframe'])
    top=set(df.head(3 if quick else 20).index); chosen=df[df.finalist | df.index.isin(top)]
    return chosen.to_dict('records')

def _data(symbol,tf):
    p=ROOT/'data_long'/f'{symbol}_{tf}.parquet'
    if tf=='4h':
        p=ROOT/'data_long'/f'{symbol}_1h.parquet'
        return resample_4h(pd.read_parquet(p))
    return pd.read_parquet(p)

def _trade_frame(trades,df,cid,tf,sym):
    idx=pd.DatetimeIndex(df.index)
    if idx.tz is not None: idx=idx.tz_localize(None)
    return [dict(candidate=cid,tf=tf,symbol=sym,entry_time=idx[int(t['entry'])],exit_time=idx[int(t['exit'])],side=t['side'],pct=float(t['pct'])) for t in trades]

def _dd(pct,exit_time):
    if not len(pct):return 0.
    x=np.asarray(pct)[np.argsort(np.asarray(exit_time))]; eq=np.cumsum(x); peak=np.maximum.accumulate(np.r_[0.,eq])[1:]
    return float(np.min(eq-peak))

def _metric(rows,mask=None):
    if mask is not None: rows=rows[mask]
    pct=rows['pct'].to_numpy(float) if len(rows) else np.array([])
    return float(pct.sum()),len(pct),_dd(pct,rows['exit_time'].to_numpy() if len(rows) else [])

def _walkforward(trades,lab,K,pool,dates):
    """Vectorized expanding-window selection; return mask aligns to input rows."""
    candidate=trades.candidate.to_numpy(np.int32)
    entry=np.asarray(trades.entry_time,dtype='datetime64[ns]')
    exit_=np.asarray(trades.exit_time,dtype='datetime64[ns]')
    pct=trades.pct.to_numpy(float)
    if 'entry_day' in trades:
        day=trades.entry_day.to_numpy(np.int64); regime=np.asarray(lab)[day]
    else: regime=trades.regime.to_numpy(float)
    return _walkforward_np(candidate,entry,exit_,pct,regime,pool,dates)

def _walkforward_np(candidate,entry,exit_,pct,regime,pool,dates,with_choices=True):
    """Numpy-only worker used by the repeated null draws."""
    candidate=np.asarray(candidate,dtype=np.int32); entry=np.asarray(entry,dtype='datetime64[ns]')
    exit_=np.asarray(exit_,dtype='datetime64[ns]'); pct=np.asarray(pct,float); regime=np.asarray(regime,float)
    valid=np.isfinite(regime); kept=np.zeros(len(candidate),bool); choices=[]
    if not len(dates): return kept,choices
    stop=np.asarray(dates,dtype='datetime64[ns]')[-1]+np.timedelta64(1,'D')
    bounds=[]; year,month=2018,7
    while np.datetime64(f'{year:04d}-{month:02d}-01','ns')<stop:
        bounds.append(np.datetime64(f'{year:04d}-{month:02d}-01','ns'))
        month+=6
        if month>12: year+=1; month-=12
    if not bounds: bounds=[np.datetime64('2018-07-01','ns')]
    bounds=np.asarray(bounds,dtype='datetime64[ns]')
    pool=np.asarray(pool,dtype=np.int32); nreg=int(np.nanmax(regime[valid]))+1 if valid.any() else 0
    ncan=int(candidate.max())+1 if len(candidate) else 0; width=max(1,ncan)
    for bi,T in enumerate(bounds):
        end=bounds[bi+1] if bi+1<len(bounds) else stop
        train_idx=np.flatnonzero(valid&(exit_<T)&np.isin(candidate,pool))
        future_idx=np.flatnonzero(valid&(entry>=T)&(entry<end))
        sums=np.bincount(candidate[train_idx]*max(1,nreg)+regime[train_idx].astype(int),weights=pct[train_idx],minlength=width*max(1,nreg)).reshape(width,max(1,nreg))
        counts=np.bincount(candidate[train_idx]*max(1,nreg)+regime[train_idx].astype(int),minlength=width*max(1,nreg)).reshape(width,max(1,nreg))
        for r in np.unique(regime[future_idx].astype(int)):
            eligible=np.flatnonzero((counts[:,r]>=15)&(sums[:,r]>0)&np.isin(np.arange(width),pool))
            best=None; bestsum=0.; nbest=0
            if len(eligible):
                # np.argmax returns the first index, giving lowest-candidate tie break.
                best=int(eligible[np.argmax(sums[eligible,r])]); bestsum=float(sums[best,r]); nbest=int(counts[best,r])
                selected=future_idx[(regime[future_idx].astype(int)==r)&(candidate[future_idx]==best)]; kept[selected]=True
            if with_choices: choices.append(dict(retrain_date=pd.Timestamp(T),regime=int(r),chosen_candidate=best,train_trades=nbest,train_sum=bestsum))
    return kept,choices

def run(draws=1000,quick=False,out=None):
    started=time.time(); out=Path(out or ROOT/'regime/results'); out.mkdir(parents=True,exist_ok=True)
    candidates=discover_candidates(quick); pd.DataFrame([{k:v for k,v in c.items() if k!='plugin_path'} for c in candidates],columns=['strategy_id','timeframe','train_return','params','sides','finalist']).to_csv(out/'candidates.csv',index=False)
    errors=[]; alltr=[]; timelog=[]
    for cid,cand in enumerate(candidates):
        mod=_load(cand['plugin_path']); tf=cand['timeframe']; params=cand['params']
        for sym in SYMBOLS:
            t0=time.time()
            try:
                df=_data(sym,tf); sig=mod.signals(df.copy(),**params)
                from common.engine import simulate
                tr,_=simulate(df,sig,params,side=getattr(mod,'SIDES','both')); alltr.extend(_trade_frame(tr,df,cid,tf,sym))
            except Exception as e:errors.append(dict(candidate=cand['strategy_id'],symbol=sym,error=repr(e),trace=traceback.format_exc(limit=3)))
            timelog.append(dict(candidate=cand['strategy_id'],symbol=sym,seconds=time.time()-t0))
    td=pd.DataFrame(alltr,columns=['candidate','tf','symbol','entry_time','exit_time','side','pct']); tdout=td.copy(); tdout['candidate']=tdout.candidate.map({i:c['strategy_id'] for i,c in enumerate(candidates)}); tdout.to_csv(out/'v0_trades.csv',index=False)
    pd.DataFrame(errors).to_csv(out/'errors.csv',index=False); pd.DataFrame(timelog).to_csv(out/'timings.csv',index=False)
    if td.empty:
        for name in ('v0.csv','results.csv','summary_by_K.csv','episodes.csv','v1_choices.csv'):pd.DataFrame().to_csv(out/name,index=False)
        (out/'trials.txt').write_text('0\n'); elapsed=time.time()-started
        (out/'run_meta.json').write_text(json.dumps(dict(n_candidates=len(candidates),N_trials=0,draws=draws,elapsed_seconds=elapsed,skipped_items=[{'reason':'15m rows dropped'},*errors]),indent=2)+'\n'); return elapsed
    # BTC-derived labels + symbol-specific trailing means
    frames={s:pd.read_parquet(ROOT/'data_long'/f'{s}_1d.parquet') for s in SYMBOLS}
    btc=frames['BTCUSDT']; S,A=trend_score(btc); dayix=pd.DatetimeIndex(btc.index)
    if dayix.tz is not None: dayix=dayix.tz_localize(None)
    dayix=dayix.floor('D')
    dayids=dayix.get_indexer(pd.DatetimeIndex(td.entry_time).floor('D')-pd.Timedelta(days=1))
    valid=dayids>=0; td=td.loc[valid].copy().reset_index(drop=True); dayids=dayids[valid]
    mask=np.isfinite(S[dayids])
    allt=td.loc[mask].copy().reset_index(drop=True); dayids=dayids[mask]
    allt['entry_day']=dayids; allt['intest']=(pd.to_datetime(allt.entry_time)>=pd.Timestamp('2018-07-01'))
    test=allt.loc[allt.intest].copy().reset_index(drop=True)
    rng=np.random.default_rng(1729); rows=[]; choicesout=[]; epout=[]; ntrials=4*(2+len(candidates)*2)
    (out/'trials.txt').write_text(str(ntrials)+'\n')
    for K in KS:
        L=labels(S,A,K); amb=ambiguous(S,A,K)
        # Episode inventory
        for regime in np.unique(L[np.isfinite(L)]):
            z=L==regime; transitions=np.sum(z&~np.r_[False,z[:-1]])
            zt=z&(dayix>=pd.Timestamp('2018-07-01')); et=np.sum(zt&~np.r_[False,zt[:-1]])
            epout.append(dict(K=K,regime=int(regime),episodes_full=int(transitions),episodes_test=int(et),bars_days=int(z.sum()),unevaluable=et<3))
        regime=L[test.entry_day.to_numpy()].astype(int); test['regime']=regime
        # Draw-loop data are immutable numpy arrays; no pandas operations occur per draw.
        all_cand=allt.candidate.to_numpy(np.int32); all_day=allt.entry_day.to_numpy(np.int32)
        all_entry=allt.entry_time.to_numpy(dtype='datetime64[ns]'); all_exit=allt.exit_time.to_numpy(dtype='datetime64[ns]')
        all_pct=allt.pct.to_numpy(float); all_long=allt.side.to_numpy()=='long'
        test_cand=test.candidate.to_numpy(np.int32); test_day=test.entry_day.to_numpy(np.int32)
        test_pct=test.pct.to_numpy(float); test_entry=test.entry_time.to_numpy(dtype='datetime64[ns]')
        test_sym=test.symbol.to_numpy(); test_regime=regime
        all_intest=allt.intest.to_numpy()
        luts={side:_regime_lut(K,side) for side in ('long','short')}
        v0by={}; v0rows=[]
        for cid,c in enumerate(candidates):
            x=test[test.candidate==cid]; ret,n,dd=_metric(x); v0by[cid]=(ret,n,dd)
            v0rows.append(dict(candidate=c['strategy_id'],timeframe=c['timeframe'],v0_return=ret,v0_trades=n,v0_maxdd=dd))
        pd.DataFrame(v0rows).to_csv(out/'v0.csv',index=False)
        # V2/V3 per candidate and V1 pools
        configs=[('V2',cid,None) for cid in range(len(candidates))]+[('V3',cid,None) for cid in range(len(candidates))]+[('V1',None,'ALL'),('V1',None,'FINALISTS')]
        for variant,cid,poolname in configs:
            v3cache={}; v1used=set()
            if variant=='V1': pool=np.array([i for i,c in enumerate(candidates) if poolname=='ALL' or c['finalist']]); allkeep,ch=_walkforward(allt,L,K,pool,dayix); obskeep=allkeep[all_intest]; v1used={z['regime'] for z in ch if z['chosen_candidate'] is not None}; choicesout += [dict(K=K,pool=poolname,**{**z,'chosen_candidate':candidates[z['chosen_candidate']]['strategy_id'] if z['chosen_candidate'] is not None else 'CASH'}) for z in ch]; baseline=float(np.mean([v0by[i][0] for i in pool])) if len(pool) else 0.; name=poolname
            else:
                name=candidates[cid]['strategy_id']; baseline=v0by[cid][0]
                if variant=='V2': sideok=np.where(test.side.to_numpy()=='long',luts['long'][regime],luts['short'][regime]); obskeep=sideok&~amb[test_day]
                else:
                    obskeep=np.ones(len(test),bool)
                    # symbol trailing 180-day means, one-day lag
                    for sym in SYMBOLS:
                        ix=np.flatnonzero(test_sym==sym)
                        sf,af=trend_score(frames[sym]); ms=pd.Series(sf).rolling(180,min_periods=1).mean().shift(1).to_numpy(); ma=pd.Series(af).rolling(180,min_periods=1).mean().shift(1).to_numpy()
                        si=pd.DatetimeIndex(frames[sym].index)
                        if si.tz is not None:si=si.tz_localize(None)
                        dloc=si.floor('D').get_indexer(pd.DatetimeIndex(test_entry[ix]).floor('D')-pd.Timedelta(days=1)); e=ambiguous(ms,ma,K); obskeep[ix]=~e[np.maximum(dloc,0)]
                        v3cache[sym]=(ix,e,np.flatnonzero(np.isfinite(ms)&np.isfinite(ma)),np.maximum(dloc,0))
            target=(test_cand==cid) if cid is not None else np.isin(test_cand,pool)
            obs=obskeep&target; obsret,nt,dd=_metric(test,obs)
            win18=(test_entry>=np.datetime64('2018-07-01'))&(test_entry<np.datetime64('2019-01-01')); win22=pd.DatetimeIndex(test_entry).year==2022
            r18,_,_=_metric(test,obs&win18); r22,_,_=_metric(test,obs&win22)
            if cid is not None:v0ret,v0n,v0dd=v0by[cid]; v18,_,_=_metric(test,(test.candidate==cid)&win18); v22,_,_=_metric(test,(test.candidate==cid)&win22)
            else:
                v0ret=baseline; v0n=int(np.mean([v0by[i][1] for i in pool])); v0dd=float(np.mean([v0by[i][2] for i in pool])); v18=float(np.mean([_metric(test,(test.candidate==i)&win18)[0] for i in pool])); v22=float(np.mean([_metric(test,(test.candidate==i)&win22)[0] for i in pool]))
            used=set(up_set(K)| (down_set(K) if cid is not None and candidates[cid]['sides']!='long' else set())) if variant=='V2' else (v1used if variant=='V1' else set())
            epok=all(next((e['episodes_test']>=3 for e in epout if e['K']==K and e['regime']==r),False) for r in used)
            # Null draws use circular shifts over the valid BTC label track.
            valid_ix=np.flatnonzero(np.isfinite(L)); nvalid=len(valid_ix); shifts=np.arange(30,nvalid-30+1,dtype=int); count=0; null=np.empty(draws)
            for j in range(draws):
                sh=int(rng.choice(shifts)) if len(shifts) else 0
                sl=L.copy(); sa=amb.copy(); sl[valid_ix]=np.roll(L[valid_ix],sh); sa[valid_ix]=np.roll(amb[valid_ix],sh)
                sr=sl[test_day].astype(float)
                if variant=='V2': keep=np.where(all_long[allt.intest.to_numpy()],luts['long'][sr.astype(int)],luts['short'][sr.astype(int)])&~sa[test_day]
                elif variant=='V1':
                    keep_all,_=_walkforward_np(all_cand,all_entry,all_exit,all_pct,sl[all_day],pool,dayix,False)
                    keep=keep_all[all_intest]
                else:
                    keep=np.ones(len(test),bool)
                    for sym in SYMBOLS:
                        ix=np.flatnonzero(test_sym==sym)
                        if not len(ix):continue
                        _,ea,vi,loc=v3cache[sym]; shs=int(rng.choice(np.arange(30,max(31,len(vi)-30)))) if len(vi)>60 else 0
                        rolled=ea.copy(); rolled[vi]=np.roll(ea[vi],shs); keep[ix]=~rolled[loc]
                null[j]=float(test_pct[keep&target].sum()) if np.any(keep&target) else 0.
            pctl=100*np.mean(null<=obsret); pemp=(1+np.sum(null>=obsret))/(1+draws); pz=.5*math.erfc((obsret-null.mean())/(null.std(ddof=1)*math.sqrt(2))) if null.std()>0 else float(obsret<=null.mean())
            beats=obsret>v0ret; loss18=(r18>=0 if v18>=0 else r18>v18); loss22=(r22>=0 if v22>=0 else r22>v22)
            other=beats and pctl>=95 and loss18 and loss22 and epok
            nf=len(shifts); pfinal=pemp
            if other and not quick:
                if variant!='V3':
                    exact_shifts=np.arange(30,nvalid-30+1,dtype=int); ge=0
                    for shx in exact_shifts:
                        slx=L.copy(); sax=amb.copy(); slx[valid_ix]=np.roll(L[valid_ix],shx); sax[valid_ix]=np.roll(amb[valid_ix],shx); rx=slx[test.entry_day.to_numpy()].astype(float)
                        if variant=='V2': kx=np.where(test.side.to_numpy()=='long',luts['long'][rx.astype(int)],luts['short'][rx.astype(int)])&~sax[test_day]
                        else: kx,_=_walkforward_np(all_cand,all_entry,all_exit,all_pct,slx[all_day],pool,dayix,False); kx=kx[all_intest]
                        ge += _metric(test,kx&target)[0]>=obsret
                    nf=len(exact_shifts); pfinal=(1+ge)/(1+nf)
                else:
                    # PREREG specifies 5,000 independent per-symbol shifts for V3 refinement.
                    ge=0; nf=5000
                    for _ in range(nf):
                        kx=np.ones(len(test),bool)
                        for sym in SYMBOLS:
                            ix=np.where(test.symbol.eq(sym))[0]
                            if not len(ix):continue
                            _,ea,vi,loc=v3cache[sym]; sx=int(rng.choice(np.arange(30,max(31,len(vi)-30)))) if len(vi)>60 else 0
                            shifted=ea.copy(); shifted[vi]=np.roll(ea[vi],sx); kx[ix]=~shifted[loc]
                        ge += _metric(test,kx&target)[0]>=obsret
                    pfinal=(1+ge)/(1+nf)
            reachable=(1/(nf+1))<=.05/ntrials
            adj=pfinal<=.05/ntrials
            passed=other and adj
            best_single=max((v0by[i][0] for i in pool),default=np.nan) if variant=='V1' else np.nan
            rows.append(dict(variant=variant,K=K,candidate=name,timeframe='pool' if cid is None else candidates[cid]['timeframe'],v0_best_single=best_single,v0_return=v0ret,ret=obsret,trades=nt,v0_trades=v0n,maxdd=dd,v0_maxdd=v0dd,ret_2018h2=r18,v0_2018h2=v18,ret_2022=r22,v0_2022=v22,null_pctl=pctl,p_emp=pemp,p_emp_final=pfinal,adj_thr=.05/ntrials,adj_reachable=reachable,adjusted_pass=adj,p_z=pz,beats_v0=beats,loss_reduced_2018=loss18,loss_reduced_2022=loss22,episodes_ok=epok,used_regimes=','.join(map(str,sorted(used))),PASS=passed))
    pd.DataFrame(rows).to_csv(out/'results.csv',index=False); pd.DataFrame(epout).drop_duplicates(['K','regime']).to_csv(out/'episodes.csv',index=False); pd.DataFrame(choicesout).to_csv(out/'v1_choices.csv',index=False)
    rr=pd.DataFrame(rows); rr.groupby(['variant','K']).apply(lambda g:pd.Series({'mean_ret_minus_v0':(g.ret-g.v0_return).mean(),'share_beating_v0':g.beats_v0.mean(),'mean_maxdd_diff':(g.maxdd-g.v0_maxdd).mean(),'n_PASS':int(g.PASS.sum())})).reset_index().to_csv(out/'summary_by_K.csv',index=False)
    elapsed=time.time()-started
    skipped=[{'reason':'15m rows dropped','count':getattr(discover_candidates,'skipped_15m',0)}]+[{'reason':'candidate execution error',**e} for e in errors]
    (out/'run_meta.json').write_text(json.dumps(dict(n_candidates=len(candidates),N_trials=ntrials,draws=draws,elapsed_seconds=elapsed,skipped_items=skipped),indent=2)+'\n')
    return elapsed

def main(argv=None):
    p=argparse.ArgumentParser(); p.add_argument('--draws',type=int,default=1000); p.add_argument('--quick',action='store_true'); p.add_argument('--out',default=str(ROOT/'regime/results')); a=p.parse_args(argv)
    elapsed=run(50 if a.quick else a.draws,a.quick,a.out); print(f'completed in {elapsed:.2f}s; outputs: {a.out}')
if __name__=='__main__':main()
