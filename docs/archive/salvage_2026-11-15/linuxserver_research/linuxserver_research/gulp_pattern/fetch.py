"""Public-data fetch (no keys). Single process, low rate. KR via FDR/Naver, US via FDR/Yahoo."""
import sys, time, json, re
from pathlib import Path
import pandas as pd
import FinanceDataReader as fdr

ROOT = Path(__file__).resolve().parent
C = ROOT / "cache"
for d in ("kr", "us", "idx"):
    (C / d).mkdir(parents=True, exist_ok=True)
END = "2026-11-12"
SLEEP = 0.4


def retry(fn, n=3):
    for i in range(n):
        try:
            return fn()
        except Exception as e:
            time.sleep(2 * (i + 1))
    return None


def kr():
    k = fdr.StockListing("KRX")
    k = k[k.Market.isin(["KOSPI", "KOSDAQ"])][["Code", "Name", "Market"]].copy()
    k.to_csv(C / "kr_universe.csv", index=False)
    for code in k.Code:
        out = C / "kr" / f"{code}.parquet"
        if out.exists():
            continue
        parts = []
        for a, b in (("2010-01-01", "2018-12-31"), ("2019-01-01", END)):
            d = retry(lambda: fdr.DataReader(code, a, b))
            if d is not None and len(d):
                parts.append(d)
            time.sleep(SLEEP)
        if not parts:
            (C / "kr" / f"{code}.empty").touch()
            continue
        d = pd.concat(parts)
        d = d[~d.index.duplicated()].sort_index()[["Open", "High", "Low", "Close", "Volume"]]
        d.columns = ["open", "high", "low", "close", "volume"]
        d.to_parquet(out)


def us():
    sp = fdr.StockListing("S&P500")
    syms = set(sp["Symbol"].astype(str))
    try:
        t = pd.read_html("https://en.wikipedia.org/wiki/Nasdaq-100")
        for df in t:
            col = [c for c in df.columns if str(c) in ("Ticker", "Symbol")]
            if col and len(df) > 80:
                syms |= set(df[col[0]].astype(str))
                break
    except Exception as e:
        print("ndx fail", e)
    syms = sorted(s.replace(".", "-") for s in syms if re.match(r"^[A-Za-z.\-]+$", s))
    pd.Series(syms).to_csv(C / "us_universe.csv", index=False, header=["symbol"])
    for s in syms:
        out = C / "us" / f"{s}.parquet"
        if out.exists():
            continue
        d = retry(lambda: fdr.DataReader(s, "2009-01-01", END))
        time.sleep(SLEEP)
        if d is None or not len(d):
            (C / "us" / f"{s}.empty").touch()
            continue
        f = d["Adj Close"] / d["Close"]
        o = pd.DataFrame({"open": d.Open * f, "high": d.High * f, "low": d.Low * f, "close": d.Close * f,
                          "rawclose": d.Close, "volume": d.Volume})
        o.to_parquet(out)


def idx():
    for name, sym in (("KOSPI", "KS11"), ("KOSDAQ", "KQ11"), ("SPY", "SPY"), ("QQQ", "QQQ")):
        d = retry(lambda: fdr.DataReader(sym, "2010-01-01", END))
        if d is not None:
            d.to_parquet(C / "idx" / f"{name}.parquet")
        time.sleep(SLEEP)


if __name__ == "__main__":
    for w in sys.argv[1:]:
        {"kr": kr, "us": us, "idx": idx}[w]()
    print("done", sys.argv[1:])
