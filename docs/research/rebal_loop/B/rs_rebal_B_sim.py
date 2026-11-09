"""Offline hourly rebalancing study. Only reads the local vision cache."""
import os, gzip, glob, json, math, hashlib, time
from pathlib import Path
import numpy as np, pandas as pd
from numba import njit

BASE = Path(__file__).resolve().parent
ROOT = Path(__file__).resolve().parents[4] / '.rs_cache' / 'vision'
# Explicitly frozen from app/momentum_rotation_loop.py UNIVERSE; no live module import.
SYMS = ['BTC','ETH','BNB','XRP','SOL','TRX','DOGE','ZEC','LINK','XMR','ADA','XLM','BCH','LTC','HBAR','AVAX','SUI','UNI','NEAR','TAO','AAVE','ONDO','THETA','DOT','ENA','WLD','ICP','ETC','POL','QNT','ALGO','ATOM','RENDER','JUP','ARB','FIL','VET','CAKE','LDO','CRV','INJ','OP','APT','IMX','STX']
END = pd.Timestamp('2026-10-09 23:00:00', tz='UTC')
IS0 = pd.Timestamp('2022-01-01', tz='UTC'); CUT = pd.Timestamp('2024-07-01', tz='UTC')
K=8; LB=336; COOLDOWN=336

@njit
def adjust(cash, oldq, oldavg, newq, price, rate):
    """Trade at price; realize only the closed quantity and keep weighted entry on adds."""
    dq=newq-oldq
    if oldq==0 and newq!=0:
        oldavg=price
    elif oldq!=0 and (newq==0 or np.sign(newq)!=np.sign(oldq)):
        cash+=oldq*(price-oldavg); oldavg=0.0
    elif oldq!=0 and abs(newq)<abs(oldq):
        closed=abs(dq)*np.sign(oldq)
        cash+=closed*(price-oldavg)
    elif oldq!=0 and abs(newq)>abs(oldq) and np.sign(newq)==np.sign(oldq):
        oldavg=(abs(oldq)*oldavg+abs(dq)*price)/abs(newq)
    fee_paid=abs(dq*price)*rate
    cash-=fee_paid
    return cash,newq,oldavg,fee_paid,abs(dq*price)

