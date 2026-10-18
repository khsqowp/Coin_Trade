"""Offline group C signals. No execution, costs, I/O or mutable global data cache.

Source audit: volume_spike_signal_core; mach7_indicators/core/portfolio/sweep;
pullback_rebound_indicators/core; squeeze_indicators/core; strategies/more_indicators;
futures_long_short_probe; round12_signals/research; new_strategy_screening;
pairs_strategies; docs/전략-백테스트-종합.md §§12,39-63 and round8/12/13 JSON.

Daily originals use days*6 on 4h. Native 4h archetypes retain bar periods on
4h (their 1d transfer uses the same bar counts). Stops are frozen at entry
and tested only on closes. Held signals are ignored, not restarted. No
forced terminal liquidation: that would violate prefix invariance. Quote
volume / close is only a proxy for original base-asset volume, explicitly
marked wherever used. Conviction is an indicator score, not a weight.
"""
from __future__ import annotations

from functools import partial
from math import prod
from time import perf_counter

import numpy as np
import pandas as pd


def _bars(D, tf):
    if tf not in ('1d', '4h'):
        raise ValueError(tf)
    return {k: pd.DataFrame(v) for k, v in D['d' if tf == '1d' else 'b4'].items()}


def _scale(tf):
    return 6 if tf == '4h' else 1


def _roll(x, n, op='mean', minimum=None):
    return getattr(x.rolling(int(n), min_periods=int(n) if minimum is None else minimum), op)()


def _ema(x, n, seeded=False):
    if not seeded:
        return x.ewm(span=n, adjust=False).mean()
    # Seed relative to each listing, not the panel's first row. This also
    # works for MACD's signal line, which starts after the slow EMA seed.
    a = x.to_numpy(copy=True)
    for j in range(a.shape[1]):
        valid = np.flatnonzero(np.isfinite(a[:, j]))
        if len(valid) < n:
            a[:, j] = np.nan
            continue
        start = valid[0]
        end = start + n - 1
        seed = np.nanmean(a[start:end+1, j])
        a[:end, j] = np.nan
        a[end, j] = seed
    return pd.DataFrame(a).ewm(span=n, adjust=False).mean()


def _rma(x, n):
    return x.ewm(alpha=1/n, min_periods=n, adjust=True).mean()


def _rsi(c, n, mode='ta'):
    d = c.diff()
    if mode == 'mach7':
        gain = d.where(d > 0, 0.).where(c.notna())
        loss = -d.where(d < 0, 0.).where(c.notna())
        up, down = _ema(gain, n), _ema(loss, n)
    elif mode == 'screen':
        up = d.clip(lower=0).ewm(alpha=1/n, adjust=False).mean()
        down = (-d.clip(upper=0)).ewm(alpha=1/n, adjust=False).mean().replace(0, np.nan)
        return (100 - 100/(1+up/down)).fillna(50).where(c.notna())
    else:
        up, down = _rma(d.clip(lower=0), n), _rma(-d.clip(upper=0), n)
    return 100*up/(up+down)


def _atr(b, n=14):
    c, h, l = b['c'], b['h'], b['l']
    a = np.fmax((h-l).to_numpy(), np.fmax((h-c.shift()).abs().to_numpy(), (l-c.shift()).abs().to_numpy()))
    return _rma(pd.DataFrame(a).where(c.shift().notna() & c.notna()), n)


def _adx(b, n=14, screen=False):
    up, down = b['h'].diff(), -b['l'].diff()
    plus = up.where((up > down) & (up > 0), 0.).where(b['c'].notna())
    minus = down.where((down > up) & (down > 0), 0.).where(b['c'].notna())
    if screen:
        tr = pd.DataFrame(np.fmax((b['h']-b['l']).to_numpy(), np.fmax((b['h']-b['c'].shift()).abs().to_numpy(), (b['l']-b['c'].shift()).abs().to_numpy())))
        smooth = lambda x: x.ewm(alpha=1/n, adjust=False).mean()
        atr = smooth(tr)
    else:
        smooth = lambda x: _rma(x, n)
        atr = _atr(b, n)
    p, m = 100*smooth(plus)/atr, 100*smooth(minus)/atr
    return smooth(100*(p-m).abs()/(p+m).replace(0, np.nan))


def _macd(c, fast=12, slow=26, signal=9):
    line = _ema(c, fast, True)-_ema(c, slow, True)
    sig = _ema(line, signal, True)
    return line, sig, line-sig


def _cross(x, y):
    return (x > y) & (x.shift() <= (y.shift() if isinstance(y, pd.DataFrame) else y))


def _warm(entry, c, bars):
    # Original sources run separate, listing-trimmed frames.
    return entry.where(c.notna().cumsum() > bars, False if entry.dtypes.iloc[0] == bool else 0.)


