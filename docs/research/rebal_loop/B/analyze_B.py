import os, json, math, sys
from pathlib import Path
import numpy as np, pandas as pd
from scipy.stats import spearmanr
sys.path.insert(0,str(Path(__file__).resolve().parents[4]))
from rs_rebal_B_sim import load_data, END, IS0, CUT, SYMS, LB, BASE

rows=json.loads((BASE/'grid.json').read_text())
z=np.load(BASE/'streams.npz',allow_pickle=True)
stream={k:v for k,v in zip(z['keys'].astype(str),[z[f'a{i}'] for i in range(len(z.files)-1)])}
def sk(mode,cost,p,part): return f"('{mode}', {cost})|{p}|{part}"
B=2000; L=168; rng=np.random.default_rng(20261101)

def paired_boot(x):
    n=len(x); nb=int(np.ceil(n/L)); xx=np.r_[x,x[:L]]; cs=np.r_[0.,np.cumsum(xx)]
    sums=cs[L:L+n]-cs[:n]
    starts=rng.integers(0,n,size=(B,nb)); b=sums[starts].sum(axis=1)/(nb*L)*8760
    obs=x.mean()*8760; centered=b-obs
    p=(1+np.sum(np.abs(centered)>=abs(obs)))/(B+1)
    return obs,np.quantile(b,[.025,.975]),p,b

# Primary OOS paired comparisons alpha, 1x, fee 5bp + slippage 0.
base=np.log(np.maximum(stream[sk('alpha_1x',0,72,'oos')][1:],1e-12))
comparisons=[]; boot_draws=[]; xs=[]
for p in range(1,72):
    alt=np.log(np.maximum(stream[sk('alpha_1x',0,p,'oos')][1:],1e-12))
    x=alt-base; obs,ci,pv,b=paired_boot(x)
    comparisons.append({'P':p,'ann_log_diff':float(obs),'ci_low':float(ci[0]),'ci_high':float(ci[1]),'p':float(pv),'se':float(np.std(b,ddof=1))})
    boot_draws.append(b);xs.append(x)
# Holm step-down
order=np.argsort([x['p'] for x in comparisons]); adjusted=np.zeros(71); running=0.
for rank,ix in enumerate(order):
    adj=min(1.,(71-rank)*comparisons[ix]['p']); running=max(running,adj);adjusted[ix]=running
for i,c in enumerate(comparisons):c['holm_p']=float(adjusted[i]);c['mde80_ann_log']=float(2.80*c['se'])
# Joint max-statistic reality check, circular 168h blocks shared across hypotheses.
X=np.stack(xs,axis=1); n=X.shape[0]; nb=int(np.ceil(n/L)); XX=np.concatenate([X,X[:L]],axis=0); cs=np.vstack([np.zeros((1,X.shape[1])),np.cumsum(XX,axis=0)])
bs=cs[L:L+n]-cs[:n]; starts=rng.integers(0,n,size=(B,nb)); draw=np.zeros((B,71))
for q in range(nb): draw+=bs[starts[:,q],:]
draw=draw/(nb*L)*8760; obs=np.array([c['ann_log_diff'] for c in comparisons]);se=np.array([c['se'] for c in comparisons]); zobs=np.abs(obs/np.maximum(se,1e-12)); centered=draw-obs[None,:]; maxdist=np.max(np.abs(centered/np.maximum(se[None,:],1e-12)),axis=1)
for i,c in enumerate(comparisons):c['maxstat_p']=float((1+np.sum(maxdist>=zobs[i]))/(B+1))

# IS rank concordance and preregistered plateau condition (mean neighbor positive, >=2/3 positive).
is_diffs=[]; oos_diffs=[]
for p in range(1,73):
    for part,arr in [('is',is_diffs),('oos',oos_diffs)]:
        r=stream[sk('alpha_1x',0,p,part)]; b=stream[sk('alpha_1x',0,72,part)]
        arr.append(float(np.log(np.maximum(r[1:],1e-12)).mean()-np.log(np.maximum(b[1:],1e-12)).mean())*8760)
