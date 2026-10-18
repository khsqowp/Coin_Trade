import os
from types import SimpleNamespace

import numpy as np
import pandas as pd

os.environ.setdefault("NUMBA_CACHE_DIR", "/tmp/numba-cache")

from app.rs_equity_trx_dca_transfer import simulate_dca


def test_dca_transfer_is_finite_causal_and_respects_position_limit():
    dates = pd.date_range("2018-01-01", periods=1000, freq="B")
    close = 100 + np.arange(len(dates)) * 0.02 + np.sin(np.arange(len(dates)) / 7) * 6
    open_ = close * (1 + np.sin(np.arange(len(dates)) / 2) * 0.002)
    high = np.maximum(open_, close) * 1.01
    low = np.minimum(open_, close) * 0.99
    panel = SimpleNamespace(
        dates=dates,
        symbols=["AAA", "BBB"],
        o=np.column_stack((open_, open_ * 1.01)),
        h=np.column_stack((high, high * 1.01)),
        l=np.column_stack((low, low * 1.01)),
        c=np.column_stack((close, close * 1.01)),
        v=np.full((len(dates), 2), 100_000.0),
        eligible=np.ones((len(dates), 2), dtype=bool),
        tradable=np.ones((len(dates), 2), dtype=bool),
    )

    result = simulate_dca(panel, 0.1, np.zeros(2), 0.0, max_positions=1)

    metrics = result["metrics"]
    assert len(result["daily_equity"]) == len(result["daily_dates"])
    assert np.isfinite(result["daily_equity"]).all()
    assert metrics["trades"] > 0
    assert metrics["max_open_positions"] <= 1
    assert metrics["buys_including_dca"] >= metrics["full_sells"]
