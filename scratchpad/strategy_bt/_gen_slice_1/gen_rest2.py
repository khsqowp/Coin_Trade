from snippets import *
import pathlib
OUT = pathlib.Path(__file__).resolve().parent.parent / "plugins" / "slice_1"
def build(sid, doc, snips, body):
    src = f'"""{doc}"""\n' + IMPORTS + "".join(snips) + "\n" + body.strip("\n") + "\n"
    (OUT / f"{sid}.py").write_text(src)

# ---------------------------------------------------------------- 17 Ichimoku long & short
build("c4-ichimoku-long-and-short-strategy", "Ichimoku long & short strategy (cloud-edge stop, risk:reward target, lagging-span exit).", [HHLL, SHIFT, STICKY, FRAME], '''
SPEC_ID = "c4-ichimoku-long-and-short-strategy"
PARAMS = {"disp": 26, "rr": 2.0}
PARAM_GRID = {"disp": [22, 26, 30], "rr": [1.5, 2.0, 2.5]}
TIMEFRAMES = ["1h", "4h"]
SIDES = "both"
IMPLEMENTED_FIELDS = ["entry_long", "entry_short", "exit", "stop_loss", "take_profit", "position_sizing", "filters", "timeframes"]
DEVIATIONS = [
    "Archived conditions are named only (conAbvBase, cloudGreen, ...); definitions taken from the cited Pine source ('Ichimoku Long and Short Strategy.pine'), default exitStrategy='Ichimoku', closeLagBelow/closelagAbove = true. No timeframe claimed: 1h and 4h.",
    "Source quirk reproduced: the `long`/`short` state vars are only cleared by the OPPOSITE entry condition (not by exits), so after a long exits (stop/target/lag) the next long can only occur after a short signal has fired.",
    "Stop = lower (long) / upper (short) cloud edge shifted by `disp` bars; target = open + (open-stop)*rr using the SIGNAL bar's open (source). The harness takes fractions, so both are converted to fractions of the signal-bar CLOSE and applied to the actual next-open fill (levels drift by the open-vs-close gap). Target not above the entry (tp<=0) is dropped.",
    "Lagging-span exit `open < close[disp+1]` (long) / `open > close[disp+1]` (short) uses the signal bar's own open and is filled at the next open. Opposite entry reverses (Pine strategy.entry semantics); reversal fills one bar later (HARNESS_ISSUES.md #1), re-using the cloud levels computed at the signal bar.",
    "Source sizing (10 contracts) replaced by harness fixed notional. Signals suppressed for the first 2*disp+52 bars (cloud lookback).",
]

def signals(df, disp=26, rr=2.0):
    o = df.open.to_numpy(float); h = df.high.to_numpy(float); l = df.low.to_numpy(float); c = df.close.to_numpy(float); n = len(c)
    disp = int(disp)
    don = lambda k: (_hh(h, k) + _ll(l, k)) / 2.0
    conv = don(9); base = don(26); l1 = (conv + base) / 2.0; l2 = don(52)
    l1d = _shift(l1, disp); l2d = _shift(l2, disp); l1dd = _shift(l1, 2 * disp); l2dd = _shift(l2, 2 * disp)
    raw_l = (conv > base) & (l1 > l2) & (o > l1d) & (o > l2d) & (c > l1dd) & (c > l2dd)
    raw_s = (conv < base) & (l2 > l1) & (o < l1d) & (o < l2d) & (c < l1dd) & (c < l2dd)
    raw_l &= np.arange(n) >= 2 * disp + 52; raw_s &= np.arange(n) >= 2 * disp + 52
    cl = np.zeros(n, bool); cs = np.zeros(n, bool)
    lf = sf = False
    for i in range(n):
        a = (not lf) and bool(raw_l[i]); b = (not sf) and bool(raw_s[i])
        if a: lf, sf = True, False; cl[i] = True
        if b: sf, lf = True, False; cs[i] = True
    lag_c = _shift(c, disp + 1)
    lag_exit_l = o < lag_c; lag_exit_s = o > lag_c
    lx = lag_exit_l | cs; sx = lag_exit_s | cl
    le = _sticky(cl, cl, lx); se = _sticky(cs, cs, sx)
    # absolute stop / target levels set at the original signal bar, carried to a sticky repeat bar
    stop_l = np.minimum(l1d, l2d); tgt_l = o + (o - stop_l) * rr
    stop_s = np.maximum(l1d, l2d); tgt_s = o - (stop_s - o) * rr
    sl = np.full(n, np.nan); tl = np.full(n, np.nan)
    for i in range(n):
        j = i if cl[i] or cs[i] else (i - 1 if i > 0 and (cl[i - 1] or cs[i - 1]) else -1)
        if j < 0: continue
        if cl[j] and le[i]:
            sl[i] = (c[i] - stop_l[j]) / c[i]; t = (tgt_l[j] - c[i]) / c[i]; tl[i] = t if t > 0 else np.nan
        elif cs[j] and se[i]:
            sl[i] = (stop_s[j] - c[i]) / c[i]; t = (c[i] - tgt_s[j]) / c[i]; tl[i] = t if t > 0 else np.nan
    # Off-signal bars get the median signal-bar stop/target distances so the harness's random-entry null (which reuses
    # these columns bar-by-bar, HARNESS_ISSUES.md #3) also applies them. Real entries only use signal-bar values.
    # Fill = EXPANDING median of past signal-bar values (causal; a full-sample median would look ahead).
    ent = le | se
    fs = pd.Series(np.where(ent, sl, np.nan)).expanding(min_periods=1).median().to_numpy()
    ft = pd.Series(np.where(ent, tl, np.nan)).expanding(min_periods=1).median().to_numpy()
    sl = np.where(ent, sl, fs); tl = np.where(ent, tl, ft)
    return _frame(df, le, se, lx, sx, stop_pct=sl, tp_pct=tl)
''')

