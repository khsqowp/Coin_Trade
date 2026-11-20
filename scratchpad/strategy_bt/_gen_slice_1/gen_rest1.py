from snippets import *
import pathlib
OUT = pathlib.Path(__file__).resolve().parent.parent / "plugins" / "slice_1"
def build(sid, doc, snips, body):
    src = f'"""{doc}"""\n' + IMPORTS + "".join(snips) + "\n" + body.strip("\n") + "\n"
    (OUT / f"{sid}.py").write_text(src)

# ---------------------------------------------------------------- 8 MACD
build("btc-macd-15-41-12", "BTC daily MACD(15,41,12) signal-line cross, stop-and-reverse.", [EMA, CROSS, STICKY, FRAME], '''
SPEC_ID = "btc-macd-15-41-12"
PARAMS = {"fast": 15, "slow": 41, "signal": 12}
PARAM_GRID = {"fast": [12, 15, 18], "slow": [35, 41, 47]}
TIMEFRAMES = ["1d"]
SIDES = "both"
IMPLEMENTED_FIELDS = ["entry_long", "entry_short", "exit", "stop_loss", "take_profit", "position_sizing", "filters", "timeframes"]
DEVIATIONS = [
    "Spec is BTC only; harness pools BTC/ETH/BNB/SOL/XRP daily bars with the same rule.",
    "MACD = EMA(fast)-EMA(slow) of close, signal = EMA(signal) of MACD; EMAs seeded at the first close (harness convention); signals suppressed for the first slow+signal bars as EMA warm-up (not in spec).",
    "Execution timing unspecified in spec: signal at daily close, fill at next daily open (harness contract).",
    "Always-in reversal: harness cannot fill an exit and the opposite entry on the same open, so the reversal entry fills one bar later (HARNESS_ISSUES.md #1).",
    "Grid axes fast/slow are neighbours of the archived 15/41; signal stays 12.",
]

def signals(df, fast=15, slow=41, signal=12):
    c = df.close.to_numpy(float)
    m = _ema(c, fast) - _ema(c, slow); s = _ema(m, signal)
    up = _crossover(m, s); dn = _crossover(s, m)
    warm = np.arange(len(c)) < int(slow) + int(signal)
    up &= ~warm; dn &= ~warm
    return _frame(df, _sticky(up, up, dn), _sticky(dn, dn, up), dn, up)
''')

# ---------------------------------------------------------------- 9 Supertrend
build("btc-supertrend-3-32", "BTC daily Supertrend(ATR 3, mult 3.2), long-only flip.", [ATR, SUPERTREND, FRAME], '''
SPEC_ID = "btc-supertrend-3-32"
PARAMS = {"atr_len": 3, "mult": 3.2}
PARAM_GRID = {"atr_len": [2, 3, 4], "mult": [2.8, 3.2, 3.6]}
TIMEFRAMES = ["1d"]
SIDES = "long"
IMPLEMENTED_FIELDS = ["entry_long", "entry_short", "exit", "stop_loss", "take_profit", "position_sizing", "filters", "timeframes"]
DEVIATIONS = [
    "Spec is BTC only; harness pools BTC/ETH/BNB/SOL/XRP daily bars.",
    "Spec says source does not identify ATR smoothing, price basis or fill timing: assumed TradingView ta.supertrend defaults (hl2 basis, Wilder/RMA ATR), signal at daily close, fill next open.",
    "'Price crosses above Supertrend line' is implemented as the Supertrend direction flip to bullish (close above the upper band); equivalent to the close crossing the plotted line. Exit on flip to bearish.",
    "Long-only per spec filter ('Long-only implementation stated'); entry_short text in spec is the exit condition only.",
]

def signals(df, atr_len=3, mult=3.2):
    h = df.high.to_numpy(float); l = df.low.to_numpy(float); c = df.close.to_numpy(float)
    d, _ = _supertrend(h, l, c, atr_len, float(mult)); bull = d == -1
    up = np.zeros(len(c), bool); dn = np.zeros(len(c), bool)
    up[1:] = bull[1:] & ~bull[:-1]; dn[1:] = ~bull[1:] & bull[:-1]
    z = np.zeros(len(c), bool)
    return _frame(df, up, z, dn, z)
''')

