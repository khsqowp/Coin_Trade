"""Offline Group B chart/ICT signals, with independent close-evaluated positions.

Provenance: technical_signal_common.find and technical_indicator_fallback, the
thin named signal cores, technical_portfolio_engine, volume_spike_signal_core,
round11_portfolio (HA chandelier), liquidation_proximity_signal_core, docs
전략-백테스트-종합.md §§13-38/80 and the technical-ict/hybrid-drawdown/round3/
round8/round11/round16 results JSONs. No original research runner is imported.

Original defaults: HA/FRVP/FVG/OB/EMA/Fibonacci/Elliott hold20, VWAP/sweep hold10;
hybrids hold20. Original coarse exits: none/pct10 SL, none/pct20 TP, hold10/20;
fine exits: atr1/atr2/pct5/structure SL, none/pct30 TP, hold5/40. The 144-point
exit grid contains that union, including the §21 donor settings. Confirmation
adds exactly one bar of close-up confirmation (the confirm_open research rule),
not a shift for execution. Rank/all, portfolio sizing, slot limits, account CB,
CB cooldown/BTC-SMA50 resume and dataset-end liquidation belong to the harness.

Positions enter at the signal close, expire at entry index + hold_days*scale,
and ignore overlapping signals while held; no extension/restart. Time exits
cannot re-enter on that same close (original close-expiry cash was unavailable
at that day's entry allocation). Explicit proximity exits can re-enter if a
fresh entry is also present, matching the original opening-exit ordering.
SL/TP use closes as requested, with SL before TP before expiry. A chandelier
uses the previous completed protection level, then updates from the current
high/ATR for the next bar. No terminal forced exit: that would break prefix
invariance. All periods defined in days scale by six on 4h; immediate candle
patterns (3-candle FVG, OB prior five candles, trailing 3-candle swing) remain
candle patterns. HA recursion and ZigZag percentage reversals are bar-native.

Strength is the original nonnegative event conviction, zero without an entry
instruction, NaN when its indicator or source data is unavailable; it is not a
binary score and does not imply that a still-held position must have a fresh
signal. Original raw volume weights were CCXT OHLCV volume, whereas D supplies
quote USDT volume. No invented conversion to base volume is performed.
Rolling windows require all their bars; gaps invalidate those windows. HA and
ZigZag preserve their last valid recursive state across absent bars. This is an
explicit missing-data extension of originals that required complete OHLCV.

Numba state machines vectorise across the panel inside compiled loops; no
Numba disk cache, global input cache, network, execution model or filesystem
writes. First use includes JIT compilation; smoke timing excludes that warmup.
"""
from __future__ import annotations

from math import prod
from time import perf_counter

import numpy as np
import pandas as pd
from numba import njit


def _bars(D, tf):
    if tf not in ('1d', '4h'):
        raise ValueError("tf must be '1d' or '4h'")
    return D['d' if tf == '1d' else 'b4'], 1 if tf == '1d' else 6


def _shift(a, k=1):
    out = np.full(a.shape, np.nan)
    if k < len(a):
        out[k:] = a[:-k]
    return out


def _roll(a, window, how='mean', minimum=None):
    r = pd.DataFrame(a).rolling(int(window), min_periods=window if minimum is None else minimum)
    return getattr(r, how)().to_numpy()


def _atr(a, period):
    prev = _shift(a['c'])
    tr = np.fmax(a['h']-a['l'], np.fmax(np.abs(a['h']-prev), np.abs(a['l']-prev)))
    # The original sets the first true range of each listed symbol to NaN.
    tr[~np.isfinite(prev) | ~np.isfinite(a['c'])] = np.nan
    return pd.DataFrame(tr).ewm(alpha=1/period, min_periods=period, adjust=True).mean().to_numpy()


def _ema(c, window):
    seed = c.copy()
    means = _roll(c, window)
    for j in range(c.shape[1]):
        valid = np.flatnonzero(np.isfinite(means[:, j]))
        if not len(valid):
            seed[:, j] = np.nan
            continue
        i = valid[0]
        seed[:i, j] = np.nan
        seed[i, j] = means[i, j]
    return pd.DataFrame(seed).ewm(span=window, adjust=False).mean().to_numpy()


