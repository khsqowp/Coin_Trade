"""Offline trend families, close-state contract (no execution or portfolio sizing).

Provenance: catalog 1/2/19/94/97/103/104; consolidated report sections
39--82; round12/13/14 result JSONs; round12_signals/round13_signals;
broad_strategies, futures_donchian_probe, extra/futures_strategies.
R14 70/25 means entry lookback / HOLD DAYS, not an exit channel.
Fixed holds ignore overlapping entries, as technical_portfolio_engine does.
The requested same-close contract removes next-open execution and terminal
liquidation. Research events have no unique net position: catalog families
below return the original ternary condition (flat when absent), explicitly
marked partial rather than inventing a holding policy. 4h scales daily periods
by six; BTC daily regime becomes available only at each day's final 4h close.
Volume rules use the supplied quote volume, which can differ from source base
volume. No caches, files, network, environment variables or fees are used.
"""
from functools import partial
from time import perf_counter
import numpy as np
import pandas as pd
from numba import njit


def _bars(D, tf):
    if tf not in ('1d', '4h'):
        raise ValueError(tf)
    return {k: pd.DataFrame(v) for k, v in D['d' if tf == '1d' else 'b4'].items()}, (1 if tf == '1d' else 6)


def _roll(x, n, op='mean'):
    return getattr(x.rolling(int(n), min_periods=int(n)), op)()


def _tr(b):
    c = b['c'].shift()
    return pd.DataFrame(np.fmax(np.fmax((b['h']-b['l']).values,
                           (b['h']-c).abs().values), (b['l']-c).abs().values))


def _atr(b, n, simple=False):
    tr = _tr(b)
    if simple:
        return _roll(tr, n)
    # pandas-ta fallback sets the first valid symbol bar's TR to NaN.
    tr = tr.where(b['c'].shift().notna())
    return tr.ewm(alpha=1/n, min_periods=n, adjust=True).mean()


def _adx(b, n, catalog=False):
    up, dn = b['h'].diff(), -b['l'].diff()
    p = up.where((up > dn) & (up > 0), 0.)
    m = dn.where((dn > up) & (dn > 0), 0.)
    # Reset artificial prelisting zeros, matching independent trimmed histories.
    p, m = p.where(b['c'].notna()), m.where(b['c'].notna())
    def smooth(x):
        return x.ewm(alpha=1/n, adjust=not catalog,
                     min_periods=0 if catalog else n).mean()
    a = smooth(_tr(b)) if catalog else _atr(b, n)
    p, m = 100*smooth(p)/a, 100*smooth(m)/a
    ad = smooth(100*(p-m).abs()/(p+m).replace(0, np.nan))
    return ad, p, m


def _out(D, tf, c, p, s, long_short=False):
    p, s = np.asarray(p, dtype=np.float64).copy(), np.asarray(s, dtype=np.float64).copy()
    valid = np.isfinite(c.values)
    if not long_short:
        s[(p == 0) & np.isfinite(s)] = 0.
    p[~valid] = np.nan
    s[~valid | ~np.isfinite(s)] = np.nan
    if tf == '4h':
        p, s = p[5::6], s[5::6]
    assert p.shape == (len(D['days']), len(D['names']))
    return p, s


def _event(long, short=None):
    p = np.where(long, 1., 0.)
    return p if short is None else np.where(short, -1., p)


def _warm(signal, c, n):
    return signal & (c.notna().cumsum() > n)


@njit(cache=False)
def _state(c, ent, ext, atr, hold, mult, trailing=False, reverse=False):
    out = np.empty(c.shape)
    for j in range(c.shape[1]):
        state, expiry, stop = 0., -1, np.nan
        for i in range(c.shape[0]):
            price = c[i,j]
            if not np.isfinite(price):
                out[i,j] = np.nan
                continue
            occupied = state != 0
            if occupied:
                stopped = np.isfinite(stop) and ((state > 0 and price <= stop) or (state < 0 and price >= stop))
                if stopped or ext[i,j]*state > 0 or (hold > 0 and i >= expiry):
                    state, stop = 0., np.nan
                elif trailing and np.isfinite(atr[i,j]):
                    candidate = price-state*mult*atr[i,j]
                    stop = max(stop,candidate) if state > 0 else min(stop,candidate)
            if state == 0 and (not occupied or reverse) and ent[i,j] != 0:
                state = ent[i,j]
                expiry = i+hold
                stop = price-state*mult*atr[i,j] if mult > 0 else np.nan
            out[i,j] = state
    return out


