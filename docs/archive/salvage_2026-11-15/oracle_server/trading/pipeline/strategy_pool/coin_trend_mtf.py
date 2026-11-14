"""Coin short-term TREND FOLLOWING with multi-timeframe consensus (base, 4x base, 16x base; e.g. 15m/1h/4h).
Entry: at least 2 of 3 timeframes show an EMA20>EMA50>EMA100 alignment AND the base timeframe is aligned.
Exit: consensus lost (fewer than 2 aligned) or ATR(14)x3 trailing stop (protective)."""
import numpy as np
from tp import ind, poolkit as pk

META = {"id": "coin_trend_mtf", "family": "trend_follow", "market": "crypto", "profile": "crypto_fast",
        "timeframes": ["15m", "1h"], "symbols": ["BTC/USDT", "ETH/USDT"]}
RULES = {"ema_align_base": "base timeframe EMA20>EMA50>EMA100", "htf4_trend": "4x timeframe aligned",
         "htf16_trend": "16x timeframe aligned", "consensus_2of3": "at least 2 of 3 timeframes aligned",
         "trend_break_exit": "exit when fewer than 2 timeframes are aligned", "atr_trail_stop": "exit when close < highest close - 3*ATR(14)"}
PROTECTIVE = {"atr_trail_stop"}
RULE_KINDS = {"ema_align_base": "filter", "htf4_trend": "filter", "htf16_trend": "filter", "consensus_2of3": "entry",
              "trend_break_exit": "exit", "atr_trail_stop": "protective"}


def _aligned(d):
    e20, e50, e100 = ind.ema(d["close"], 20), ind.ema(d["close"], 50), ind.ema(d["close"], 100)
    return ((e20 > e50) & (e50 > e100)).astype(float).where(e100.notna())


def generate_signals(df, disabled=frozenset()):
    disabled = frozenset(disabled)
    base = _aligned(df)
    h4 = pk.htf_align(df, 4, _aligned)
    h16 = pk.htf_align(df, 16, _aligned)
    v_base = pk.cond(disabled, "ema_align_base", base == 1.0)
    v4 = pk.cond(disabled, "htf4_trend", h4 == 1.0)
    v16 = pk.cond(disabled, "htf16_trend", h16 == 1.0)
    votes = v_base.astype(int) + v4.astype(int) + v16.astype(int)
    consensus = np.ones(len(df), bool) if "consensus_2of3" in disabled else votes >= 2
    entry = consensus & v_base
    exit_sig = np.zeros(len(df), bool) if "trend_break_exit" in disabled else votes < 2
    atr = ind.atr(df, 14).values
    sig = pk.position_loop(entry, df["close"].values, atr, exit_sig,
                           trail_mult=None if "atr_trail_stop" in disabled else 3.0)
    return pk.to_series(sig, df)