@njit(cache=False)
def _ha(o, h, l, c):
    m, n = c.shape
    signal = np.zeros((m, n), np.bool_)
    delta = np.full((m, n), np.nan)
    for j in range(n):
        ho = np.nan
        previous_close = np.nan
        previous_bullish = True
        for i in range(m):
            if not (np.isfinite(o[i,j]) and np.isfinite(h[i,j]) and
                    np.isfinite(l[i,j]) and np.isfinite(c[i,j])):
                continue
            hc = (o[i,j]+h[i,j]+l[i,j]+c[i,j])/4
            ho = (o[i,j]+c[i,j])/2 if not np.isfinite(ho) else (ho+previous_close)/2
            bullish = hc > ho
            signal[i,j] = bullish and not previous_bullish
            delta[i,j] = hc-ho
            previous_close = hc
            previous_bullish = bullish
    return signal, delta


@njit(cache=False)
def _profile(c, typical, v, window, bins):
    """np.histogram-compatible uniform edges, past window excludes today."""
    m, n = c.shape
    signal = np.zeros((m,n), np.bool_)
    score = np.full((m,n), np.nan)
    for j in range(n):
        for i in range(window, m):
            lo, hi = np.inf, -np.inf
            valid = np.isfinite(c[i,j]) and np.isfinite(c[i-1,j])
            for k in range(i-window, i):
                t = typical[k,j]
                if not np.isfinite(t) or not np.isfinite(v[k,j]):
                    valid = False
                    break
                lo, hi = min(lo,t), max(hi,t)
            if not valid:
                continue
            if lo == hi:
                lo -= .5
                hi += .5
            edges = np.linspace(lo, hi, bins+1)
            hist = np.zeros(bins)
            for k in range(i-window, i):
                t = typical[k,j]
                b = int((t-lo)/(hi-lo)*bins)
                b = min(bins-1, max(0,b))
                # Correct floating-point edges exactly as NumPy histogram does.
                if t < edges[b]:
                    b -= 1
                if b < bins-1 and t >= edges[b+1]:
                    b += 1
                hist[b] += v[k,j]
            poc = int(np.argmax(hist))
            below = -1
            for b in range(poc):
                if hist[b] > 0 and hist[b] < .5*hist[poc]:
                    below = b
            score[i,j] = 0.
            if below >= 0:
                level = (edges[poc]+edges[poc+1])/2
                lvn = (edges[below]+edges[below+1])/2
                if lvn <= c[i-1,j] < level and c[i,j] > level:
                    signal[i,j] = True
                    score[i,j] = hist[poc]/max(hist[below],1.)
    return signal, score


@njit(cache=False)
def _zones(o,h,l,c,atr,structure,kind,max_age,ob_warmup):
    m,n = c.shape
    signal = np.zeros((m,n),np.bool_)
    score = np.full((m,n),np.nan)
    stops = structure.copy()
    for j in range(n):
        lows = np.empty(max_age+2)
        highs = np.empty(max_age+2)
        births = np.empty(max_age+2,np.int64)
        size = 0
        for i in range(m):
            if not np.isfinite(c[i,j]):
                continue
            score[i,j] = 0. if np.isfinite(atr[i,j]) else np.nan
            kept = 0
            # Test old zones first; a new zone cannot be tapped on its birth bar.
            for z in range(size):
                low,high,born = lows[z],highs[z],births[z]
                if i-born > max_age or c[i,j] < low:
                    continue
                if l[i,j] <= high and h[i,j] >= low and (kind == 0 or c[i,j] > high):
                    signal[i,j] = True
                    width = (high-low)/atr[i,j] if atr[i,j] > 0 else np.nan
                    if np.isfinite(width):
                        score[i,j] = max(score[i,j],width)
                    # Original last qualifying zone wins the stop; max width wins score.
                    stops[i,j] = low
                else:
                    lows[kept],highs[kept],births[kept] = low,high,born
                    kept += 1
            size = kept
            if kind == 0 and i >= 2 and l[i,j] > h[i-2,j]:
                lows[size],highs[size],births[size] = h[i-2,j],l[i,j],i
                size += 1
            if (kind == 1 and i >= ob_warmup and c[i,j]-o[i,j] > 1.5*atr[i-1,j]
                    and c[i,j] > h[i-1,j]):
                for k in range(i-1,max(-1,i-6),-1):
                    if c[k,j] < o[k,j]:
                        lows[size],highs[size],births[size] = l[k,j],h[k,j],i
                        size += 1
                        break
    return signal,score,stops


