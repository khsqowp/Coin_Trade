"""Deterministic preregistered statistics and report tables for the A cadence sweep."""
import glob, json, os
import numpy as np
from scipy.stats import spearmanr, skew, kurtosis, norm

ROOT=os.environ.get('RS_FINAL_SCRATCH','')
DATA=os.path.join(ROOT,'rebalA')
OUT='docs/research/rebal_loop/A'
SEED=20261101; B=4000

def clean(x): return float(x) if np.isfinite(x) else None
def ann_g(r): return 365*np.nanmean(r)
def sharpe(r):
    sd=np.nanstd(r,ddof=1); return np.sqrt(365)*np.nanmean(r)/sd if sd>0 else np.nan
def metrics(r):
    r=r[np.isfinite(r)]; eq=np.exp(np.r_[0.,np.cumsum(r)]); dd=1-eq/np.maximum.accumulate(eq)
    return {'g':ann_g(r),'sharpe':sharpe(r),'mdd':float(dd.max()),'calmar':ann_g(r)/dd.max() if dd.max()>0 else np.nan}
def asr(r):
    r=r[np.isfinite(r)]; s=sharpe(r); sr=s/np.sqrt(365); sk=skew(r,bias=False); ku=kurtosis(r,fisher=True,bias=False)
    return float(np.sqrt(365)*(sr+sk*sr*sr/6-ku*sr**3/24))
def adj(p,method):
    p=np.asarray(p,float); n=len(p); order=np.argsort(p); q=np.empty(n)
    if method=='holm':
        vals=np.maximum.accumulate((n-np.arange(n))*p[order]); q[order]=np.minimum(vals,1)
    else:
        vals=p[order]*n/(np.arange(n)+1); vals=np.minimum.accumulate(vals[::-1])[::-1]; q[order]=np.minimum(vals,1)
    return q
def boot_ci(x,rng):
    x=np.asarray(x); n=len(x); starts=rng.integers(0,n,size=(B,int(np.ceil(n/15))))
    ix=((starts[:,:,None]+np.arange(15))%n).reshape(B,-1)[:,:n]
    vals=365*np.mean(x[ix],axis=1)
    obs=365*np.mean(x); centered=vals-obs
    pval=(1+np.sum(np.abs(centered)>=abs(obs)))/(B+1)
    return float(np.quantile(vals,.025)),float(np.quantile(vals,.975)),float(min(pval,1.)),float(np.std(vals,ddof=1)),float(np.quantile(vals,.005)),float(np.quantile(vals,.995))
def readfile(path):
    z=np.load(path); return z['rets'],z['meta'],str(z['window'].item()),float(z['cost']),int(z['resize'])
def path_table(rets,meta):
    out={}
    for p in range(1,73):
        ix=np.where(meta[:,0]==p)[0]; ms=[]
        for k in ix: ms.append(metrics(rets[k]))
        row={}
        for key in ('g','sharpe','mdd','calmar'):
            vals=np.array([x[key] for x in ms]); row[key]=[clean(np.nanpercentile(vals,q)) for q in (10,50,90)]
        for j,key in enumerate(('','', 'close_mdd','worst_mdd','kills','liq_flags','rebals','fills','turnover_notional','costs','final_eq')):
            if key and j>=2:
                v=meta[ix,j]; row[key]=[clean(np.nanpercentile(v,q)) for q in (10,50,90)]
        nday=rets.shape[1]; av=np.nanmean(rets[ix],axis=0); row['daily_mean']=av; row['offset_n']=len(ix)
        row['asr']=[clean(asr(av))]*3; row['dsr']=[clean(dsr(av)[0])]*3
        years=nday/365
        eqmean=np.array([np.mean(np.exp(np.r_[0.,np.cumsum(rets[k][np.isfinite(rets[k])])])) for k in ix])
        tv=np.array([meta[k,8]/max(eqmean[z],1e-12)/years for z,k in enumerate(ix)])
        row['turnover_ann']=[clean(np.nanpercentile(tv,q)) for q in (10,50,90)]
        row['cost_pct_initial']=row['costs']
        out[p]=row
    return out