# ---------------------------------------------------------------- 10 weekend
build("crypto-weekend-gated-7d-momentum", "Weekend-only exposure gated by prior 7-day return sign (daily UTC).", [FRAME, TIMES], '''
SPEC_ID = "crypto-weekend-gated-7d-momentum"
PARAMS = {"lookback": 7}
PARAM_GRID = {"lookback": [7, 10, 14]}
TIMEFRAMES = ["1d"]
SIDES = "both"
IMPLEMENTED_FIELDS = ["entry_long", "entry_short", "exit", "stop_loss", "take_profit", "position_sizing", "filters", "timeframes"]
DEVIATIONS = [
    "Weekend = Saturday+Sunday UTC daily bars (identical to the paper's alternative 'Fri close - Mon open' for UTC daily bars). Position opens at the Saturday open and is closed at the Sunday close via max_hold=1.",
    "'Reassess daily' is NOT implemented: the sign of the prior L-day return (close_Fri / close_Fri-L - 1) is frozen at Friday's close for the whole weekend (a Saturday-close re-evaluation would need a Sunday reversal fill which the harness cannot do at the same open).",
    "Harness passes RangeIndex frames (HARNESS_ISSUES.md #2): bar timestamps recovered by exact OHLCV matching against the cached parquet.",
    "Spec says 'cryptocurrencies'; harness pools BTC/ETH/BNB/SOL/XRP; zero return -> flat; unit notional (sizing unspecified).",
    "Grid lookback [7,10,14]: 7 is default, 14 is the paper's alternative stated in the spec.",
]

def signals(df, lookback=7):
    c = df.close.to_numpy(float); n = len(c); k = int(lookback)
    dow = np.asarray(_times(df, TIMEFRAMES[0]).day_of_week)
    ret = np.full(n, np.nan)
    if n > k: ret[k:] = c[k:] / c[:-k] - 1.0
    fri = dow == 4
    le = fri & (ret > 0); se = fri & (ret < 0)
    mh = np.full(n, 1.0)   # constant on every bar so the harness's random-entry null also gets the weekend exit
    z = np.zeros(n, bool)
    return _frame(df, le, se, z, z, max_hold=mh)
''')

# ---------------------------------------------------------------- 11 Keltner
build("keltner-first-close-20-2", "Keltner EMA20/ATR20 x2 first close outside the band, stop at signal bar extreme, 2R target.", [EMA, ATR, FRAME], '''
SPEC_ID = "keltner-first-close-20-2"
PARAMS = {"ema_len": 20, "mult": 2.0, "atr_len": 20, "rr": 2.0}
PARAM_GRID = {"ema_len": [15, 20, 25], "mult": [1.5, 2.0, 2.5]}
TIMEFRAMES = ["1d"]
SIDES = "both"
IMPLEMENTED_FIELDS = ["entry_long", "entry_short", "exit", "stop_loss", "take_profit", "filters", "timeframes"]
DEVIATIONS = [
    "Spec claims QQQ/BTC examples; harness pools the 5 crypto majors on daily bars.",
    "Bands = EMA(close, ema_len) +/- mult * Wilder ATR(atr_len). 'Previous close inside' = previous close between the bands. First-outside-close entry at the next daily open.",
    "'Close back inside channel' exit implemented as: long exits when close <= upper band; short exits when close >= lower band (signal at close, fill next open).",
    "Stop = signal-bar low (long) / high (short) and target = rr x risk are expressed to the harness as fractions of the signal-bar CLOSE (stop_pct=(close-low)/close, tp_pct=rr*stop_pct) and then applied to the actual next-open fill, so the absolute stop level differs from the signal bar extreme by the open-vs-close gap.",
    "Risk-based position sizing NOT implemented (spec leaves the fraction unspecified): harness fixed notional per trade.",
    "Signals suppressed for the first max(ema_len, atr_len)+1 bars (indicator warm-up).",
]

def signals(df, ema_len=20, mult=2.0, atr_len=20, rr=2.0):
    h = df.high.to_numpy(float); l = df.low.to_numpy(float); c = df.close.to_numpy(float); n = len(c)
    mid = _ema(c, ema_len); a = _atr(h, l, c, atr_len)
    up = mid + mult * a; lo = mid - mult * a
    inside = (c <= up) & (c >= lo)
    prev_inside = np.r_[False, inside[:-1]]
    ok = ~np.isnan(a) & (np.arange(n) > max(int(ema_len), int(atr_len)))
    le = (c > up) & prev_inside & ok
    se = (c < lo) & prev_inside & ok
    lx = c <= up; sx = c >= lo
    sp = np.full(n, np.nan)
    sp[le] = ((c - l) / c)[le]; sp[se] = ((h - c) / c)[se]
    # Off-signal bars get the (causal, expanding) median signal-bar risk so the harness's random-entry null (which reuses these
    # columns bar-by-bar, HARNESS_ISSUES.md #3) also applies a stop and 2R target. Real entries only use signal-bar values.
    # Fill = EXPANDING median of past signal-bar risks (causal; a full-sample median would look ahead).
    ent = le | se
    fill = pd.Series(np.where(ent, sp, np.nan)).expanding(min_periods=1).median().to_numpy()
    sp = np.where(ent, sp, fill)
    return _frame(df, le, se, lx, sx, stop_pct=sp, tp_pct=sp * float(rr))
''')