@njit(cache=False)
def _waves(c,atr,structure,kind,reversal):
    m,n = c.shape
    signal = np.zeros((m,n),np.bool_)
    score = np.full((m,n),np.nan)
    stops = structure.copy()
    for j in range(n):
        extreme = np.nan
        direction = 0
        types = np.zeros(5,np.int64)
        points = np.zeros(5)
        size = 0
        impulse = False
        tapped = False
        low,high = 0.,0.
        for i in range(m):
            value = c[i,j]
            if not np.isfinite(value):
                continue
            score[i,j] = 0.
            if not np.isfinite(extreme):
                extreme = value
            pivot = 0
            price = 0.
            if direction >= 0:
                if value > extreme:
                    extreme = value
                elif value <= extreme*(1-reversal):
                    pivot,price = 1,extreme
                    direction,extreme = -1,value
            if direction <= 0 and pivot == 0:
                if value < extreme:
                    extreme = value
                elif value >= extreme*(1+reversal):
                    pivot,price = -1,extreme
                    direction,extreme = 1,value
            if pivot:
                if size == 5:
                    for z in range(4):
                        types[z],points[z] = types[z+1],points[z+1]
                    size = 4
                types[size],points[size] = pivot,price
                size += 1
            if kind == 0:
                if (pivot and size == 5 and types[0] == -1 and types[1] == 1 and
                        types[2] == -1 and types[3] == 1 and types[4] == -1):
                    p0,p1,p2,p3,p4 = points
                    if p2 > p0 and p3 > p1 and p4 > p1 and p3-p2 > p1-p0:
                        retr = (p3-p4)/(p3-p2)
                        if .236 <= retr <= .618:
                            signal[i,j] = True
                            score[i,j] = (p3-p2)/(p1-p0)
                            stops[i,j] = p4
            else:
                if pivot and size >= 2 and types[size-2] == -1 and pivot == 1:
                    low,high = points[size-2],price
                    impulse,tapped = True,False
                if impulse:
                    upper = high-.5*(high-low)
                    lower = high-.618*(high-low)
                    if value < high-.786*(high-low):
                        impulse = False
                        continue
                    if lower <= value <= upper:
                        tapped = True
                    elif tapped and value > upper:
                        signal[i,j] = True
                        score[i,j] = (high-low)/atr[i,j] if atr[i,j] > 0 else np.nan
                        stops[i,j] = high-.786*(high-low)
                        impulse = False
    return signal,score,stops


def _technical(D,tf,name):
    """Raw entries, original rank, ATR, frozen-at-entry structural protection."""
    a,scale = _bars(D,tf)
    o,h,l,c,v = (a[k] for k in 'ohlcv')
    atr = _atr(a,14*scale)
    structure = _roll(_shift(l),20*scale,'min')
    prev = _shift(c)
    if name == 'heikin_ashi':
        signal,delta = _ha(o,h,l,c)
        with np.errstate(divide='ignore',invalid='ignore'):
            score = delta/atr
    elif name == 'frvp':
        signal,score = _profile(c,(h+l+c)/3,v,60*scale,24)
    elif name == 'ema_cross':
        fast,slow = _ema(c,9*scale),_ema(c,21*scale)
        signal = (_shift(fast) <= _shift(slow)) & (fast > slow) & (c > _roll(c,200*scale))
        score = (fast/slow-1)*100
    elif name == 'vwap':
        with np.errstate(divide='ignore',invalid='ignore'):
            vw = _roll((h+l+c)/3*v,20*scale,'sum')/_roll(v,20*scale,'sum')
            signal = (prev < _shift(vw)) & (c > vw)
            score = (_shift(vw)-prev)/atr
    elif name == 'liquidity_sweep':
        level = structure
        swept = (l < level) & (l >= level*.95)
        same = swept & (c > level)
        yesterday = _shift(swept.astype(float)) == 1
        next_bar = yesterday & (prev <= _shift(level)) & (c > _shift(level))
        signal = same | next_bar
        with np.errstate(divide='ignore',invalid='ignore'):
            score = np.where(next_bar,(_shift(level)-_shift(l))/atr,(level-l)/atr)
        structure = np.minimum(l,_shift(l))
    elif name in ('fvg','order_block'):
        signal,score,structure = _zones(o,h,l,c,atr,structure,int(name == 'order_block'),60*scale,14*scale)
    elif name in ('fibonacci','elliott_wave'):
        signal,score,structure = _waves(c,atr,structure,int(name == 'fibonacci'),.05)
    else:
        raise ValueError(name)
    return a,scale,signal,score,atr,structure


