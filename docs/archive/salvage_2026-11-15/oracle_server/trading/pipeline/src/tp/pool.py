"""Strategy pool registry + context joins + evaluation. Strategies live in strategy_pool/*.py (deterministic, no LLM).

Common interface of every pool module: RULES (dict), generate_signals(df, disabled=frozenset()), META, PROTECTIVE, RULE_KINDS;
optional NEEDS_BTC / NEEDS_LIQ (extra context columns) and verifiable() -> None | reason (UNVERIFIABLE strategies can never pass
the gate). Market profiles (crypto_fast / kr_equity / us_equity) are in tp.risk.PROFILES."""
import importlib.util
import json
from pathlib import Path

import numpy as np
import pandas as pd

from . import ablation, bt, store
from .config import ROOT

POOL_DIR = ROOT / "strategy_pool"
COIN_TFS = ("5m", "15m", "1h")


def pool_ids():
    return sorted(p.stem for p in POOL_DIR.glob("*.py") if not p.stem.startswith("_"))


def load(sid, path=None):
    p = path or (POOL_DIR / (sid + ".py"))
    spec = importlib.util.spec_from_file_location("pool_" + sid, str(p))
    mod = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(mod)
    return mod


def with_btc_context(df, tf):
    """Add btc_close/btc_high/btc_low aligned on the same bars (same-bar values only => causal)."""
    b = store.get_ohlcv("BTC/USDT", tf)
    out = df.copy()
    for k in ("close", "high", "low"):
        out["btc_" + k] = b[k].reindex(df.index)
    return out.dropna(subset=["btc_close"])


def with_liq_context(df, tf, symbol="BTC"):
    """Join the Binance-proxy liquidation features (availability-time stamped). Only exists for the OI-history window."""
    from . import deriv, liqmap
    import datetime as dt
    asof = df.index[-1] + pd.Timedelta(minutes=1)
    con = liqmap._ro(deriv.DB)
    oi = pd.read_sql_query("SELECT ts_ms, oi_value FROM oi_hist WHERE symbol=? ORDER BY ts_ms", con, params=(symbol + "USDT",))
    ls = pd.read_sql_query("SELECT ts_ms, long_share FROM ls_ratio WHERE kind='global_acct' AND symbol=? ORDER BY ts_ms", con, params=(symbol + "USDT",))
    con.close()
    ix = lambda s: pd.to_datetime(s, unit="ms", utc=True) + pd.Timedelta("5min")
    oi_s = pd.Series(oi["oi_value"].values, index=ix(oi["ts_ms"]))
    ls_s = pd.Series(ls["long_share"].values, index=ix(ls["ts_ms"]))
    k5 = store.get_ohlcv(symbol + "/USDT", "5m")
    feats = liqmap.proxy_series(oi_s, ls_s, k5)
    left = pd.DataFrame({"t": df.index + pd.Timedelta(store.TF_MS[tf], unit="ms")})
    right = feats.reset_index().rename(columns={"index": "t"}) if feats.index.name is None else feats.reset_index().rename(columns={feats.index.name: "t"})
    m = pd.merge_asof(left, right[["t", "liq_imb", "liq_dist_up_pct"]].sort_values("t"), on="t", direction="backward")
    out = df.copy()
    out["liq_imb"] = m["liq_imb"].values
    out["liq_dist_up_pct"] = m["liq_dist_up_pct"].values
    first = feats.index.min()
    return out[out.index >= first]


def context_for(mod, df, tf, symbol):
    if getattr(mod, "NEEDS_BTC", False):
        df = with_btc_context(df, tf)
    if getattr(mod, "NEEDS_LIQ", False):
        df = with_liq_context(df, tf, symbol.split("/")[0])
    return df


def rotation_picks(closes, asof=None, k=3):
    """Cross-sectional momentum rotation (portfolio level): rank symbols by 12-1 month momentum, keep only those with close>SMA200,
    return the top-k with equal weight. closes: DataFrame(columns=symbols, index=dates). Causal (uses data <= asof)."""
    c = closes if asof is None else closes[closes.index <= asof]
    mom = c.shift(21).iloc[-1] / c.shift(252).iloc[-1] - 1
    ok = c.iloc[-1] > c.rolling(200).mean().iloc[-1]
    cand = mom[ok & mom.notna() & (mom > 0)].sort_values(ascending=False).head(k)
    return {s: round(1.0 / len(cand), 4) for s in cand.index} if len(cand) else {}


def evaluate(sid, symbol, tf, market="crypto"):
    """Deterministic evaluation of one pool strategy: trusted backtest + lookahead + ablation (with protective stress)."""
    mod = load(sid)
    fee, slip, ppy = bt.COSTS["crypto" if market == "crypto" else "kr"]
    if market == "crypto":
        ppy = store.PERIODS_PER_YEAR[tf]
    src = {"crypto": "binance", "kr": "kis-paper", "us": "yahoo"}[market]
    df = store.get_ohlcv(symbol, tf, source=src)
    df = context_for(mod, df, tf, symbol)
    rep = bt.evaluate(df, mod.generate_signals, ppy, fee=fee, slip=slip)
    abl = ablation.run_ablation(df, mod.generate_signals, mod.RULES, ppy, None, fee, slip,
                                protective=set(getattr(mod, "PROTECTIVE", ()) or ()), kinds=dict(getattr(mod, "RULE_KINDS", {})))
    abl["summary"] = ablation.summarize(abl)
    unver = mod.verifiable() if hasattr(mod, "verifiable") else None
    rep["symbol"], rep["market"], rep["strategy_id"] = symbol, market, sid
    if unver:
        rep["unverifiable"] = unver
    return rep, abl, mod.META