def cscv_pbo(R):
    # R is cadence x time daily log return matrix, phase-averaged.
    blocks=np.array_split(np.arange(R.shape[1]),16); combos=[]
    import itertools
    for c in itertools.combinations(range(16),8): combos.append(c)
    bm=np.stack([R[:,b].mean(axis=1) for b in blocks],axis=1)
    mask=np.zeros((len(combos),16),bool)
    for i,c in enumerate(combos): mask[i,list(c)]=True
    ins=mask.astype(float)@bm.T/8; outs=(~mask).astype(float)@bm.T/8
    best=np.argmax(ins,axis=1); ranks=np.argsort(np.argsort(outs,axis=1),axis=1)
    omega=(ranks[np.arange(len(combos)),best]+.5)/R.shape[0]
    return float(np.mean(omega<.5)),len(combos)
def trend_bootstrap(R,rng):
    xlog=np.log(np.arange(1,73)); w=(xlog-xlog.mean())/np.sum((xlog-xlog.mean())**2)
    # OLS slope is a linear combination of per-day returns, so bootstrap that series.
    lo,hi,pv,_,_,_=boot_ci(np.sum(R*w[:,None],axis=0),rng)
    return [lo,hi],pv
def dsr(r,N=72):
    r=r[np.isfinite(r)]; n=len(r); sr=sharpe(r)/np.sqrt(365); g1=skew(r,bias=False) if n>2 else 0.; g2=kurtosis(r,fisher=False,bias=False) if n>3 else 3.
    denom=np.sqrt(max(1e-12,(1-g1*sr+(g2-1)*sr*sr/4)/(n-1)))
    # Expected maximum under the null, in observed-SR units.
    ez=(1-0.5772156649)*norm.ppf(1-1/N)+0.5772156649*norm.ppf(1-1/(N*np.e))
    emax=denom*ez
    return float(norm.cdf((sr-emax)/denom)),float(sr),float(emax)