@njit(cache=False)
def _state(c,h,signal,exit_signal,atr,structure,duration,stop_kind,stop_amount,tp,trailing):
    """Independent symbol books; no dataset-end exit and no held-signal extension."""
    m,n = c.shape
    pos = np.full((m,n),np.nan)
    for j in range(n):
        held = False
        expiry = -1
        price,target,sl,peak = 0.,0.,0.,0.
        for i in range(m):
            close = c[i,j]
            if not np.isfinite(close):
                continue
            allow_entry = True
            if held:
                explicit = exit_signal[i,j]
                stopped = sl > 0 and close <= sl
                profitable = target > 0 and close >= target
                expired = i >= expiry
                if explicit or stopped or profitable or expired:
                    held = False
                    # Only an original opening exit freed a same-bar entry slot.
                    allow_entry = explicit or (stopped and not profitable and not expired)
                elif trailing > 0:
                    peak = max(peak,h[i,j])
                    if np.isfinite(atr[i,j]):
                        sl = max(sl,peak-trailing*atr[i,j])
            if not held and allow_entry and signal[i,j]:
                sl = 0.
                if stop_kind == 1:
                    sl = close*(1-stop_amount)
                elif stop_kind == 2:
                    sl = close-stop_amount*atr[i,j]
                elif stop_kind == 3:
                    sl = structure[i,j]
                if trailing > 0:
                    if not np.isfinite(atr[i,j]) or atr[i,j] <= 0:
                        pos[i,j] = 0.
                        continue
                    sl = max(0.,close-trailing*atr[i,j])
                if (stop_kind != 0 and (not np.isfinite(sl) or sl <= 0)) or sl >= close:
                    pos[i,j] = 0.
                    continue
                held = True
                price = close
                target = price*(1+tp) if tp > 0 else 0.
                expiry = i+duration
                peak = close
                # A close entry cannot use highs that occurred before its entry.
            pos[i,j] = 1. if held else 0.
    return pos


def _position(D,tf,a,scale,signal,score,atr,structure,hold_days,stop,tp,confirmation=0,
              trailing=0.,exit_signal=None):
    if hold_days < 1 or tp < 0 or confirmation not in (0,1):
        raise ValueError('invalid holding/target/confirmation')
    stops = {'none':(0,0.),'pct5':(1,.05),'pct10':(1,.10),
             'atr1':(2,1.),'atr2':(2,2.),'structure':(3,0.)}
    if stop not in stops:
        raise ValueError('unknown stop')
    if confirmation:
        # Original confirm_open checks one extra close against the signal close;
        # retain the SIGNAL-bar ATR and structure, not the confirmation-bar ones.
        signal = (_shift(signal.astype(float)) == 1) & (a['c'] > _shift(a['c']))
        score,structure = _shift(score),_shift(structure)
        entry_atr = _shift(atr)
    else:
        entry_atr = atr
    if exit_signal is None:
        exit_signal = np.zeros(signal.shape,np.bool_)
    kind,amount = stops[stop]
    pos = _state(a['c'],a['h'],signal,exit_signal,entry_atr,structure,
                 int(hold_days*scale),kind,amount,float(tp),float(trailing))
    strength = np.where(signal,np.maximum(score,0.),0.).astype(np.float64)
    strength[~np.isfinite(score)] = np.nan
    strength[~np.isfinite(a['c'])] = np.nan
    if tf == '4h':
        pos,strength = pos[5::6],strength[5::6]
    expected = (len(D['days']),len(D['names']))
    if pos.shape != expected or strength.shape != expected:
        raise ValueError('D calendar/panel shapes disagree')
    return pos,strength


