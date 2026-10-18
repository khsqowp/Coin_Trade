"""Read-only loader for .rs_cache/vision (1h klines + funding). No network."""
import glob, os
import pandas as pd
V = os.path.join(os.path.dirname(os.path.dirname(os.path.abspath(__file__))), ".rs_cache", "vision")

def load():
    ohlc, fund = {}, {}
    for p in sorted(glob.glob(f"{V}/klines_1h/*USDT.csv.gz")):
        b = os.path.basename(p)[:-len("USDT.csv.gz")]
        d = pd.read_csv(p, header=None, comment=None)
        if not str(d.iloc[0, 0]).isdigit():
            d = d.iloc[1:]
        d = d.iloc[:, :6].astype(float)
        d.columns = ["ts", "open", "high", "low", "close", "volume"]
        d.index = pd.to_datetime(d.pop("ts").astype("int64"), unit="ms", utc=True)
        ohlc[b] = d[~d.index.duplicated()].sort_index()
    for p in sorted(glob.glob(f"{V}/funding/*USDT.csv.gz")):
        b = os.path.basename(p)[:-len("USDT.csv.gz")]
        d = pd.read_csv(p, header=None)
        if not str(d.iloc[0, 0]).isdigit():
            d = d.iloc[1:]
        t = pd.to_datetime(d.iloc[:, 0].astype("int64"), unit="ms", utc=True).dt.round("1h")
        s = pd.Series(d.iloc[:, 2].astype(float).values, index=t)
        fund[b] = s[~s.index.duplicated()]
    return ohlc, fund