# ---------------------------------------------------------------- 12 SMA 30/150
build("sma-30-150-always-in", "SMA(30)/SMA(150) always-in trend reversal on daily bars.", [SMA, CROSS, STICKY, FRAME], '''
SPEC_ID = "sma-30-150-always-in"
PARAMS = {"fast": 30, "slow": 150}
PARAM_GRID = {"fast": [20, 30, 40], "slow": [120, 150, 180]}
TIMEFRAMES = ["1d"]
SIDES = "both"
IMPLEMENTED_FIELDS = ["entry_long", "entry_short", "exit", "stop_loss", "take_profit", "position_sizing", "filters", "timeframes"]
DEVIATIONS = [
    "Spec universe is liquid futures; harness pools the 5 crypto majors on daily bars. Execution convention unspecified: signal at daily close, fill at next open.",
    "Position is entered/reversed only AT crossover events (first cross after warm-up); the archived 'always invested while SMA30 > SMA150' state before the first cross is not entered (harness has no start-in-state).",
    "Always-in reversal fills one bar later than the exit (HARNESS_ISSUES.md #1).",
]

def signals(df, fast=30, slow=150):
    c = df.close.to_numpy(float)
    f = _sma(c, fast); s = _sma(c, slow)
    up = _crossover(f, s); dn = _crossover(s, f)
    return _frame(df, _sticky(up, up, dn), _sticky(dn, dn, up), dn, up)
''')