# ---------------------------------------------------------------- 19 Myth busting OSGFC + Supertrend
build("c4-strategy-myth-busting-12-osgfc-supertrend-myn", "MYN Strategy Myth-Busting #12: one-sided Gaussian filter cross + Supertrend confirmation, reversal on filter cross.", [ATR, SUPERTREND, FRAME, STICKY], '''
SPEC_ID = "c4-strategy-myth-busting-12-osgfc-supertrend-myn"
PARAMS = {"smthper": 10, "extrasmthper": 10, "factor": 3.0, "st_atr": 10}
PARAM_GRID = {"extrasmthper": [8, 10, 14], "factor": [2.5, 3.0, 3.5]}
TIMEFRAMES = ["1h", "4h"]
SIDES = "both"
IMPLEMENTED_FIELDS = ["entry_long", "entry_short", "exit", "stop_loss", "take_profit", "position_sizing", "filters", "timeframes"]
DEVIATIONS = [
    "Archived conditions are abstract (longConditionCalc, calcPeriod ...); real logic from the cited Pine source (Strategy Myth-Busting #12 - OSGFC+SuperTrend - [MYN].pine) with all defaults: source=Close, one-sided Gaussian filter on Fibonacci levels with smthper=10 (reduces to a Gaussian-weighted mean of the last 11 closes), then 2-pole Ehlers smoother (extrasmthper=10); goLong = crossover(out, out[1]), goShort = crossunder(out, out[1]); Supertrend(10, factor 3) must agree (direction<0 long / >0 short); ADX filter disabled (default); lookback-validation inputs 0.",
    "Pine `ta.barssince(x) > 0` is NA-false until x has occurred once, so entries only become possible after the first opposite filter cross and the first opposite Supertrend bar have occurred; reproduced via 'seen before' flags.",
    "Exit: opposite filter cross (closeLong = goShort, closeShort = goLong). Stop-loss input default 999% = disabled. Take-profit default is 100% of price with 100% of the position: applied as tp_pct=1.0 (a long doubling closes; for shorts a 100% gain is unreachable). The Kaufman/T3/AMA smoothing options only affect the unused 'HAB' sources and are not implemented.",
    "Reversal on opposite entry fills one bar later (HARNESS_ISSUES.md #1). Sizing = harness fixed notional (source: 10% equity). Signals suppressed for first 60 bars.",
    "No timeframe claimed: 1h and 4h.",
]

def _weights(p):
    lv = []; t1, t2, nxt = 0, 1, 1
    for _ in range(p + 1):
        lv.append(nxt); t1 = t2; t2 = nxt; nxt = t1 + t2
    size = lv[p]
    w = np.array([np.exp(-i * i * 9.0 / ((size + 1) * (size + 1))) if i < size else 0.0 for i in range(p + 1)])
    return w / w.sum()

def _twopole(src, per):
    a1 = np.exp(-1.414 * np.pi / per); b1 = 2 * a1 * np.cos(1.414 * np.pi / per)
    c2 = b1; c3 = -a1 * a1; c1 = 1 - c2 - c3
    f = np.zeros(len(src))
    for i in range(len(src)):
        f[i] = src[i] if i < 3 else c1 * src[i] + c2 * f[i - 1] + c3 * f[i - 2]
    return f

def signals(df, smthper=10, extrasmthper=10, factor=3.0, st_atr=10):
    h = df.high.to_numpy(float); l = df.low.to_numpy(float); c = df.close.to_numpy(float); n = len(c)
    out1 = np.convolve(c, _weights(int(smthper)))[:n]     # nz() of missing history = 0
    out = _twopole(out1, float(extrasmthper))
    go_long = np.zeros(n, bool); go_short = np.zeros(n, bool)
    go_long[2:] = (out[2:] > out[1:-1]) & (out[1:-1] <= out[:-2])
    go_short[2:] = (out[2:] < out[1:-1]) & (out[1:-1] >= out[:-2])
    d, _ = _supertrend(h, l, c, int(st_atr), float(factor)); bull = d < 0; bear = d > 0
    prior = lambda x: np.r_[False, np.maximum.accumulate(x)[:-1]]   # x occurred strictly before this bar
    long_c = go_long & prior(go_short) & bull & prior(bear)
    short_c = go_short & prior(go_long) & bear & prior(bull)
    warm = np.arange(n) >= 60
    long_c &= warm; short_c &= warm
    lx = go_short; sx = go_long
    le = _sticky(long_c, go_long, lx); se = _sticky(short_c, go_short, sx)
    return _frame(df, le, se, lx, sx, tp_pct=np.full(n, 1.0))
''')