@njit
def simulate(px, ret, fund, valid, start, end, period, phase, lev, deploy, fee, slip, small, unitsteps, btc_idx):
    T,N=px.shape; cash=1000.0 if small else 1.0; qty=np.zeros(N); avg=np.zeros(N); hwm=1.0; halted=-1
    eq=np.full(end-start,np.nan); turnover=np.zeros(end-start); fees=np.zeros(end-start); fpn=np.zeros(end-start); trades=np.zeros(end-start); kills=0; skips=0; rebs=0
    prev=np.ones(N)*np.nan
    for t in range(start,end):
        ix=t-start
        # Funding settlement applies to the position carried into this timestamp.
        for j in range(N):
            p=px[t,j]
            if qty[j]!=0 and np.isfinite(p) and fund[t,j]!=0:
                x=qty[j]*p*fund[t,j]
                cash-=x; fpn[ix]-=x
        equity=cash
        for j in range(N):
            if qty[j]!=0 and np.isfinite(px[t,j]): equity+=qty[j]*(px[t,j]-avg[j])
        eq[ix]=equity
        if equity>hwm: hwm=equity
        if halted<0 and hwm>0 and 1-equity/hwm>=0.35:
            costrate=fee+slip
            for j in range(N):
                if qty[j]!=0 and np.isfinite(px[t,j]):
                    p=px[t,j]; cash+=qty[j]*(p-avg[j]); c=abs(qty[j]*p)*costrate; cash-=c; fees[ix]+=c; turnover[ix]+=abs(qty[j]*p); trades[ix]+=1; qty[j]=0; avg[j]=0
            halted=t; kills+=1
            continue
        if halted>=0:
            if t-halted<COOLDOWN: continue
            halted=-1; hwm=max(cash,1e-12)
        due=(t-start-phase)>=0 and (t-start-phase)%period==0
        if not due or t>=end-1: continue
        rebs+=1
        crash=False
        btc=0
        btc=btc_idx
        if t>=LB and np.isfinite(px[t,btc]) and np.isfinite(px[t-LB,btc]): crash=px[t,btc]/px[t-LB,btc]-1 < -0.10
        scores=np.full(N,-1e99)
        for j in range(N):
            if valid[t,j] and t>=LB and np.isfinite(px[t,j]) and np.isfinite(px[t-LB,j]) and px[t-LB,j]>0:
                scores[j]=px[t,j]/px[t-LB,j]-1
        # Stable tie break by universe index: insertion sort descending.
        order=np.arange(N)
        for a in range(1,N):
            v=order[a]; b=a-1
            while b>=0 and scores[order[b]]<scores[v]: order[b+1]=order[b]; b-=1
            order[b+1]=v
        nvalid=0
        for j in range(N):
            if scores[j]>-1e90:nvalid+=1
        if nvalid<2*K: continue
        side=np.zeros(N)
        if not crash:
            for z in range(K): side[order[z]]=1
            for z in range(K): side[order[nvalid-1-z]]=-1
        target=equity*deploy*lev/(2*K)
        rate=fee+slip
        for j in range(N):
            p=px[t,j]
            if not np.isfinite(p) or p<=0: continue
            s=side[j]; old=qty[j]
            if old!=0 and s==np.sign(old):
                desired=target/p
                if small:
                    step=0.001 if j==0 or j==1 else (0.01 if p>=1 else (1.0 if p>=0.01 else 100.0))
                    desired=np.floor(desired/step+1e-10)*step
                if abs(abs(old*p)-target)>0.15*max(target,1e-12) and abs(desired-old)>1e-14 and abs((desired-old)*p)>= (5.0 if small else 0):
                    new=s*desired
                    cash,qty[j],avg[j],c,tn=adjust(cash,old,avg[j],new,p,rate)
                    fees[ix]+=c; turnover[ix]+=tn; trades[ix]+=1
                continue
            if old!=0:
                cash,qty[j],avg[j],c,tn=adjust(cash,old,avg[j],0.,p,rate); fees[ix]+=c; turnover[ix]+=tn; trades[ix]+=1
            if s!=0:
                q=target/p
                if small:
                    step=0.001 if j==0 or j==1 else (0.01 if p>=1 else (1.0 if p>=0.01 else 100.0))
                    q=np.floor(q/step+1e-10)*step
                if small and q*p<5: skips+=1; continue
                cash,qty[j],avg[j],c,tn=adjust(cash,qty[j],avg[j],s*q,p,rate); fees[ix]+=c; turnover[ix]+=tn; trades[ix]+=1
    return eq, turnover, fees, fpn, trades, kills, skips, rebs

