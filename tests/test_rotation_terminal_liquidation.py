from __future__ import annotations

import numpy as np
import pandas as pd

from app.rs_risk_engine import Cfg, build_panel, simulate


def _panel():
    idx = pd.date_range("2024-01-01", periods=144, freq="h", tz="UTC")
    ohlc = {}
    for symbol, closes in {"A": [100.0] * 24 + [101.0] * 120,
                           "B": [100.0] * 24 + [99.0] * 120}.items():
        close = np.asarray(closes)
        ohlc[symbol] = pd.DataFrame(
            {"open": close, "high": close, "low": close, "close": close}, index=idx
        )
    return build_panel(ohlc)


def test_terminal_liquidation_charges_final_close_and_default_is_unchanged():
    panel = _panel()
    cfg = Cfg(lookback=1, rebal=1, K=1, cost=0.001, funding=False)

    continuing = simulate(panel, cfg)
    liquidated = simulate(panel, cfg, terminal_liquidation=True)

    assert abs(continuing["final"] - liquidated["final"] - 0.000999) < 1e-12
    assert liquidated["_eq"].iloc[-1] < continuing["_eq"].iloc[-1]


def test_terminal_liquidation_is_idempotent_when_flat():
    panel = _panel()
    cfg = Cfg(lookback=10, rebal=1, K=1, cost=0.001, funding=False)
    result = simulate(panel, cfg, terminal_liquidation=True)
    assert result["final"] == 1.0
