"""Stocks (daily/weekly) TREND FOLLOWING, SMA200 family (library card ct-donchian70-sma200 / classic 200-day filter).
Entry: close>SMA200 and SMA50>SMA200 and weekly trend (SMA26w rising) confirmed. Exit: close < 0.97*SMA200 or crash stop
(close < highest close since entry * 0.80, protective). Long holding periods are allowed (kr_equity / us_equity)."""
import numpy as np
from tp import ind, poolkit as pk

META = {"id": "stock_trend_sma200", "family": "stock_trend", "market": "stocks", "profile": "kr_equity|us_equity",
        "timeframes": ["1d"], "symbols": ["005930", "000660", "SPY", "QQQ", "AAPL", "MSFT"]}
RULES = {"sma200_entry": "close > SMA200", "sma50_confirm": "SMA50 > SMA200", "weekly_trend_confirm": "weekly SMA26 rising",
         "sma200_band_exit": "exit when close < 0.97*SMA200", "crash_stop_20pct": "exit when close < highest close since entry*0.80"}
PROTECTIVE = {"crash_stop_20pct"}
RULE_KINDS = {"sma200_entry": "entry", "sma50_confirm": "filter", "weekly_trend_confirm": "filter", "sma200_band_exit": "exit",
              "crash_stop_20pct": "protective"}


def _wk(d):
    s = ind.sma(d["close"], 26)
    return (s > s.shift(2)).astype(float).where(s.shift(2).notna())


def generate_signals(df, disabled=frozenset()):
    disabled = frozenset(disabled)
    c = df["close"]
    s200, s50 = ind.sma(c, 200), ind.sma(c, 50)
    wk = pk.htf_align(df, 7, _wk) if len(df) > 400 else c * np.nan
    entry = (pk.cond(disabled, "sma200_entry", c > s200) & pk.cond(disabled, "sma50_confirm", s50 > s200)
             & pk.cond(disabled, "weekly_trend_confirm", wk == 1.0)) & pk.b(s200.notna())
    exit_sig = np.zeros(len(df), bool) if "sma200_band_exit" in disabled else pk.b(c < 0.97 * s200)
    sig = pk.position_loop(entry, c.values, ind.atr(df, 14).values, exit_sig,
                           hard_stop_pct=None, trail_mult=None)
    if "crash_stop_20pct" not in disabled:
        sig = _crash_stop(sig, c.values, entry, exit_sig)
    return pk.to_series(sig, df)


def _crash_stop(sig, c, entry, exit_sig):
    """Re-run the state machine adding a 20% drawdown-from-peak stop (kept separate for readability)."""
    n = len(c)
    out = np.zeros(n)
    pos, peak, armed = False, 0.0, True
    for i in range(n):
        exited = False
        if pos:
            peak = max(peak, c[i])
            if exit_sig[i] or c[i] < peak * 0.80:
                pos, exited = False, True
                armed = armed and not (c[i] < peak * 0.80)
        if not entry[i]:
            armed = True
        if (not pos) and (not exited) and entry[i] and armed:
            pos, peak = True, c[i]
        out[i] = 1.0 if pos else 0.0
    return out