def _state(c, entry, exit_long=None, exit_short=None, hold=0, stop=None,
           tp=None, cooldown=0, strict=False, reenter=False):
    """Time recursion, vectorised across symbols; inputs and outputs are copied.

    entry is signed. Stops/targets are absolute prices calculated at signal
    close and frozen on entry. Exit branch never flips a held position. Only
    the volume/common portfolio expiry variant may refill after an exit.
    """
    prices = c.to_numpy()
    e = np.asarray(entry, dtype=float)
    shape = prices.shape
    xl = np.zeros(shape, bool) if exit_long is None else np.asarray(exit_long, bool)
    xs = xl if exit_short is None else np.asarray(exit_short, bool)
    st = np.full(shape, np.nan) if stop is None else np.asarray(stop, float)
    target = np.full(shape, np.nan) if tp is None else np.asarray(tp, float)
    out = np.full(shape, np.nan)
    n = shape[1]
    pos = np.zeros(n)
    entered = np.zeros(n, int)
    sl = np.full(n, np.nan)
    take = np.full(n, np.nan)
    wait = np.zeros(n, int)
    for i in range(shape[0]):
        valid = np.isfinite(prices[i])
        held = pos != 0
        long = pos > 0
        if strict:
            risk = np.where(long, prices[i] < sl, prices[i] > sl)
            reward = np.where(long, prices[i] > take, prices[i] < take)
        else:
            risk = np.where(long, prices[i] <= sl, prices[i] >= sl)
            reward = np.where(long, prices[i] >= take, prices[i] <= take)
        expired = (i-entered >= hold) if hold else np.zeros(n, bool)
        leave = valid & held & (np.where(long, xl[i], xs[i]) | risk | reward | expired)
        pos[leave] = 0
        wait[leave] = cooldown
        free = valid & (~held | (leave & reenter))
        cooling = free & (wait > 0)
        wait[cooling] -= 1
        choose = free & ~cooling & np.isfinite(e[i]) & (e[i] != 0)
        if stop is not None:
            choose &= np.isfinite(st[i]) & np.where(e[i] > 0, st[i] < prices[i], st[i] > prices[i])
        pos[choose] = e[i, choose]
        entered[choose] = i
        sl[choose], take[choose] = st[i, choose], target[i, choose]
        out[i, valid] = pos[valid]
    return out


def _finish(D, tf, pos, strength):
    valid = np.isfinite(D['d' if tf == '1d' else 'b4']['c'])
    p = np.where(valid, np.asarray(pos, dtype=np.float64), np.nan)
    s = np.asarray(strength, dtype=np.float64).copy()
    s[~valid | ~np.isfinite(s)] = np.nan
    if tf == '4h':
        p, s = p[5::6], s[5::6]
    return p, s


def _conv(score):
    return score.clip(lower=0)


def _btc_gate(D, tf, window=200):
    c = pd.Series(D['d']['c'][:, D['names'].index('BTC')])
    gate = (c > c.rolling(window).mean()).to_numpy()
    if tf == '4h':
        # The current daily close is unavailable until its final 4h bar.
        old = np.r_[False, gate[:-1]]
        gate4 = np.repeat(old, 6)
        gate4[5::6] = gate
        return gate4
    return gate


def volume_surge(D, tf, volume_multiple=3., price_cap=3., hold_days=20,
                 lookback=20, stop_pct=0., tp_pct=0., regime=0,
                 month_cap=0., positive_rs=0, rs_top_frac=0.):
    b = _bars(D, tf); c = b['c']; q = _scale(tf)
    v = b['v']/c
    ratio = v/_roll(v.shift(), lookback*q)
    entry = (ratio >= volume_multiple) & (c.pct_change(fill_method=None)*100 < price_cap)
    if month_cap:
        entry &= c.pct_change(lookback*q, fill_method=None).abs()*100 <= month_cap
    if regime:
        entry &= _btc_gate(D, tf)[:, None]
    rs = c.pct_change(90*q, fill_method=None)
    if positive_rs:
        entry &= rs > 0
    if rs_top_frac:
        eligible = rs.where(entry)
        cutoff = eligible.quantile(1-rs_top_frac, axis=1)
        entry &= eligible.ge(cutoff, axis=0)
    stop = c*(1-stop_pct) if stop_pct else None
    target = c*(1+tp_pct) if tp_pct else None
    p = _state(c, entry.astype(float), hold=hold_days*q, stop=stop, tp=target, reenter=True)
    return _finish(D, tf, p, _conv(ratio))


def mach7(D, tf, ema_fast=20, ema_slow=100, pullback_window=5,
          risk_reward_ratio=1.5, exit_ema=50, kind='ma'):
    b = _bars(D, tf); c, l = b['c'], b['l']; q = _scale(tf)
    fast, mid, slow = (_ema(c, k*q) for k in (ema_fast, 50, ema_slow))
    stop = _roll(l, pullback_window*q, 'min', 1)
    if kind == 'ma':
        dip = _roll((l <= fast).astype(float), pullback_window*q, 'max', 1) > 0
        entry = (fast > mid) & (mid > slow) & dip & (c > fast) & (c > b['h'].shift())
        exit_ = c < _ema(c, exit_ema*q)
        score = (c-fast)/_atr(b, 14*q)
    elif kind == 'rsi':
        r = _rsi(c, 14*q, 'mach7')
        entry = (_ema(c, 10*q) > _ema(c, 34*q)) & (r >= 55) & (r.shift() < 55)
        exit_ = r < 55
        score = (r-55)/45
    else:
        mean, sd = _roll(c, 20*q), c.rolling(20*q).std(ddof=1)
        upper, lower = mean+2*sd, mean-2*sd
        touched = _roll((c >= upper*.99).astype(float), 10*q, 'max', 1) > 0
        entry, exit_ = touched & (c > stop), c < lower
        score = (c-stop)/_atr(b, 14*q)
    entry &= stop < c
    target = c+(c-stop)*risk_reward_ratio
    return _finish(D, tf, _state(c, entry.astype(float), exit_, stop=stop, tp=target, cooldown=3*q), _conv(score))


