"""Offline cross-sectional research. No exchange/API imports or pickle loading."""
from __future__ import annotations
import ast
import json
from dataclasses import dataclass, asdict
from pathlib import Path
import numpy as np
import pandas as pd

ROOT = Path(__file__).resolve().parents[1]
FIELDS = ['open','high','low','close','volume','quote_volume','trades','taker_buy_base','taker_buy_quote']

def universe():
    tree = ast.parse((ROOT/'app/momentum_rotation_loop.py').read_text())
    for node in tree.body:
        if isinstance(node, ast.Assign) and any(isinstance(t, ast.Name) and t.id == 'UNIVERSE' for t in node.targets):
            return ast.literal_eval(node.value)
    raise ValueError('UNIVERSE assignment missing')

def load_daily(cache=Path('/tmp/.rs_alpha_cache'), source=None, names=None):
    """CSV cache under /tmp respects the three-file workspace write restriction."""
    cache.mkdir(parents=True, exist_ok=True)
    source = Path(source) if source is not None else ROOT/'.rs_cache/vision'
    frames, missing, failures, coverage = {}, [], {}, {}
    for base in (universe() if names is None else names):
        path = source/'klines_1h'/f'{base}USDT.csv.gz'
        if not path.exists():
            missing.append(base); continue
        fpath = source/'funding'/f'{base}USDT.csv.gz'
        signature = [str(path), path.stat().st_size, path.stat().st_mtime_ns,
                     fpath.stat().st_size if fpath.exists() else 0,
                     fpath.stat().st_mtime_ns if fpath.exists() else 0]
        meta, cached = cache/f'{base}.json', cache/f'{base}.csv'
        try:
            if meta.exists() and cached.exists() and json.loads(meta.read_text()) == signature:
                daily = pd.read_csv(cached, index_col=0, parse_dates=True)
            else:
                raw = pd.read_csv(path, header=None, names=['time','open','high','low','close','volume','end','quote_volume','trades','taker_buy_base','taker_buy_quote','ignore'])
                raw = raw.apply(pd.to_numeric, errors='coerce').dropna(subset=['time','close'])
                raw.index = pd.to_datetime(raw.time, unit='ms', utc=True).dt.tz_localize(None)
                raw = raw[~raw.index.duplicated(keep='last')].sort_index()
                daily = raw.resample('1D').agg({k: ('first' if k=='open' else 'max' if k=='high' else 'min' if k=='low' else 'last' if k=='close' else 'sum') for k in FIELDS})
                counts = raw.close.resample('1D').count()
                # All incomplete days are excluded, including a live final UTC day.
                daily = daily.loc[(counts==24) & (daily.index < pd.Timestamp.now(tz='UTC').tz_localize(None).normalize())]
                daily['funding'] = 0.; daily['funding_observed'] = 0.
                if fpath.exists():
                    f = pd.read_csv(fpath, header=None, usecols=[0,1,2], names=['time','interval','rate']).apply(pd.to_numeric, errors='coerce').dropna(subset=['time','rate'])
                    f.index = pd.to_datetime(f.time, unit='ms', utc=True).dt.tz_localize(None)
                    f = f[~f.index.duplicated(keep='last')].sort_index()
                    daily['funding'] = f.rate.resample('1D').sum().reindex(daily.index).fillna(0)
                    daily['funding_observed'] = f.rate.resample('1D').count().reindex(daily.index).fillna(0)
                daily.to_csv(cached); meta.write_text(json.dumps(signature))
            if daily.empty:
                raise ValueError('No complete daily bars')
            frames[base] = daily
            coverage[base] = {'days':len(daily),'funding_days':int((daily.funding_observed>0).sum())}
        except (ValueError, OSError, pd.errors.ParserError) as exc:
            failures[base] = str(exc)
    if not frames: raise ValueError('No usable local symbols')
    idx = pd.date_range(min(f.index.min() for f in frames.values()), max(f.index.max() for f in frames.values()))
    panels = {key: pd.DataFrame({b:f[key] for b,f in frames.items()}).reindex(idx) for key in FIELDS+['funding','funding_observed']}
    return panels, {'missing':missing,'load_failures':failures,'coverage':coverage,'cache':str(cache)}

