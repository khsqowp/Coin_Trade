"""Offline, close-known research features; external regimes have one extra day lag."""
from pathlib import Path
import json
import numpy as np
import pandas as pd

ROOT = Path(__file__).resolve().parents[1]
SECTORS = {'L1': ['BTC','ETH','BNB','SOL','ADA','AVAX','DOT','ATOM','NEAR','APT','SUI','ICP','ALGO','HBAR','TRX','XLM','XRP','VET'], 'L2_INFRA': ['ARB','OP','POL','IMX','STX','INJ','LINK','FIL','RENDER','THETA','QNT'], 'DEFI': ['AAVE','UNI','CRV','LDO','CAKE','JUP','ENA','ONDO'], 'MEME_AI_OTHER': ['DOGE','WLD'], 'OLD_PAYMENT_PRIVACY': ['LTC','BCH','ETC','XMR','ZEC']}


def shift_signal(a, lag=0):
    """Positive lag delays information; negative lag is a future-leak control."""
    out = np.full_like(a, np.nan, dtype=float)
    if lag == 0:
        return a.copy()
    if abs(lag) < len(a):
        if lag > 0:
            out[lag:] = a[:-lag]
        else:
            out[:lag] = a[-lag:]
    return out


def rank_z(a):
    r = pd.DataFrame(a).rank(axis=1).to_numpy()
    n = np.isfinite(a).sum(axis=1, keepdims=True)
    return (r - (n + 1) / 2) / np.sqrt(np.maximum((n*n-1)/12, 1))


def roll(a, w, method='mean'):
    return getattr(pd.DataFrame(a).rolling(w, min_periods=w), method)().to_numpy()


def divide(a, b):
    return np.divide(a, b, out=np.full_like(a, np.nan, dtype=float), where=np.isfinite(b) & (b != 0))


def raw_arrays(P):
    nd, _, n = P['C'].shape
    arrays = [np.full((nd,24,n), np.nan) for _ in range(3)]
    funding = np.full((nd,n), np.nan)
    start = P['days'][0].value // 10**6
    coverage = {}
    for j, name in enumerate(P['names']):
        path = ROOT / '.rs_cache/vision/klines_1h' / f'{name}USDT.csv.gz'
        if path.exists():
            df = pd.read_csv(path, header=None, usecols=[0,7,8,10])
            ts = pd.to_numeric(df.iloc[:,0], errors='coerce').to_numpy()
            # Binance archives may contain microseconds; normalize before alignment.
            ts = np.where(ts > 1e14, ts/1000, ts)
            ix = np.floor((ts-start)/3600000).astype(np.int64)
            ok = (ix >= 0) & (ix < nd*24) & (ts % 3600000 == 0)
            for a, col in zip(arrays, [1,3,2]):
                a[:,:,j].reshape(-1)[ix[ok]] = pd.to_numeric(df.iloc[:,col], errors='coerce').to_numpy()[ok]
        path = ROOT / '.rs_cache/vision/funding' / f'{name}USDT.csv.gz'
        if path.exists():
            df = pd.read_csv(path, header=None, names=['ts','interval','rate'])
            dates = pd.to_datetime(df.ts, unit='ms', utc=True).dt.floor('D')
            s = pd.Series(pd.to_numeric(df.rate, errors='coerce').values, index=dates)
            funding[:,j] = s.groupby(level=0).sum(min_count=1).reindex(P['days']).to_numpy()
        else:
            prev = shift_signal(P['C'][:,-1,j], 1)
            funding[:,j] = divide(P['FD'][:,j], prev)
        coverage[name] = dict(hourly_fraction=float(np.isfinite(arrays[0][:,:,j]).mean()), funding_fraction=float(np.isfinite(funding[:,j]).mean()))
    return (*arrays, funding, coverage)


def external_series(path, kind, days):
    data = json.loads((ROOT/path).read_text())
    if kind == 'dvol':
        t, v, unit = [x[0] for x in data], [x[4] for x in data], 'ms'
    elif kind == 'fng':
        t, v, unit = [int(x['timestamp']) for x in data['data']], [float(x['value']) for x in data['data']], 's'
    else:
        t, v, unit = [x['date'] for x in data], [x['tvl'] for x in data], 's'
    s = pd.Series(v, index=pd.to_datetime(t, unit=unit, utc=True).floor('D')).sort_index()
    return s.groupby(level=0).last()


