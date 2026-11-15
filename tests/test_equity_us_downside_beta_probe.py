from pathlib import Path

import numpy as np

from scripts.research.equity_us_downside_beta_probe import CUTOFF, bootstrap_ci, read_prices


def test_read_prices_stops_before_exclusive_cutoff(tmp_path: Path):
    cache = tmp_path / "cache"
    cache.mkdir()
    (cache / "US_SPY.csv").write_text(
        "date,open,high,low,close,volume\n"
        "2024-11-11T00:00:00Z,10,11,9,10.5,100\n"
        "2024-11-12T00:00:00Z,malformed,row,must,not,parse\n",
        encoding="utf-8",
    )
    result = read_prices("SPY", cache)
    assert len(result) == 1
    assert result.index[-1] < CUTOFF
    assert result.close.iloc[0] == 10.5


def test_month_block_bootstrap_is_reproducible_and_ordered():
    monthly = np.array([0.02, -0.01, 0.03, 0.005] * 6)
    first = bootstrap_ci(monthly)
    second = bootstrap_ci(monthly)
    assert first == second
    assert len(first) == 2
    assert first[0] <= first[1]
