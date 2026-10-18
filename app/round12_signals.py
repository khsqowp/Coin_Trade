"""Daily entry adapters; exits/sizing deliberately belong to the common engine.

Original 4h/1h archetypes are evaluated on the fixed daily cache. This is an
entry-signal rotation experiment, not reproduction of their native exit rules.
No historical narrative REGIME column is used.
"""
import numpy as np
import pandas as pd
from app.technical_signal_common import ta
from app.mach7_indicators import add_mach7_ma_pullback

FAMILIES = ['mach7', 'squeeze', 'rebound', 'supertrend', 'range', 'rsi2',
            'bb_macd_adx', 'donchian', 'dual_thrust', 'ma_pullback', 'gap']
EXTRA_FAMILIES = ['compression_breakout', 'dry_pullback', 'obv_breakout', 'residual_rebound',
                  'cci', 'roc', 'cmf', 'stochastic']


def supertrend_direction(high, low, close, length=10, multiplier=3.):
    """pandas-ta algorithm with explicit forward-only band recursion."""
    mid = (high+low)/2
    upper = (mid+multiplier*ta.atr(high, low, close, length=length)).to_numpy(copy=True)
    lower = (mid-multiplier*ta.atr(high, low, close, length=length)).to_numpy(copy=True)
    c = close.to_numpy()
    direction = np.ones(len(close), dtype=int)
    for i in range(1, len(close)):
        if c[i] > upper[i-1]:
            direction[i] = 1
        elif c[i] < lower[i-1]:
            direction[i] = -1
        else:
            direction[i] = direction[i-1]
            if direction[i] > 0 and lower[i] < lower[i-1]:
                lower[i] = lower[i-1]
            if direction[i] < 0 and upper[i] > upper[i-1]:
                upper[i] = upper[i-1]
    return pd.Series(direction, index=close.index)