def synthetic():
    rng = np.random.default_rng(519)
    idx = pd.date_range('2021-06-01','2026-09-30'); cols=universe()
    common=rng.normal(.00025,.025,(len(idx),1))
    r=common*rng.uniform(.6,1.4,(1,len(cols)))+rng.normal(.0001,.035,(len(idx),len(cols)))
    c=pd.DataFrame(100*np.exp(np.cumsum(r,axis=0)),index=idx,columns=cols)
    for j in range(8): c.iloc[:300+j*50,-j-1]=np.nan
    q=pd.DataFrame(rng.lognormal(18,1,c.shape),index=idx,columns=cols).where(c.notna())
    p={k:c.copy() for k in ['open','high','low','close']}
    p.update(volume=q/c,quote_volume=q,trades=q/1000,taker_buy_base=q/c*.5,taker_buy_quote=q*rng.uniform(.35,.65,c.shape),funding=pd.DataFrame(rng.normal(.0001,.0002,c.shape),index=idx,columns=cols),funding_observed=c.notna().astype(float)*3)
    return p, {'synthetic':True,'missing':[],'load_failures':{}}

def signals(p):
    c=p['close']; r=c.pct_change(fill_method=None); vol=r.rolling(30).std()
    btc=r['BTC'] if 'BTC' in r else pd.Series(np.nan,index=r.index)
    beta=r.rolling(60).cov(btc).div(btc.rolling(60).var(),axis=0)
    residual=r-beta.mul(btc,axis=0)
    s={}
    for n in [7,14,21,30,60]:
        s[f'ret_{n}']=c.pct_change(n,fill_method=None)
        s[f'skip_{n}']=c.shift(1)/c.shift(n)-1
        s[f'volmom_{n}']=s[f'ret_{n}']/r.rolling(n).std().replace(0,np.nan)
        s[f'resid_{n}']=residual.rolling(n).sum()
        s[f'sma_{n}']=c/c.rolling(n).mean()-1
    rank=lambda x:x.rank(axis=1,pct=True)-.5
    s['rankblend']=sum(rank(s[f'ret_{n}']) for n in [7,14,30,60])/4
    for n in [1,2,3]:
        s[f'reversal_{n}']=-c.pct_change(n,fill_method=None)
        s[f'revmom_{n}']=rank(s['ret_14'])+rank(s[f'reversal_{n}'])
    for n in [7,30]:
        carry=p['funding'].fillna(0).rolling(n).mean()
        s[f'carry_pos_{n}']=carry; s[f'carry_neg_{n}']=-carry
    s['lowvol']=-vol; s['idiovol']=-residual.rolling(30).std()
    s['volume']=p['quote_volume'].rolling(7).mean()/p['quote_volume'].rolling(30).mean()-1
    s['breakout']=c/c.rolling(60).max()-1
    s['taker']=(p['taker_buy_quote']/p['quote_volume'].replace(0,np.nan)).rolling(7).mean()
    return s

@dataclass(frozen=True)
class Config:
    signal: str
    k: int=8
    r: int=3
    liquidity: float=0.
    weighting: str='equal'

