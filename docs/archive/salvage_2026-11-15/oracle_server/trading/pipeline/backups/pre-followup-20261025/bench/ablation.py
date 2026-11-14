import sys
sys.path.insert(0, "/app/src")
from tp import bt, store
df = store.get_ohlcv("BTC/USDT", "1d")
f2 = bt.load_signal_fn("/app/runs/run-main-002/work/strategy.py")
s2 = f2(df.copy())
sma_only = (df["close"] > df["close"].rolling(200).mean()).astype(float)
print("run-002 signals identical to plain close>SMA200:", bool((s2 == sma_only).all()), "diff bars:", int((s2 != sma_only).sum()))