def _held(D, tf, b, entry, strength, hold, exit=None, stop=0., trailing=False, reverse=False, long_short=False):
    empty = np.zeros(b['c'].shape)
    a = _atr(b, 14*(6 if tf == '4h' else 1)).values if stop else empty
    p = _state(b['c'].values, np.asarray(entry,dtype=float),
               empty if exit is None else np.asarray(exit,dtype=float), a,
               int(hold), float(stop), trailing, reverse)
    return _out(D, tf, b['c'], p, strength, long_short)


def catalog(D, tf, rule='dual', period=4, k1=.5, k2=.5, mult=2., adx_min=0.):
    b, q = _bars(D, tf)
    c,h,l,o = (b[k] for k in 'chlo')
    a = _atr(b,20*q,simple=True)
    if rule in ('dual','larry'):
        n = period*q
        r = (_roll(h.shift(),q,'max')-_roll(l.shift(),q,'min')) if rule == 'larry' else pd.DataFrame(np.fmax(
            (_roll(h.shift(),n,'max')-_roll(c.shift(),n,'min')).values,
            (_roll(c.shift(),n,'max')-_roll(l.shift(),n,'min')).values))
        z = (c-o)/r.replace(0,np.nan)
        long, short = c > o+k1*r, c < o-k2*r
        s = z
    elif rule == 'dynamic':
        ret = c.ffill().pct_change(fill_method=None)
        ratio = (_roll(ret,20*q,'std')/_roll(ret,100*q,'std')).clip(.5,2).fillna(1)
        lb = (period*q/ratio).round().clip(20*q,60*q).astype(int).values
        upper,lower = _adaptive(h.values,l.values,lb,60*q,c.values)
        long,short = c > upper,c < lower
        s = (c-(upper+lower)/2)/a
    elif rule == 'dynamic_fast':
        upper,lower = _roll(h.shift(),period*q,'max'),_roll(l.shift(),period*q,'min')
        long,short = c > upper,c < lower
        s = (c-(upper+lower)/2)/a
    elif rule.startswith('ichimoku'):
        ten = (_roll(h,9*q,'max')+_roll(l,9*q,'min'))/2
        kij = (_roll(h,26*q,'max')+_roll(l,26*q,'min'))/2
        sa = ((ten+kij)/2).shift(26*q)
        sb = ((_roll(h,52*q,'max')+_roll(l,52*q,'min'))/2).shift(26*q)
        top,bot = np.fmax(sa,sb),np.fmin(sa,sb)
        long,short = (ten > kij)&(c > top),(ten < kij)&(c < bot)
        s = (c-(top+bot)/2)/a
        if rule == 'ichimoku_strict':
            ok = (_adx(b,14*q,True)[0] >= adx_min)&(c.pct_change(20*q,fill_method=None).abs() > a/c)
            long,short = long&ok,short&ok
    elif rule == 'keltner':
        center = c.ewm(span=period*q,adjust=False).mean()
        z = (c-center)/a
        long,short,s = c > center+mult*a,c < center-mult*a,z
    elif rule == 'nr7':
        r=h-l
        narrow=r.shift() == _roll(r.shift(),period*q,'min')
        long,short=narrow&(c > h.shift()),narrow&(c < l.shift())
        s=(c-(h.shift()+l.shift())/2)/a
    elif rule == 'williams':
        hh,ll = _roll(h,period*q,'max'),_roll(l,period*q,'min')
        wr = -100*(hh-c)/(hh-ll).replace(0,np.nan)
        long,short = (wr.shift() < -80)&(wr > -80),(wr.shift() > -20)&(wr < -20)
        s = (wr+50)/50
    else:
        raise ValueError(rule)
    if adx_min and rule != 'ichimoku_strict':
        ok = _adx(b,14*q,True)[0] >= adx_min
        long,short = long&ok,short&ok
    return _out(D,tf,c,_event(long,short),s,True)


@njit(cache=False)
def _adaptive(h,l,lb,warm,c):
    u,v = np.full(h.shape,np.nan),np.full(l.shape,np.nan)
    for j in range(h.shape[1]):
        count = 0; started = False
        for i in range(h.shape[0]):
            if np.isfinite(c[i,j]): started = True
            if not started: continue
            count += 1
            if count <= warm:
                continue
            start = max(0,i-lb[i,j])
            hi,lo = -np.inf,np.inf
            for k in range(start,i):
                if np.isfinite(h[k,j]): hi = max(hi,h[k,j])
                if np.isfinite(l[k,j]): lo = min(lo,l[k,j])
            u[i,j],v[i,j] = hi if np.isfinite(hi) else np.nan,lo if np.isfinite(lo) else np.nan
    return u,v