def gongdol(D, tf, ma_length=5, volume_filter=0, volume_multiplier=1.5,
            loss_pct=3., profit_pct=6.):
    b = _bars(D, tf); c = b['c']; q = _scale(tf)
    mean = _roll(c, ma_length*q); above = c > mean
    entry = above & ~above.shift(fill_value=False)
    if volume_filter:
        entry &= b['v']/_roll(b['v'], 60*q, minimum=1) >= volume_multiplier
    p = _state(c, entry.astype(float), ~above, stop=c*(1-loss_pct/100),
               tp=c*(1+profit_pct/100), strict=True)
    return _finish(D, tf, p, _conv((c-mean)/_atr(b, 14*q)))


def squeeze(D, tf, threshold=3., recent=10, max_crosses=3):
    b = _bars(D, tf); c = b['c']; q = _scale(tf)
    fast, slow = _roll(c, 20*q), _roll(c, 200*q)
    gap = (fast-slow).abs()/slow*100
    compressed = _roll((gap <= threshold).astype(float), recent*q, 'max', 1) > 0
    aligned = fast > slow
    # Preserve original false->valid comparisons and first-row cross.
    crosses = aligned != aligned.shift()
    chop = _roll(crosses.astype(float), 20*q, 'sum', 1) > max_crosses
    above = c > fast
    entry = above & ~above.shift(fill_value=False) & (c > slow) & compressed & ~chop
    return _finish(D, tf, _state(c, entry.astype(float), ~above), _conv((c-fast)/_atr(b, 14*q)))


def golden_wide(D, tf, fast=9, slow=21, stop_pct=12., ma_type='ema'):
    b = _bars(D, tf); c = b['c']; q = _scale(tf)
    f, s = (_ema(c, fast*q, True), _ema(c, slow*q, True)) if ma_type == 'ema' else (_roll(c, fast*q), _roll(c, slow*q))
    return _finish(D, tf, _state(c, _cross(f, s).astype(float), stop=c*(1-stop_pct/100)), _conv((f-s)/_atr(b, 14*q)))


def rsi2_native(D, tf, period=2, rsi_entry=10., rsi_exit=70., hold_bars=42, stop_atr=1.5):
    b = _bars(D, tf); c = b['c']
    r, atr = _rsi(c, period), _atr(b)
    entry = _warm((r < rsi_entry) & (c > _roll(c, 200)), c, 200)
    exit_ = (c > _roll(c, 5)) | (r > rsi_exit)
    p = _state(c, entry.astype(float), exit_, hold=hold_bars, stop=c-stop_atr*atr)
    return _finish(D, tf, p, _conv((100-r)/100))


def bb_macd_adx(D, tf, adx_min=30., stop_atr=2.5, width=2.):
    b = _bars(D, tf); c = b['c']
    mean, sd = _roll(c, 20), c.rolling(20).std(ddof=0)
    line, sig, _ = _macd(c); adx = _adx(b)
    entry = _warm((adx > adx_min) & (line > sig) & (c <= (mean-width*sd)*1.02), c, 40)
    exit_ = (adx > 70) | (line < sig) | (c > mean+width*sd)
    p = _state(c, entry.astype(float), exit_, stop=c-stop_atr*_atr(b))
    return _finish(D, tf, p, _conv((mean-c)/sd))


def bollinger(D, tf, window=20, width=2., kind='reversion', stop_atr=2., adx_min=25.):
    b = _bars(D, tf); c = b['c']; q = _scale(tf)
    mean = _roll(c, window*q)
    sd = c.rolling(window*q).std(ddof=0 if kind == 'breakout' else 1)
    z = (c-mean)/sd
    if kind == 'breakout':
        entry = _warm(z > width, c, 30*q)
        p = _state(c, entry.astype(float), c < mean, stop=c-stop_atr*_atr(b, 14*q))
        score = _conv(z)
    else:
        # Catalog sources are direction/event series, not midpoint-exit trades.
        sign = -1 if kind == 'reversion' else 1
        p = (z > width).astype(float)*sign-(z < -width).astype(float)*sign
        if kind == 'riding':
            p *= (_adx(b, 14*q, True) > adx_min)
        score = sign*z
    return _finish(D, tf, p, score)


def macd_native(D, tf, fast=12, slow=26, signal=9, min_adx=15., stop_atr=2.):
    b = _bars(D, tf); c = b['c']; q = _scale(tf)
    line, sig, hist = _macd(c, fast*q, slow*q, signal*q)
    # Source assigns pandas-ta iloc[:,1] (HIST) to MACD_SIGNAL and
    # iloc[:,2] (SIGNAL) to MACD_HIST. Replicate the executable swap.
    trigger = sig
    up, down = _cross(trigger, 0), _cross(-trigger, 0)
    adx, atr, mean = _adx(b, 14*q), _atr(b, 14*q), _roll(c, 200*q)
    long = up & (adx >= min_adx) & (c > mean)
    short = down & (adx >= min_adx) & ~(c > mean)
    entry = _warm(long.astype(float)-short.astype(float), c, 35*q)
    stop = c- np.sign(entry)*stop_atr*atr
    p = _state(c, entry, down, up, stop=stop)
    return _finish(D, tf, p, trigger/atr)