def find_signals(frame, family, **params):
    out = frame.copy()
    c, h, l, v = (out[k] for k in ['Close', 'High', 'Low', 'Volume'])
    atr = ta.atr(h, l, c, length=14)
    sma20, sma50, sma200 = (c.rolling(n).mean() for n in [20, 50, 200])
    ratio = v/v.shift(1).rolling(20).median()
    warmup = 0
    if family == 'mach7':
        # Actual portfolio module defaults, rather than core's 20/50/100 defaults.
        enriched = add_mach7_ma_pullback(out, ema_fast=10, ema_mid=50,
                                        ema_slow=200, pullback_window=10)
        signal = enriched.ENTRY_SIGNAL
        warmup = 200
    elif family == 'squeeze':
        above = c > sma20
        compressed = ((sma20-sma200).abs()/sma200*100 <= 3).rolling(10, min_periods=1).max().astype(bool)
        aligned = sma20 > sma200
        choppy = (aligned != aligned.shift(1)).rolling(20, min_periods=1).sum() > 3
        signal = above & ~above.shift(1, fill_value=False) & (c > sma200) & compressed & ~choppy
    elif family == 'rebound':
        above = c > c.rolling(params.get('ma_length', 5)).mean()
        signal = above & ~above.shift(1, fill_value=False)
    elif family == 'supertrend':
        direction = supertrend_direction(h, l, c)
        signal = (direction > 0) & (direction.shift(1) < 0)
        warmup = 30
    elif family == 'range':
        upper, lower = h.rolling(30).max(), l.rolling(30).min()
        signal = (upper > lower) & (c <= lower+.2*(upper-lower))
        warmup = 35
    elif family == 'rsi2':
        signal = (ta.rsi(c, length=2) < params.get('rsi_entry', 10)) & (c > sma200)
        warmup = 200
    elif family == 'bb_macd_adx':
        # Non-TA-Lib pandas-ta BB uses population SD. MACD signal EMA starts
        # at the first valid MACD bar. ADX uses Wilder RMA and directional moves.
        lower = sma20-2*c.rolling(20).std(ddof=0)
        fast = ta.ema(c, length=12) if len(c) >= 12 else pd.Series(np.nan, index=c.index)
        slow = ta.ema(c, length=26) if len(c) >= 26 else pd.Series(np.nan, index=c.index)
        macd = fast-slow
        valid_macd = macd.dropna()
        ms = (ta.ema(valid_macd, length=9).reindex(c.index) if len(valid_macd) >= 9
              else pd.Series(np.nan, index=c.index))
        up, down = h.diff(), -l.diff()
        positive = up.where((up > down) & (up > 0), 0.)
        negative = down.where((down > up) & (down > 0), 0.)
        di_p = 100*ta.rma(positive, length=14)/atr
        di_m = 100*ta.rma(negative, length=14)/atr
        adx = ta.rma(100*(di_p-di_m).abs()/(di_p+di_m), length=14)
        signal = (adx > params.get('adx_min', 30)) & (macd > ms) & (c <= lower*1.02)
        warmup = 40
    elif family == 'donchian':
        signal = (c > h.shift(1).rolling(params.get('lookback', 55)).max()) & (c >= sma200)
        warmup = 210
    elif family == 'dual_thrust':
        hh, lc = h.shift(1).rolling(21).max(), c.shift(1).rolling(21).min()
        hc, ll = c.shift(1).rolling(21).max(), l.shift(1).rolling(21).min()
        width = pd.concat([hh-lc, hc-ll], axis=1).max(axis=1)
        signal = c > out.Open+params.get('k1', .71)*width
        warmup = 25
    elif family == 'ma_pullback':
        signal = (c > sma50) & (sma50 > sma200) & (ta.rsi(c, length=14) < params.get('rsi_entry', 35))
        warmup = 210
    elif family == 'gap':
        # Existing implementation means close-to-close surge, NOT opening gap.
        signal = c.pct_change(fill_method=None) >= params.get('gap', .10)
        warmup = 5
    elif family == 'compression_breakout':
        width = 4*c.rolling(20).std(ddof=0)/sma20
        threshold = width.shift(1).rolling(120, min_periods=60).quantile(.25)
        compressed = (width < threshold).rolling(10, min_periods=1).max().astype(bool)
        signal = compressed & (c > h.shift(1).rolling(20).max()) & (c > sma50)
    elif family == 'dry_pullback':
        # Uptrend, prior low-volume dip, then reclaim prior high on rising volume.
        dry = (v < v.shift(1).rolling(20).mean()*.6) & (c < c.rolling(10).mean())
        signal = dry.shift(1).rolling(5).max().fillna(0).astype(bool) & (c > h.shift(1)) & (c > sma50) & (v > v.shift(1))
    elif family == 'obv_breakout':
        obv = (np.sign(c.diff()).fillna(0)*v).cumsum()
        signal = (obv > obv.shift(1).rolling(55).max()) & (c > sma50) & (c > h.shift(1).rolling(20).max())
    elif family == 'residual_rebound':
        # BTC-relative residual threshold is added by the multi-asset builder.
        signal = (c > c.shift(1)) & (c > sma200)
    elif family == 'cci':
        typical = (h+l+c)/3
        mean = typical.rolling(20).mean()
        mad = typical.rolling(20).apply(lambda x: np.mean(np.abs(x-x.mean())), raw=True)
        cci = (typical-mean)/(.015*mad)
        signal = (cci < -100) & (c > sma200)
        warmup = 205
    elif family == 'roc':
        signal = (c.pct_change(12, fill_method=None) > .05) & (c > sma200)
        warmup = 205
    elif family == 'cmf':
        flow = (2*c-h-l)/(h-l).replace(0, np.nan)*v
        cmf = flow.rolling(20).sum()/v.rolling(20).sum()
        signal = (cmf.shift(1) <= 0) & (cmf > 0) & (c > sma50)
        warmup = 55
    elif family == 'stochastic':
        lower, upper = l.rolling(14).min(), h.rolling(14).max()
        k = (100*(c-lower)/(upper-lower)).rolling(3).mean()
        d = k.rolling(3).mean()
        signal = (k.shift(1) <= d.shift(1)) & (k > d) & (k < 20)
        warmup = 30
    else:
        raise ValueError(family)
    out['SIGNAL'] = signal.fillna(False).astype(bool)
    out.iloc[:warmup, out.columns.get_loc('SIGNAL')] = False
    out['VOL_RATIO'] = ratio.replace([np.inf, -np.inf], 0.).fillna(0.)
    out['ATR14'] = atr
    out['STOP_LEVEL'] = l.shift(1).rolling(20).min()
    return out