# ---------------------------------------------------------------- 21 Turtle
build("c4-turtle-trend-trading-system-racer8", "Turtle system: 55-bar Donchian breakout entries, 20-bar Donchian exits, long/short.", [HHLL, STICKY, FRAME], '''
SPEC_ID = "c4-turtle-trend-trading-system-racer8"
PARAMS = {"n": 55, "e": 20}
PARAM_GRID = {"n": [40, 55, 70], "e": [15, 20, 25]}
TIMEFRAMES = ["1h", "4h"]
SIDES = "both"
IMPLEMENTED_FIELDS = ["entry_long", "entry_short", "exit", "stop_loss", "take_profit", "position_sizing", "filters", "timeframes"]
DEVIATIONS = [
    "Exact rule from the cited Pine source (Turtle Trend Trading System [racer8].pine): long if close > highest(high,n)[1]; short if close < lowest(low,n)[1]; close long if low < lowest(low,e)[1]; close short if high > highest(high,e)[1]. Entries are state-based (re-fired every bar the condition holds while flat, as Pine does).",
    "Exit conditions are evaluated at bar close (Pine default calc-on-close) and filled at the next open (not at the channel level intrabar). Reversal fills one bar later (HARNESS_ISSUES.md #1). No timeframe claimed: 1h and 4h. Source sizing replaced by harness fixed notional.",
]

def signals(df, n=55, e=20):
    h = df.high.to_numpy(float); l = df.low.to_numpy(float); c = df.close.to_numpy(float); N = len(c)
    sh1 = lambda x: np.r_[np.nan, x[:-1]]
    HI = sh1(_hh(h, n)); LO = sh1(_ll(l, n)); hi = sh1(_hh(h, e)); lo = sh1(_ll(l, e))
    ent_l = c > HI; ent_s = c < LO
    lx = l < lo; sx = h > hi
    lxt = lx | ent_s; sxt = sx | ent_l
    return _frame(df, _sticky(ent_l, sxt, lxt), _sticky(ent_s, lxt, sxt), lxt, sxt)
''')