def _family(D,tf,name,hold_days=20,stop='none',tp=0.,confirmation=0):
    a,s,sig,score,atr,structure = _technical(D,tf,name)
    return _position(D,tf,a,s,sig,score,atr,structure,hold_days,stop,tp,confirmation)


def heikin_ashi(D,tf,hold_days=20,stop='none',tp=0.,confirmation=0):
    return _family(D,tf,'heikin_ashi',hold_days,stop,tp,confirmation)


def frvp(D,tf,hold_days=20,stop='none',tp=0.,confirmation=0):
    return _family(D,tf,'frvp',hold_days,stop,tp,confirmation)


def vwap(D,tf,hold_days=10,stop='none',tp=0.,confirmation=0):
    return _family(D,tf,'vwap',hold_days,stop,tp,confirmation)


def fvg(D,tf,hold_days=20,stop='none',tp=0.,confirmation=0):
    return _family(D,tf,'fvg',hold_days,stop,tp,confirmation)


def order_block(D,tf,hold_days=20,stop='none',tp=0.,confirmation=0):
    return _family(D,tf,'order_block',hold_days,stop,tp,confirmation)


def liquidity_sweep(D,tf,hold_days=10,stop='none',tp=0.,confirmation=0):
    return _family(D,tf,'liquidity_sweep',hold_days,stop,tp,confirmation)


def ema_cross(D,tf,hold_days=20,stop='none',tp=0.,confirmation=0):
    return _family(D,tf,'ema_cross',hold_days,stop,tp,confirmation)


def fibonacci(D,tf,hold_days=20,stop='none',tp=0.,confirmation=0):
    return _family(D,tf,'fibonacci',hold_days,stop,tp,confirmation)


def elliott_wave(D,tf,hold_days=20,stop='none',tp=0.,confirmation=0):
    return _family(D,tf,'elliott_wave',hold_days,stop,tp,confirmation)


def _hybrid(D,tf,name,loose=False,hold_days=20,volume_multiple=3.,price_cap=3.,tp=0.):
    a,s,technical,score,atr,structure = _technical(D,tf,name)
    with np.errstate(divide='ignore',invalid='ignore'):
        ratio = a['v']/_roll(_shift(a['v']),20*s)
        # The original price cap is a one-day return, also on the 4h extension.
        change = (a['c']/_shift(a['c'],s)-1)*100
    volume = (ratio >= volume_multiple) & (change < price_cap)
    if loose:
        # Original inclusive rolling(4): today OR previous three bars, never future.
        window = 3*s+1
        signal = (technical & (_roll(volume.astype(float),window,'max',1) == 1)) | (
            volume & (_roll(technical.astype(float),window,'max',1) == 1))
        score = pd.DataFrame(np.where(volume,ratio,np.nan)).ffill(limit=3*s).fillna(0.).to_numpy()
    else:
        signal = technical & volume
        score = ratio
    return _position(D,tf,a,s,signal,score,atr,structure,hold_days,'none',tp)


def heikin_ashi_volume_spike(D,tf,hold_days=20,volume_multiple=3.,price_cap=3.,tp=0.):
    return _hybrid(D,tf,'heikin_ashi',False,hold_days,volume_multiple,price_cap,tp)


def heikin_ashi_volume_spike_loose(D,tf,hold_days=20,volume_multiple=3.,price_cap=3.,tp=0.):
    return _hybrid(D,tf,'heikin_ashi',True,hold_days,volume_multiple,price_cap,tp)


def frvp_volume_spike(D,tf,hold_days=20,volume_multiple=3.,price_cap=3.,tp=0.):
    return _hybrid(D,tf,'frvp',False,hold_days,volume_multiple,price_cap,tp)


def frvp_volume_spike_loose(D,tf,hold_days=20,volume_multiple=3.,price_cap=3.,tp=0.):
    return _hybrid(D,tf,'frvp',True,hold_days,volume_multiple,price_cap,tp)


def heikin_ashi_chandelier(D,tf,trailing=2.,hold_days=10000):
    a,s,signal,score,atr,structure = _technical(D,tf,'heikin_ashi')
    return _position(D,tf,a,s,signal,score,atr,structure,hold_days,'none',0.,trailing=trailing)