class Engine:
    def __init__(self,p):
        self.p=p; self.close=p['close']; self.returns=self.close.pct_change(fill_method=None)
        self.vol=self.returns.rolling(30).std()
        self.liq=p['quote_volume'].rolling(30).mean()
        self.eligible=self.close.notna() & (self.close.notna().rolling(60).sum()==60)
        self.anchor=pd.Timestamp('2022-01-01')
    def weights(self,score,cfg,allowed=None):
        valid=self.eligible & score.notna() & np.isfinite(score)
        if allowed is not None: valid &= self.close.columns.isin(allowed)[None,:]
        if cfg.liquidity: valid &= self.liq.where(valid).rank(axis=1,pct=True)>cfg.liquidity
        if cfg.weighting=='inverse_vol': valid &= self.vol.gt(0)
        a=score.where(valid).to_numpy(); ok=np.isfinite(a); count=ok.sum(axis=1)
        k=np.minimum(cfg.k,count//2)
        order=np.argsort(np.where(ok,a,-np.inf),axis=1,kind='stable')
        ranks=np.empty_like(order); np.put_along_axis(ranks,order,np.arange(a.shape[1])[None,:],axis=1)
        long=ok & (ranks>=a.shape[1]-k[:,None]); short=ok & (ranks<a.shape[1]-count[:,None]+k[:,None])
        scale=np.ones_like(a)
        if cfg.weighting=='inverse_vol': scale=1/self.vol.to_numpy()
        if cfg.weighting=='score':
            # Positive rank strength, defined even when all scores share a sign.
            scale=np.abs(ranks-(a.shape[1]-count[:,None]+(count[:,None]-1)/2))+1
        l=np.where(long,scale,0); h=np.where(short,scale,0)
        w=.5*np.divide(l,l.sum(axis=1)[:,None],out=np.zeros_like(l),where=l.sum(axis=1)[:,None]>0)-.5*np.divide(h,h.sum(axis=1)[:,None],out=np.zeros_like(h),where=h.sum(axis=1)[:,None]>0)
        dates=self.close.index; reb=((dates-self.anchor).days%cfg.r==0)&(dates>=self.anchor)
        w=pd.DataFrame(w,index=dates,columns=self.close.columns).where(np.broadcast_to(reb[:,None],w.shape))
        # Insert forced-exit events BEFORE forward fill: exits persist until rebalance.
        w=w.where(self.close.notna(),0).ffill().fillna(0)
        # Forced exits rebalance surviving sides to preserve dollar neutrality.
        long=w.clip(lower=0); short=-w.clip(upper=0)
        ls=long.sum(axis=1); ss=short.sum(axis=1)
        neutral=.5*long.div(ls.replace(0,np.nan),axis=0).fillna(0)-.5*short.div(ss.replace(0,np.nan),axis=0).fillna(0)
        return neutral.where(((ls>0)&(ss>0)).to_numpy()[:,None].repeat(w.shape[1],axis=1),0)
    def backtest(self,w,cost=.001):
        held=w.shift(1).fillna(0)
        gross=(held*self.returns.fillna(0)).sum(axis=1)
        funding=(held*self.p['funding'].fillna(0)).sum(axis=1)
        turnover=w.diff().fillna(w).abs().sum(axis=1)
        net=(1+gross-funding)*(1-cost*turnover)-1
        return pd.DataFrame({'net':net,'gross':gross,'funding':funding,'turnover':turnover,'fee':cost*turnover,'missing_return_exposure':held.where(self.returns.isna(),0).abs().sum(axis=1),'funding_coverage':(held.abs()*(self.p['funding_observed'].fillna(0)>0)).sum(axis=1)})

def metrics(bt,start='2022-01-01',end=None):
    x=bt.loc[start:end]; r=x.net
    if not len(r): return {'Calmar':None,'CAGR':None,'MDD':None,'Sharpe':None}
    eq=(1+r).cumprod(); peak=eq.cummax().clip(lower=1); dd=float((1-eq/peak).max())
    years=len(r)/365; cagr=float(eq.iloc[-1]**(1/years)-1) if eq.iloc[-1]>0 else -1.
    return {'CAGR':cagr,'MDD':dd,'Calmar':cagr/dd if dd>0 else 0.,'Sharpe':float(r.mean()/r.std()*np.sqrt(365)) if r.std()>0 else 0.,'worst_day':float(r.min()),'turnover':float(x.turnover.sum()/years),'fee_drag':float(x.fee.sum()/years),'funding_drag':float(x.funding.sum()/years),'funding_coverage':float(x.funding_coverage.mean()),'missing_return_exposure':float(x.missing_return_exposure.sum()),'yearly':{str(k):float(v) for k,v in r.groupby(r.index.year).apply(lambda a:(1+a).prod()-1).items()},'days':len(r)}

def windows(bt):
    return {'IS':metrics(bt,'2022-01-01','2024-06-30'),'OOS':metrics(bt,'2024-07-01'),'full':metrics(bt)}

def no_lookahead_test(p):
    t=pd.Timestamp('2023-06-01'); altered={k:v.copy() for k,v in p.items()}
    for k,v in altered.items(): v.loc[v.index>t]*=3.7
    a,b=Engine(p),Engine(altered); sa,sb=signals(p),signals(altered)
    for name in sa:
        pd.testing.assert_frame_equal(sa[name].loc[:t],sb[name].loc[:t])
        for method in ['equal','inverse_vol','score']:
            cfg=Config(name,6,3,.2,method)
            pd.testing.assert_frame_equal(a.weights(sa[name],cfg).loc[:t],b.weights(sb[name],cfg).loc[:t])
    w=a.weights(sa['ret_14'],Config('ret_14'))
    np.testing.assert_allclose(w.sum(axis=1),0,atol=1e-12)
    assert w.abs().sum(axis=1).max()<=1+1e-12
    # Explicit causal holding and turnover accounting check.
    bt=a.backtest(w)
    np.testing.assert_allclose(bt.gross,(w.shift().fillna(0)*a.returns.fillna(0)).sum(axis=1))
    return {'passed':True,'signals':len(sa),'weighting_methods':3,'cutoff':str(t.date())}


def lookback_neighbors(p, name):
    """Predeclared one-coordinate horizon perturbations for every signal family."""
    c=p['close']; r=c.pct_change(fill_method=None)
    prefix, _, suffix=name.rpartition('_')
    base=int(suffix) if suffix.isdigit() else {'lowvol':30,'idiovol':30,'volume':7,'breakout':60,'taker':7,'rankblend':3}.get(name,14)
    horizons=sorted(set([max(1,base-3),base+3])-{base})
    output=[]
    for n in horizons:
        if prefix=='ret': a=c.pct_change(n,fill_method=None)
        elif prefix=='skip': a=c.shift(1)/c.shift(n)-1
        elif prefix=='volmom': a=c.pct_change(n,fill_method=None)/r.rolling(n).std().replace(0,np.nan)
        elif prefix=='sma': a=c/c.rolling(n).mean()-1
        elif prefix=='resid' or name=='idiovol':
            btc=r['BTC'] if 'BTC' in r else pd.Series(np.nan,index=r.index)
            beta=r.rolling(60).cov(btc).div(btc.rolling(60).var(),axis=0)
            residual=r-beta.mul(btc,axis=0)
            a=-residual.rolling(n).std() if name=='idiovol' else residual.rolling(n).sum()
        elif prefix=='reversal': a=-c.pct_change(n,fill_method=None)
        elif prefix=='revmom':
            a=c.pct_change(14,fill_method=None).rank(axis=1,pct=True)-.5
            a+=(-c.pct_change(n,fill_method=None)).rank(axis=1,pct=True)-.5
        elif prefix in ['carry_pos','carry_neg']:
            a=p['funding'].fillna(0).rolling(n).mean()*(1 if prefix=='carry_pos' else -1)
        elif name=='lowvol': a=-r.rolling(n).std()
        elif name=='volume': a=p['quote_volume'].rolling(n).mean()/p['quote_volume'].rolling(30).mean()-1
        elif name=='breakout': a=c/c.rolling(n).max()-1
        elif name=='taker': a=(p['taker_buy_quote']/p['quote_volume'].replace(0,np.nan)).rolling(n).mean()
        elif name=='rankblend':
            # Perturb one of four constituent horizons at a time, not the blend weights.
            for h in [7,14,30,60]:
                for delta in [-3,3]:
                    hs=[max(1,j+delta) if j==h else j for j in [7,14,30,60]]
                    a=sum(c.pct_change(j,fill_method=None).rank(axis=1,pct=True)-.5 for j in hs)/4
                    output.append((f'{name}_h{h}_{delta:+d}',a))
            return output
        else: raise ValueError(f'Unknown signal {name}')
        output.append((f'{name}_horizon{n}',a))
    if name=='volume':
        for n in [27,33]:
            output.append((f'volume_denominator{n}',p['quote_volume'].rolling(7).mean()/p['quote_volume'].rolling(n).mean()-1))
    if prefix=='revmom':
        for n in [11,17]:
            a=c.pct_change(n,fill_method=None).rank(axis=1,pct=True)-.5
            a+=(-c.pct_change(base,fill_method=None)).rank(axis=1,pct=True)-.5
            output.append((f'{name}_momentum{n}',a))
    return output


def accounting_test():
    idx=pd.date_range('2022-01-01',periods=3)
    c=pd.DataFrame({'A':[100.,110.,121.],'B':[100.,90.,81.]},index=idx)
    p={'close':c,'quote_volume':c*1000,'funding':pd.DataFrame({'A':[.001]*3,'B':[.002]*3},index=idx),'funding_observed':c*0+3}
    e=Engine(p); w=c*0; w.iloc[0]=[.5,-.5]; w.iloc[1]=[-.5,.5]; w.iloc[2]=0
    b=e.backtest(w)
    np.testing.assert_allclose(b.gross,[0,.1,-.1])
    np.testing.assert_allclose(b.funding,[0,-.0005,.0005])
    np.testing.assert_allclose(b.turnover,[1,2,1])
    np.testing.assert_allclose(b.net,[-.001,(1+.1+.0005)*.998-1,(1-.1-.0005)*.999-1])
    # A missing observation must not resurrect old holdings on the next day.
    dates=pd.date_range('2021-10-01','2022-01-15')
    prices=pd.DataFrame(100.,index=dates,columns=['A','B','C','D'])
    prices.loc['2022-01-05','D']=np.nan
    q={'close':prices,'quote_volume':prices*1000}
    eng=Engine(q)
    score=pd.DataFrame(np.tile([1.,2.,3.,4.],(len(dates),1)),index=dates,columns=prices.columns)
    weights=eng.weights(score,Config('test',1,7))
    assert weights.loc['2022-01-01','D']==.5
    assert weights.loc['2022-01-05':'2022-01-07','D'].eq(0).all()
    return True


def loader_test():
    import tempfile
    with tempfile.TemporaryDirectory(prefix='rs_alpha_loader_',dir='/tmp') as tmp:
        root=Path(tmp); (root/'klines_1h').mkdir(); (root/'funding').mkdir()
        time=pd.date_range('2021-06-01',periods=53,freq='h')
        raw=pd.DataFrame({'time':time.as_unit('ms').astype('int64'),'open':100.,'high':102.,'low':98.,'close':101.,'volume':1.,'end':time.as_unit('ms').astype('int64')+3599999,'quote_volume':100.,'trades':2,'taker_buy_base':.5,'taker_buy_quote':50.,'ignore':0})
        raw.to_csv(root/'klines_1h/BTCUSDT.csv.gz',header=False,index=False)
        f=pd.DataFrame({'calc_time':[time[0].value//1000000,time[8].value//1000000],'interval':[8,8],'rate':[.001,.002]})
        f.to_csv(root/'funding/BTCUSDT.csv.gz',index=False)
        p,info=load_daily(root/'cache',root,['BTC','MISSING'])
        assert len(p['close'])==2 and info['missing']==['MISSING']
        np.testing.assert_allclose(p['quote_volume']['BTC'],[2400,2400])
        np.testing.assert_allclose(p['funding']['BTC'],[.003,0])
        again,_=load_daily(root/'cache',root,['BTC'])
        pd.testing.assert_frame_equal(p['close'],again['close'])
        f.to_csv(root/'funding/BTCUSDT.csv.gz',header=False,index=False)
        again,_=load_daily(root/'cache',root,['BTC'])
        np.testing.assert_allclose(again['funding']['BTC'],[.003,0])
    return True