# ---------------------------------------------------------------- 22 Volatility range breakout
build("c4-volatility-range-breakout-strategy-wbburgin", "wbburgin Volatility Range Breakout: breakouts of volatility-weighted bands, exit on cross of band midpoint.", [SMA, HHLL, STICKY, FRAME], '''
SPEC_ID = "c4-volatility-range-breakout-strategy-wbburgin"
PARAMS = {"vm1": 100, "vol_len": 100}
PARAM_GRID = {"vm1": [75, 100, 150], "vol_len": [75, 100, 150]}
TIMEFRAMES = ["1h", "4h"]
SIDES = "both"
IMPLEMENTED_FIELDS = ["entry_long", "entry_short", "exit", "stop_loss", "take_profit", "position_sizing", "filters", "timeframes"]
DEVIATIONS = [
    "Rule from the cited Pine source (Volatility Range Breakout Strategy [wbburgin].pine), defaults: volatility = 2*(HH-LL)/(HH+LL) of close over vol_len; bands = close*(1 +/- volatility); the source's wma(price, len, weight) multiplies by a constant (current-bar) weight in both numerator and denominator, so it is exactly a simple moving average of the band series over vm1 bars -> hb1/lb1 = SMA(bands, vm1); hlavg = mean(hb1, lb1).",
    "Long = crossover(high, hb1); short = crossunder(low, lb1); exits ('Volatility MA' default): long exit crossunder(close, hlavg), short exit crossover(close, hlavg). Opposite entry reverses (one-bar-later fill, HARNESS_ISSUES.md #1).",
    "Source has pyramiding=20 with repeated entry signals adding to the position; harness holds one position (no pyramiding). No timeframe claimed: 1h and 4h.",
]

def signals(df, vm1=100, vol_len=100):
    h = df.high.to_numpy(float); l = df.low.to_numpy(float); c = df.close.to_numpy(float); n = len(c)
    hh = _hh(c, vol_len); ll = _ll(c, vol_len); vol = 2 * (hh - ll) / (hh + ll)
    hb = _sma(c * (1 + vol), vm1); lb = _sma(c * (1 - vol), vm1); mid = (hb + lb) / 2.0
    cx = lambda a, b: np.r_[False, (a[1:] > b[1:]) & (a[:-1] <= b[:-1])]
    up = cx(h, hb); dn = cx(lb, l)                # crossunder(low, lb1)
    lx = cx(mid, c); sx = cx(c, mid)              # crossunder(close, hlavg) ; crossover(close, hlavg)
    lxt = lx | dn; sxt = sx | up
    return _frame(df, _sticky(up, sxt, lxt), _sticky(dn, lxt, sxt), lxt, sxt)
''')

# ---------------------------------------------------------------- 23 Cluc
build("ft_cluc_may2018", "Freqtrade ClucMay72018: oversold below lower Bollinger band, exit above mid band, 1% ROI, -5% stop.", [EMA, FRAME], '''
SPEC_ID = "ft_cluc_may2018"
PARAMS = {"ema_len": 50, "band_factor": 0.985}
PARAM_GRID = {"ema_len": [40, 50, 60], "band_factor": [0.98, 0.985, 0.99]}
TIMEFRAMES = ["1h", "4h"]
SIDES = "long"
IMPLEMENTED_FIELDS = ["entry_long", "entry_short", "exit", "stop_loss", "take_profit", "position_sizing", "filters", "timeframes"]
DEVIATIONS = [
    "Claimed timeframe is 5m, which is not cached: run on 1h and 4h (a 5m-designed strategy on much slower bars; results are not a test of the 5m claim).",
    "Bollinger bands follow the cited source (ClucMay72018.py): window 20, 2 std (pandas ddof=1, as qtpylib) on TYPICAL PRICE (hlc3), not close. Entry: close < EMA(close, ema_len) and close < band_factor*lower and volume < 20*rolling_mean(volume,30).shift(1). Exit: close > middle band. RSI/MACD/ADX columns in the source are unused.",
    "Freqtrade minimal_roi {0: 1%} = take profit +1% (tp_pct=0.01, checked by harness against bar high from the entry bar); stoploss -5% (stop_pct=0.05). Freqtrade ROI/stop fill-price conventions differ slightly from the harness. Long-only.",
]

def signals(df, ema_len=50, band_factor=0.985):
    h = df.high.to_numpy(float); l = df.low.to_numpy(float); c = df.close.to_numpy(float); v = df.volume.to_numpy(float); n = len(c)
    tp = pd.Series((h + l + c) / 3.0)
    mid = tp.rolling(20, min_periods=20).mean(); sd = tp.rolling(20, min_periods=20).std(ddof=1)
    mid = mid.to_numpy(); lower = (mid - 2 * sd.to_numpy())
    vmean = pd.Series(v).rolling(30, min_periods=30).mean().shift(1).to_numpy()
    le = (c < _ema(c, ema_len)) & (c < float(band_factor) * lower) & (v < vmean * 20)
    le &= np.arange(n) >= max(int(ema_len), 30)
    lx = c > mid
    z = np.zeros(n, bool)
    return _frame(df, le, z, lx, z, stop_pct=np.full(n, 0.05), tp_pct=np.full(n, 0.01))
''')

