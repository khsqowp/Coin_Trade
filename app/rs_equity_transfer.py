"""Shared daily-signal adapter for transferring the crypto family registry to equities.

The adapter never treats a synthetic broad-market proxy as a tradable security.
Strategies that require BTC use the proxy only as an explicitly documented market
regime substitute. Equity execution/cost simulation is implemented separately.
"""
from __future__ import annotations

from dataclasses import dataclass
from typing import Any

import numpy as np
import pandas as pd


@dataclass
class EquityPanel:
    market: str
    dates: pd.DatetimeIndex
    symbols: list[str]
    o: np.ndarray
    h: np.ndarray
    l: np.ndarray
    c: np.ndarray
    v: np.ndarray
    eligible: np.ndarray
    tradable: np.ndarray
    slip: np.ndarray
    proxy_close: np.ndarray
    D: dict[str, Any]


def _benchmark_ohlcv(o: np.ndarray, h: np.ndarray, l: np.ndarray,
                     c: np.ndarray, v: np.ndarray) -> tuple[np.ndarray, ...]:
    """Construct a causal equal-weight index proxy from constituent daily returns."""
    nday, nsym = c.shape
    valid = np.isfinite(c)
    close_ret = np.full_like(c, np.nan, dtype=float)
    close_ret[1:] = c[1:] / c[:-1] - 1.0
    close_ret[~valid] = np.nan
    counts = np.isfinite(close_ret).sum(axis=1)
    daily_ret = np.divide(
        np.nansum(close_ret, axis=1), counts,
        out=np.zeros(nday, dtype=float), where=counts > 0,
    )
    daily_ret = np.nan_to_num(daily_ret, nan=0.0)
    idx_c = np.empty(nday, dtype=float)
    idx_c[0] = 100.0
    for t in range(1, nday):
        idx_c[t] = idx_c[t - 1] * (1.0 + daily_ret[t])

    prev_c = np.vstack((np.full((1, nsym), np.nan), c[:-1]))
    def index_ratio(px: np.ndarray) -> np.ndarray:
        ratio = px / prev_c
        counts = np.isfinite(ratio).sum(axis=1)
        out = np.divide(
            np.nansum(ratio, axis=1), counts,
            out=np.ones(nday, dtype=float), where=counts > 0,
        )
        return np.r_[1.0, out[1:]]

    idx_o = idx_c * index_ratio(o)
    idx_h = np.maximum.reduce((idx_c * index_ratio(h), idx_o, idx_c))
    idx_l = np.minimum.reduce((idx_c * index_ratio(l), idx_o, idx_c))
    idx_v = np.nansum(v, axis=1)
    return idx_o, idx_h, idx_l, idx_c, idx_v


def _make_D(dates: pd.DatetimeIndex, symbols: list[str],
            o: np.ndarray, h: np.ndarray, l: np.ndarray,
            c: np.ndarray, v: np.ndarray) -> tuple[dict[str, Any], np.ndarray]:
    proxy = _benchmark_ohlcv(o, h, l, c, v)
    days = dates.tz_localize("UTC") if dates.tz is None else dates.tz_convert("UTC")
    names = [*symbols, "BTC"]
    d = {
        "o": np.column_stack((o, proxy[0])),
        "h": np.column_stack((h, proxy[1])),
        "l": np.column_stack((l, proxy[2])),
        "c": np.column_stack((c, proxy[3])),
        "v": np.column_stack((v, proxy[4])),
    }
    # This registry is evaluated only at 1d. Keeping the empty b4 entry makes
    # unsupported intraday access fail visibly rather than fabricate 4h bars.
    D = {"names": names, "days": days, "d": d, "b4": {}}
    return D, proxy[3]


def load_equity_panel(market: str) -> EquityPanel:
    """Load existing KIS cache files only; do not fetch or create market data."""
    if market == "US":
        from app.rs_us_engine import load_panel

        raw = load_panel()
        dates = raw["Close"].index
        symbols = list(raw["Close"].columns)
        o, h, l, c, v = (raw[k].reindex(index=dates, columns=symbols).to_numpy(float)
                         for k in ("Open", "High", "Low", "Close", "Volume"))
        eligible = np.isfinite(c)
        tradable = np.isfinite(o) & np.isfinite(c) & (v > 0)
        slip = np.full(len(symbols), 0.0003)
    elif market == "KR":
        from app.rs_kr_data import load

        raw = load()
        dates, symbols = raw.dates, list(raw.syms)
        o, h, l, c, v = (np.asarray(getattr(raw, key), dtype=float)
                         for key in ("o", "h", "l", "c", "v"))
        eligible, tradable, slip = raw.elig, raw.tradable, raw.slip
    else:
        raise ValueError(f"unsupported market: {market}")

    D, proxy_close = _make_D(dates, symbols, o, h, l, c, v)
    return EquityPanel(market, pd.DatetimeIndex(dates), symbols, o, h, l, c, v,
                       np.asarray(eligible, bool), np.asarray(tradable, bool),
                       np.asarray(slip, float), proxy_close, D)


def evaluate_family_signal(panel: EquityPanel, family: dict[str, Any],
                           timeframe: str, params: dict[str, Any]) -> tuple[np.ndarray, np.ndarray, np.ndarray]:
    """Return tradable-symbol signals plus the non-tradable proxy signal."""
    if timeframe != "1d":
        raise ValueError("equity caches contain daily OHLCV only; intraday bars are not synthesized")
    pos, strength = family["fn"](panel.D, timeframe, **params)
    pos = np.asarray(pos, dtype=float)
    proxy_pos = pos[:, -1].copy()
    n_symbols = len(panel.symbols)
    pos = pos[:, :n_symbols]
    strength = np.asarray(strength, dtype=float)[:, :n_symbols]
    if pos.shape != panel.c.shape or strength.shape != panel.c.shape:
        raise ValueError(f"bad family output shape: {pos.shape}, {strength.shape}, expected {panel.c.shape}")
    pos[~panel.eligible] = np.nan
    strength[~panel.eligible] = np.nan
    return pos, strength, proxy_pos
