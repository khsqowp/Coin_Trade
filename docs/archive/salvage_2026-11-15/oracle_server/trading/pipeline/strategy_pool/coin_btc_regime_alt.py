"""ALT strategy with a BTC REGIME FILTER (card: 'Donchian70 + SMA200 + BTC regime'). Needs extra columns btc_close (and
btc_high/btc_low) aligned to the alt's bars; the harness adds them via tp.pool.with_btc_context (causal join).
Entry: close breaks the previous 70-bar high, close>SMA(200), BTC regime ok (BTC close > BTC SMA(200) and BTC EMA20>EMA50)
and BTC not dumping (24-bar BTC return > -3%). Exit: close < previous 35-bar low or ATRx3 trailing stop (protective)."""
import numpy as np
from tp import ind, poolkit as pk

NEEDS_BTC = True
META = {"id": "coin_btc_regime_alt", "family": "btc_regime_alt", "market": "crypto", "profile": "crypto_fast",
        "timeframes": ["1h", "15m"], "symbols": ["ETH/USDT"]}
RULES = {"donchian70_break": "close above the previous 70-bar high", "own_sma200": "close > SMA(200)",
         "btc_trend_regime": "BTC close > BTC SMA(200) and BTC EMA20 > EMA50",
         "btc_not_dumping": "BTC 24-bar return > -3%", "donchian35_exit": "exit when close < previous 35-bar low",
         "atr_trail_stop": "exit when close < highest close - 3*ATR(14)"}
PROTECTIVE = {"atr_trail_stop"}
RULE_KINDS = {"donchian70_break": "entry", "own_sma200": "filter", "btc_trend_regime": "filter", "btc_not_dumping": "filter",
              "donchian35_exit": "exit", "atr_trail_stop": "protective"}


def generate_signals(df, disabled=frozenset()):
    disabled = frozenset(disabled)
    c = df["close"]
    if "btc_close" not in df.columns:
        raise ValueError("btc_close column missing (use tp.pool.with_btc_context)")
    bc = df["btc_close"]
    regime = (bc > ind.sma(bc, 200)) & (ind.ema(bc, 20) > ind.ema(bc, 50))
    notdump = ind.roc(bc, 24) > -0.03
    entry = (pk.cond(disabled, "donchian70_break", c > ind.donchian_high(df, 70)) & pk.cond(disabled, "own_sma200", c > ind.sma(c, 200))
             & pk.cond(disabled, "btc_trend_regime", regime) & pk.cond(disabled, "btc_not_dumping", notdump))
    entry &= pk.b(ind.sma(c, 200).notna()) & pk.b(ind.sma(bc, 200).notna()) & pk.b(ind.donchian_high(df, 70).notna())
    exit_sig = np.zeros(len(df), bool) if "donchian35_exit" in disabled else pk.b(c < ind.donchian_low(df, 35))
    sig = pk.position_loop(entry, c.values, ind.atr(df, 14).values, exit_sig,
                           trail_mult=None if "atr_trail_stop" in disabled else 3.0)
    return pk.to_series(sig, df)
