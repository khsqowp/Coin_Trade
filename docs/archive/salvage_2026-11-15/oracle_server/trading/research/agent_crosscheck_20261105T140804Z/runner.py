#!/usr/bin/env python3
"""Independent, order-free reproduction of six Coin_Trade equity strategy configs."""
from __future__ import annotations
import os, sys, json, glob, time, hashlib, subprocess, argparse
from pathlib import Path
from datetime import datetime, timezone
import numpy as np
import pandas as pd
import requests

START = pd.Timestamp('2022-01-03')
END = pd.Timestamp('2026-10-30')
KR_CODES = ['005930','000660','005380','373220','035420','105560','000270','068270','051910','207940']
KR_BENCH = '069500'
US_FEE_CASES = {'KIS':0.0036, 'CHEAP':0.0008}
KR_COMM = 0.00015
KR_TAX = 0.0018


def sha256_file(p):
    h=hashlib.sha256()
    with open(p,'rb') as f:
        for b in iter(lambda:f.read(1024*1024),b''): h.update(b)
    return h.hexdigest()

def write_json(p,obj):
    Path(p).write_text(json.dumps(obj,ensure_ascii=False,indent=2,default=str)+'\n',encoding='utf-8')

def met(eq, dates, trades=None, held=None):
    s=pd.Series(np.asarray(eq,float),index=pd.DatetimeIndex(dates)).loc[START:END]
    s=s.dropna()
    if len(s)<2 or s.iloc[0]<=0: return {}
    r=s/s.iloc[0]
    yrs=(r.index[-1]-r.index[0]).days/365.25
    dr=r.pct_change().dropna()
    sd=float(dr.std(ddof=1)) if len(dr)>1 else 0.0
    out={'eval_start':str(r.index[0].date()),'eval_end':str(r.index[-1].date()),'n_eval_sessions':int(len(r)),
         'total_return':float(r.iloc[-1]-1),'cagr':float(r.iloc[-1]**(1/yrs)-1) if yrs>0 and r.iloc[-1]>0 else -1.0,
         'mdd':float((r/r.cummax()-1).min()),'sharpe':float(dr.mean()/sd*np.sqrt(252)) if sd>0 else 0.0,'years':float(yrs)}
    if held is not None:
        h=pd.Series(held,index=pd.DatetimeIndex(dates)).loc[START:END]
        out['exposure_any']=float(h.mean())
    if trades is not None:
        ts=[x for x in trades if START<=pd.Timestamp(x['exit_date'])<=END]
        out['closed_trades']=len(ts); out['winning_trade_pct']=float(np.mean([x['net_return']>0 for x in ts])) if ts else None
        out['open_positions_at_end']=None
    return out

def matrices(frames, cols):
    dates=sorted(set().union(*[set(d.index) for d in frames.values()]))
    idx=pd.DatetimeIndex(dates)
    mats={k:pd.DataFrame({s:d[k] for s,d in frames.items()},index=idx).sort_index() for k in cols}
    return idx,mats

def cross_up(a,b):
    return ((a.shift(1)<=b.shift(1)) & (a>b)).fillna(False)
def cross_down(a,b):
    return ((a.shift(1)>=b.shift(1)) & (a<b)).fillna(False)

def us_weights_engine(ret, target, fee):
    R=np.nan_to_num(ret.to_numpy(float),nan=0.0,posinf=0.0,neginf=0.0); T,N=R.shape
    v=np.zeros(N); cash=1.0; eq=np.ones(T); turnover=cost_sum=0.0; invested=np.zeros(T)
    tgt=target.to_numpy(float)
    for t in range(T):
        v*=1+R[t]
        E=cash+v.sum()
        if t-1>=0 and not np.isnan(tgt[t-1,0]):
            w=np.nan_to_num(tgt[t-1]); target_val=w*E; delta=target_val-v
            tr=float(np.abs(delta).sum()); cst=tr*fee
            E-=cst; v=w*E; cash=E-v.sum(); turnover+=tr; cost_sum+=cst
        eq[t]=cash+v.sum(); invested[t]=(np.abs(v).sum()/eq[t]) if eq[t] else 0.0
    return eq,turnover,cost_sum,invested