# ---------------------------------------------------------------- 24 Volatility system
build("ft_volatility_system", "Freqtrade VolatilitySystem: stop-and-reverse on close change exceeding 2*ATR(14) of a 3h resample.", [ATR, STICKY, FRAME, TIMES], '''
SPEC_ID = "ft_volatility_system"
PARAMS = {"atr_mult": 2.0, "resample_hours": 3}
PARAM_GRID = {"atr_mult": [1.5, 2.0, 2.5], "resample_hours": [2, 3, 4]}
TIMEFRAMES = ["1h"]
SIDES = "both"
IMPLEMENTED_FIELDS = ["entry_long", "entry_short", "exit", "stop_loss", "take_profit", "filters", "timeframes"]
DEVIATIONS = [
    "Rule from the cited source (VolatilitySystem.py): on a 180-minute resample of the 1h data, atr = ATR(14)*2 and close_change = close.diff(); on the 1h rows enter_long = close_change > atr.shift(1), enter_short = -close_change > atr.shift(1); exit_short = enter_long and exit_long = enter_short (stop-and-reverse). The spec's 'resample lookahead check' is honoured: each 1h row only sees the last 3h bucket that was COMPLETE by that row's open time (like technical.resampled_merge), then shift(1) on 1h rows.",
    "Harness passes RangeIndex frames (HARNESS_ISSUES.md #2): bar timestamps recovered by exact OHLCV matching against the cached parquet.",
    "Resampled ATR uses Wilder ATR(14) via own implementation instead of TA-Lib (tiny seed differences). Buckets with missing bars are dropped.",
    "Source's 50% initial stake + one position-adjustment add and 2x leverage are NOT modelled (harness: one fixed notional). roi (10000%) and stoploss (-100%) are effectively disabled in the source. Reversal fills one bar later (HARNESS_ISSUES.md #1).",
]

def signals(df, atr_mult=2.0, resample_hours=3):
    n = len(df); k = int(resample_hours)
    c = df.close.to_numpy(float); h = df.high.to_numpy(float); l = df.low.to_numpy(float)
    z = np.zeros(n, bool)
    if n < 10: return _frame(df, z, z, z, z)
    ts = _times(df, TIMEFRAMES[0])      # harness passes RangeIndex frames (HARNESS_ISSUES.md #2)
    idx = ts.tz_convert("UTC").tz_localize(None) if ts.tz is not None else ts
    r = pd.DataFrame({"high": h, "low": l, "close": c}, index=idx)
    cnt = r.close.resample(f"{k}h").count()
    b = r.resample(f"{k}h").agg({"high": "max", "low": "min", "close": "last"})
    b = b[cnt.reindex(b.index).to_numpy() == k]
    if len(b) < 20: return _frame(df, z, z, z, z)
    atr_b = _atr(b.high.to_numpy(), b.low.to_numpy(), b.close.to_numpy(), 14) * float(atr_mult)
    chg_b = np.r_[np.nan, np.diff(b.close.to_numpy())]
    ends = (b.index + pd.Timedelta(hours=k)).to_numpy()
    pos = np.searchsorted(ends, idx.to_numpy(), side="right") - 1      # last bucket completed at or before this row's open
    ok = pos >= 0
    atr = np.where(ok, atr_b[np.clip(pos, 0, None)], np.nan); chg = np.where(ok, chg_b[np.clip(pos, 0, None)], np.nan)
    atr_prev = np.r_[np.nan, atr[:-1]]
    el = chg > atr_prev; es = (-chg) > atr_prev
    return _frame(df, _sticky(el, el, es), _sticky(es, es, el), es, el)
''')

