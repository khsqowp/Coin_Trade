"""Stocks time-series MOMENTUM (12-1 months, library card ct-momentum-rotation per-symbol form). Long when the 12-month return
skipping the last month is positive and the 3-month return is positive; exit when the 12-1 momentum turns negative or a 15%
peak-drawdown stop (protective). The cross-sectional rotation version lives in tp.pool.rotation_picks."""
import numpy as np
from tp import ind, poolkit as pk

META = {"id": "stock_tsmom", "family": "momentum_rotation", "market": "stocks", "profile": "kr_equity|us_equity",
        "timeframes": ["1d"], "symbols": ["005930", "000660", "SPY", "QQQ", "AAPL", "MSFT"]}
RULES = {"mom_12_1_positive": "close[-21]/close[-252]-1 > 0", "mom_3m_positive": "63-bar return > 0",
         "mom_loss_exit": "exit when 12-1 momentum <= 0", "peak_dd_stop_15pct": "exit when close < peak since entry*0.85"}
PROTECTIVE = {"peak_dd_stop_15pct"}
RULE_KINDS = {"mom_12_1_positive": "entry", "mom_3m_positive": "filter", "mom_loss_exit": "exit", "peak_dd_stop_15pct": "protective"}


def generate_signals(df, disabled=frozenset()):
    disabled = frozenset(disabled)
    c = df["close"]
    m = c.shift(21) / c.shift(252) - 1.0
    entry = pk.cond(disabled, "mom_12_1_positive", m > 0) & pk.cond(disabled, "mom_3m_positive", ind.roc(c, 63) > 0) & pk.b(m.notna())
    exit_sig = np.zeros(len(df), bool) if "mom_loss_exit" in disabled else pk.b(m <= 0)
    n = len(c)
    cv = c.values
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
