import os
from types import SimpleNamespace

import numpy as np
import pandas as pd

os.environ.setdefault("NUMBA_CACHE_DIR", "/tmp/numba-cache")

from app.crypto_round10_research import configs
from app.rs_equity_round10_transfer import _stock_frames


def test_round10_transfer_grid_matches_source_predeclared_unique_configs():
    groups = configs()
    rows = [config for _, _, group in groups for config in group]
    assert [len(group) for _, _, group in groups] == [20, 60, 56]
    assert len(rows) == 136
    assert len({repr(sorted(config.items())) for config in rows}) == 136


def test_round10_stock_inputs_exclude_prestart_and_invalid_rows():
    dates = pd.date_range("2018-12-28", periods=6, freq="B")
    close = np.array([[10.], [11.], [12.], [13.], [np.nan], [15.]])
    panel = SimpleNamespace(
        symbols=["AAA"], dates=dates,
        o=close.copy(), h=close.copy(), l=close.copy(), c=close.copy(),
        v=np.full_like(close, 1000.),
    )
    frames = _stock_frames(panel)
    assert frames["AAA"].index[0] >= pd.Timestamp("2019-01-01")
    assert not frames["AAA"].isna().any().any()
    assert len(frames["AAA"]) == 3