def main():
    files=glob.glob(os.path.join(DATA,'*.npz'))
    if len(files)<24: raise RuntimeError(f'expected 24 preregistered files; found {len(files)}')
    groups={}
    for f in files:
        rr,mm,w,c,z=readfile(f); key=(w,round(c,7),z); groups[key]=(path_table(rr,mm),rr,mm)
    report={'seed':SEED,'bootstrap_reps':B,'files':len(files),'settings':{},'inference':{}}
    rng=np.random.default_rng(SEED)
    # Save compact JSON metrics, excluding daily series.
    for (w,c,z),(tab,rr,mm) in groups.items():
        label=f'{w}_gross_resize{z}' if c==0 else f'{w}_slip{round((c-.0005)*10000):02d}_resize{z}'
        report['settings'][label]={str(p):{k:v for k,v in row.items() if k!='daily_mean'} for p,row in tab.items()}
        # Per-cadence contrasts against mean p72 phase series, paired by date.
        base=tab[72]['daily_mean']; individual=[]; pvals=[]; cis=[]; ses=[]
        for p in range(1,72):
            d=tab[p]['daily_mean']-base; lo,hi,pv,se,lo99,hi99=boot_ci(d,rng); individual.append({'p':p,'delta_g':ann_g(d),'ci':[lo,hi],'ci99_bonf71':[lo99,hi99],'p_raw':pv,'se':se}); pvals.append(pv); cis.append((lo,hi)); ses.append(se)
        coarse=[]
        for lo_p,hi_p in ((1,6),(7,12),(13,24),(25,48),(49,71)):
            d=np.nanmean(np.stack([tab[p]['daily_mean'] for p in range(lo_p,hi_p+1)]),axis=0)-base
            lo,hi,pv,se,lo99,hi99=boot_ci(d,rng); coarse.append({'range':[lo_p,hi_p],'delta_g':ann_g(d),'ci':[lo,hi],'ci99_bonf5':[lo99,hi99],'p_raw':pv,'se':se,'mde_g':2.8*se})
        for method in ('holm','bh'):
            q=adj(pvals,method)
            for i,x in enumerate(individual): x[method+'_q']=float(q[i])
            qc=adj([x['p_raw'] for x in coarse],method)
            for i,x in enumerate(coarse): x[method+'_q']=float(qc[i])
        daily=np.stack([tab[p]['daily_mean'] for p in range(1,73)])
        gs=np.array([ann_g(tab[p]['daily_mean']) for p in range(1,73)])
        ranks=spearmanr(gs[:],np.arange(1,73)).statistic
        slope=np.polyfit(np.log(np.arange(1,73)),gs,1)[0]
        slope_ci,slope_p=trend_bootstrap(daily,rng)
        # Moving averages ±3 hours and positive neighboring regions.
        ma=np.array([np.mean(gs[max(0,i-3):min(72,i+4)]) for i in range(72)])
        dsrval,sr,emax=dsr(tab[72]['daily_mean'])
        pbo,ncomb=cscv_pbo(daily)
        report['inference'][label]={'individual':individual,'coarse':coarse,'rank_spearman_vs_p':float(ranks),'ma_pm3_g':ma.tolist(),'trend_slope_g_per_ln_p':float(slope),'trend_slope_ci95':slope_ci,'trend_slope_p_raw':slope_p,'pbo':pbo,'pbo_combinations':ncomb,'dsr_p72':dsrval,'sr_daily_p72':sr,'expected_max_sr_N72':emax,'mde_g_coarse':[x['mde_g'] for x in coarse]}
        if c>0:
            gross=groups.get((w,0.,z))
            if gross:
                gt=gross[0]
                for p in range(1,73):
                    paid=report['settings'][label][str(p)]; gr=gt[p]['g'][1]; paid['cost_drag_g']=gr-paid['g'][1]
                    cg=np.array([v/max(abs(gv-1),1e-12) for v,gv in zip(paid['costs'],gt[p]['final_eq'])])
                    paid['cost_pct_gross_pnl']=[clean(np.nanpercentile(cg,q)) for q in (10,50,90)]
    # IS/OOS consistency under the preregistered primary costs and resize modes.
    for slip in (0,5):
      for resize in (0,1):
        i=f'IS_slip{slip:02d}_resize{resize}'; o=f'OOS_slip{slip:02d}_resize{resize}'
        if i in report['inference'] and o in report['inference']:
            gi=np.array([report['settings'][i][str(p)]['g'][1] for p in range(1,73)])
            go=np.array([report['settings'][o][str(p)]['g'][1] for p in range(1,73)])
            rho=float(spearmanr(gi,go).statistic); best=np.where(gi==np.nanmax(gi))[0]+1
            report['inference'][f'IS_OOS_slip{slip:02d}_resize{resize}']={'spearman':rho,'sign_agreement':float(np.mean(np.sign(gi[1:]-gi[71])==np.sign(go[1:]-go[71]))),'IS_best_p':best.tolist(),'IS_best_OOS_rank_percentile':[float((np.argsort(np.argsort(go))[p-1]+1)/72) for p in best]}
    with open(os.path.join(OUT,'stats.json'),'w') as f: json.dump(report,f,ensure_ascii=False,separators=(',',':'))
    with open(os.path.join(OUT,'summary.csv'),'w') as f:
        f.write('setting,p,g_p10,g_median,g_p90,sharpe_median,mdd_median,worst_mdd_median,kills_median,liq_flags_median,turnover_notional_median,fills_median,costs_median,final_eq_median\n')
        for label,tab in report['settings'].items():
            for p,row in tab.items(): f.write(f"{label},{p},{row['g'][0]},{row['g'][1]},{row['g'][2]},{row['sharpe'][1]},{row['mdd'][1]},{row['worst_mdd'][1]},{row['kills'][1]},{row['liq_flags'][1]},{row['turnover_notional'][1]},{row['fills'][1]},{row['costs'][1]},{row['final_eq'][1]}\n")
    print(f"stats complete: {len(files)} settings, B={B}, seed={SEED}; outputs stats.json, summary.csv")
if __name__=='__main__': main()
