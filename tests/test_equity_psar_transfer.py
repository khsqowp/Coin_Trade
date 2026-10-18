import os
from types import SimpleNamespace

import numpy as np
import pandas as pd

os.environ.setdefault("NUMBA_CACHE_DIR", "/tmp/numba-cache")

from app.rs_equity_psar_transfer import prepare_psar


def test_psar_adapter_outputs_causal_entry_exit_and_aligned_execution_fields():
    dates = pd.date_range("2022-01-03", periods=320, freq="B")
    close = 100 + np.arange(len(dates)) * 0.15 + np.sin(np.arange(len(dates)) / 5) * 4
    opens = close * (1 + np.sin(np.arange(len(dates)) / 3) * 0.002)
    panel = SimpleNamespace(
        dates=dates,
        symbols=["AAA"],
        o=opens[:, None],
        h=(np.maximum(opens, close) * 1.01)[:, None],
        l=(np.minimum(opens, close) * 0.99)[:, None],
        c=close[:, None],
        v=np.full((len(dates), 1), 100_000.0),
        eligible=np.ones((len(dates), 1), dtype=bool),
        tradable=np.ones((len(dates), 1), dtype=bool),
    )

    prepared = prepare_psar(panel, dates)["AAA"]

    assert prepared.index.equals(dates)
    assert {"Open", "High", "Low", "Close", "SIGNAL", "EXIT_SIGNAL", "ATR14", "STOP_LEVEL"} <= set(prepared.columns)
    assert prepared["SIGNAL"].dtype == bool
    assert prepared["EXIT_SIGNAL"].dtype == bool
    assert prepared["SIGNAL"].any()
    assert prepared["EXIT_SIGNAL"].any()