@njit(cache=False)
def _clusters(h,l,c,window,tiers):
    """Surviving assumed anchors; equal-weight log bins, nearest proper side."""
    m,n = c.shape
    distances = np.full((m,n,2),np.nan)
    densities = np.zeros((m,n,2))
    width = np.log1p(.005)
    capacity = window*len(tiers)+len(tiers)
    for j in range(n):
        for side in range(2):
            prices = np.empty(capacity)
            born = np.empty(capacity,np.int64)
            size = 0
            for i in range(m):
                if not np.isfinite(c[i,j]):
                    continue
                kept = 0
                for z in range(size):
                    p = prices[z]
                    survived = l[i,j] > p if side == 0 else h[i,j] < p
                    if born[z] >= i-window+1 and survived:
                        prices[kept],born[kept] = p,born[z]
                        kept += 1
                size = kept
                swing = False
                if i >= 2:
                    if side == 0:
                        swing = h[i,j] >= max(h[i-1,j],h[i-2,j]) and np.isfinite(h[i-1,j]) and np.isfinite(h[i-2,j])
                    else:
                        swing = l[i,j] <= min(l[i-1,j],l[i-2,j]) and np.isfinite(l[i-1,j]) and np.isfinite(l[i-2,j])
                if swing:
                    anchor = h[i,j] if side == 0 else l[i,j]
                    for tier in tiers:
                        prices[size] = anchor*(1-.995/tier) if side == 0 else anchor*(1+.995/tier)
                        born[size] = i
                        size += 1
                # Keep summation in original anchor order, preserving mean rounding.
                ids = np.empty(size,np.int64)
                counts = np.zeros(size,np.int64)
                sums = np.zeros(size)
                groups = 0
                for z in range(size):
                    b = int(np.floor(np.log(prices[z])/width))
                    found = -1
                    for g in range(groups):
                        if ids[g] == b:
                            found = g
                            break
                    if found == -1:
                        found = groups
                        ids[groups] = b
                        groups += 1
                    counts[found] += 1
                    sums[found] += prices[z]
                best = np.inf
                best_bin = np.iinfo(np.int64).max
                best_count = 0
                for g in range(groups):
                    direction = -1 if side == 0 else 1
                    dist = direction*(sums[g]/counts[g]/c[i,j]-1)*100
                    if counts[g] >= 2 and dist > 0 and (dist < best or (dist == best and ids[g] < best_bin)):
                        best,best_count,best_bin = dist,counts[g],ids[g]
                if np.isfinite(best):
                    distances[i,j,side] = best
                    densities[i,j,side] = best_count
    return distances,densities


def liquidation_proximity(D,tf,window=14,threshold=2.,tier_set=0,hold_days=20):
    """Round16 A: downside proximity entry, upside proximity exit, time cap."""
    if window not in (7,14,30) or threshold not in (1.,2.,3.,5.) or tier_set not in (0,1):
        raise ValueError('outside original liquidation grid')
    a,s = _bars(D,tf)
    tiers = np.array((5.,10.,20.) if tier_set == 0 else (25.,50.,100.))
    distances,densities = _clusters(a['h'],a['l'],a['c'],window*s,tiers)
    signal = distances[:,:,0] <= threshold
    exits = distances[:,:,1] <= threshold
    score = densities[:,:,0]/(1+distances[:,:,0])
    zero = np.zeros(a['c'].shape)
    return _position(D,tf,a,s,signal,score,zero,zero,hold_days,'none',0.,exit_signal=exits)


# Ordered stop categories follow the research's declared rule order. They are
# categorical neighbours, not a numerical ordering of protective tightness.
_EXIT_GRID = dict(hold_days=[5,10,20,40],
                  stop=['none','pct5','pct10','atr1','atr2','structure'],
                  tp=[0.,.20,.30],confirmation=[0,1])
_HYBRID_GRID = dict(hold_days=[10,20,40],volume_multiple=[2.,3.,4.],
                    price_cap=[2.,3.,5.],tp=[0.,.20,.30])
