import datetime as dt, time, json
from pathlib import Path
import numpy as np, pandas as pd, requests

BASE=Path('/app/data/ohlcv')
KR_CODES=['005930','000660','005380','373220','035420','105560','000270','068270','051910','207940']
KR_TICKERS=['%s.KS'%x for x in KR_CODES]+['069500.KS']
US_STOCKS=['AAPL','MSFT','NVDA','AMZN','GOOGL','META','TSLA','BRK-B','JPM','V','UNH','XOM','LLY','AVGO','WMT','COST']
US_BENCH=['SPY','QQQ']
START=pd.Timestamp('2022-09-05'); END=pd.Timestamp('2026-10-30')
P1=int(dt.datetime(2021,1,1,tzinfo=dt.timezone.utc).timestamp())
P2=int(dt.datetime(2026,11,6,tzinfo=dt.timezone.utc).timestamp())
session=requests.Session(); frames={}; meta={}; last=0.0

for sym in KR_TICKERS:
    wait=2.0-(time.monotonic()-last)
    if wait>0: time.sleep(wait)
    resp=session.get('https://query1.finance.yahoo.com/v8/finance/chart/'+sym,
      params={'period1':P1,'period2':P2,'interval':'1d','events':'div,splits'},
      headers={'User-Agent':'Mozilla/5.0 (research; low-rate)'},timeout=30)
    last=time.monotonic()
    if resp.status_code!=200: raise RuntimeError('%s HTTP %s'%(sym,resp.status_code))
    chart=resp.json().get('chart') or {}; rr=chart.get('result') or []
    if not rr: raise RuntimeError('%s no data: %s'%(sym,str(chart.get('error'))[:120]))
    r=rr[0]; q=r['indicators']['quote'][0]
    adj=(r.get('indicators',{}).get('adjclose') or [{}])[0].get('adjclose')
    if not adj: raise RuntimeError('%s lacks adjusted close'%sym)
    idx=pd.to_datetime(r['timestamp'],unit='s',utc=True).tz_convert('Asia/Seoul').tz_localize(None).normalize()
    x=pd.DataFrame({'open_raw':q['open'],'close_raw':q['close'],'close':adj},index=idx).dropna()
    x['open']=x.open_raw*x.close/x.close_raw
    frames['KR:'+sym]=x[['open','close']].sort_index()
    meta['KR:'+sym]={'rows':len(x),'first':str(x.index.min().date()),'last':str(x.index.max().date()),'source':'Yahoo chart API'}

for sym in US_STOCKS+US_BENCH:
    f=BASE/('yahoo_%s_1d.parquet'%sym)
    x=pd.read_parquet(f)[['open','close']].dropna().copy()
    ix=pd.DatetimeIndex(x.index)
    x.index=ix.tz_convert('UTC').tz_localize(None).normalize() if ix.tz is not None else ix.normalize()
    frames['US:'+sym]=x.sort_index()
    meta['US:'+sym]={'rows':len(x),'first':str(x.index.min().date()),'last':str(x.index.max().date()),'source':'stored Yahoo split/dividend-adjusted OHLC'}

def simulate(df,cost):
    d=df[(df.index>=pd.Timestamp('2021-01-01'))&(df.index<=END)].copy()
    if len(d)<220: return None
    weeks=d.groupby(d.index.to_period('W-FRI')).agg(close=('close','last'),last_session=('close',lambda s:s.index[-1]))
    weeks=weeks[weeks.last_session<=END]
    weeks['ma40']=weeks.close.rolling(40,min_periods=40).mean()
    pc,pm=weeks.close.shift(1),weeks.ma40.shift(1)
    buy=(weeks.close>weeks.ma40)&(pc<=pm)&weeks.ma40.notna()&pm.notna()
    sell=(weeks.close<weeks.ma40)&(pc>=pm)&weeks.ma40.notna()&pm.notna()
    events={}
    for key,row in weeks.iterrows():
        sig='buy' if bool(buy.loc[key]) else 'sell' if bool(sell.loc[key]) else None
        if sig:
            i=d.index.searchsorted(row.last_session,side='right')
            if i<len(d): events[d.index[i]]=sig
    eq=1.; pos=0; prev=None; curve=[]; entries=exits=0
    for date,row in d.iterrows():
        op,cl=float(row.open),float(row.close)
        if prev is not None and pos: eq*=op/prev
        action=events.get(date)
        if action=='buy' and pos==0:
            eq*=1-cost;pos=1
            if START<=date<=END: entries+=1
        elif action=='sell' and pos==1:
            eq*=1-cost;pos=0
            if START<=date<=END: exits+=1
        if pos: eq*=cl/op
        curve.append((date,eq,pos));prev=cl
    c=pd.DataFrame(curve,columns=['date','equity','position']).set_index('date')
    c=c.loc[(c.index>=START)&(c.index<=END)]
    if c.empty:return None
    v=c.equity.to_numpy();v=v/v[0];rets=np.r_[v[0]-1,v[1:]/v[:-1]-1]
    days=max(1,(c.index[-1]-c.index[0]).days)
    cagr=v[-1]**(365.25/days)-1 if v[-1]>0 else float('nan')
    mdd=float((v/np.maximum.accumulate(v)-1).min())
    sd=float(np.std(rets,ddof=1)) if len(rets)>1 else 0
    sharpe=float(np.mean(rets)/sd*np.sqrt(252)) if sd else 0
    px=d.close.loc[c.index[0]:c.index[-1]].to_numpy(float); bh=px/px[0]
    return {'equity':pd.Series({date:eq for date,eq,_ in curve}),'position':pd.Series({date:pos for date,_,pos in curve}),
      'total_return':float(v[-1]-1),'cagr':float(cagr),'mdd':mdd,'sharpe':sharpe,
      'exposure':float(c.position.mean()),'entries':entries,'exits':exits,'position_at_start':int(c.position.iloc[0]),'open_at_end':int(pos),
      'buyhold_return':float(bh[-1]-1),'buyhold_cagr':float(bh[-1]**(365.25/days)-1),
      'buyhold_mdd':float((bh/np.maximum.accumulate(bh)-1).min()),'start':str(c.index[0].date()),'end':str(c.index[-1].date())}

