"""Coin short-term MEAN REVERSION (long only): Bollinger(20,2) lower-band close + RSI(14)<30, only inside an uptrend
(close>EMA200 filter) to avoid catching falling knives. Exit at the Bollinger mid band, after 48 bars, or at a 3% hard stop."""
import numpy as np
from tp import ind, poolkit as pk

META = {"id": "coin_mean_reversion", "family": "mean_reversion", "market": "crypto", "profile": "crypto_fast",
        "timeframes": ["15m", "1h"], "symbols": ["BTC/USDT", "ETH/USDT"]}
RULES = {"bb_lower_entry": "close below the Bollinger(20,2) lower band", "rsi_oversold": "RSI(14) < 30",
         "uptrend_filter": "close > EMA200", "mid_band_exit": "exit when close >= Bollinger mid band",
         "time_stop": "exit after 48 bars", "hard_stop_3pct": "exit when close <= entry*0.97"}
PROTECTIVE = {"hard_stop_3pct"}
RULE_KINDS = {"bb_lower_entry": "entry", "rsi_oversold": "entry", "uptrend_filter": "filter", "mid_band_exit": "exit",
              "time_stop": "exit", "hard_stop_3pct": "protective"}


def generate_signals(df, disabled=frozenset()):
    disabled = frozenset(disabled)
    c = df["close"]
    mid, up, lo = ind.bollinger(c, 20, 2.0)
    rsi = ind.rsi(c, 14)
    e200 = ind.ema(c, 200)
    entry = (pk.cond(disabled, "bb_lower_entry", c < lo) & pk.cond(disabled, "rsi_oversold", rsi < 30)
             & pk.cond(disabled, "uptrend_filter", c > e200))
    entry &= pk.b(e200.notna()) & pk.b(lo.notna())
    exit_sig = np.zeros(len(df), bool) if "mid_band_exit" in disabled else pk.b(c >= mid)
    sig = pk.position_loop(entry, c.values, ind.atr(df, 14).values, exit_sig,
                           hard_stop_pct=None if "hard_stop_3pct" in disabled else 0.03,
                           max_bars=None if "time_stop" in disabled else 48)
    return pk.to_series(sig, df)