def us_s1_targets(C, ret, L=60,K=5,R=21,filter_sma200=True,offset=0):
    score=C/C.shift(L)-1
    # Coin_Trade rs_us_run equal-weight return proxy across eligible matrix columns.
    avail=ret.notna(); idx_ret=ret.where(avail).mean(axis=1).fillna(0.0)
    idx=(1+idx_ret).cumprod(); sma=idx.rolling(200).mean()
    bad=(idx<sma).fillna(False).to_numpy() if filter_sma200 else np.zeros(len(C),bool)
    tgt=np.full(C.shape,np.nan); base=np.zeros(C.shape[1]); prev_bad=False
    sv=score.to_numpy(float)
    for t in range(len(C)):
        due=(t%R)==offset
        force=prev_bad and not bad[t]
        if bad[t]: tgt[t]=0.0
        elif due or force:
            row=sv[t]; ok=np.isfinite(row); w=np.zeros(C.shape[1])
            if ok.sum()>=2*K:
                order=np.argsort(-np.where(ok,row,-np.inf),kind='stable')
                w[order[:K]]=1.0/K
            base=w; tgt[t]=base
        prev_bad=bad[t]
    return pd.DataFrame(tgt,index=C.index,columns=C.columns)

def run_us_slots(O,H,L,C,V,entry,exit_sig,score,slots,fee,sl=None,tp=None,name=''):
    dates=C.index; syms=list(C.columns); ov=O.to_numpy(float); hv=H.to_numpy(float); lv=L.to_numpy(float); cv=C.to_numpy(float); vv=V.to_numpy(float)
    ent=entry.to_numpy(bool); ex=exit_sig.to_numpy(bool); sc=score.to_numpy(float)
    T,N=cv.shape; cash=1.0; pos={}; eq=np.ones(T); held_count=np.zeros(T); trades=[]; turn=cost_sum=0.0
    for t in range(T):
        if t>0:
            for i in list(pos):
                if not np.isfinite(cv[t,i]): continue
                p=pos[i]; o,h,l,c=ov[t,i],hv[t,i],lv[t,i],cv[t,i]; px=None
                if sl is not None and l<=p['entry']*(1-sl): px=min(p['entry']*(1-sl),o)
                elif tp is not None and h>=p['entry']*(1+tp): px=max(p['entry']*(1+tp),o)
                elif ex[t-1,i]: px=c
                if px is not None:
                    gross=p['qty']*px; fee_cash=gross*fee; cash+=gross-fee_cash; turn+=gross; cost_sum+=fee_cash
                    ret=(px/p['entry']-1)-2*fee
                    trades.append({'strategy':name,'ticker':syms[i],'entry_date':str(p['date'].date()),'exit_date':str(dates[t].date()),'entry_price':float(p['entry']),'exit_price':float(px),'gross_return':float(px/p['entry']-1),'net_return':float(ret),'exit_reason':'stop' if (sl is not None and l<=p['entry']*(1-sl)) else ('take_profit' if (tp is not None and h>=p['entry']*(1+tp)) else 'signal')})
                    del pos[i]
        if t>0 and len(pos)<slots:
            E=cash+sum(p['qty']*(cv[t,i] if np.isfinite(cv[t,i]) else p['entry']) for i,p in pos.items())
            candidates=[]
            for i in np.where(ent[t-1])[0]:
                if i not in pos and np.isfinite(cv[t,i]) and np.isfinite(sc[t-1,i]) and np.isfinite(vv[t,i]) and vv[t,i]>0:
                    candidates.append((float(sc[t-1,i]),int(i)))
            candidates.sort(reverse=True)
            for score_i,i in candidates:
                if len(pos)>=slots: break
                px=cv[t,i]; alloc=min(E/slots,cash/(1+fee))
                if alloc<=1e-9: break
                cst=alloc*fee; cash-=alloc+cst; turn+=alloc; cost_sum+=cst
                pos[i]={'qty':alloc/px,'entry':px,'date':dates[t]}
        eq[t]=cash+sum(p['qty']*(cv[t,i] if np.isfinite(cv[t,i]) else p['entry']) for i,p in pos.items())
        held_count[t]=len(pos)>0
    return eq,trades,turn,cost_sum,held_count,pos

