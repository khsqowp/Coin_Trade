"""Deterministic market-data summary (input to Researcher; also ground truth for data-QA benchmark)."""
import numpy as np

from . import store


def one(symbol, tf):
    df = store.get_ohlcv(symbol, tf)
    m = store.meta_of(symbol, tf)
    c = df["close"]
    r = c.pct_change().dropna()
    ppy = store.PERIODS_PER_YEAR[tf]
    eq = c / c.cummax()
    out = {
        "symbol": symbol, "timeframe": tf, "source": m["source"], "exchange": m["exchange"],
        "fetched_at": m["fetched_at"], "sha256_prefix": m["sha256"][:12], "rows": len(df),
        "first": str(df.index[0].date()), "last": str(df.index[-1].date()),
        "last_close": round(float(c.iloc[-1]), 2),
        "ret_30bars_pct": round(float(c.iloc[-1] / c.iloc[-31] - 1) * 100, 2),
        "ret_90bars_pct": round(float(c.iloc[-1] / c.iloc[-91] - 1) * 100, 2),
        "ann_vol_pct": round(float(r.std() * np.sqrt(ppy)) * 100, 1),
        "max_drawdown_pct": round(float(1 - eq.min()) * 100, 1),
        "close_vs_sma200_pct": round(float(c.iloc[-1] / c.rolling(200).mean().iloc[-1] - 1) * 100, 2),
        "corr_note": "n/a",
    }
    out.pop("corr_note")
    return out


def market_summary():
    items = [one(s, "1d") for s in ("BTC/USDT", "ETH/USDT")]
    a = store.get_ohlcv("BTC/USDT", "1d")["close"].pct_change()
    b = store.get_ohlcv("ETH/USDT", "1d")["close"].pct_change()
    corr = float(a.tail(365).corr(b.tail(365)))
    return {"datasets": items, "btc_eth_daily_return_corr_last365": round(corr, 3),
            "notes": ["spot, closed candles only, UTC", "costs to assume: 0.10% fee + 0.05% slippage per side"]}