def rsi_recovery(D, tf, period=14, threshold=30., hold_days=10,
                 stop_pct=0., tp_pct=0.):
    b = _bars(D, tf); c = b['c']; q = _scale(tf)
    r = _rsi(c, period*q)
    entry = (r >= threshold) & (r.shift() < threshold)
    p = _state(c, entry.astype(float), hold=hold_days*q,
               stop=c*(1-stop_pct) if stop_pct else None,
               tp=c*(1+tp_pct) if tp_pct else None, reenter=True)
    return _finish(D, tf, p, _conv((100-r)/100))


def rsi_catalog(D, tf, period=2, threshold=10.):
    b = _bars(D, tf); c = b['c']; q = _scale(tf)
    r, mean = _rsi(c, period*q, 'screen'), _roll(c, 200*q)
    p = ((c > mean) & (r < threshold)).astype(float)-((c < mean) & (r > 100-threshold)).astype(float)
    return _finish(D, tf, p, (50-r)/50)


def reversal(D, tf, lookback=5, quantile=.2):
    c = _bars(D, tf)['c']; score = -c.pct_change(lookback*_scale(tf), fill_method=None)
    a = score.to_numpy(); valid = np.isfinite(a)
    n = valid.sum(axis=1); counts = np.maximum(1, (n*quantile).astype(int))
    # Stable ordering matches sorted(dict) tie-breaking in original universe order.
    order = np.argsort(np.where(valid, a, np.inf), axis=1, kind='stable')
    rank = np.empty_like(order)
    np.put_along_axis(rank, order, np.broadcast_to(np.arange(a.shape[1]), a.shape), axis=1)
    p = np.where(rank < counts[:, None], -1., np.where(rank >= (n-counts)[:, None], 1., 0.))
    p[~valid | (n[:, None] < 10)] = 0
    return _finish(D, tf, p, score)


def seasonality(D, tf, history=4):
    c = _bars(D, tf)['c']; ret = c.pct_change(fill_method=None)
    days = D['days'] if tf == '1d' else D['days'].repeat(6)
    out = np.full(c.shape, np.nan)
    for month in range(1, 13):
        ids = np.flatnonzero(days.month == month)
        out[ids] = ret.iloc[ids].shift().rolling(history).mean().to_numpy()
    return _finish(D, tf, np.sign(np.nan_to_num(out)), out)


def _residual(D, tf, beta_window=90, minimum=60, lag=True):
    c = _bars(D, tf)['c']; q = _scale(tf)
    r = c.pct_change(fill_method=None); market = r.iloc[:, D['names'].index('BTC')]
    beta = r.rolling(beta_window*q, min_periods=minimum*q).cov(market).div(market.rolling(beta_window*q, min_periods=minimum*q).var().replace(0, np.nan), axis=0)
    return r-(beta.shift() if lag else beta).mul(market, axis=0)


def pairs_residual(D, tf, lookback=60, entry_z=2., exit_z=.5, stop_z=3.5, beta_window=60):
    c = _bars(D, tf)['c']; q = _scale(tf)
    residual = _residual(D, tf, beta_window, beta_window, False)
    spread = _roll(residual, 20*q, 'sum')
    z = (spread-_roll(spread, lookback*q))/spread.rolling(lookback*q).std()
    e = (z <= -entry_z).astype(float)-(z >= entry_z).astype(float)
    p = _state(c, e, (z >= -exit_z) | (z <= -stop_z), (z <= exit_z) | (z >= stop_z))
    # BTC is its own benchmark; neither conviction nor trading is defined.
    j = D['names'].index('BTC'); p[:, j] = 0.; z.iloc[:, j] = np.nan
    return _finish(D, tf, p, -z)