def donchian(D,tf,lookback=55,hold_days=20,btc_hysteresis=0.):
    b,q = _bars(D,tf)
    c = b['c']; upper = _roll(b['h'].shift(),lookback*q,'max')
    entry = _warm((c > upper)&(c >= _roll(c,200*q)),c,210*q)
    if btc_hysteresis:
        bc = pd.DataFrame(D['d']['c'][:,D['names'].index('BTC')])
        regime = _hyster(bc.values[:,0],_roll(bc,200).values[:,0],btc_hysteresis)
        if q == 6:
            # rows 0..4 know yesterday; row 5 knows today's daily close.
            regime = np.repeat(np.r_[False,regime[:-1]],6)
            regime[5::6] = _hyster(bc.values[:,0],_roll(bc,200).values[:,0],btc_hysteresis)
        entry &= regime[:,None]
    s = ((c-upper)/_atr(b,14*q)).clip(lower=0)
    return _held(D,tf,b,_event(entry),s,hold_days*q)


@njit(cache=False)
def _hyster(c,ma,w):
    result = np.zeros(len(c),np.bool_); state = False
    for i in range(len(c)):
        if np.isfinite(ma[i]):
            if c[i] > ma[i]*(1+w): state = True
            elif c[i] < ma[i]*(1-w): state = False
        result[i] = state
    return result


def research(D,tf,rule='gap',hold_days=20,period=20,threshold=.1):
    b,q = _bars(D,tf); c,h,l,v = (b[k] for k in 'chlv')
    a = _atr(b,14*q)
    trend = c > _roll(c,200*q)
    warm = 200*q
    if rule == 'gap':
        z = c.pct_change(q,fill_method=None); entry = z >= threshold; warm = 5*q
    elif rule == 'range':
        hi,lo = _roll(h,period*q,'max'),_roll(l,period*q,'min')
        z = (hi-c)/(hi-lo).replace(0,np.nan)
        entry = z >= 1-threshold; warm = 35*q
    elif rule == 'dual':
        rng = np.fmax(_roll(h.shift(),period*q,'max')-_roll(c.shift(),period*q,'min'),
                      _roll(c.shift(),period*q,'max')-_roll(l.shift(),period*q,'min'))
        z = (c-b['o'])/rng; entry = c > b['o']+threshold*rng; warm = 25*q
    elif rule == 'obv':
        obv = (np.sign(c.diff()).fillna(0)*v).cumsum()
        hi = _roll(obv.shift(),period*q,'max')
        z = (obv-hi)/_roll(v,20*q)
        entry = (obv > hi)&(c > _roll(c,50*q))&(c > _roll(h.shift(),20*q,'max')); warm = 0
    elif rule == 'compression':
        width = 4*_roll(c,20*q,'std')*np.sqrt((20*q-1)/(20*q))/_roll(c,20*q)
        level = width.shift().rolling(120*q,min_periods=60*q).quantile(threshold)
        compressed = (width < level).rolling(10*q,min_periods=1).max().astype(bool)
        hi = _roll(h.shift(),period*q,'max'); z = (c-hi)/a
        entry = compressed&(c > hi)&(c > _roll(c,50*q)); warm = 0
    elif rule == 'keltner':
        upper = c.ewm(span=period*q,adjust=False,min_periods=period*q).mean()+threshold*_atr(b,period*q)
        z = (c-upper)/a; entry = (c > upper)&(c.shift() <= upper.shift())&trend
    elif rule == 'trix':
        e = c
        for _ in range(3): e = e.ewm(span=period*q,adjust=False,min_periods=period*q).mean()
        z = e.pct_change(fill_method=None); entry = (z > 0)&(z.shift() <= 0)&trend
    elif rule == 'awesome':
        mid = (h+l)/2; z = (_roll(mid,5*q)-_roll(mid,period*q))/a
        entry = (z > 0)&(z.shift() <= 0)&trend
    elif rule == 'williams':
        hi,lo = _roll(h,period*q,'max'),_roll(l,period*q,'min')
        z = -100*(hi-c)/(hi-lo).replace(0,np.nan)-threshold
        entry = (z > 0)&(z.shift() <= 0)&trend
    elif rule == 'aroon':
        up,dn = _aroon(h.values,l.values,period*q+1)
        z = pd.DataFrame(up-dn)
        entry = (z > 0)&(z.shift() <= 0)&(up >= threshold)&trend
    elif rule == 'psar':
        direction,line = _psar(h.values,l.values,threshold)
        z = (c-line)/a
        dr = pd.DataFrame(direction); entry = (dr > 0)&(dr.shift() < 0)&trend
    elif rule == 'ichimoku':
        ten = (_roll(h,9*q,'max')+_roll(l,9*q,'min'))/2
        kij = (_roll(h,26*q,'max')+_roll(l,26*q,'min'))/2
        cloud = pd.DataFrame(np.fmax(((ten+kij)/2).shift(26*q),
            ((_roll(h,52*q,'max')+_roll(l,52*q,'min'))/2).shift(26*q)))
        z = (c-cloud)/a; entry = (c > cloud)&(c.shift() <= cloud.shift())&(ten > kij); warm = 78*q
    else: raise ValueError(rule)
    entry = _warm(entry,c,warm)
    return _held(D,tf,b,_event(entry),np.maximum(z,0),hold_days*q)


