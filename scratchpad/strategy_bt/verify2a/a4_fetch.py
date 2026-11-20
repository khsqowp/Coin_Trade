"""Fetch Binance USDT-M funding history (public) -> funding/<SYMBOL>.csv. Reports honestly on failure."""
import time, requests, pandas as pd, sys
from lib import HERE, SYMS
URL = "https://fapi.binance.com/fapi/v1/fundingRate"
START = int(pd.Timestamp("2019-09-01", tz="UTC").timestamp() * 1000)
END = int(pd.Timestamp.now(tz="UTC").timestamp() * 1000)
for s in SYMS:
    rows, t = [], START
    try:
        while t < END:
            r = requests.get(URL, params=dict(symbol=s, startTime=t, limit=1000), timeout=20); r.raise_for_status()
            j = r.json()
            if not j: break
            rows += j; t = j[-1]["fundingTime"] + 1
            if len(j) < 1000: break
            time.sleep(0.2)
    except Exception as e:
        print(s, "FETCH_FAILED", repr(e)); continue
    d = pd.DataFrame(rows)
    d["time"] = pd.to_datetime(d.fundingTime, unit="ms", utc=True).dt.round("min")
    d[["time", "fundingRate"]].assign(fundingRate=d.fundingRate.astype(float)).to_csv(HERE / "funding" / f"{s}.csv", index=False)
    print(s, len(d), d.time.min(), d.time.max(), "mean rate %.6f" % d.fundingRate.astype(float).mean())