def research_event(D, tf, kind='rsi2', hold_days=20, rsi_entry=10., adx_min=30.,
                   lookback=55, calendar='none', volume_confirm=0, self_trend=0,
                   btc_trend=0):
    """Round12 entry families with their researched fixed-expiry exits."""
    b = _bars(D, tf); c, h, l = b['c'], b['h'], b['l']; q = _scale(tf)
    v = b['v']/c
    ratio = v/_roll(v.shift(), 20*q, 'median')
    sma50, sma200 = _roll(c, 50*q), _roll(c, 200*q)
    warmup = 0
    if kind == 'rsi2':
        r = _rsi(c, 2*q); entry = (r < rsi_entry) & (c > sma200); score = (100-r)/100; warmup = 200*q
    elif kind == 'bb_macd_adx':
        mean, sd = _roll(c, 20*q), c.rolling(20*q).std(ddof=0)
        line, sig, _ = _macd(c, 12*q, 26*q, 9*q)
        entry = (_adx(b, 14*q) > adx_min) & (line > sig) & (c <= (mean-2*sd)*1.02)
        score = (mean-c)/sd; warmup = 40*q
    elif kind == 'rebound':
        above = c > _roll(c, 5*q); entry = above & ~above.shift(fill_value=False); score = (c-_roll(c, 5*q))/_atr(b, 14*q)
    elif kind == 'mach7':
        f, m, s = (_ema(c, k*q) for k in (10, 50, 200))
        dipped = _roll((l <= f).astype(float), 10*q, 'max', 1) > 0
        entry = (f > m) & (m > s) & dipped & (c > f) & (c > h.shift()); score = (c-f)/_atr(b, 14*q); warmup = 200*q
    elif kind == 'squeeze':
        f, s = _roll(c, 20*q), sma200; above = c > f; aligned = f > s
        compressed = _roll(((f-s).abs()/s*100 <= 3).astype(float), 10*q, 'max', 1) > 0
        chop = _roll((aligned != aligned.shift()).astype(float), 20*q, 'sum', 1) > 3
        entry = above & ~above.shift(fill_value=False) & (c > s) & compressed & ~chop; score = (c-f)/_atr(b, 14*q)
    elif kind == 'obv':
        obv = (np.sign(c.diff()).fillna(0)*v).cumsum()
        upper = _roll(obv.shift(), lookback*q, 'max')
        entry = (obv > upper) & (c > sma50) & (c > _roll(h.shift(), 20*q, 'max'))
        score = (obv-upper)/_roll(v.shift(), 20*q)
    elif kind == 'dry':
        dry = (v < _roll(v.shift(), 20*q)*.6) & (c < _roll(c, 10*q))
        prior = _roll(dry.astype(float).shift(), 5*q, 'max') > 0
        entry = prior & (c > h.shift()) & (c > sma50) & (v > v.shift()); score = ratio
    elif kind == 'compression':
        width = 4*c.rolling(20*q).std(ddof=0)/_roll(c, 20*q)
        threshold = width.shift().rolling(120*q, min_periods=60*q).quantile(.25)
        compressed = _roll((width < threshold).astype(float), 10*q, 'max', 1) > 0
        entry = compressed & (c > _roll(h.shift(), 20*q, 'max')) & (c > sma50)
        score = (c-_roll(h.shift(), 20*q, 'max'))/_atr(b, 14*q)
    elif kind == 'residual':
        resid = _residual(D, tf)
        past = _roll(resid.shift(), 5*q, 'sum')
        threshold = resid.shift().rolling(60*q).std()*np.sqrt(5*q)
        entry = (past < -threshold) & (resid > 0) & (c > c.shift()) & (c > sma200)
        score = -past/threshold
    elif kind == 'ma_pullback':
        r = _rsi(c, 14*q); entry = (c > sma50) & (sma50 > sma200) & (r < rsi_entry)
        score = (100-r)/100; warmup = 210*q
    elif kind == 'range':
        upper, lower = _roll(h, 30*q, 'max'), _roll(l, 30*q, 'min')
        score = (upper-c)/(upper-lower)
        entry = (upper > lower) & (c <= lower+.2*(upper-lower)); warmup = 35*q
    else:
        raise ValueError(kind)
    entry = _warm(entry, c, warmup)
    if volume_confirm:
        entry &= ratio >= 1.5
    if self_trend:
        entry &= c > sma200
    if btc_trend:
        entry &= _btc_gate(D, tf)[:, None]
    days = D['days']+pd.Timedelta(days=1)  # original tomorrow calendar gate
    if calendar != 'none':
        gate = (days.weekday < 5) if calendar == 'weekdays' else ((days.day <= 5) | (days.day >= 25))
        entry &= (np.repeat(gate, 6) if tf == '4h' else np.asarray(gate))[:, None]
    p = _state(c, entry.astype(float), hold=hold_days*q, reenter=True)
    return _finish(D, tf, p, _conv(score))


def connors_pullback(D, tf, rsi_period=3, rank_period=100, threshold=20.):
    b = _bars(D, tf); c = b['c']; q = _scale(tf)
    delta = c.diff().to_numpy(); streak = np.zeros_like(delta)
    for i in range(1, len(delta)):
        up, down = delta[i] > 0, delta[i] < 0
        streak[i] = np.where(up, np.where(streak[i-1] > 0, streak[i-1]+1, 1),
                             np.where(down, np.where(streak[i-1] < 0, streak[i-1]-1, -1), 0))
    crsi = (_rsi(c, rsi_period*q, 'screen') + _rsi(pd.DataFrame(streak), 2*q, 'screen') +
            c.pct_change(fill_method=None).rolling(rank_period*q).rank(pct=True)*100)/3
    mean = _roll(c, 200*q)
    pos = ((c > mean) & (crsi < threshold)).astype(float)-((c < mean) & (crsi > 100-threshold)).astype(float)
    return _finish(D, tf, pos, (50-crsi)/50)


def rsi_long_short(D, tf, period=14, threshold=30., hold_days=20, stop_atr=2.):
    b = _bars(D, tf); c = b['c']; q = _scale(tf)
    r, atr, mean = _rsi(c, period*q), _atr(b, 14*q), _roll(c, 200*q)
    entry = ((r < threshold) & (c > mean*.97)).astype(float)-((r > 100-threshold) & (c < mean*1.03)).astype(float)
    entry = _warm(entry, c, 20*q)
    stop = c-np.sign(entry)*stop_atr*atr
    return _finish(D, tf, _state(c, entry, hold=hold_days*q, stop=stop), (50-r)/50)


