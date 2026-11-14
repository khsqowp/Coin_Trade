"""Coin short-term BREAKOUT after volatility contraction: Bollinger bandwidth in its lowest quintile (100-bar window) during
the last 10 bars, then a close above the previous 20-bar high on volume > 1.5x its 20-bar mean. Exit: close<EMA20 or ATRx2.5 trail."""
import numpy as np
from tp import ind, poolkit as pk

META = {"id": "coin_breakout_squeeze", "family": "breakout", "market": "crypto", "profile": "crypto_fast",
        "timeframes": ["15m", "1h"], "symbols": ["BTC/USDT", "ETH/USDT"]}
RULES = {"squeeze_recent": "Bollinger bandwidth was in its lowest 20% (100 bars) within the last 10 bars",
         "donchian20_break": "close above the previous 20-bar high", "volume_confirm": "volume > 1.5 x 20-bar mean",
         "ema20_exit": "exit when close < EMA20", "atr_trail_stop": "exit when close < highest close - 2.5*ATR(14)"}
PROTECTIVE = {"atr_trail_stop"}
RULE_KINDS = {"squeeze_recent": "filter", "donchian20_break": "entry", "volume_confirm": "filter", "ema20_exit": "exit",
              "atr_trail_stop": "protective"}


def generate_signals(df, disabled=frozenset()):
    disabled = frozenset(disabled)
    c = df["close"]
    mid, up, lo = ind.bollinger(c, 20, 2.0)
    bw = (up - lo) / mid
    sq = (bw <= bw.rolling(100, min_periods=100).quantile(0.2)).astype(float)
    sq_recent = sq.rolling(10, min_periods=1).max() > 0
    brk = c > ind.donchian_high(df, 20)
    volok = df["volume"] > 1.5 * ind.sma(df["volume"], 20)
    entry = (pk.cond(disabled, "squeeze_recent", sq_recent) & pk.cond(disabled, "donchian20_break", brk)
             & pk.cond(disabled, "volume_confirm", volok))
    entry &= pk.b(bw.rolling(100, min_periods=100).quantile(0.2).notna())
    exit_sig = np.zeros(len(df), bool) if "ema20_exit" in disabled else pk.b(c < ind.ema(c, 20))
    sig = pk.position_loop(entry, c.values, ind.atr(df, 14).values, exit_sig,
                           trail_mult=None if "atr_trail_stop" in disabled else 2.5)
    return pk.to_series(sig, df)