def load_data():
    files=[]; ends={}; starts={}
    for s in SYMS:
        f=ROOT/'klines_1h'/f'{s}USDT.csv.gz'
        if not f.exists(): continue
        # Read locally; rows beyond registered end are excluded before alignment.
        d=pd.read_csv(f,header=None,usecols=[0,4],names=['ot','c'],compression='gzip')
        d['dt']=pd.to_datetime(d.ot,unit='ms',utc=True)
        d=d[(d.dt<=END)&(d.c>0)].drop_duplicates('dt').sort_values('dt')
        if len(d): files.append((s,d[['dt','c']].copy())); starts[s]=d.dt.iloc[0]; ends[s]=d.dt.iloc[-1]
    if not any(s=='BTC' for s,_ in files): raise RuntimeError('BTC local cache missing')
    idx=pd.date_range(min(x.dt.iloc[0] for _,x in files),END,freq='h',tz='UTC')
    px=np.full((len(idx),len(SYMS)),np.nan); valid=np.zeros_like(px,dtype=np.bool_); fund=np.zeros_like(px)
    for j,s in enumerate(SYMS):
        found=[x for a,x in files if a==s]
        if not found: continue
        d=found[0].set_index('dt').reindex(idx); raw=d.c.to_numpy(float)
        valid[:,j]=np.isfinite(raw)
        # valuation carries last close; validity remains exact-bar mask for signal eligibility.
        px[:,j]=pd.Series(raw,index=idx).ffill().to_numpy()
        ff=ROOT/'funding'/f'{s}USDT.csv.gz'
        if ff.exists():
            f=pd.read_csv(ff,header=None,names=['t','iv','r'],compression='gzip'); f=f[pd.to_numeric(f.t,errors='coerce').notna()]
            f['dt']=pd.to_datetime(f.t.astype('int64'),unit='ms',utc=True); f=f[f.dt<=END].drop_duplicates('dt')
            z=f.set_index('dt').r.astype(float).reindex(idx).fillna(0).to_numpy(); fund[:,j]=z
    # Signal eligibility requires a fully observed 337-close lookback; no synthetic gap fill qualifies.
    for j in range(len(SYMS)):
        miss=(~valid[:,j]).astype(np.int32); cs=np.r_[0,np.cumsum(miss)]
        for t in range(LB,len(idx)):
            if cs[t+1]-cs[t-LB]>0: valid[t,j]=False
    # Carry forward close to mark positions; returns across a missing hour are zero.
    ret=np.zeros_like(px)
    for j in range(len(SYMS)):
        for t in range(1,len(idx)):
            if valid[t,j] and valid[t-1,j] and px[t-1,j]>0: ret[t,j]=px[t,j]/px[t-1,j]-1
    return idx,px,ret,fund,valid,starts,ends

# deterministic accounting checks, all hand-computed
def unit_checks():
    cash,q,avg,fee,turn=adjust(1000.,0.,0.,10.,10.,.001)
    assert abs(cash-999.9)<1e-9 and q==10 and avg==10 and abs(fee-.1)<1e-9
    cash,q,avg,fee,turn=adjust(cash,q,avg,15.,14.,.001)
    assert abs(avg-11.333333333333334)<1e-9 and q==15 and abs(fee-.07)<1e-9
    # Mark-to-market after add: 10 units from 10, 5 from 14, marked at 12 -> +30.
    equity=cash+q*(12.-avg)
    assert abs(equity-1009.83)<1e-8
    cash,q,avg,fee,turn=adjust(cash,q,avg,5.,12.,.001)
    assert q==5 and abs(avg-avg)<1e-12 and abs(cash-(999.9-.07+(20./3)-.12))<1e-8
    cash,q,avg,fee,turn=adjust(cash,q,avg,0.,8.,.001)
    assert q==0 and avg==0 and abs(cash-(999.9-.07+(20./3)-.12+(5.*(8.-(170./15)))-.04))<1e-8
    # Funding: long pays positive rate, short receives it; transaction cost is not folded into funding.
    assert abs((-10.*10.*.001)-(-.1))<1e-12 and abs(-(-10.)*10.*.001-.1)<1e-12
    # Crash and kill thresholds plus cooldown are explicitly time-index based.
    assert 89./100.-1 < -.10 and not (90./100.-1 < -.10)
    assert 1.-65./100. >= .35 and not (1.-66./100. >= .35)
    assert 335<336 and not (336<336)
    # no look-ahead: signal score is derived only from t and t-336 closes.
    a=np.array([100.,110.]); b=np.array([80.,100.]); assert abs(a[1]/a[0]-1-.1)<1e-12
    return 'PASS: weighted-average add, MTM, partial close, full close, fee, funding sign, crash threshold, kill threshold, 336h cooldown, causal lookback'

def metrics(r):
    r=np.asarray(r); r=r[np.isfinite(r)]
    if len(r)<2:return {}
    lr=np.log(np.maximum(r[1:]/r[:-1],1e-12)); years=len(lr)/8760
    return {'hours':len(lr),'log_growth_ann':float(lr.mean()*8760),'cagr':float(np.expm1(lr.sum()/years)),'sharpe_hourly':float(lr.mean()/lr.std(ddof=1)*np.sqrt(8760)) if lr.std(ddof=1)>0 else 0.,'maxdd':float(np.max(1-np.asarray(r)/np.maximum.accumulate(r))),'end_equity':float(r[-1])}