# ---------------------------------------------------------------- 25 jesse macd ema
build("jesse_macd_ema", "Jesse MACD+EMA100: long while MACD>signal and close>EMA, exit when both flip.", [EMA, FRAME], '''
SPEC_ID = "jesse_macd_ema"
PARAMS = {"ema": 100, "fast": 12, "slow": 26, "signal": 9}
PARAM_GRID = {"ema": [75, 100, 150], "signal": [7, 9, 11]}
TIMEFRAMES = ["1h"]
SIDES = "long"
IMPLEMENTED_FIELDS = ["entry_long", "entry_short", "exit", "stop_loss", "take_profit", "position_sizing", "filters", "timeframes"]
DEVIATIONS = [
    "Rule from the cited source (jesse example MACD_EMA): should_long = close > EMA(ema) and MACD > signal (state-based, evaluated while flat); liquidate when MACD < signal and close < EMA. Long-only, no stops/targets.",
    "Jesse places a limit order at the current price; harness fills at the next open. All-in sizing replaced by harness fixed notional. EMAs seeded at first close; signals suppressed for the first max(ema, slow+signal) bars.",
]

def signals(df, ema=100, fast=12, slow=26, signal=9):
    c = df.close.to_numpy(float); n = len(c)
    m = _ema(c, fast) - _ema(c, slow); s = _ema(m, signal); e = _ema(c, ema)
    le = (c > e) & (m > s); lx = (c < e) & (m < s)
    le &= np.arange(n) >= max(int(ema), int(slow) + int(signal))
    z = np.zeros(n, bool)
    return _frame(df, le, z, lx, z)
''')

# ---------------------------------------------------------------- 26 jesse tv rsi
build("jesse_tv_rsi", "Jesse TradingView RSI: long on RSI(5) crossing above 35; exit RSI<75 cross or <10 cross; -5% stop, +10% target.", [FRAME], '''
SPEC_ID = "jesse_tv_rsi"
PARAMS = {"rsi": 5, "xparam": 75}
PARAM_GRID = {"rsi": [5, 7, 10], "xparam": [70, 75, 80]}
TIMEFRAMES = ["1h", "4h"]
SIDES = "long"
IMPLEMENTED_FIELDS = ["entry_long", "entry_short", "exit", "stop_loss", "take_profit", "position_sizing", "filters", "timeframes"]
DEVIATIONS = [
    "Rule from the cited source (jesse TradingView_RSI): long when RSI(rsi) crosses above 35 (prev <= 35, now > 35); close when RSI crosses below xparam (prev >= x, now < x) or below 10; stop at 0.95*entry, take profit at 1.10*entry (jesse limit/stop orders, filled by harness stop/tp logic).",
    "Wilder RSI (SMA seed) implemented here; jesse uses TA-Lib RSI. Leverage 3x ignored (harness fixed notional, unleveraged returns). No timeframe claimed (crypto): 1h and 4h. Jesse 'crossed' helper approximated by prev/current comparison.",
]

def _rsi(c, n):
    c = np.asarray(c, float); n = int(n); out = np.full(len(c), np.nan)
    if len(c) <= n: return out
    d = np.diff(c); g = np.maximum(d, 0.0); ls = np.maximum(-d, 0.0)
    ag = g[:n].mean(); al = ls[:n].mean()
    out[n] = 100.0 if al == 0 else 100 - 100 / (1 + ag / al)
    for i in range(n, len(d)):
        ag = (ag * (n - 1) + g[i]) / n; al = (al * (n - 1) + ls[i]) / n
        out[i + 1] = 100.0 if al == 0 else 100 - 100 / (1 + ag / al)
    return out

def signals(df, rsi=5, xparam=75):
    c = df.close.to_numpy(float); n = len(c)
    r = _rsi(c, rsi); p = np.r_[np.nan, r[:-1]]
    le = (p <= 35) & (r > 35)
    lx = ((p >= xparam) & (r < xparam)) | ((p >= 10) & (r < 10))
    z = np.zeros(n, bool)
    return _frame(df, le, z, lx, z, stop_pct=np.full(n, 0.05), tp_pct=np.full(n, 0.10))
''')