def mach7_portfolio_rule(D, tf, regime='none', rs_rank=0, exit_mode='trail_ema', stop_mode='swing'):
    b = _bars(D, tf); c = b['c']; q = _scale(tf)
    f, m, s = (_ema(c, k*q) for k in (10, 50, 200))
    dipped = _roll((b['l'] <= f).astype(float), 10*q, 'max', 1) > 0
    entry = (f > m) & (m > s) & dipped & (c > f) & (c > b['h'].shift())
    if regime == 'self_sma200':
        entry &= c > _roll(c, 200*q)
    elif regime == 'btc_sma200':
        entry &= _btc_gate(D, tf)[:, None]
    rs = c.pct_change(90*q, fill_method=None)
    if rs_rank:
        entry &= rs.gt(rs.median(axis=1), axis=0)
    stop = _roll(b['l'], 10*q, 'min', 1) if stop_mode == 'swing' else c*.92
    target = c+2*(c-stop) if exit_mode == 'rr2' else None
    exit_ = c < (f if exit_mode == 'trail_ema' else _ema(c, 50*q))
    return _finish(D, tf, _state(c, entry.astype(float), exit_, stop=stop, tp=target, reenter=True), _conv((c-f)/_atr(b, 14*q)))


FAMILIES = {}


def _register(name, fn, grid, source, fidelity='exact', long_short=False, tfs=('1d', '4h')):
    assert prod(map(len, grid.values())) <= 150
    assert all(2 <= len(axis) <= 6 for axis in grid.values())
    FAMILIES['c_'+name] = dict(fn=fn, grid=grid, tfs=tfs, long_short=long_short,
                              fidelity=fidelity, source=source)


_VOLUME = ('approx: base volume reconstructed as quote volume/close; independent positions '
           'omit TOP_K/cash allocation; close entries replace next-open; no held-signal restart')
_CLOSE = 'approx: original intrabar stops/targets evaluated on closes; no execution shift'
_RESEARCH = ('partial: Round12 entry/expiry adaptation; independent positions omit '
             'TOP_K/cash allocation; close entry replaces next-open; base volume proxy where used')
_register('volume_surge', volume_surge,
          dict(volume_multiple=[2., 3., 4., 5.], price_cap=[1., 2., 3., 5.], hold_days=[5, 10, 20]),
          'app/crypto_volume_spike_sweep.py + app/volume_spike_signal_core.py; docs/전략-백테스트-종합.md §12-3', _VOLUME)
_register('volume_lookback', volume_surge, dict(lookback=[10, 20, 30], hold_days=[10, 20]),
          'app/crypto_volume_spike_sweep.py BONUS', _VOLUME)
_register('volume_tp', volume_surge, dict(lookback=[20, 60], tp_pct=[0., .1, .15, .2, .3]),
          'app/crypto_volume_spike_tp_sweep.py; §12-4', _VOLUME+'; high/low TP replaced by close TP')
_register('volume_stop_regime', partial(volume_surge, hold_days=10),
          dict(stop_pct=[0., .1, .2], regime=[0, 1]),
          'app/crypto_volume_spike_portfolio_backtest.py; §12-2', _VOLUME+'; low stop replaced by close stop')
_register('volume_month_cap', partial(volume_surge, hold_days=10), dict(month_cap=[0., 3., 5.], lookback=[20, 30]),
          'app/crypto_volume_spike_portfolio_backtest.py; §12-2', _VOLUME)
_register('volume_positive_rs', volume_surge, dict(positive_rs=[0, 1], price_cap=[3., 5.]),
          'app/crypto_volume_spike_research_loop.py R06/R15', _VOLUME)
_register('volume_rs_half', volume_surge, dict(rs_top_frac=[.25, .5], price_cap=[3., 5.]),
          'app/crypto_volume_spike_research_loop.py R05', _VOLUME+'; RS quantile over signal candidates includes already-held symbols, unlike portfolio free candidates')
_register('mach7_ma', mach7, dict(ema_fast=[10, 20], ema_slow=[100, 200], pullback_window=[3, 5, 10],
          risk_reward_ratio=[1.5, 2.5], exit_ema=[50, 100]),
          'app/mach7_ma_pullback_sweep.py + app/mach7_backtest_core.py', _CLOSE)
_register('mach7_rsi', partial(mach7, kind='rsi'), dict(pullback_window=[3, 5, 10], risk_reward_ratio=[1.5, 2.5]),
          'app/crypto_mach7_backtest.py + app/mach7_indicators.py', _CLOSE)
_register('mach7_bb', partial(mach7, kind='bb'), dict(pullback_window=[3, 5, 10], risk_reward_ratio=[1.5, 2.5]),
          'app/crypto_mach7_backtest.py + app/mach7_indicators.py', _CLOSE)
_register('gongdol', gongdol, dict(ma_length=[5, 10], volume_filter=[0, 1], volume_multiplier=[1., 1.5, 2.]),
          'app/crypto_pullback_rebound_backtest.py + app/pullback_rebound_backtest_core.py',
          'approx: filtered variant uses provided quote turnover instead of base Volume*Close; unfiltered rule exact')