@njit(cache=False)
def _aroon(h,l,n):
    up,dn = np.full(h.shape,np.nan),np.full(h.shape,np.nan)
    for j in range(h.shape[1]):
        for i in range(n-1,h.shape[0]):
            x,y = h[i-n+1:i+1,j],l[i-n+1:i+1,j]
            if np.all(np.isfinite(x)) and np.all(np.isfinite(y)):
                up[i,j],dn[i,j] = np.argmax(x)*100/(n-1),np.argmin(y)*100/(n-1)
    return up,dn


@njit(cache=False)
def _psar(h,l,step):
    dr,line = np.full(h.shape,np.nan),np.full(h.shape,np.nan)
    for j in range(h.shape[1]):
        started=False; bull=True; sar=0.; ep=0.; af=step; prev=0; prev2=0
        for i in range(h.shape[0]):
            if not np.isfinite(h[i,j]): continue
            if not started:
                sar=l[i,j]; ep=h[i,j]; started=True; prev=i; prev2=i
            else:
                sar += af*(ep-sar)
                if bull:
                    sar=min(sar,l[prev,j],l[prev2,j])
                    if l[i,j] < sar: bull=False; sar=ep; ep=l[i,j]; af=step
                    elif h[i,j] > ep: ep=h[i,j]; af=min(.2,af+step)
                else:
                    sar=max(sar,h[prev,j],h[prev2,j])
                    if h[i,j] > sar: bull=True; sar=ep; ep=h[i,j]; af=step
                    elif l[i,j] < ep: ep=l[i,j]; af=min(.2,af+step)
            dr[i,j],line[i,j]=1 if bull else -1,sar
            prev2,prev=prev,i
    return dr,line


@njit(cache=False)
def _super(c,upper,lower):
    dr,line=np.full(c.shape,np.nan),np.full(c.shape,np.nan)
    for j in range(c.shape[1]):
        state=1.; previous=-1
        for i in range(c.shape[0]):
            if not np.isfinite(c[i,j]): continue
            if previous >= 0:
                if c[i,j] > upper[previous,j]: state=1.
                elif c[i,j] < lower[previous,j]: state=-1.
                else:
                    if state > 0 and lower[i,j] < lower[previous,j]: lower[i,j]=lower[previous,j]
                    if state < 0 and upper[i,j] > upper[previous,j]: upper[i,j]=upper[previous,j]
            dr[i,j]=state; line[i,j]=lower[i,j] if state > 0 else upper[i,j]
            previous=i
    return dr,line


def supertrend(D,tf,length=10,mult=3.,adx_min=0.,volume_mult=0.,long_short=False,research_hold=0):
    b,q=_bars(D,tf)
    if not research_hold: q=1  # Original native periods are bars, not days.
    c=b['c']; a=_atr(b,length*q); mid=(b['h']+b['l'])/2
    dr,line=_super(c.values,(mid+mult*a).values,(mid-mult*a).values)
    dr=pd.DataFrame(dr); flip=(dr != dr.shift())&dr.shift().notna()
    ok=_adx(b,14*q)[0] >= adx_min if adx_min else c.notna()
    if volume_mult: ok &= b['v'] >= _roll(b['v'],20*q,'median')*volume_mult
    entry=_warm(flip&ok&(c > line)&(dr > 0),c,30*q)
    short=_warm(flip&ok&(c < line)&(dr < 0),c,30*q) if long_short else None
    s=(c-line)/_atr(b,14*q)
    if not long_short: s=s.clip(lower=0)
    if research_hold: return _held(D,tf,b,_event(entry),s,research_hold*q)
    # Direction exits plus a monotone line stop, checked against prior close's stop.
    ext=np.where(dr < 0,1.,-1.) if long_short else np.where(dr < 0,1.,0.)
    p=_line_state(c.values,_event(entry,short),ext,line,long_short)
    return _out(D,tf,c,p,s,long_short)


