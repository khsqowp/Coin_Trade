import numpy as np
import pandas as pd

from scripts.research.equity_trend_gate_probe import us_run


def test_monthly_us_rebalance_has_lower_turnover_than_daily_rebalance():
    dates = pd.bdate_range('2020-01-01', periods=320, tz='UTC')
    frames = {}
    for i in range(10):
        daily_return = 0.0002 + 0.001 * np.sin(np.arange(len(dates)) / (5 + i) + i)
        close = 100 * np.cumprod(1 + daily_return)
        open_ = np.r_[close[0], close[:-1]]
        frames[f'S{i:02d}'] = pd.DataFrame({'Open': open_, 'Close': close}, index=dates)
    frames['SPY'] = frames['S00'].copy()

    daily = us_run(frames, gated=False, fee=0.0008, slip=0.0010, rebalance='daily')
    monthly = us_run(frames, gated=False, fee=0.0008, slip=0.0010, rebalance='monthly')

    assert monthly['one_way_turnover_x'] < daily['one_way_turnover_x']