rank_corr=float(spearmanr(is_diffs,oos_diffs).statistic)
plateau=[]
for p in range(1,73):
    ns=[q for q in range(max(1,p-3),min(72,p+3)+1) if q!=p]
    def ok(a):return bool(ns and np.mean([a[q-1] for q in ns])>0 and sum(a[q-1]>0 for q in ns)>=math.ceil(2*len(ns)/3))
    plateau.append({'P':p,'IS_pass':ok(is_diffs),'OOS_pass':ok(oos_diffs),'both':ok(is_diffs) and ok(oos_diffs)})

# Signal attenuation and mechanism, all hourly observations as preregistered.
idx,px,ret,fund,valid,starts,ends=load_data(); end=int(idx.searchsorted(END))+1; K=8
horizons=[1,2,3,6,12,24,36,48,72,96,120,168]
rows_sig=[]
for h in horizons:
    t=np.arange(LB,end-h); hist_ok=valid[t,:] & valid[t-LB,:] & valid[t+h,:]
    sig=np.full((len(t),len(SYMS)),np.nan); sig[hist_ok]=px[t[:,None],np.arange(len(SYMS))[None,:]][hist_ok]/px[(t-LB)[:,None],np.arange(len(SYMS))[None,:]][hist_ok]-1
    fr=px[t+h,:]/px[t,:]-1; fr[~hist_ok]=np.nan
    # Rank each row using eligible names only; stable sort preserves registered universe tie order.
    ords=np.argsort(np.where(np.isfinite(sig),sig,-np.inf),axis=1,kind='stable')
    for krow in range(len(t)):
        n=int(hist_ok[krow].sum())
        if n<2*K: continue
    # vectorized top/bottom portfolios and IC
    spread=[]; ic=[]; retention=[]
    for r0 in range(len(t)):
        good=np.flatnonzero(hist_ok[r0])
        if len(good)<2*K: continue
        order=good[np.argsort(sig[r0,good],kind='stable')]
        bot=order[:K]; top=order[-K:]
        spread.append(float(np.mean(fr[r0,top])-np.mean(fr[r0,bot])))
        a=sig[r0,good]; b=fr[r0,good]
        ra=pd.Series(a).rank(method='average').to_numpy(); rb=pd.Series(b).rank(method='average').to_numpy()
        vv=np.std(ra)*np.std(rb)
        if vv>0: ic.append(float(np.corrcoef(ra,rb)[0,1]))
        tf=t[r0]+h
        if tf<end:
            goodf=np.flatnonzero(valid[tf,:] & valid[tf-LB,:])
            if len(goodf)>=2*K:
                scoref=px[tf,goodf]/px[tf-LB,goodf]-1
                orderf=goodf[np.argsort(scoref,kind='stable')]
                botf=orderf[:K]; topf=orderf[-K:]
                retention.append((len(set(top)&set(topf))+len(set(bot)&set(botf)))/(2*K))
    rows_sig.append({'h':h,'n_hours':len(spread),'ls_forward_return_mean':float(np.mean(spread)) if spread else None,'ls_forward_return_bp':float(np.mean(spread)*10000) if spread else None,'spearman_ic':float(np.nanmean(ic)) if ic else None,'constituent_retention':float(np.mean(retention)) if retention else None,'turnover_fraction':float(1-np.mean(retention)) if retention else None})