@njit(cache=False)
def _line_state(c,ent,ext,line,reverse):
    out=np.full(c.shape,np.nan)
    for j in range(c.shape[1]):
        state=0.; stop=np.nan
        for i in range(c.shape[0]):
            if not np.isfinite(c[i,j]): continue
            occupied=state != 0
            if occupied:
                if ext[i,j]*state > 0 or state*(c[i,j]-stop) <= 0: state=0.; stop=np.nan
                elif np.isfinite(line[i,j]): stop=max(stop,line[i,j]) if state > 0 else min(stop,line[i,j])
            if state == 0 and (not occupied or reverse) and ent[i,j] != 0:
                state=ent[i,j]; stop=line[i,j]
            out[i,j]=state
    return out


def broad(D,tf,rule='adx',threshold=20.,stop_mult=2.,period=20):
    b,q=_bars(D,tf); c,h,l=(b[k] for k in 'chl'); a=_atr(b,14*q)
    warm=30*q
    if rule == 'adx':
        ad,p,m=_adx(b,14*q); z=(p-m)/100
        entry=(z > 0)&(z.shift() <= 0)&(ad > threshold); exit=(z < 0)&(z.shift() >= 0)
    elif rule == 'williams':
        hi,lo=_roll(h,14*q,'max'),_roll(l,14*q,'min')
        wr=-100*(hi-c)/(hi-lo).replace(0,np.nan)
        entry=(wr < threshold)&(c > _roll(c,200*q)); exit=wr > -20; z=(-wr-20)/80; warm=205*q
    elif rule == 'obv':
        obv=(np.sign(c.diff()).fillna(1)*b['v']).cumsum(); avg=_roll(obv,20*q); ma=_roll(c,50*q)
        entry=(obv > avg)&(c > ma); exit=(obv < avg)|(c < ma); z=(obv-avg)/_roll(b['v'],20*q); warm=55*q
    elif rule == 'keltner':
        center=c.ewm(span=period*q,adjust=False,min_periods=period*q).mean()
        width=_tr(b).ewm(span=period*q,adjust=False,min_periods=period*q).mean()*2
        entry=c > center+width; exit=c < center-width; z=(c-center)/a
    elif rule == 'ichimoku':
        ten=(_roll(h,9*q,'max')+_roll(l,9*q,'min'))/2
        kij=(_roll(h,26*q,'max')+_roll(l,26*q,'min'))/2
        z=(ten-kij)/a; entry=(z > 0)&(z.shift() <= 0)&(c > kij); exit=(z < 0)&(z.shift() >= 0)
    elif rule in ('trix','awesome'):
        if rule == 'trix':
            e=c
            for _ in range(3): e=e.ewm(span=15*q,adjust=False,min_periods=15*q).mean()
            z=e.pct_change(fill_method=None); warm=50*q
        else: z=(_roll((h+l)/2,5*q)-_roll((h+l)/2,34*q))/a; warm=40*q
        entry=(z > 0)&(z.shift() <= 0); exit=(z < 0)&(z.shift() >= 0)
    elif rule == 'aroon':
        up,dn=_aroon(h.values,l.values,25*q+1); z=pd.DataFrame((up-dn)/100)
        entry=(z > 0)&(z.shift() <= 0)&(up > threshold); exit=(z < 0)&(z.shift() >= 0)
    elif rule == 'donchian_ls':
        hi,lo=_roll(h.shift(),period*q,'max'),_roll(l.shift(),period*q,'min')
        z=(c-(hi+lo)/2)/a; warm=25*q
        ent=_event(_warm(c > hi,c,warm),_warm(c < lo,c,warm))
        return _held(D,tf,b,ent,z,0,stop=stop_mult,trailing=True,long_short=True)
    else: raise ValueError(rule)
    return _held(D,tf,b,_event(_warm(entry,c,warm)),np.maximum(z,0),0,_event(exit),stop_mult)


@njit(cache=False)
def _protect(c,entry,exit,initial,target,atr,trail,hold):
    out=np.full(c.shape,np.nan)
    for j in range(c.shape[1]):
        state=False; stop=np.nan; tp=np.nan; peak=0.; expiry=-1
        for i in range(c.shape[0]):
            price=c[i,j]
            if not np.isfinite(price): continue
            occupied=state
            if state:
                if price <= stop or price >= tp or exit[i,j] or (hold > 0 and i >= expiry):
                    state=False
                elif trail > 0:
                    peak=max(peak,price)
                    stop=max(stop,peak-trail*atr[i,j])
            if not occupied and entry[i,j] and np.isfinite(initial[i,j]) and 0 < initial[i,j] < price:
                state=True; stop=initial[i,j]; tp=target[i,j]; peak=price; expiry=i+hold
            out[i,j]=1. if state else 0.
    return out