_register('squeeze_200_20', squeeze, dict(threshold=[2., 3., 4.], recent=[5, 10, 15], max_crosses=[2, 3, 4]),
          'app/crypto_squeeze_backtest.py + app/squeeze_indicators.py + app/squeeze_backtest_core.py')
_register('trx_ema_wide', golden_wide, dict(fast=[7, 9, 12], slow=[18, 21, 26], stop_pct=[8., 12., 16.]),
          'app/trx_buy_hold_wide_stop_backtest.py + app/more_indicators.py',
          'exact', tfs=('1d', '4h'))
_register('rsi2_native', rsi2_native, dict(period=[2, 3], rsi_entry=[5., 10., 15.], rsi_exit=[65., 70., 75.], hold_bars=[30, 42]),
          'app/strategies.py Rsi2MeanReversionStrategy + app/more_indicators.py', _CLOSE+'; native 4h periods retained; 1d is bar-count transfer')
_register('bb_macd_adx_native', bb_macd_adx, dict(adx_min=[20., 30., 40.], width=[1.5, 2., 2.5], stop_atr=[2., 2.5, 3.]),
          'app/strategies.py BollingerMacdStrategy + app/more_indicators.py', _CLOSE+'; native 4h periods retained; 1d is bar-count transfer')
_register('bollinger_reversion', bollinger, dict(window=[15, 20, 30], width=[1.5, 2., 2.5]),
          'app/new_strategy_screening.py bollinger_reversion; docs/신규전략100-카탈로그.md #99',
          'partial: exact catalog direction states; original event study has overlapping horizons, no unique held trade state', True)
_register('bollinger_riding', partial(bollinger, kind='riding'), dict(window=[15, 20, 30], width=[1.5, 2., 2.5], adx_min=[20., 25., 30.]),
          'app/new_strategy_screening.py bollinger_trend; catalog #100',
          'partial: exact catalog direction states; event horizons not collapsed into invented exit', True)
_register('bollinger_breakout', partial(bollinger, kind='breakout'), dict(window=[15, 20, 30], width=[1.5, 2., 2.5], stop_atr=[1.5, 2., 2.5]),
          'app/broad_strategies.py BollingerBreakoutStrategy', _CLOSE)
_register('macd_long_short', macd_native, dict(fast=[10, 12, 14], slow=[24, 26, 30], signal=[7, 9, 11], min_adx=[10., 15., 20.]),
          'app/futures_macd_full_universe.py + app/futures_long_short_probe.py MacdLongShortStrategy',
          _CLOSE+'; preserves executable pandas-ta histogram/signal column swap; source full-universe runner uses daily bars, scaled x6 on 4h', True)
_register('rsi14_recovery', rsi_recovery, dict(period=[3, 14], threshold=[25., 30., 35.], hold_days=[5, 10, 20, 40], stop_pct=[0., .1]),
          'app/crypto_rsi_portfolio_backtest.py + app/technical_signal_common.py; docs/round8-results-2026-10-07.json',
          'partial: recovery trigger exact; close entry/stop and independent fixed-hold state omit portfolio slots')
_register('rsi2_catalog', rsi_catalog, dict(period=[2, 3], threshold=[5., 10., 15.]),
          'app/new_strategy_screening.py rsi2_pullback + app/strategy_screen_core.py',
          'partial: exact screening direction state; event horizons have no unique native exit', True)
_register('short_term_reversal', reversal, dict(lookback=[3, 5, 10], quantile=[.1, .2, .3]),
          'app/new_strategy_screening.py cs_reversal/_rank_panel; catalog #7',
          'partial: exact cross-sectional direction state; original is an overlapping event study', True)
_register('seasonality_month', seasonality, dict(history=[3, 4, 6]),
          'app/new_strategy_screening.py seasonality_month; catalog #23',
          'partial: exact grouped prior same-calendar-month bar-return direction, not historical whole-month performance; event study has no held exit', True)
_register('pairs_residual_btc', pairs_residual, dict(lookback=[40, 60, 120], entry_z=[1.5, 2., 2.5], exit_z=[.25, .5], stop_z=[3., 3.5]),
          'app/pairs_strategies.py + app/new_strategy_screening.py beta_relative_value',
          'approx: single-leg residual proxy; no real pair legs; 60-bar rolling-beta return residual summed over 20 bars replaces synthetic pair ratio; original z entry/exit/stop retained', True)
for _kind in ('mach7', 'squeeze', 'rebound', 'rsi2', 'bb_macd_adx', 'obv', 'dry', 'compression', 'residual', 'ma_pullback', 'range'):
    _grid: dict[str, list[int | float]] = dict(hold_days=[10, 20, 30, 40], btc_trend=[0, 1])
    if _kind in ('rsi2', 'ma_pullback'):
        _grid['rsi_entry'] = [5., 10., 15.] if _kind == 'rsi2' else [25., 35., 45.]
    if _kind == 'bb_macd_adx':
        _grid['adx_min'] = [20., 30., 40.]
    if _kind == 'obv':
        _grid['lookback'] = [40, 55, 70]
    _register('round12_'+_kind, partial(research_event, kind=_kind), _grid,
              'app/round12_signals.py + app/crypto_round12_research.py; docs/round12-results-2026-10-07.json §§39-63; round13 OBV hold sweep', _RESEARCH)