def build_us_signals(C,H,L,V):
    ema=lambda n:C.ewm(span=n,adjust=False).mean()
    e9,e21=ema(9),ema(21); sma10=C.rolling(10).mean(); sma20=C.rolling(20).mean(); sma200=C.rolling(200).mean()
    rs90=C/C.shift(90)-1; rs20=C/C.shift(20)-1
    # S3
    e3=cross_up(e9,e21); x3=cross_down(e9,e21); s3=pd.DataFrame(0.0,index=C.index,columns=C.columns)
    # S4
    e4=e3 & C.gt(sma200); x4=x3; s4=(C-sma200)/sma200
    # Mach7 defaults from rs_kr_strats
    ef,em,es,ex=ema(10),ema(50),ema(200),ema(50)
    aligned=ef.gt(em)&em.gt(es); dipped=L.le(ef).rolling(10,min_periods=1).max().astype(bool)
    prevh=H.shift(1); reclaim=C.gt(ef)&C.gt(prevh)
    m_entry=(aligned&dipped&reclaim).fillna(False); m_exit=C.lt(ex).fillna(False)
    # Squeeze
    gap=(sma20-sma200).abs()/sma200*100; sq=gap.le(3).rolling(10,min_periods=1).max().astype(bool)
    above200=sma20.gt(sma200); changes=above200.ne(above200.shift(1)); whips=changes.rolling(20,min_periods=1).sum().gt(3)
    ab20=C.gt(sma20); cu=ab20&~ab20.shift(1).fillna(False).astype(bool)
    q_entry=(cu&C.gt(sma200)&sq&~whips).fillna(False); q_exit=(~ab20).fillna(False)
    # Pullback SMA10 + amount/60d mean >=1.5
    turn=C*V; volratio=turn/turn.rolling(60,min_periods=20).mean()
    ab10=C.gt(sma10); pb_cross=ab10&~ab10.shift(1).fillna(False).astype(bool)
    p_entry=(pb_cross&volratio.ge(1.5)).fillna(False); p_exit=(~ab10).fillna(False)
    return {
      'S3_EMA9_21_SL12_slots20':(e3,x3,s3,20,.12,None),
      'S4_swing6_EMA9_21_SMA200_slots6_TP8_SL4':(e4,x4,s4,6,.04,.08),
      'S5_mach7_top5_SL8':(m_entry,m_exit,rs90,5,.08,None),
      'S5_squeeze_top5':(q_entry,q_exit,rs90,5,None,None),
      'S5_pullback_SMA10_VF_top5_SL3_TP6':(p_entry,p_exit,rs20,5,.03,.06),
    }

def kr_get(code,session,p1,p2):
    url=f'https://query1.finance.yahoo.com/v8/finance/chart/{code}.KS'
    r=session.get(url,params={'period1':p1,'period2':p2,'interval':'1d','events':'div,splits'},headers={'User-Agent':'Mozilla/5.0 (research; low-rate)'},timeout=35)
    r.raise_for_status(); raw=r.content; j=r.json()['chart']; rr=j.get('result') or []
    if not rr: raise RuntimeError(f'{code}: Yahoo empty result {j.get("error")}')
    z=rr[0]; q=z['indicators']['quote'][0]; adj=z.get('indicators',{}).get('adjclose',[{}])[0].get('adjclose')
    if adj is None: raise RuntimeError(f'{code}: no adjclose')
    ix=pd.to_datetime(z['timestamp'],unit='s',utc=True).tz_convert('Asia/Seoul').tz_localize(None).normalize()
    d=pd.DataFrame({'open_raw':q['open'],'high_raw':q['high'],'low_raw':q['low'],'close_raw':q['close'],'adjclose':adj,'volume':q['volume']},index=ix).dropna(subset=['open_raw','high_raw','low_raw','close_raw','adjclose'])
    ratio=d.adjclose/d.close_raw
    out=pd.DataFrame({'open':d.open_raw*ratio,'high':d.high_raw*ratio,'low':d.low_raw*ratio,'close':d.adjclose,'volume':d.volume,'raw_close':d.close_raw,'raw_open':d.open_raw},index=d.index)
    return out,{'ticker':code+'.KS','rows':len(out),'first':str(out.index.min().date()),'last':str(out.index.max().date()),'sha256_response':hashlib.sha256(raw).hexdigest(),'source':'Yahoo Finance chart v8 (unofficial; adjusted close ratio applied to OHLC)'}

def kr_s1_targets(C,elig,R=21,K=5):
    score=C/C.shift(60)-1; rets=C.pct_change(fill_method=None).where(elig)
    idxret=rets.mean(axis=1).fillna(0); idx=(1+idxret).cumprod(); bad=(idx<idx.rolling(200).mean()).fillna(False).to_numpy()
    T,N=C.shape; sv=score.to_numpy(float); el=elig.to_numpy(bool); tgt=np.full((T,N),np.nan); base=np.zeros(N); prev_bad=False
    # source-native single phase: phase starts at first available date in the panel
    start=int(np.flatnonzero(C.notna().any(axis=1))[0])
    for t in range(start,T):
        force=prev_bad and not bad[t]; due=((t-start)%R==0)
        if bad[t]: tgt[t]=0
        elif due or force:
            row=sv[t]; ok=el[t]&np.isfinite(row); w=np.zeros(N)
            if ok.sum()>=K:
                ix=np.argsort(-np.where(ok,row,-np.inf),kind='stable')[:K]; w[ix]=1/K
            base=w; tgt[t]=base
        prev_bad=bad[t]
    return pd.DataFrame(tgt,index=C.index,columns=C.columns)

