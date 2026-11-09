"""R2-B step 2: public READ-ONLY download of 1m last + mark-price klines (no keys). Saves npz per day.
usage: python rs_lev_r2b_fetch.py  (reads data/days.json). Output arrays [sym, 1440, 4] OHLC, NaN if missing."""
import json, os, sys, time, urllib.request, urllib.error
import numpy as np, pandas as pd
HERE = os.path.dirname(os.path.abspath(__file__))
D = os.path.join(HERE, "..", "docs", "research", "lev_loop", "R2B", "data")
NAMES = ['BTC','ETH','BNB','XRP','SOL','TRX','DOGE','ZEC','LINK','XMR','ADA','XLM','BCH','LTC','HBAR','AVAX','SUI','UNI','NEAR','TAO','AAVE','ONDO','THETA','DOT','ENA','WLD','ICP','ETC','POL','QNT','ALGO','ATOM','RENDER','JUP','ARB','FIL','VET','CAKE','LDO','CRV','INJ','OP','APT','IMX','STX']
BASE = os.environ.get("R2B_BASE", "https://fapi.binance.com")
def get(path, params):
    url = BASE + path + "?" + "&".join(f"{k}={v}" for k, v in params.items())
    for t in range(6):
        try:
            return json.loads(urllib.request.urlopen(url, timeout=30).read())
        except urllib.error.HTTPError as e:
            if e.code in (400, 404): return None
            time.sleep(2 * (t + 1))
        except Exception:
            time.sleep(2 * (t + 1))
    return None
def fetch(sym, kind, day):
    t0 = int(pd.Timestamp(day, tz="UTC").timestamp() * 1000)
    p = {"interval": "1m", "startTime": t0, "endTime": t0 + 1440 * 60000 - 1, "limit": 1500}
    p["symbol" if kind == "klines" else "symbol"] = sym
    path = "/fapi/v1/klines" if kind == "klines" else "/fapi/v1/markPriceKlines"
    r = get(path, p)
    out = np.full((1440, 4), np.nan)
    if not r: return out, 0
    for row in r:
        i = (int(row[0]) - t0) // 60000
        if 0 <= i < 1440: out[i] = [float(row[1]), float(row[2]), float(row[3]), float(row[4])]
    return out, len(r)
if __name__ == "__main__":
    days = json.load(open(os.path.join(D, "days.json")))["days"]
    for day in days:
        fn = os.path.join(D, f"{day}.npz")
        if os.path.exists(fn): continue
        L = np.full((len(NAMES), 1440, 4), np.nan); M = L.copy(); cov = {}
        for k, n in enumerate(NAMES):
            sym = n + "USDT"
            L[k], nl = fetch(sym, "klines", day); time.sleep(0.4)
            M[k], nm = fetch(sym, "mark", day); time.sleep(0.4)
            cov[n] = [nl, nm]
        np.savez_compressed(fn, last=L, mark=M, names=np.array(NAMES))
        full = sum(1 for v in cov.values() if v[0] >= 1400 and v[1] >= 1400)
        print(day, "full-coverage symbols", full, "/", len(NAMES), "partial", [n for n, v in cov.items() if 0 < min(v) < 1400], "missing", [n for n, v in cov.items() if min(v) == 0], flush=True)