_ADAPTATION = ('approx: exact original causal entry definitions on supplied bars; '
               'close entry instead of next open, close-only SL/TP instead of intraday fills; '
               'no terminal liquidation or portfolio allocation; 4h is a day-scaled extension; '
               'missing-bar extension uses full rolling windows and skips missing recursive observations')
_VOLUME = '; quote-USDT weights replace original CCXT OHLCV volume, which D cannot reconstruct exactly'


def _record(fn,grid,source,extra=''):
    return dict(fn=fn,grid={k:list(v) for k,v in grid.items()},tfs=('1d','4h'),
                long_short=False,fidelity=_ADAPTATION+extra,source=source)


FAMILIES = {
    'b_heikin_ashi': _record(heikin_ashi,_EXIT_GRID,
        'app/heikin_ashi_signal_core.py + app/technical_signal_common.py; docs §§13,21-22; technical-ict-results-2026-10-06.json'),
    'b_heikin_ashi_volume_spike': _record(heikin_ashi_volume_spike,_HYBRID_GRID,
        'app/heikin_ashi_volume_spike_signal_core.py + app/volume_spike_signal_core.py; docs §14; hybrid-drawdown-results-2026-10-06.json',_VOLUME),
    'b_heikin_ashi_volume_spike_loose': _record(heikin_ashi_volume_spike_loose,_HYBRID_GRID,
        'app/heikin_ashi_volume_spike_loose_signal_core.py; docs §15; round3-results-2026-10-06.json',_VOLUME),
    'b_frvp': _record(frvp,_EXIT_GRID,
        'app/frvp_signal_core.py + app/technical_signal_common.py; docs §§13,21; technical-ict-results-2026-10-06.json',
        '; reproduces original past60/24-bin typical-price histogram proxy, not real volume-at-price'+_VOLUME),
    'b_frvp_volume_spike': _record(frvp_volume_spike,_HYBRID_GRID,
        'app/frvp_volume_spike_signal_core.py; docs §14; hybrid-drawdown-results-2026-10-06.json',
        '; original typical-price profile proxy'+_VOLUME),
    'b_frvp_volume_spike_loose': _record(frvp_volume_spike_loose,_HYBRID_GRID,
        'app/frvp_volume_spike_loose_signal_core.py; docs §15; round3-results-2026-10-06.json',
        '; original typical-price profile proxy'+_VOLUME),
    'b_vwap': _record(vwap,_EXIT_GRID,
        'app/crypto_vwap_portfolio_backtest.py + app/technical_signal_common.py; docs §§13,21; technical-ict-results-2026-10-06.json',_VOLUME),
    'b_fvg': _record(fvg,_EXIT_GRID,
        'app/fvg_signal_core.py + app/technical_signal_common.py; docs §§13,21; technical-ict-results-2026-10-06.json'),
    'b_order_block': _record(order_block,_EXIT_GRID,
        'app/order_block_signal_core.py + app/technical_signal_common.py; docs §13; technical-ict-results-2026-10-06.json'),
    'b_liquidity_sweep': _record(liquidity_sweep,_EXIT_GRID,
        'app/liquidity_sweep_signal_core.py + app/technical_signal_common.py; docs §§13,21; technical-ict-results-2026-10-06.json'),
    'b_ema_cross': _record(ema_cross,_EXIT_GRID,
        'app/ema_cross_signal_core.py + app/technical_indicator_fallback.py; docs §§13,21; technical-ict-results-2026-10-06.json',
        '; research fallback SMA-seeded EMA/RMA, not optional TA-Lib definitions'),
    'b_fibonacci': _record(fibonacci,_EXIT_GRID,
        'app/fibonacci_signal_core.py + app/technical_signal_common.py; docs §§13,21; technical-ict-results-2026-10-06.json'),
    'b_elliott_wave': _record(elliott_wave,_EXIT_GRID,
        'app/elliott_wave_signal_core.py + app/technical_signal_common.py; docs §§13,21; technical-ict-results-2026-10-06.json'),
    'b_heikin_ashi_chandelier': _record(heikin_ashi_chandelier,
        dict(trailing=[2.,2.5,3.],hold_days=[10000,20000]),
        'app/crypto_round11_research.py + app/round11_portfolio.py; docs §34; round11-results-2026-10-07.json',
        '; previous completed high/ATR protection retained; intraday/gap exits converted to closes'),
    'b_liquidation_proximity': _record(liquidation_proximity,
        dict(window=[7,14,30],threshold=[1.,2.,3.,5.],tier_set=[0,1],hold_days=[10,20]),
        'app/liquidation_proximity_signal_core.py + app/crypto_round16_liquidation_research.py; docs §80; round16-results-2026-10-08.json',
        '; exact assumed leverage-anchor cluster definition, not observed liquidations/OI/heatmaps'),
}