# ---------------------------------------------------------------- 15 ema-supertrend
build("c4-ema-supertrend", "hasnocool 'EMA & Supertrend' Pine strategy: long-only EMA21/55 + EMA233 trend entry, exit on close under EMA55.", [EMA, CROSS, FRAME], '''
SPEC_ID = "c4-ema-supertrend"
PARAMS = {"len1": 21, "len2": 55, "len4": 233}
PARAM_GRID = {"len1": [15, 21, 28], "len2": [45, 55, 70]}
TIMEFRAMES = ["1h", "4h"]
SIDES = "long"
IMPLEMENTED_FIELDS = ["entry_long", "entry_short", "exit", "stop_loss", "take_profit", "position_sizing", "filters", "timeframes"]
DEVIATIONS = [
    "The archived spec text ('time is at least start') is lossy; the real trading rule was taken from the cited Pine source (hasnocool/tradingview-pine-scripts 'EMA & Supertrend.pine'): Enterlong = crossover(ema1,ema2) or (close>ema1 and close>ema2 and ema1>ema2 and close>ema4) [Pine precedence: `and` binds tighter than `or`, so the ema4 filter applies only to the state branch, not the crossover branch]; Exitlong = crossunder(close, ema2). The Supertrend plot in the source is cosmetic and does not enter the trading logic.",
    "Short side is commented out in the source -> long-only. Date window (start 2008) irrelevant to cached data. No timeframe claimed: run on 1h and 4h.",
    "Entry condition is state-based (re-evaluated every bar while flat) as in Pine; sizing = harness fixed notional (source: 100% equity).",
    "Signals suppressed for the first len4 bars as EMA warm-up (EMAs seeded at first close).",
]

def signals(df, len1=21, len2=55, len4=233):
    c = df.close.to_numpy(float); n = len(c)
    e1 = _ema(c, len1); e2 = _ema(c, len2); e4 = _ema(c, len4)
    enter = _crossover(e1, e2) | ((c > e1) & (c > e2) & (e1 > e2) & (c > e4))
    exit_ = _crossover(e2, c)
    enter &= np.arange(n) >= int(len4)
    z = np.zeros(n, bool)
    return _frame(df, enter, z, exit_, z)
''')

# ---------------------------------------------------------------- 16 fukuiz
build("c4-fukuiz-octa-ema-ichimoku-strategy", "Fukuiz Octa-EMA + Ichimoku: long when EMA2>EMA8 and ribbon midpoint above cloud.", [EMA, HHLL, SHIFT, FRAME], '''
SPEC_ID = "c4-fukuiz-octa-ema-ichimoku-strategy"
PARAMS = {"ema2": 11, "ema8": 34}
PARAM_GRID = {"ema2": [8, 11, 14], "ema8": [28, 34, 40]}
TIMEFRAMES = ["1h", "4h"]
SIDES = "long"
IMPLEMENTED_FIELDS = ["entry_long", "entry_short", "exit", "stop_loss", "take_profit", "position_sizing", "filters", "timeframes"]
DEVIATIONS = [
    "Archived text is lossy; rule taken from the cited Pine source ('Fukuiz Octa-EMA + Ichimoku (Strategy).pine'): active orders are buy2 = (EMA2 > EMA8) and fukuiz > SenkouA[26] and fukuiz > SenkouB, exit sell2 = EMA2 < EMA8, where fukuiz = (EMA2+EMA8)/2. The cross-based `buy`/`sell` in the source are unused.",
    "SenkouA = Donchian-mid(52) (as in the source, NOT the usual (Tenkan+Kijun)/2) delayed 26 bars; SenkouB = (Tenkan[26]+Kijun[26])/2 with Tenkan=Donchian-mid(9), Kijun=Donchian-mid(26) (source's own, unconventional, definitions). Donchian uses high/low.",
    "Source date window (2017-01-01..2023-12-31) NOT applied (would remove most of the test period). No timeframe claimed: 1h and 4h. State-based entry re-evaluated every flat bar (Pine behaviour). Long-only. 0.25% commission in source replaced by harness costs.",
    "Signals suppressed for the first 120 bars (Ichimoku 52+26 lookback and EMA warm-up).",
]

def signals(df, ema2=11, ema8=34):
    h = df.high.to_numpy(float); l = df.low.to_numpy(float); c = df.close.to_numpy(float); n = len(c)
    e2 = _ema(c, ema2); e8 = _ema(c, ema8); fk = (e2 + e8) / 2.0
    don = lambda k: (_hh(h, k) + _ll(l, k)) / 2.0
    tenkan = don(9); kijun = don(26); sa = _shift(don(52), 26)
    sb = (_shift(tenkan, 26) + _shift(kijun, 26)) / 2.0
    buy2 = (e2 > e8) & (fk > sa) & (fk > sb) & (np.arange(n) >= 120)
    sell2 = e2 < e8
    z = np.zeros(n, bool)
    return _frame(df, buy2, z, sell2, z)
''')
print("ok")
