"""Stocks LOW-VOLATILITY / simple QUALITY proxy (daily). Long when 60-day realised volatility is in the lowest 40% of its own
trailing 504-day history, the close is above SMA100 and the drawdown from the 252-day high is shallower than 15% (a
'quality-ish' stability proxy; no fundamentals are available). Exit: close<SMA100*0.97 or 15% peak-drawdown stop (protective)."""
import numpy as np
from tp import ind, poolkit as pk

META = {"id": "stock_lowvol_quality", "family": "lowvol_quality", "market": "stocks", "profile": "kr_equity|us_equity",
        "timeframes": ["1d"], "symbols": ["005930", "000660", "SPY", "QQQ", "AAPL", "MSFT"]}
RULES = {"lowvol_rank": "60d realised vol <= its 40th percentile over 504 days", "above_sma100": "close > SMA100",
         "shallow_drawdown": "drawdown from 252d high < 15%", "sma100_band_exit": "exit when close < 0.97*SMA100",
         "peak_dd_stop_15pct": "exit when close < peak since entry*0.85"}
PROTECTIVE = {"peak_dd_stop_15pct"}
RULE_KINDS = {"lowvol_rank": "entry", "above_sma100": "filter", "shallow_drawdown": "filter", "sma100_band_exit": "exit",
              "peak_dd_stop_15pct": "protective"}


def generate_signals(df, disabled=frozenset()):
    disabled = frozenset(disabled)
    c = df["close"]
    vol = c.pct_change().rolling(60, min_periods=60).std()
    thr = vol.rolling(504, min_periods=504).quantile(0.4)
    s100 = ind.sma(c, 100)
    dd = c / c.rolling(252, min_periods=252).max() - 1.0
    entry = (pk.cond(disabled, "lowvol_rank", vol <= thr) & pk.cond(disabled, "above_sma100", c > s100)
             & pk.cond(disabled, "shallow_drawdown", dd > -0.15)) & pk.b(thr.notna()) & pk.b(dd.notna())
    exit_sig = np.zeros(len(df), bool) if "sma100_band_exit" in disabled else pk.b(c < 0.97 * s100)
    cv, n = c.values, len(c)
    out = np.zeros(n)
    pos, peak, armed = False, 0.0, True
    for i in range(n):
        exited = False
        if pos:
            peak = max(peak, cv[i])
            stop = ("peak_dd_stop_15pct" not in disabled) and cv[i] < peak * 0.85
            if exit_sig[i] or stop:
                pos, exited = False, True
                if stop:
                    armed = False
        if not entry[i]:
            armed = True
        if (not pos) and (not exited) and entry[i] and armed:
            pos, peak = True, cv[i]
        out[i] = 1.0 if pos else 0.0
    return pk.to_series(out, df)