def protected(D,tf,rule='swing',entry_n=55,exit_m=20,stop_mult=2.,trail_mult=3.,
              gap=.10,tp_pct=.05,sl_pct=.03,hold_days=5,k1=.71,entry_band=.2,exit_band=.5):
    b,q=_bars(D,tf)
    if rule in ('range','dual'): q=1
    c,h,l=(b[k] for k in 'chl'); a=_atr(b,14*q)
    target=np.full(c.shape,np.inf); exit=np.zeros(c.shape,np.bool_); hold=0; trail=0.
    if rule == 'swing':
        hi=_roll(h.shift(),entry_n*q,'max'); lo=_roll(l.shift(),exit_m*q,'min')
        entry=_warm((c > hi)&(c >= _roll(c,200*q)),c,210*q)
        exit=(c < lo).values; initial=c-stop_mult*a; trail=trail_mult
        z=(c-hi)/a
    elif rule == 'gap':
        z=c.pct_change(q,fill_method=None); entry=_warm(z >= gap,c,5*q)
        initial=c*(1-sl_pct); target=(c*(1+tp_pct)).values; hold=hold_days*q
    elif rule == 'dual':
        rng=np.fmax(_roll(h.shift(),21*q,'max')-_roll(c.shift(),21*q,'min'),
                    _roll(c.shift(),21*q,'max')-_roll(l.shift(),21*q,'min'))
        z=(c-b['o'])/rng; entry=_warm(c > b['o']+k1*rng,c,25*q); initial=c-stop_mult*a
    elif rule == 'range':
        hi,lo=_roll(h,30*q,'max'),_roll(l,30*q,'min'); width=hi-lo
        z=(hi-c)/width.replace(0,np.nan)
        entry=_warm((width > 0)&(c <= lo+entry_band*width),c,35*q)
        exit=(c >= lo+exit_band*width).values; initial=lo-stop_mult*a
    else: raise ValueError(rule)
    pos=_protect(c.values,np.asarray(entry),exit,np.asarray(initial),target,a.values,trail,hold)
    return _out(D,tf,c,pos,np.maximum(z,0))


def catalog_btc(D,tf,rule='ichimoku',period=20,mult=1.5,btc_period=200):
    pos,s=catalog(D,tf,rule=rule,period=period,mult=mult)
    btc=pd.DataFrame(D['d']['c'][:,D['names'].index('BTC')])
    regime=(btc > _roll(btc,btc_period)).values
    pos=np.where(((pos > 0)&~regime)|((pos < 0)&regime),0.,pos)
    return pos,s


FAMILIES={}
def _register(name,fn,grid,source,fidelity='exact',long_short=False):
    FAMILIES['a_'+name]=dict(fn=fn,grid=grid,tfs=('1d','4h'),long_short=long_short,fidelity=fidelity,source=source)