NOT_REPRODUCED = {
    'b_tjr_discretionary': 'docs §13 explicitly excludes full TJR discretionary execution; no complete machine rule.',
    'b_ict_session': 'No machine-defined session filter in the original daily ICT research (§13).',
    'b_ict_kill_zone': 'Kill-zone timing was explicitly outside the researched rule definitions (§13).',
    'b_ict_mss': 'No original machine definition of MSS joined to these entries (§13).',
    'b_ict_bos': 'No original machine definition of BOS joined to these entries (§13).',
    'b_bollinger_divergence_intraday': 'app/bollinger_divergence_indicators.py defines 1-minute session rules; D has no 1-minute bars. Daily/4h signals cannot reproduce same-session exits or daily entry limit.',
}


def _smoke():
    """Only read existing data caches; never silently let load_data create files."""
    import os
    from app.rs_map_off_data import load_data, CACHE
    from app.rs_final_data import SCRATCH
    if not (os.path.isfile(CACHE) and os.path.isfile(os.path.join(SCRATCH,'rs_final_panel.npz'))):
        raise RuntimeError('Existing data/panel caches required: smoke must not create extra files')
    D = load_data()
    # Compile the path-dependent kernels on a tiny synthetic panel. Reporting
    # separates compilation cost from the actual real-panel family-call budget.
    tiny = {'names':['BTC'],'days':pd.date_range('2021-01-01',periods=64,tz='UTC')}
    for key,length in (('d',64),('b4',384)):
        x = (100+np.sin(np.arange(length)/3)*10)[:,None]
        tiny[key] = dict(o=x.copy(),h=x+2,l=x-2,c=x.copy(),v=np.full(x.shape,100.))
    started = perf_counter()
    for name in ('b_heikin_ashi','b_frvp','b_fvg','b_order_block','b_fibonacci','b_elliott_wave','b_liquidation_proximity'):
        FAMILIES[name]['fn'](tiny,'1d')
    print(f'JIT warmup {perf_counter()-started:.3f}s (cache=False)')
    total = 0
    for name,meta in FAMILIES.items():
        assert prod(map(len,meta['grid'].values())) <= 150
        assert all(2 <= len(values) <= 6 for values in meta['grid'].values())
        first = {k:v[0] for k,v in meta['grid'].items()}
        for tf in meta['tfs']:
            start = perf_counter()
            pos,strength = meta['fn'](D,tf,**first)
            elapsed = perf_counter()-start
            expected = (len(D['days']),len(D['names']))
            assert pos.shape == strength.shape == expected
            assert pos.dtype == strength.dtype == np.float64
            assert np.isin(pos[np.isfinite(pos)],[-1.,0.,1.]).all()
            assert not np.isinf(pos).any() and not np.isinf(strength).any()
            assert (strength[np.isfinite(strength)] >= 0).all()
            close = D['d']['c'] if tf == '1d' else D['b4']['c'][5::6]
            missing = ~np.isfinite(close)
            assert np.isnan(pos[missing]).all()
            assert np.isnan(strength[missing]).all()
            assert elapsed < (1. if tf == '1d' else 3.), (name,tf,elapsed)
            print(f'{name:37} {tf:2} grid={prod(map(len,meta["grid"].values())):3d} '
                  f'long_fraction={np.mean(pos == 1):.6f} runtime={elapsed:.3f}s')
            total += 1
    print(f'PASS: {len(FAMILIES)} families / {total} real-data calls; '
          f'{sum(prod(map(len,m["grid"].values())) for m in FAMILIES.values())} grid points per timeframe')
    for name,reason in NOT_REPRODUCED.items():
        print('NOT_REPRODUCED',name,reason)


if __name__ == '__main__':
    _smoke()