results={}
for name in ['KR:069500.KS','US:SPY','US:QQQ']:
    for fee in [0,0.001]:
        r=simulate(frames[name],fee); r.pop('equity');r.pop('position')
        results[name+'|'+str(fee)]=r

for market,syms in [('KR',['KR:%s.KS'%x for x in KR_CODES]),('US',['US:'+x for x in US_STOCKS])]:
    for fee in [0,0.001]:
        rows={s:simulate(frames[s],fee) for s in syms}
        rows={s:r for s,r in rows.items() if r}
        # Reset each ticker to equal capital at the evaluation start; exclude
        # all pre-evaluation performance from the basket's initial weights.
        normalized=[]
        for r in rows.values():
            e=r['equity'].loc[START:END]
            normalized.append(e/e.iloc[0])
        eqs=pd.concat(normalized,axis=1).ffill().loc[START:END]
        port=eqs.mean(axis=1)
        daily=port.pct_change().fillna(port.iloc[0]-1);days=max(1,(port.index[-1]-port.index[0]).days)
        bhs=[]
        pos=[]
        for s,r in rows.items():
            d=frames[s];px=d.close.loc[START:END];bhs.append(px/px.iloc[0]);pos.append(r['position'])
        bh=pd.concat(bhs,axis=1).ffill().loc[START:END].mean(axis=1);bh=bh/bh.iloc[0]
        exposures=pd.concat(pos,axis=1).ffill().loc[START:END].mean(axis=1)
        sd=float(daily.std(ddof=1))
        results[market+'_equal_initial_weight|'+str(fee)]={'n_symbols':len(rows),'total_return':float(port.iloc[-1]-1),'cagr':float(port.iloc[-1]**(365.25/days)-1),'mdd':float((port/port.cummax()-1).min()),'sharpe':float(daily.mean()/sd*np.sqrt(252)) if sd else 0,'exposure':float(exposures.mean()),'entries':sum(r['entries'] for r in rows.values()),'exits':sum(r['exits'] for r in rows.values()),'buyhold_return':float(bh.iloc[-1]-1),'buyhold_cagr':float(bh.iloc[-1]**(365.25/days)-1),'buyhold_mdd':float((bh/bh.cummax()-1).min()),'start':str(port.index[0].date()),'end':str(port.index[-1].date())}

individual={}
for market,syms in [('KR',['KR:%s.KS'%x for x in KR_CODES]),('US',['US:'+x for x in US_STOCKS])]:
    individual[market]={s.split(':',1)[1]:simulate(frames[s],0.001) for s in syms}
    for ticker,r in individual[market].items():
        r.pop('equity');r.pop('position')

print(json.dumps({'method':{'signal':'weekly adjusted close strict cross of SMA40; long/cash','execution':'first local session open after weekly close','evaluation_period':[str(START.date()),str(END.date())],'cost_scenarios':'strategy: 0 and 0.10% each entry/exit; buy-and-hold benchmark shown gross, no entry cost; 10bp is illustrative, not broker schedule','corporate_actions':'Yahoo dividend- and split-adjusted OHLC; signals on adjusted weekly close','week_build':'local trading-session dates grouped to Friday; partial final week excluded','KR_universe':'10 current server-listed large caps plus 069500.KS KODEX 200','US_universe':US_STOCKS+US_BENCH,'survivorship':'current ticker sample only; not point-in-time'},'data':meta,'results':results,'individual_net_10bp':individual},ensure_ascii=False,default=str,separators=(',',':')))