CAT='app/new_strategy_screening.py (+ docs/신규전략100-카탈로그.md; app/new_strategy_precision.py)'
EVENT='partial: exact original direction events; overlapping event-study horizons have no unique position/exit policy; condition used as close state'
_register('dual_thrust_ls',partial(catalog,rule='dual'),dict(period=[3,4,6],k1=[.5,.7,.85],k2=[.5,.7,.85]),CAT,EVENT,True)
_register('dynamic_breakout_ii_ls',partial(catalog,rule='dynamic',period=40),dict(period=[30,40,50],adx_min=[0.,25.]),CAT,EVENT,True)
_register('dynamic_fast_ls',partial(catalog,rule='dynamic_fast',period=20),dict(period=[15,20,30]),CAT,EVENT,True)
_register('keltner_catalog_ls',partial(catalog,rule='keltner',period=20),dict(period=[15,20,30],mult=[1.5,2.,2.5],adx_min=[0.,25.]),CAT,EVENT,True)
_register('ichimoku_cloud_ls',partial(catalog,rule='ichimoku'),dict(adx_min=[0.,18.,25.]),CAT,EVENT,True)
_register('ichimoku_strict_ls',partial(catalog,rule='ichimoku_strict'),dict(adx_min=[18.,20.,25.]),CAT,EVENT,True)
_register('larry_williams_ls',partial(catalog,rule='larry'),dict(k1=[.3,.5,.7],k2=[.3,.5,.7]),CAT,EVENT,True)
_register('williams_catalog_ls',partial(catalog,rule='williams',period=14),dict(period=[10,14,20]),CAT,EVENT,True)
_register('donchian_r12',donchian,dict(lookback=[20,35,55,70,90],hold_days=[10,20,25,35,40]),'app/round12_signals.py (+ round12/14-results JSON; report §59–82)')
_register('donchian_btc_hysteresis',donchian,dict(lookback=[35,55,70,90],hold_days=[15,25,35],btc_hysteresis=[.01,.03,.05,.10]),'app/round13_signals.py:hysteresis (+ app/crypto_round14_research.py; round14-results JSON)', 'exact')
for name,rule,periods,thresholds in [
 ('gap_r12','gap',[1,2],[.05,.10,.15]),
 ('range_lower_r12','range',[20,30,40],[.1,.2,.3]),
 ('dual_thrust_r12','dual',[14,21,28],[.5,.71,.85]),
 ('compression_breakout','compression',[15,20,30],[.2,.25,.3]),
 ('obv_breakout','obv',[35,55,70],[0.,1.]),
 ('keltner_r13','keltner',[15,20,30],[1.5,2.,2.5]),
 ('trix_r13','trix',[10,15,20],[0.,1.]),
 ('awesome_r13','awesome',[26,34,42],[0.,1.]),
 ('williams_r13','williams',[10,14,20],[-90.,-80.,-70.]),
 ('aroon_r13','aroon',[20,25,30],[60.,70.,80.]),
 ('psar_r13','psar',[1,2],[.01,.02,.03]),
 ('ichimoku_r13','ichimoku',[1,2],[0.,1.])]:
    grid=dict(hold_days=[10,20,40])
    # Do not expose inert axes for fixed-formula indicators.
    if rule not in ('gap','psar','ichimoku'): grid['period']=periods
    if rule not in ('obv','trix','awesome','ichimoku'): grid['threshold']=thresholds
    fidelity='approx: supplied quote volume instead of original Volume units' if rule in ('obv',) else 'exact'
    defaults={'gap':(1,.1),'range':(30,.2),'dual':(21,.71),'compression':(20,.25),'obv':(55,0.),'keltner':(20,2.),'trix':(15,0.),'awesome':(34,0.),'williams':(14,-80.),'aroon':(25,70.),'psar':(1,.02),'ichimoku':(1,0.)}
    default_period,default_threshold=defaults[rule]
    _register(name,partial(research,rule=rule,period=default_period,threshold=default_threshold),grid,'app/round12_signals.py / app/round13_signals.py (+ round12/13-results JSON)',fidelity)
STOPNOTE='approx: pandas-ta non-TA-Lib Wilder/EMA formulas; native intrabar stops evaluated on closes as requested; library-version/TA-Lib initialization not guaranteed'
for rule,thresholds in [('adx',[15.,20.,25.,30.]),('williams',[-90.,-80.,-70.]),('obv',None),('keltner',None),('ichimoku',None),('trix',None),('awesome',None),('aroon',[60.,70.,80.])]:
    grid=dict(stop_mult=[1.5,2.,2.5,3.])
    if thresholds is not None: grid['threshold']=thresholds
    _register(rule+'_native',partial(broad,rule=rule),grid,'app/broad_strategies.py (+ app/param_grids.py)',STOPNOTE + ('; quote rather than base volume' if rule == 'obv' else ''))