for _kind in ('mach7', 'rebound'):
    _register('weekday_'+_kind, partial(research_event, kind=_kind, calendar='weekdays', volume_confirm=1),
              dict(hold_days=[10, 20, 30], calendar=['none', 'weekdays']),
              'app/crypto_round12_research.py §50 weekdays+volume_confirm', _RESEARCH+'; original tomorrow weekday gate retained')
    _register('month_edge_'+_kind, partial(research_event, kind=_kind, calendar='month_edge', self_trend=1),
              dict(hold_days=[10, 20, 30], calendar=['none', 'month_edge']),
              'app/crypto_round12_research.py §50 month_edge+self_trend', _RESEARCH+'; original tomorrow days <=5 or >=25 gate retained')

_register('connors_rsi3', connors_pullback, dict(rsi_period=[2, 3, 4], rank_period=[60, 100, 120], threshold=[15., 20., 25.]),
          'app/new_strategy_screening.py connors_pullback + app/strategy_screen_core.py connors_rsi',
          'partial: exact catalog composite and direction states; event study has no unique held exit', True)
_register('rsi14_long_short', rsi_long_short, dict(period=[3, 14], threshold=[25., 30., 35.], hold_days=[10, 20, 30], stop_atr=[1.5, 2., 2.5]),
          'app/futures_long_short_probe.py RsiMeanReversionStrategy', _CLOSE, True)
_register('mach7_portfolio_rule', mach7_portfolio_rule,
          dict(regime=['none', 'self_sma200', 'btc_sma200'], rs_rank=[0, 1], exit_mode=['trail_ema', 'rr2'], stop_mode=['swing', 'pct']),
          'app/mach7_portfolio_backtest.py', _CLOSE+'; independent states omit top_n/capital slots')

NOT_REPRODUCED = {
    'c_ten_thousand_rule': 'not_reproducible: app/crypto_tenthousand_rule_backtest.py uses 1-minute bars, same-session exit and one entry/day; 1d/4h bars cannot recover minute indicators or intraday path; day-end positions would all be flat',
    'c_pairs_best_partner': 'not_reproducible: new_strategy_screening.pair_zscore chooses BTC/ETH/SOL/BNB partner by full-sample average rolling correlation (future leak); replaced by explicitly approximate BTC residual family',
    'c_volume_account_circuit': 'not_reproducible: research_loop R02/R03/R04/R07 circuit depends on account equity/cash/weights; absent from pure per-symbol state interface',
    'c_volume_sizing_topk': 'not_reproducible: R08-R14 inverse-vol/equity allocation and TOP_K/cash fractions are portfolio execution policies, not {-1,0,1} signal definitions',
    'c_mach7_portfolio_allocation': 'not_reproducible: mach7_portfolio_backtest top_n/capital slots differ from independent core; portfolio variants are not claimed reproduced by c_mach7_ma',
    'c_sma_wide_original': 'not_reproducible: inspected TRX wide-stop original uses EMA9/21 only; no independently researched SMA wide-stop rule found, so no invented SMA family registered',
    'c_round12_account_weekly_policies': 'not_reproducible: §§47-48,51,53-56,59-63 ranking/sizing/circuit/weekly-policy combinations are not all represented; registered Round12 families reproduce base entry/expiry and specified BTC/calendar gates only',
    'c_round13_sizing_unions': 'not_reproducible: online completed-trade sizing, monthly/weekly policy combinations and unions with out-of-group trend families require portfolio state; only OBV base rule/hold neighbourhood reproduced',
}


def _smoke():
    from pathlib import Path
    from app.rs_map_off_data import load_data, CACHE
    from app.rs_final_data import SCRATCH
    # load_data's cache-miss path writes files. Refuse it under this task's
    # single-new-file restriction, rather than silently generating a cache.
    if not Path(CACHE).is_file() or not (Path(SCRATCH)/'rs_final_panel.npz').is_file():
        raise RuntimeError('Existing offline caches required; cache generation prohibited')
    D = load_data()
    expected = (len(D['days']), len(D['names']))
    for name, meta in FAMILIES.items():
        params = {k: v[0] for k, v in meta['grid'].items()}
        for tf in meta['tfs']:
            start = perf_counter()
            p, s = meta['fn'](D, tf, **params)
            elapsed = perf_counter()-start
            assert p.shape == s.shape == expected, name
            assert p.dtype == s.dtype == np.float64, name
            assert np.all(np.isnan(p) | np.isin(p, [-1., 0., 1.])), name
            assert not np.isinf(s).any(), name
            if not meta['long_short']:
                assert not (p == -1).any(), name
                assert np.all(np.isnan(s) | (s >= 0)), name
            limit = 1. if tf == '1d' else 3.
            assert elapsed < limit, (name, tf, elapsed)
            print(f'{name:30s} {tf} grid={prod(map(len, meta["grid"].values())):3d} long={np.mean(p == 1):.5f} time={elapsed:.3f}s')
    print(f'FAMILIES={len(FAMILIES)} GRID_TOTAL={sum(prod(map(len, m["grid"].values())) for m in FAMILIES.values())}')
    for name, meta in FAMILIES.items():
        print(name, meta['fidelity'])
    for name, reason in NOT_REPRODUCED.items():
        print(name, reason)


if __name__ == '__main__':
    _smoke()