def kr_weights_engine(O,H,L,C,V,rawO,rawC,elig,tradable,slip,target):
    dates=C.index; syms=list(C.columns); ov=O.to_numpy(float); cv=C.to_numpy(float); rov=rawO.to_numpy(float); rc=rawC.to_numpy(float)
    trad=tradable.to_numpy(bool); tg=target.to_numpy(float); slipv=np.asarray(slip,float); T,N=cv.shape
    v=np.zeros(N); cash=1.; eq=np.ones(T); pending=None; turn=cost=0.; exposure=np.zeros(T); ret_hist=[]
    for t in range(1,T):
        gap=np.nan_to_num(rov[t]/rc[t-1]-1,nan=0,posinf=0,neginf=0)
        v*=1+gap; E=cash+v.sum()
        if pending is not None:
            delta=pending*E-v; delta[~trad[t]]=0
            buys=np.clip(delta,0,None); sells=np.clip(-delta,0,None)
            cst=float((buys*(KR_COMM+slipv)).sum()+(sells*(KR_COMM+slipv+KR_TAX)).sum())
            cash-=delta.sum()+cst; v+=delta; turn+=float(np.abs(delta).sum()); cost+=cst; pending=None
        intra=np.nan_to_num(cv[t]/ov[t]-1,nan=0,posinf=0,neginf=0); v*=1+intra
        Enew=cash+v.sum(); eq[t]=Enew; exposure[t]=float((v.sum()/Enew) if Enew else 0); ret_hist.append(Enew/E-1 if E>0 else 0)
        if not np.isnan(tg[t]).all(): pending=np.nan_to_num(tg[t])
    return eq,turn,cost,exposure

def kr_events_engine(O,H,L,C,V,rawO,rawC,eligible,tradable,slip,entry,exit_sig,score,slots,sl=None,tp=None,name=''):
    dates=C.index; syms=list(C.columns); ov=O.to_numpy(float); hv=H.to_numpy(float); lv=L.to_numpy(float); cv=C.to_numpy(float); vv=V.to_numpy(float); rov=rawO.to_numpy(float); rcv=rawC.to_numpy(float)
    trad=tradable.to_numpy(bool); ent=entry.to_numpy(bool); ex=exit_sig.to_numpy(bool); sc=score.to_numpy(float); slipv=np.asarray(slip,float)
    T,N=cv.shape; sh=np.zeros(N); epx=np.zeros(N); held=np.zeros(N,bool); flagged=np.zeros(N,bool); entry_dates=[None]*N
    cash=1.; eq=np.ones(T); turn=cost=0.; trades=[]; held_any=np.zeros(T); want=[]
    def sell(j,px,t,reason):
        nonlocal cash,turn,cost
        gross=sh[j]*px; cst=gross*(KR_COMM+slipv[j]+KR_TAX); cash+=gross-cst; turn+=gross; cost+=cst
        buyc=KR_COMM+slipv[j]; sellc=KR_COMM+slipv[j]+KR_TAX
        trades.append({'strategy':name,'ticker':syms[j],'entry_date':str(entry_dates[j].date()),'exit_date':str(dates[t].date()),'entry_price':float(epx[j]),'exit_price':float(px),'gross_return':float(px/epx[j]-1),'net_return':float(px/epx[j]-1-buyc-sellc),'exit_reason':reason})
        sh[j]=0; held[j]=False; flagged[j]=False; entry_dates[j]=None
    for t in range(1,T):
        for j in np.where(held)[0]:
            if not trad[t,j]: continue
            o=ov[t,j]; h=hv[t,j]; l=lv[t,j]; px=None; reason=''
            if flagged[j]: px=o; reason='signal_next_open'
            elif sl and o<=epx[j]*(1-sl): px=o; reason='stop_gap'
            elif tp and o>=epx[j]*(1+tp): px=o; reason='tp_gap'
            if px is not None: sell(j,px,t,reason)
        if want:
            E=cash+np.nansum(sh*ov[t])
            for j in want:
                if held[j] or not trad[t,j] or held.sum()>=slots: continue
                alloc=min(E/slots,cash/(1+KR_COMM+slipv[j]))
                if alloc<=1e-9: continue
                cst=alloc*(KR_COMM+slipv[j]); sh[j]=alloc/ov[t,j]; epx[j]=ov[t,j]; held[j]=True; entry_dates[j]=dates[t]
                cash-=alloc+cst; turn+=alloc; cost+=cst
            want=[]
        for j in np.where(held)[0]:
            if sl and lv[t,j]<=epx[j]*(1-sl): sell(j,min(ov[t,j],epx[j]*(1-sl)),t,'stop_intraday')
            elif tp and hv[t,j]>=epx[j]*(1+tp): sell(j,max(ov[t,j],epx[j]*(1+tp)),t,'tp_intraday')
        eq[t]=cash+np.nansum(sh*cv[t]); held_any[t]=held.any()
        flagged |= held & ex[t]
        free=slots-int((held&~flagged).sum())
        if free>0:
            cand=np.where(ent[t]&eligible.iloc[t].to_numpy(bool)&tradable.iloc[t].to_numpy(bool)&~held)[0]
            if len(cand): cand=cand[np.argsort(-np.nan_to_num(sc[t,cand],nan=-1e18),kind='stable')][:free]; want=list(cand)
    return eq,trades,turn,cost,held_any,held