_register('donchian_native_ls',partial(broad,rule='donchian_ls'),dict(period=[15,20,30],stop_mult=[2.,3.,4.]),'app/futures_donchian_probe.py',STOPNOTE,True)
_register('supertrend_native',supertrend,dict(length=[7,10,14],mult=[2.,3.,4.],volume_mult=[0.,1.,1.5,2.]),'app/extra_strategies.py (+ app/extra_indicators.py; app/param_grids.py)',STOPNOTE+'; quote volume confirmation')
_register('supertrend_native_ls',partial(supertrend,long_short=True),dict(length=[7,10,14],mult=[2.,3.,4.],adx_min=[0.,20.,25.]),'app/futures_strategies.py',STOPNOTE,True)
_register('supertrend_r12',partial(supertrend,research_hold=20),dict(length=[7,10,14],mult=[2.,3.,4.]),'app/round12_signals.py', 'approx: explicit R12 fallback Supertrend recursion; original pandas-ta/TA-Lib initialization not guaranteed')
_register('nr7_catalog_ls',partial(catalog,rule='nr7',period=7),dict(period=[5,7,10]),CAT,EVENT,True)
_register('ichimoku_btc_ls',partial(catalog_btc,rule='ichimoku'),dict(btc_period=[150,200,250]),CAT,EVENT,True)
_register('keltner_btc_ls',partial(catalog_btc,rule='keltner'),dict(period=[15,20,30],mult=[1.5,2.,2.5]),CAT,EVENT,True)
_register('donchian_channel_native',partial(protected,rule='swing'),dict(entry_n=[20,35,55,70],exit_m=[10,20,25],stop_mult=[1.5,2.],trail_mult=[2.,3.,4.]),'app/swing_strategies.py (+ app/swing_indicators.py; app/param_grids.py)',STOPNOTE)
_register('gap_native',partial(protected,rule='gap'),dict(gap=[.05,.10,.15,.20],tp_pct=[.03,.05,.08],sl_pct=[.02,.03],hold_days=[3,5,10]),'app/momentum_strategy.py (+ app/param_grids.py)','approx: native intrabar stop/target evaluated on closes as requested')
_register('dual_thrust_native',partial(protected,rule='dual'),dict(k1=[.5,.6,.71,.85,1.],stop_mult=[1.5,2.,2.5]),'app/strategies.py (+ app/more_indicators.py; app/param_grids.py)',STOPNOTE+'; original 1h unavailable: preserve 21/14/25-bar counts on supplied timeframe')
_register('range_native',partial(protected,rule='range'),dict(entry_band=[.1,.2,.3],exit_band=[.4,.5,.6],stop_mult=[1.,1.5,2.]),'app/extra_strategies.py (+ app/extra_indicators.py; app/param_grids.py)',STOPNOTE)
NOT_REPRODUCED={
 'a_opening_range_breakout':'not_reproducible: catalog #91 requires minute opening-range data and a session definition absent from D',
 'a_nr7_opening_range':'not_reproducible: catalog #98 requires minute opening-range data absent from D',
 'a_advanced_drawdown_protection':'not_reproducible: exits depend on simulated portfolio equity, which the pure signal interface excludes',
 'a_advanced_regime_switch':'not_reproducible: optional RSI14/SMA200 input columns select different source rules; source does not specify the indicator bank',
 'a_advanced_multitimeframe':'not_reproducible: SUPERTREND/SUPERT_LINE input bank is unspecified; native ADX-filtered Supertrend provided separately',
 'a_advanced_adaptive_sizing':'not_reproducible: input indicator bank unspecified; risk sizing excluded by harness contract',
 'a_advanced_high_quality':'not_reproducible: indicator bank unspecified; its PRICE_MOVE_FACTOR is a tautological same-close check for factor<=1, not a delayed confirmation',
}


def _smoke():
    from app.rs_map_off_data import load_data, CACHE
    from app.rs_final_data import SCRATCH
    from pathlib import Path
    # Refuse an implicit loader cache write: only this new source file is allowed.
    if not Path(CACHE).is_file() or not (Path(SCRATCH)/'rs_final_panel.npz').is_file(): raise RuntimeError('Data cache absent; loader would create another file')
    D=load_data(); nd,n=len(D['days']),len(D['names'])
    # Compile path-dependent kernels before timing numerical family calls.
    tiny=np.ones((3,1)); zero=np.zeros_like(tiny)
    _state(tiny,zero,zero,tiny,1,0.); _hyster(tiny[:,0],tiny[:,0],.03)
    _adaptive(tiny,tiny,np.ones((3,1),dtype=np.int64),1,tiny)
    _aroon(tiny,tiny,2); _psar(tiny,tiny,.02); _super(tiny,tiny.copy(),tiny.copy())
    _line_state(tiny,zero,zero,tiny,False)
    _protect(tiny,zero.astype(bool),zero.astype(bool),tiny,tiny,tiny,0.,1)
    cut=nd//2
    changed=dict(D)
    for key in ('d','b4'):
        changed[key]={k:v.copy() for k,v in D[key].items()}
        for k,v in changed[key].items(): v[(cut+1)*(6 if key=='b4' else 1):] *= 7 if k=='v' else 3
    for name,meta in FAMILIES.items():
        kw={k:v[0] for k,v in meta['grid'].items()}
        size=np.prod([len(v) for v in meta['grid'].values()]); assert size <= 150
        for tf in meta['tfs']:
            start=perf_counter(); p,s=meta['fn'](D,tf,**kw); elapsed=perf_counter()-start
            assert p.shape == s.shape == (nd,n)
            assert np.isin(p[np.isfinite(p)],[-1.,0.,1.]).all()
            assert not np.isinf(p).any() and not np.isinf(s).any()
            if not meta['long_short']: assert (s[np.isfinite(s)] >= 0).all() and not (p == -1).any()
            p2,s2=meta['fn'](changed,tf,**kw)
            assert np.array_equal(p[:cut+1],p2[:cut+1],equal_nan=True),name
            assert np.allclose(s[:cut+1],s2[:cut+1],equal_nan=True,rtol=0,atol=0),name
            assert elapsed < (1 if tf=='1d' else 3),(name,tf,elapsed)
            print(f'{name} {tf} grid={size} long={np.mean(p==1):.5f} seconds={elapsed:.3f}')
        print(' fidelity:',meta['fidelity'])
    print('NOT_REPRODUCED:',NOT_REPRODUCED)


if __name__ == '__main__':
    _smoke()