# ---------------------------------------------------------------- 27 pk macd trend
build("pk_macd_trend", "paulcpk MACDCrossoverWithTrend: long when MACD<0 crosses above signal with low above EMA100.", [EMA, FRAME], '''
SPEC_ID = "pk_macd_trend"
PARAMS = {"ema": 100, "fast": 12, "slow": 26, "signal": 9}
PARAM_GRID = {"ema": [75, 100, 150], "signal": [7, 9, 11]}
TIMEFRAMES = ["1h"]
SIDES = "long"
IMPLEMENTED_FIELDS = ["entry_long", "entry_short", "exit", "stop_loss", "take_profit", "position_sizing", "filters", "timeframes"]
DEVIATIONS = [
    "Rule from the cited source (MACDCrossoverWithTrend.py): buy = macd<0 and crossed_above(macd, signal) and low>EMA100; sell = crossed_below(macd, 0) or low<EMA100; stoploss -20%. The source's minimal_roi tables are commented out -> no ROI exit (spec text 'see source' therefore means none). Trailing stop disabled in source.",
    "Note the source's sell fires whenever low<EMA100, so a position can be closed on the bar after entry only if low dips under the EMA. MACD via harness-style EMAs (TA-Lib seeds with SMA); signals suppressed for the first max(ema, slow+signal) bars. Long-only; fixed notional.",
]

def signals(df, ema=100, fast=12, slow=26, signal=9):
    c = df.close.to_numpy(float); l = df.low.to_numpy(float); n = len(c)
    m = _ema(c, fast) - _ema(c, slow); s = _ema(m, signal); e = _ema(c, ema)
    pm = np.r_[np.nan, m[:-1]]; ps = np.r_[np.nan, s[:-1]]
    cross_up = (m > s) & (pm <= ps)
    le = (m < 0) & cross_up & (l > e)
    lx = ((m < 0) & (pm >= 0)) | (l < e)
    le &= np.arange(n) >= max(int(ema), int(slow) + int(signal))
    z = np.zeros(n, bool)
    return _frame(df, le, z, lx, z, stop_pct=np.full(n, 0.20))
''')

