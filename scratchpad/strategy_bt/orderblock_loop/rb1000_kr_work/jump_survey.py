"""Data-quality survey only (TRAIN window). Counts limit-exceeding close-to-close jumps; no strategy metrics."""
import pandas as pd, numpy as np
CUT = pd.Timestamp("2018-10-26 23:59:59")
D = "/Users/user/CODE/Coin_Trade/trading_data/external/equities/kr/"
frames = []
for f in ["daily_stocks_current.parquet", "daily_stocks_delisted.parquet"]:
    df = pd.read_parquet(D + f, columns=["code", "date", "open", "high", "low", "close", "volume"])
    df = df[df["date"] <= CUT]
    frames.append(df)
df = pd.concat(frames).sort_values(["code", "date"]).drop_duplicates(["code", "date"])
df["prev"] = df.groupby("code")["close"].shift(1)
df["ret"] = df["close"] / df["prev"] - 1
df["vr"] = df["volume"] / df.groupby("code")["volume"].shift(1)
j = df[df["ret"].abs() > 0.31].copy()
j["ratio"] = j["close"] / j["prev"]
print("codes", df["code"].nunique(), "rows", len(df))
print("jumps >31%:", len(j), "codes:", j["code"].nunique())
def near_split(r):
    for n in range(2, 21):
        if abs(r * n - 1) < 0.02 or abs(r - n) / n < 0.02 or abs(1 / r - n) / n < 0.02:
            return n
    return 0
j["split_n"] = j["ratio"].map(near_split)
print("split-like (n in 2..20):", (j.split_n > 0).sum())
print(j.groupby("split_n").size().to_string())
print("unmatched ratios sample:")
print(j[j.split_n == 0][["code", "date", "prev", "close", "ret", "vr"]].head(25).to_string())
print("ratio quantiles (all jumps):", j["ratio"].quantile([0, .01, .1, .5, .9, .99, 1]).round(4).to_dict())
print("vol ratio for split-like median:", j[j.split_n > 0]["vr"].median(), " unmatched median:", j[j.split_n == 0]["vr"].median())
print("jumps by year:", j.groupby(j.date.dt.year).size().to_dict())
