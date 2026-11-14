"""Coin short-term MOMENTUM ACCELERATION: ROC(20)>0 and rising (ROC20 - ROC20 10 bars ago > 0) with EMA50 sloping up.
Exit when ROC(10) turns negative or ATRx3 trailing stop."""
import numpy as np
from tp import ind, poolkit as pk

META = {"id": "coin_momentum_accel", "family": "momentum_accel", "market": "crypto", "profile": "crypto_fast",
        "timeframes": ["5m", "15m", "1h"], "symbols": ["BTC/USDT", "ETH/USDT"]}
RULES = {"roc20_positive": "ROC(20) > 0", "accel_positive": "ROC(20) - ROC(20)[10 bars ago] > 0",
         "ema50_slope_up": "EMA50 > EMA50 5 bars ago", "momentum_loss_exit": "exit when ROC(10) < 0",
         "atr_trail_stop": "exit when close < highest close - 3*ATR(14)"}
PROTECTIVE = {"atr_trail_stop"}
RULE_KINDS = {"roc20_positive": "entry", "accel_positive": "entry", "ema50_slope_up": "filter", "momentum_loss_exit": "exit",
              "atr_trail_stop": "protective"}


def generate_signals(df, disabled=frozenset()):
    disabled = frozenset(disabled)
    c = df["close"]
    r20 = ind.roc(c, 20)
    acc = r20 - r20.shift(10)
    e50 = ind.ema(c, 50)
    entry = (pk.cond(disabled, "roc20_positive", r20 > 0) & pk.cond(disabled, "accel_positive", acc > 0)
             & pk.cond(disabled, "ema50_slope_up", e50 > e50.shift(5)))
    entry &= pk.b(acc.notna()) & pk.b(e50.shift(5).notna())
    exit_sig = np.zeros(len(df), bool) if "momentum_loss_exit" in disabled else pk.b(ind.roc(c, 10) < 0)
    sig = pk.position_loop(entry, c.values, ind.atr(df, 14).values, exit_sig,
                           trail_mult=None if "atr_trail_stop" in disabled else 3.0)
    return pk.to_series(sig, df)
