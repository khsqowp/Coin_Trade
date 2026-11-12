import pandas as pd
from app.aw_data import _us_stock_eligibility


def test_us_stock_rank_uses_60_day_median_not_spike_day_volume():
    symbols=[f'S{i:02}' for i in range(31)]
    med=pd.DataFrame([[100+i for i in range(30)]+[1]],columns=symbols)
    listed=pd.DataFrame(True,index=med.index,columns=symbols)
    assert not _us_stock_eligibility(med,symbols,listed).iloc[0,-1]