def main():
    ap=argparse.ArgumentParser(); ap.add_argument('--out',required=True); a=ap.parse_args(); out=Path(a.out); out.mkdir(parents=True,exist_ok=True); (out/'inputs_kr').mkdir(exist_ok=True)
    # US universe filters
    base='/app/data/us_daily'; metas=[]; excluded=[]; usframes={}
    for mf in sorted(glob.glob(base+'/*.meta.json')):
        meta=json.load(open(mf,encoding='utf-8')); sym=os.path.basename(mf).replace('.meta.json',''); typ=meta.get('vendor',{}).get('instrumentType','unknown')
        if typ!='EQUITY': excluded.append({'ticker':sym,'reason':'instrument_type_'+str(typ)}); continue
        pf=f'{base}/{sym}.parquet'
        if not os.path.exists(pf): excluded.append({'ticker':sym,'reason':'missing_parquet'}); continue
        d=pd.read_parquet(pf).sort_index(); ix=pd.DatetimeIndex(d.index)
        if ix.tz is not None: d.index=ix.tz_convert('UTC').tz_localize(None).normalize()
        else: d.index=ix.normalize()
        d=d[~d.index.duplicated(keep='last')]; d=d.loc[:END]
        valid=d.close.notna() & d.adjclose.notna(); warm=int((valid & (d.index<START)).sum()); last=d.index[valid].max() if valid.any() else pd.NaT
        if warm<200: excluded.append({'ticker':sym,'reason':'pre_start_valid_bars_lt_200','valid_pre_start_bars':warm,'last_valid':str(last.date()) if pd.notna(last) else ''}); continue
        if pd.isna(last) or last<END: excluded.append({'ticker':sym,'reason':'no_valid_data_through_2026-10-30','valid_pre_start_bars':warm,'last_valid':str(last.date()) if pd.notna(last) else ''}); continue
        ratio=d.adjclose/d.close.replace(0,np.nan)
        f=pd.DataFrame(index=d.index)
        for k in ('open','high','low','close'):
            f[k]=d[k]*ratio
        f['volume']=d.volume
        # Keep one full year for indicator warmup after validating lifetime coverage.
        usframes[sym]=f.loc['2021-01-01':,['open','high','low','close','volume']]
        metas.append({'ticker':sym,'instrumentType':typ,'rows':int(valid.sum()),'first':str(d.index[valid].min().date()),'last':str(last.date()),'valid_pre_start_bars':warm,'meta_sha256':meta.get('sha256','')})
    if not usframes: raise RuntimeError('US universe empty')
    udates,um=matrices(usframes,['open','high','low','close','volume']); UO,UH,UL,UC,UV=(um[k] for k in ['open','high','low','close','volume'])
    # US metrics and results
    us_summary=[]; us_ledgers=[]; C=UC; R=C.pct_change();
    for fee_label,fee in US_FEE_CASES.items():
        phase_eq=[]; phase_turn=[]; phase_cost=[]; phase_inv=[]
        for phase in [0,7,14]:
            tg=us_s1_targets(C,R,offset=phase)
            eq,to,cs,inv=us_weights_engine(R,tg,fee); phase_eq.append(eq); phase_turn.append(to); phase_cost.append(cs); phase_inv.append(inv)
        # engine averages each phase's daily return series, then compounds
        rr=[pd.Series(x,index=udates).pct_change().fillna(0).to_numpy() for x in phase_eq]
        ensemble=np.cumprod(1+np.mean(rr,axis=0)); inv=np.mean(phase_inv,axis=0)
        ms=met(ensemble,udates,held=(inv>1e-6)); ms.update({'market':'US','strategy':'S1_momentum_L60_K5_R21_SMA200_long','fee_case':fee_label,'fee_per_side':fee,'universe_n':len(usframes),'phase_offsets':[0,7,14],'avg_turnover_x':float(np.mean(phase_turn)),'avg_cost_paid_fraction':float(np.mean(phase_cost)),'avg_invested_fraction':float(np.mean(inv[udates>=START]))})
        us_summary.append(ms)
        sigs=build_us_signals(C,UH,UL,UV)
        for name,(en,ex,score,slots,sl,tp) in sigs.items():
            eq,tr,turn,cost,held,pos=run_us_slots(UO,UH,UL,C,UV,en,ex,score,slots,fee,sl,tp,name)
            ms=met(eq,udates,tr,held); ms.update({'market':'US','strategy':name,'fee_case':fee_label,'fee_per_side':fee,'universe_n':len(usframes),'max_slots':slots,'sl_pct':sl,'tp_pct':tp,'turnover_x':float(turn/max(np.mean(eq),1e-9)/( (END-START).days/365.25)),'cost_paid_fraction':float(cost/max(np.mean(eq),1e-9))})
            ms['open_positions_at_end']=len(pos); us_summary.append(ms); us_ledgers.extend(tr)
    # US buy & hold comparison; SPY is outside strategy universe and used only as benchmark
    bhs=[]
    for s,d in usframes.items():
        if s in C.columns and C[s].loc[START:END].dropna().shape[0]>0: bhs.append(C[s].loc[START:END]/C[s].loc[START:END].dropna().iloc[0])
    if bhs:
        bh=pd.concat(bhs,axis=1).ffill().mean(axis=1); bh=bh/bh.iloc[0]
        ms=met(bh.to_numpy(),bh.index); ms.update({'market':'US','strategy':'B&H_equal_initial_weight_available_equities_gross','fee_case':'gross','universe_n':len(bhs)}); us_summary.append(ms)
    # Persist US stage before KR acquisition/aggregation so a downstream failure cannot lose it.
    pd.DataFrame(excluded).sort_values('ticker').to_csv(out/'excluded_us_tickers.csv',index=False)
    pd.DataFrame(metas).sort_values('ticker').to_csv(out/'included_us_tickers.csv',index=False)
    pd.DataFrame(us_summary).to_csv(out/'us_strategy_summary.csv',index=False)
    pd.DataFrame(us_ledgers).to_csv(out/'us_trade_ledger.csv',index=False)
    # KR Yahoo adjusted input: previously approved public chart endpoint, 2-sec pacing.
    p1=int(datetime(2021,1,1,tzinfo=timezone.utc).timestamp()); p2=int(datetime(2026,11,1,tzinfo=timezone.utc).timestamp())
    sess=requests.Session(); krframes={}; kr_meta=[]; last_req=0.0
    for code in KR_CODES+[KR_BENCH]:
        wait=2.0-(time.monotonic()-last_req)
        if wait>0: time.sleep(wait)
        d,m=kr_get(code,sess,p1,p2); last_req=time.monotonic(); d=d.loc[:END]
        krframes[code]=d
        d.to_csv(out/'inputs_kr'/f'{code}.csv',index_label='date')
        kr_meta.append(m)
    kd,km=matrices(krframes,['open','high','low','close','volume','raw_open','raw_close'])
    # Strategy panel excludes benchmark
    kcols=KR_CODES; O,H,L,Ck,V,RO,RC=(km[k][kcols] for k in ['open','high','low','close','volume','raw_open','raw_close'])
    # Eligibility/tradability matching rs_kr_data thresholds.
    value=RC*V; med=value.rolling(60,min_periods=30).median(); bars=Ck.notna().cumsum()
    elig=(med>=1.0e9)&(bars>=30)&Ck.notna()
    prev=RC.shift(1); jump=(RO/prev-1).abs(); trad=(V>0)&RO.notna()&(jump<.29)
    big=(value.tail(750).median(axis=0).fillna(0)>=50e9).to_numpy(); slip=np.where(big,.0005,.0010)
    # common KR signals
    ema=lambda n:Ck.ewm(span=n,adjust=False).mean(); e9,e21=ema(9),ema(21); sma200=Ck.rolling(200,min_periods=200).mean()
    s3e=cross_up(e9,e21); s3x=cross_down(e9,e21); s3sc=pd.DataFrame(0.,index=kd,columns=kcols)
    s4e=s3e&Ck.gt(sma200); s4x=s3x; s4sc=(Ck-sma200)/sma200
    # Per instructions, exact KR default definitions (independent translation).
    ef,em,es,ex=ema(10),ema(50),ema(200),ema(50)
    dipped=L.le(ef).rolling(10,min_periods=1).max().astype(bool); reclaim=Ck.gt(ef)&Ck.gt(H.shift(1))
    mentry=(ef.gt(em)&em.gt(es)&dipped&reclaim).fillna(False); mexit=Ck.lt(ex).fillna(False); rs90=Ck/Ck.shift(90)-1
    sma20=Ck.rolling(20,min_periods=20).mean(); gap=(sma20-sma200).abs()/sma200*100
    sq=gap.le(3).rolling(10,min_periods=1).max().astype(bool); above=sma20.gt(sma200); whip=above.ne(above.shift(1)).rolling(20,min_periods=1).sum().gt(3)
    ab20=Ck.gt(sma20); qentry=(ab20&~ab20.shift(1).fillna(False).astype(bool)&Ck.gt(sma200)&sq&~whip).fillna(False); qexit=(~ab20).fillna(False)
    sma10=Ck.rolling(10,min_periods=10).mean(); ab10=Ck.gt(sma10); turnover=Ck*V; ratio=turnover/turnover.rolling(60,min_periods=20).mean()
    pentry=(ab10&~ab10.shift(1).fillna(False).astype(bool)&ratio.ge(1.5)).fillna(False); pexit=(~ab10).fillna(False); rs20=Ck/Ck.shift(20)-1
    kr_specs={
      'S3_EMA9_21_SL12_slots20':(s3e,s3x,s3sc,20,.12,None),
      'S4_swing6_EMA9_21_SMA200_slots6_TP8_SL4':(s4e,s4x,s4sc,6,.04,.08),
      'S5_mach7_top5_SL8':(mentry,mexit,rs90,5,.08,None),
      'S5_squeeze_top5':(qentry,qexit,rs90,5,None,None),
      'S5_pullback_SMA10_VF_top5_SL3_TP6':(pentry,pexit,rs20,5,.03,.06),
    }
    kr_summary=[]; kr_ledgers=[]
    for name,(en,exs,score,slots,sl,tp) in kr_specs.items():
        eq,tr,to,co,held,pos=kr_events_engine(O,H,L,Ck,V,RO,RC,elig,trad,slip,en,exs,score,slots,sl,tp,name)
        ms=met(eq,kd,tr,held); ms.update({'market':'KR_selected_10','strategy':name,'fee_case':'KR_source_cost','universe_n':len(kcols),'max_slots':slots,'sl_pct':sl,'tp_pct':tp,'commission_per_side':KR_COMM,'sell_tax':KR_TAX,'slippage_small':.001,'slippage_large':.0005,'large_by_latest_median_turnover':50e9,'turnover_x':float(to/max(np.mean(eq),1e-9)/((END-START).days/365.25)),'cost_paid_fraction':float(co/max(np.mean(eq),1e-9)),'open_positions_at_end':int(np.sum(pos))}); kr_summary.append(ms); kr_ledgers.extend(tr)
    # KR S1 source-native one phase, market filter.
    kt=kr_s1_targets(Ck,elig); eq,to,co,inv=kr_weights_engine(O,H,L,Ck,V,RO,RC,elig,trad,slip,kt)
    ms=met(eq,kd,held=(inv>1e-6)); ms.update({'market':'KR_selected_10','strategy':'S1_momentum_L60_K5_R21_SMA200_long','fee_case':'KR_source_cost','universe_n':len(kcols),'phase_offsets':'source_native_single','commission_per_side':KR_COMM,'sell_tax':KR_TAX,'slippage_small':.001,'slippage_large':.0005,'large_by_latest_median_turnover':50e9,'turnover_x':float(to/max(np.mean(eq),1e-9)/((END-START).days/365.25)),'cost_paid_fraction':float(co/max(np.mean(eq),1e-9)),'avg_invested_fraction':float(np.mean(inv[kd>=START]))}); kr_summary.append(ms)
    # KR benchmarks
    for s,label in [(KR_BENCH,'KODEX200_BH_gross')]:
        px=km['close'][s].loc[START:END].dropna(); ms=met((px/px.iloc[0]).to_numpy(),px.index); ms.update({'market':'KR_selected_10','strategy':label,'fee_case':'gross','universe_n':1}); kr_summary.append(ms)
    avail=[s for s in kcols if Ck[s].loc[START:END].dropna().size]
    vals=[]
    for s in avail:
        px=Ck[s].loc[START:END].dropna(); vals.append(px/px.iloc[0])
    if vals:
        bh=pd.concat(vals,axis=1).ffill().mean(axis=1); bh=bh/bh.iloc[0]; ms=met(bh.to_numpy(),bh.index); ms.update({'market':'KR_selected_10','strategy':'B&H_equal_initial_weight_available_2022_names_gross','fee_case':'gross','universe_n':len(avail),'excluded_unlisted_at_start':['373220' if '373220' not in avail else '']}); kr_summary.append(ms)
    # Write coverage, exclusions, summaries, ledgers, manifest.
    pd.DataFrame(excluded).sort_values('ticker').to_csv(out/'excluded_us_tickers.csv',index=False)
    pd.DataFrame(metas).sort_values('ticker').to_csv(out/'included_us_tickers.csv',index=False)
    pd.DataFrame(us_summary+kr_summary).to_csv(out/'strategy_summary.csv',index=False)
    pd.DataFrame(us_ledgers).to_csv(out/'us_trade_ledger.csv',index=False)
    pd.DataFrame(kr_ledgers).to_csv(out/'kr_trade_ledger.csv',index=False)
    src='/home/opc/Coin_Trade'; commit=subprocess.run(['git','-C',src,'rev-parse','HEAD'],capture_output=True,text=True).stdout.strip() if Path(src,'/.git').exists() else subprocess.run(['git','-C',src,'rev-parse','HEAD'],capture_output=True,text=True).stdout.strip()
    m={'run_id':out.name,'generated_utc':datetime.now(timezone.utc).isoformat(),'coin_trade_commit':commit,'source_paths':['/home/opc/Coin_Trade/app/rs_kr_strats.py','/home/opc/Coin_Trade/app/rs_kr_run.py','/home/opc/Coin_Trade/app/rs_kr_engine.py','/home/opc/Coin_Trade/app/rs_us_engine.py','/home/opc/Coin_Trade/app/rs_us_run.py'],
       'evaluation_period':[str(START.date()),str(END.date())],'us_input_dir':base,'us_universe_label':'Oracle available US equity universe','us_parquet_count':len(glob.glob(base+'/*.parquet')),'us_meta_count':len(metas)+len(excluded),'us_included_equity_count':len(usframes),'us_excluded_by_reason':pd.DataFrame(excluded).reason.value_counts().to_dict() if excluded else {},
       'us_fee_cases_per_side':US_FEE_CASES,'us_adjustment':'Yahoo adjclose/close ratio applied to open, high, low and close; close=adjclose.','us_fills':'Coin_Trade rs_us_engine: close(t) signal fills close(t+1); OHLC stops checked on the fill-day bar only for positions already held, stop priority over take profit, gap fills at open.',
       'us_s1':'L60, top5 equal weight, rebalance 21 sessions, equal-weight universe return proxy below SMA200 => cash; three phase offsets 0/7/14 averaged by daily returns as rs_us_run.',
       'kr_scope':'10 KRX ticker sample only, plus KODEX 200 benchmark; not full KRX universe. Yahoo adjusted chart history used from 2021-01-01 through 2026-10-30; KIS parquet cache is shorter.',
       'kr_data':kr_meta,'kr_fills':'Coin_Trade rs_kr_engine: close(t) signal fills next tradable session open; exits use signal next open; stop/TP gap/intraday; if both intraday levels hit, stop priority.',
       'kr_costs':{'commission_per_side':KR_COMM,'small_slippage_per_side':.001,'large_slippage_per_side':.0005,'sell_tax':KR_TAX,'large_classification':'latest 750-day median turnover >= 50,000,000,000 KRW (source-native; uses end-of-sample liquidity classification)'},
       'limitations':['US is the Oracle available equity parquet subset, not all US exchanges; active/end-date filtered data and missing delisted equities create survivorship bias.','KR tests only 10 selected current tickers; results do not represent all KRX securities.','Yahoo Finance chart v8 is unofficial, data/revision/corporate-action accuracy is not independently licensed or guaranteed.','The US and KR Coin_Trade engines use different execution lags (next close versus next open), so cross-market comparisons are not apples-to-apples.','KR fee/tax/slippage parameters reproduce research code assumptions, not verified current broker cost schedules.'],
       'inputs':{'us_tickers_included':[x['ticker'] for x in metas],'us_exclusions':excluded,'kr_tickers':[x+'.KS' for x in KR_CODES],'kr_benchmark':KR_BENCH+'.KS'},'summary_csv':'strategy_summary.csv','trade_ledgers':['us_trade_ledger.csv','kr_trade_ledger.csv'],'script_sha256':os.environ.get('CROSSCHECK_RUNNER_SHA256')}
    write_json(out/'manifest.json',m)
    print(json.dumps({'run_id':out.name,'included_us':len(usframes),'excluded_us':len(excluded),'kr_tickers':KR_CODES,'rows':pd.DataFrame(us_summary+kr_summary)[['market','strategy','fee_case','total_return','cagr','mdd','sharpe','closed_trades','open_positions_at_end']].to_dict('records'),'out':str(out)},ensure_ascii=False,default=str))
if __name__=='__main__': main()