# ---------------------------------------------------------------- 28 chandelier
build("tv_chandelier_exit", "Chandelier Exit (ATR 22 x 3, close-based extremes) stop-and-reverse on direction flips.", [ATR, HHLL, STICKY, FRAME], '''
SPEC_ID = "tv_chandelier_exit"
PARAMS = {"length": 22, "mult": 3.0}
PARAM_GRID = {"length": [18, 22, 26], "mult": [2.5, 3.0, 3.5]}
TIMEFRAMES = ["1h", "4h"]
SIDES = "both"
IMPLEMENTED_FIELDS = ["entry_long", "entry_short", "exit", "stop_loss", "take_profit", "position_sizing", "filters", "timeframes"]
DEVIATIONS = [
    "Spec is a lossy summary of a TradingView INDICATOR (not a strategy); the TradingView source could not be read here. Implemented the standard Chandelier Exit logic (as in the widely used Pine 'Chandelier Exit' study with useClose=true): longStop = highest(close,L) - mult*ATR(L), shortStop = lowest(close,L) + mult*ATR(L), each ratcheted (longStop only rises while close[1] > longStop[1]; shortStop only falls while close[1] < shortStop[1]); dir = 1 if close > shortStop[1], -1 if close < longStop[1], else unchanged (initial 1). Buy on dir -1->1, sell on 1->-1; stop-and-reverse, i.e. the 'stop' IS the flip so no separate stop.",
    "This signal inference was not verified against the original script; treat as the standard-definition test. ATR = Wilder (Pine ta.atr). Reversal fills one bar later (HARNESS_ISSUES.md #1). No timeframe claimed: 1h and 4h.",
]

def signals(df, length=22, mult=3.0):
    h = df.high.to_numpy(float); l = df.low.to_numpy(float); c = df.close.to_numpy(float); n = len(c); L = int(length)
    atr = float(mult) * _atr(h, l, c, L)
    ls_raw = _hh(c, L) - atr; ss_raw = _ll(c, L) + atr
    ls = np.full(n, np.nan); ss = np.full(n, np.nan); d = np.ones(n, int)
    for i in range(n):
        if np.isnan(ls_raw[i]) or np.isnan(ss_raw[i]):
            continue
        lp = ls[i - 1] if i > 0 and not np.isnan(ls[i - 1]) else ls_raw[i]
        sp = ss[i - 1] if i > 0 and not np.isnan(ss[i - 1]) else ss_raw[i]
        ls[i] = max(ls_raw[i], lp) if c[i - 1] > lp else ls_raw[i]
        ss[i] = min(ss_raw[i], sp) if c[i - 1] < sp else ss_raw[i]
        prev = d[i - 1] if i > 0 else 1
        d[i] = 1 if c[i] > sp else (-1 if c[i] < lp else prev)
    buy = np.zeros(n, bool); sell = np.zeros(n, bool)
    valid = ~np.isnan(ls) & np.r_[False, ~np.isnan(ls[:-1])]
    buy[1:] = (d[1:] == 1) & (d[:-1] == -1); sell[1:] = (d[1:] == -1) & (d[:-1] == 1)
    buy &= valid; sell &= valid
    return _frame(df, _sticky(buy, buy, sell), _sticky(sell, sell, buy), sell, buy)
''')

# ---------------------------------------------------------------- 29 tv st ema200
build("tv_st_ema200_btc1h", "Bitcoin SuperFlip: Supertrend(10, 1.8) flips filtered by EMA200, reverse on opposite flip.", [EMA, ATR, SUPERTREND, STICKY, FRAME], '''
SPEC_ID = "tv_st_ema200_btc1h"
PARAMS = {"factor": 1.8, "ema_len": 200, "atr_len": 10}
PARAM_GRID = {"factor": [1.5, 1.8, 2.1], "ema_len": [150, 200, 250]}
TIMEFRAMES = ["1h"]
SIDES = "both"
IMPLEMENTED_FIELDS = ["entry_long", "entry_short", "exit", "stop_loss", "take_profit", "position_sizing", "filters", "timeframes"]
DEVIATIONS = [
    "Spec is a lossy summary and the TradingView source was not readable here: implemented from the spec text. Long = Supertrend direction flips bullish AND close > EMA(ema_len); short = flips bearish AND close < EMA. Exit = opposite flip (regardless of the EMA filter). Supertrend per Pine ta.supertrend (hl2, RMA ATR).",
    "Optional ADX(14,14)>20 filter, optional 4% stop and 8% target are OFF by default per spec and are not implemented. Claimed timeframe BTCUSD 1h kept; harness pools the 5 majors. Reversal on an opposite flip that passes the filter fills one bar later (HARNESS_ISSUES.md #1).",
]

def signals(df, factor=1.8, ema_len=200, atr_len=10):
    h = df.high.to_numpy(float); l = df.low.to_numpy(float); c = df.close.to_numpy(float); n = len(c)
    d, _ = _supertrend(h, l, c, int(atr_len), float(factor)); bull = d == -1
    fu = np.zeros(n, bool); fd = np.zeros(n, bool)
    fu[1:] = bull[1:] & ~bull[:-1]; fd[1:] = ~bull[1:] & bull[:-1]
    e = _ema(c, ema_len); warm = np.arange(n) >= int(ema_len)
    le = fu & (c > e) & warm; se = fd & (c < e) & warm
    return _frame(df, _sticky(le, fu, fd), _sticky(se, fd, fu), fd, fu)
''')
print("ok2")
