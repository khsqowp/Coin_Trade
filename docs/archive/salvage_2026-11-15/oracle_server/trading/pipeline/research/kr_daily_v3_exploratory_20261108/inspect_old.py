import pandas as pd
import numpy as np
base='/app/kr_daily_v2/data/'
a=pd.read_parquet(base+'036220.parquet')
b=pd.read_parquet(base+'036220_old.parquet')
common=a.index.intersection(b.index)
print({'normal_rows':len(a),'normal_start':str(a.index.min()),'normal_end':str(a.index.max()),'old_rows':len(b),'old_start':str(b.index.min()),'old_end':str(b.index.max()),'normal_cols':list(a.columns),'old_cols':list(b.columns),'overlap_rows':len(common),'close_equal_overlap':int(np.isclose(a.loc[common,'close'],b.loc[common,'close'],equal_nan=True).sum()) if len(common) else 0,'volume_equal_overlap':int(np.isclose(a.loc[common,'volume'],b.loc[common,'volume'],equal_nan=True).sum()) if len(common) else 0})