def build_features(P):
    V, TB, NT, F, coverage = raw_arrays(P)
    signals, metadata, flags = {}, {}, {}
    def add(family, label, a, **kw):
        a = np.asarray(a, float).copy()
        a[~np.isfinite(a)] = np.nan
        for suffix, sign in [('p',1), ('n',-1)]:
            name = f'{family}_{label}_{suffix}'
            signals[name] = np.ascontiguousarray(a*sign)
            metadata[name] = dict(family=family, sign=sign, params=kw)
    for w in [3,7,14,30]:
        add('d',f'fund_mean_{w}',roll(F,w),w=w)
    for a,b in [(3,14),(7,30)]:
        add('d',f'fund_chg_{a}_{b}',roll(F,a)-roll(F,b),short=a,long=b)
    for w in [30,90]:
        add('d',f'fund_z_{w}',divide(roll(F,7)-roll(F,w),roll(F,w,'std')),w=w)
    C = P['C']; nd, _, n = C.shape
    lc = np.log(np.where(C>0,C,np.nan)).reshape(-1,n)
    r = np.full_like(lc,np.nan); r[1:] = np.diff(lc,axis=0)
    rh = r.reshape(nd,24,n)
    def daily(a):
        out = np.sum(a,axis=1)
        out[~np.isfinite(a).all(axis=1)] = np.nan
        return out
    rv = daily(rh**2)
    for w in [3,7,14]:
        for h in [0,8,16]:
            add('h',f'session_{h}_{w}',roll(daily(rh[:,h:h+8]),w,'sum'),w=w,hour=h)
    for a,b in [(3,14),(7,30)]:
        add('h',f'rv_ratio_{a}_{b}',np.sqrt(divide(roll(rv,a),roll(rv,b))),short=a,long=b)
    for w in [7,14,30]:
        add('h',f'rv_level_{w}',np.sqrt(roll(rv,w)),w=w)
    bp = np.full_like(r,np.nan); bp[1:] = np.pi/2*np.abs(r[1:])*np.abs(r[:-1])
    dbp = daily(bp.reshape(nd,24,n))
    for w in [7,14]:
        add('h',f'jump_share_{w}',1-divide(roll(dbp,w,'sum'),roll(rv,w,'sum')),w=w)
        mx = np.max(np.abs(rh),axis=1)
        add('h',f'max_abs_{w}',roll(mx,w,'max'),w=w)
        sk = pd.DataFrame(r).rolling(w*24,min_periods=w*24).skew().to_numpy().reshape(nd,24,n)[:,-1]
        add('h',f'skew_{w}',sk,w=w)
    dv, dtb, dnt = daily(V), daily(TB), daily(NT)
    imbalance = {}
    for w in [1,3,7,14,28]:
        imbalance[w] = divide(roll(2*dtb-dv,w,'sum'),roll(dv,w,'sum'))
        add('b',f'taker_imb_{w}',imbalance[w],w=w)
    for label,a in [('count',dnt),('volume',dv)]:
        for w in [3,7]:
            add('b',f'{label}_surge_{w}_28',divide(roll(a,w),roll(a,28)),short=w,long=28)
    groups = {}
    for j,name in enumerate(P['names']):
        sec = next((s for s, members in SECTORS.items() if name in members),'OTHER')
        groups.setdefault(sec,[]).append(j)
    dc = C[:,-1]
    for w in [7,14,28]:
        ret = divide(dc,shift_signal(dc,w))-1
        sm, rel, neutral = [np.full_like(dc,np.nan) for _ in range(3)]
        for inds in groups.values():
            x = ret[:,inds]; valid = np.isfinite(x); count = valid.sum(axis=1,keepdims=True)
            total = np.nansum(x,axis=1,keepdims=True)
            sm[:,inds] = np.broadcast_to(divide(total,count),x.shape)
            rel[:,inds] = x-divide(total-np.where(valid,x,0),count-valid)
            neutral[:,inds] = rank_z(x)
        # A symbol with no own price history must never become eligible via peers.
        for a in [sm,rel,neutral]:
            a[~np.isfinite(ret)] = np.nan
        add('e',f'sector_mom_{w}',sm,w=w)
        add('e',f'rel_strength_{w}',rel,w=w)
        add('e',f'neutral_mom_{w}',neutral,w=w)
    def flag(label, cond):
        s = pd.Series(cond, index=cond.index if isinstance(cond,pd.Series) else P['days'])
        flags['g_'+label] = s.astype(float).shift(1).reindex(P['days']).fillna(0.).to_numpy(dtype=float)
    dvol = external_series('.rs_cache/online/misc/dvol_BTC.json','dvol',P['days'])
    fng = external_series('.rs_cache/online/misc/fng.json','fng',P['days'])
    tvl = external_series('.rs_cache/online/defillama/hist_all.json','tvl',P['days'])
    # Reindex to calendar before rolling/lagging; missing dates are never compressed.
    def calendar(s):
        return s.reindex(pd.date_range(min(s.index[0],P['days'][0]),P['days'][-1],freq='D',tz='UTC'))
    dvol,fng,tvl = map(calendar,[dvol,fng,tvl])
    for p in [70,80,90]:
        flag(f'dvol_p{p}',dvol > dvol.rolling(365,min_periods=365).quantile(p/100))
    for x in [.2,.3]:
        flag(f'dvol_chg7_{int(x*100)}',dvol/dvol.shift(7)-1>x)
    for x in [15,25]: flag(f'fng_fear_{x}',fng<=x)
    for x in [75,85]: flag(f'fng_greed_{x}',fng>=x)
    flag('fng_drop7',fng-fng.shift(7)<-20)
    for x in [.05,.1]: flag(f'tvl_drop14_{int(x*100)}',tvl/tvl.shift(14)-1 < -x)
    fm = pd.DataFrame(roll(F,7)).mean(axis=1).set_axis(P['days'])
    im = pd.DataFrame(imbalance[7]).mean(axis=1).set_axis(P['days'])
    for p in [80,90]: flag(f'fund_p{p}',fm>fm.rolling(365,min_periods=365).quantile(p/100))
    for p in [10,20]: flag(f'taker_p{p}',im<im.rolling(365,min_periods=365).quantile(p/100))
    bi = pd.Series(imbalance[3][:,P['names'].index('BTC')],index=P['days'])
    flag('btc_taker_p10',bi<bi.rolling(365,min_periods=365).quantile(.1))
    return signals, metadata, flags, dict(coverage=coverage, sectors=groups, percentile_window=365, sector_membership='current assumption, not point-in-time')
