"""R2-B step 4: public READ-ONLY 1m markPriceKlines for the live period (no keys). Output: <OUT>/mark1m_<SYM>.npy float32 [T,4] from START.
usage: python rs_lev_r2b_fetch_live.py <outdir> <START iso date> <symbols comma>"""
import sys, os, time, json, urllib.request, urllib.error
import numpy as np, pandas as pd
out, start, syms = sys.argv[1], sys.argv[2], sys.argv[3].split(",")
os.makedirs(out, exist_ok=True)
t0 = int(pd.Timestamp(start, tz="UTC").timestamp() * 1000)
now = int(time.time() * 1000)
T = (now - t0) // 60000 + 1
def get(url):
    for t in range(6):
        try: return json.loads(urllib.request.urlopen(url, timeout=30).read())
        except urllib.error.HTTPError as e:
            if e.code in (400, 404): return None
            time.sleep(3 * (t + 1))
        except Exception: time.sleep(3 * (t + 1))
    return None
for s in syms:
    fn = os.path.join(out, f"mark1m_{s}.npy")
    if os.path.exists(fn): continue
    arr = np.full((T, 4), np.nan, dtype=np.float32); st = t0
    while st < now:
        r = get(f"https://fapi.binance.com/fapi/v1/markPriceKlines?symbol={s}USDT&interval=1m&startTime={st}&limit=1500")
        time.sleep(0.8)
        if not r: break
        for row in r:
            i = (int(row[0]) - t0) // 60000
            if 0 <= i < T: arr[i] = [float(row[1]), float(row[2]), float(row[3]), float(row[4])]
        st = int(r[-1][0]) + 60000
        if len(r) < 1500: break
    np.save(fn, arr); print(s, int(np.isfinite(arr[:, 3]).sum()), "/", T, flush=True)