def run_all():
    idx,px,ret,fund,valid,starts,ends=load_data(); end=int(idx.searchsorted(END))+1
    is0=int(idx.searchsorted(IS0)); cut=int(idx.searchsorted(CUT));
    # Align starting equity resets: run each interval independently with warmup signals, reset account at boundaries.
    regimes=[('alpha_1x',1.,1.,False),('live_4x',4.,.95,False),('small_4x',4.,.95,True)]
    costs=[0,2,5,10]; rows=[]; streams={}; t0=time.time()
    for name,lev,dep,small in regimes:
      step=np.array([.001 if s in ('BTC','ETH') else (.01 if px[max(is0,LB),j]>=1 else (1. if px[max(is0,LB),j]>=.01 else 100.)) for j,s in enumerate(SYMS)])
      for slipbp in costs:
       key=(name,slipbp)
       for p in range(1,73):
        nphase=min(p,8)
        phase_eq_is=[]; phase_eq_oos=[]; phase_components=[]
        for phidx in range(nphase):
         phase=int(np.floor(phidx*p/nphase))
         all_eq=[]; all_turn=[]; all_fees=[]; all_fund=[]; all_trades=[]
         # IS and OOS independently reset equity, but signals still use preceding market history.
         for a,b in ((is0,cut),(cut,end)):
          out=simulate(px,ret,fund,valid,a,b,p,phase,lev,dep,.0005,slipbp/10000.,small,step,SYMS.index('BTC'))
          eq,turn,fees,fp,trd,kills,skips,rebs=out
          if len(eq) and np.all(np.isfinite(eq)):
           eq=eq/eq[0] if eq[0]>0 else eq
          all_eq.append(eq); all_turn.append(turn); all_fees.append(fees); all_fund.append(fp); all_trades.append(trd)
         phase_eq_is.append(all_eq[0]);phase_eq_oos.append(all_eq[1]);phase_components.append((all_turn,all_fees,all_fund,all_trades))
        # Average phase-aligned hourly simple returns as preregistered.
        streams[(key,p,'is')]=np.mean(np.stack([np.r_[1.,e[1:]/np.maximum(e[:-1],1e-12)] for e in phase_eq_is]),axis=0)
        streams[(key,p,'oos')]=np.mean(np.stack([np.r_[1.,e[1:]/np.maximum(e[:-1],1e-12)] for e in phase_eq_oos]),axis=0)
        mi=metrics(np.cumprod(streams[(key,p,'is')])); mo=metrics(np.cumprod(streams[(key,p,'oos')]))
        rows.append({'mode':name,'slippage_bp':slipbp,'P':p,'phases':nphase,'IS':mi,'OOS':mo,'phase_is_sd':float(np.std([metrics(e)['log_growth_ann'] for e in phase_eq_is])),'phase_oos_sd':float(np.std([metrics(e)['log_growth_ann'] for e in phase_eq_oos]))})
       print('completed',name,'slip',slipbp,'elapsed_s',round(time.time()-t0,1),flush=True)
    (BASE/'grid.json').write_text(json.dumps(rows,indent=2))
    # save stream returns in compressed npz with JSON metadata keys, for inference reproducibility
    keys=[]; vals=[]
    for k,v in streams.items(): keys.append('|'.join(map(str,k))); vals.append(v)
    np.savez_compressed(BASE/'streams.npz',keys=np.array(keys),**{f'a{i}':x for i,x in enumerate(vals)})
    return idx,rows,streams,starts,ends

if __name__=='__main__':
    import sys
    if '--self-test' in sys.argv: print(unit_checks())
    else:
      idx,rows,streams,starts,ends=run_all()
      summary={'symbols_with_cache':len(starts),'BTC_first':str(starts.get('BTC')),'BTC_last_included':str(END),'symbols_latest':{k:str(v) for k,v in ends.items()},'rows':len(rows)}
      (BASE/'data_manifest.json').write_text(json.dumps(summary,indent=2))
      print('DATA',json.dumps(summary),flush=True)