# Funding data coverage as observed settlement rows / expected 8-hour timestamps in each local file.
fund_cov={}
for s0 in SYMS:
    fp=Path(__file__).resolve().parents[4]/'.rs_cache'/'vision'/'funding'/f'{s0}USDT.csv.gz'
    if not fp.exists():fund_cov[s0]=0.;continue
    ff=pd.read_csv(fp,header=None,names=['t','iv','r'],compression='gzip'); ff=ff[pd.to_numeric(ff.t,errors='coerce').notna()]
    tt=pd.to_datetime(ff.t.astype('int64'),unit='ms',utc=True); mask=(tt>=IS0)&(tt<=END)
    dur=max(1,int((END-IS0).total_seconds()//28800)+1); fund_cov[s0]=float(mask.sum()/dur)

# 72h cross-checks with the existing daily engines; all local-only, output goes to B.
os.environ['RS_FINAL_SCRATCH']=str(BASE)
from app.rs_final_data import load_panel
from app.rs_final_engine import Sim, window_metrics
from app.rs_cadence_engine import Engine, Cfg
PANEL=load_panel(); fs=Sim(PANEL); d0=fs.d_start('2022-01-01'); cuti=fs.d_start('2024-07-01'); d1=min(fs.nd,fs.d_start('2026-10-10'))
rsf={}
for nm,a,b in [('IS',d0,cuti),('OOS',cuti,d1)]:
    r=fs.run(lbs=(14,),K=8,rebal=3,lev=4.,deploy=.95,cost=.0005,mmr=.005,kill=.35,cool=14,crash_flat=True,phase=0,d0=a,d1=b,fund=1)
    m=window_metrics(r)
    rr=r['eq'].iloc[a:b].to_numpy();rr=rr[np.isfinite(rr)];rsf[nm]={'days':len(rr),'end_equity':float(rr[-1]/rr[0]) if len(rr)>1 else None,'maxdd':m.get('mdd') if m else None}
# Daily cadence engine is a unit-gross-alpha reference without the live kill/crash overlay.
close=pd.DataFrame(PANEL['C'][:,-1,:],index=PANEL['days'],columns=PANEL['names'])
fund=pd.DataFrame(0.,index=PANEL['days'],columns=PANEL['names'])
vision=Path(__file__).resolve().parents[4]/'.rs_cache'/'vision'/'funding'
for sym in PANEL['names']:
    fp=vision/f'{sym}USDT.csv.gz'
    if fp.exists():
        ff=pd.read_csv(fp,header=None,names=['t','iv','r'],compression='gzip'); ff=ff[pd.to_numeric(ff.t,errors='coerce').notna()]
        ff['dt']=pd.to_datetime(ff.t.astype('int64'),unit='ms',utc=True); daily=ff.groupby(ff.dt.dt.floor('D')).r.sum()
        fund[sym]=daily.reindex(PANEL['days'],fill_value=0.).to_numpy()
ce=Engine({'close':close,'funding':fund},sim_start='2022-01-01')
rsc={}
for nm,a,b in [('IS',d0,cuti),('OOS',cuti,d1)]:
    for f_on in (True,False):
        res=ce.run(Cfg(lbs=(14,),k=8,cadence=3,offset=0),fee=.0005,funding=f_on,start=a,end=b)
        vals=np.r_[1.,np.cumprod(1+res['net'][a+1:b])]
        rsc[f'{nm}_funding_{f_on}']={'days':len(vals)-1,'end_equity':float(vals[-1]),'annual_log_growth':float(np.log(max(vals[-1],1e-300))*365/max(1,len(vals)-1))}

# 72h daily versus independent hourly phase-zero 4x live-like; decompose obvious rule differences.
for nm,part in [('IS','is'),('OOS','oos')]:
    h=np.cumprod(stream[sk('live_4x',0,72,part)])
    rsf[nm]['hourly_B_4x_end_equity']=float(h[-1]);rsf[nm]['final_engine_end_ratio']=rsf[nm]['end_equity'];rsf[nm]['final_vs_hourly_end_diff']=float(rsf[nm]['end_equity']-h[-1])
    rsc[f'{nm}_hourly_B_1x_end_equity']=float(np.cumprod(stream[sk('alpha_1x',0,72,part)])[-1])

result={'primary_comparisons':comparisons,'rank_corr_IS_OOS':rank_corr,'plateau':plateau,'signal_decay':rows_sig,'funding_coverage_fraction_mean':float(np.mean(list(fund_cov.values()))),'funding_symbols_with_files':sum(v>0 for v in fund_cov.values()),'cross_validation':{'rs_final_engine_4x':rsf,'rs_cadence_engine_1x':rsc},'data':{'hours_total':len(idx),'start':str(idx[0]),'last':str(idx[end-1]),'IS_hours':cuti*24-d0*24,'OOS_hours':int(end-cuti)}}
(BASE/'analysis.json').write_text(json.dumps(result,indent=2))
print('PRIMARY OOS alpha base, 72h',json.dumps({'top':sorted(comparisons,key=lambda x:-x['ann_log_diff'])[:5],'bottom':sorted(comparisons,key=lambda x:x['ann_log_diff'])[:5],'rank_corr':rank_corr,'plateau_both':[x['P'] for x in plateau if x['both']]}))
print('DECAY',json.dumps(rows_sig))
print('CROSSVAL',json.dumps(result['cross_validation']))
print('FUNDING coverage mean',result['funding_coverage_fraction_mean'],'symbols',result['funding_symbols_with_files'])
