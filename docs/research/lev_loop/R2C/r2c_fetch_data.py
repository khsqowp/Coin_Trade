"""R2C data fetch (public data.binance.vision only, no keys). Usage:
  python r2c_fetch_data.py daily            -> data/daily_1d.csv.gz  (date,sym,close,qv) for every USDT perp with monthly 1d klines
  python r2c_fetch_data.py hourly SYMLIST   -> raw/h/<SYM>.npz (ts,o,h,l,c) and raw/f/<SYM>.npz (ts,rate); months limited to listing range
Raw cache dir RAW (zip bytes are parsed on the fly; only parsed arrays are cached)."""
import io, json, os, sys, zipfile, urllib.request, urllib.parse, time
import numpy as np
from concurrent.futures import ThreadPoolExecutor
HERE = os.path.dirname(os.path.abspath(__file__))
B = "https://data.binance.vision/data/futures/um/monthly"
RAW = os.environ.get("R2C_RAW", os.path.join(HERE, "raw"))

def get(url):
    for t in range(6):
        try:
            return urllib.request.urlopen(urllib.parse.quote(url, safe=":/"), timeout=60).read()
        except urllib.error.HTTPError as e:
            if e.code == 404: return None
            time.sleep(1 + t)
        except Exception:
            time.sleep(1 + t)
    print("WARN fetch failed", url, flush=True); return None

def parse(zbytes):
    z = zipfile.ZipFile(io.BytesIO(zbytes)); txt = z.read(z.namelist()[0]).decode()
    rows = [l.split(",") for l in txt.strip().split("\n")]
    if rows and not rows[0][0].isdigit(): rows = rows[1:]
    return rows

def months(a, b):
    y, m = int(a[:4]), int(a[5:])
    out = []
    while f"{y}-{m:02d}" <= b:
        out.append(f"{y}-{m:02d}"); m += 1
        if m == 13: y += 1; m = 1
    return out

def one_klines(args):
    sym, iv, mo = args
    zb = get(f"{B}/klines/{sym}/{iv}/{sym}-{iv}-{mo}.zip")
    return mo, (parse(zb) if zb else [])

def one_fund(args):
    sym, mo = args
    zb = get(f"{B}/fundingRate/{sym}/{sym}-fundingRate-{mo}.zip")
    return mo, (parse(zb) if zb else [])

def do_daily():
    S = json.load(open(os.path.join(HERE, "data/symbols_all.json")))
    syms = [k for k in sorted(S) if k.endswith("USDT") and "_" not in k and k.isascii() and k.isalnum()]
    jobs = [(s, "1d", m) for s in syms for m in months(S[s][0], S[s][1])]
    print(len(syms), "symbols", len(jobs), "files", flush=True)
    out = {}
    with ThreadPoolExecutor(32) as ex:
        for n, (job, (mo, rows)) in enumerate(zip(jobs, ex.map(one_klines, jobs))):
            out.setdefault(job[0], []).extend((int(r[0]), float(r[4]), float(r[7])) for r in rows)
            if n % 5000 == 0: print(n, flush=True)
    import gzip
    with gzip.open(os.path.join(HERE, "data/daily_1d.csv.gz"), "wt") as f:
        f.write("date,sym,close,qv\n")
        for s in syms:
            for t, c, q in sorted(set(out.get(s, []))):
                f.write(f"{time.strftime('%Y-%m-%d', time.gmtime(t/1000))},{s},{c},{q}\n")

def do_hourly(symfile):
    S = json.load(open(os.path.join(HERE, "data/symbols_all.json")))
    plan = json.load(open(symfile)); syms = sorted(plan)
    os.makedirs(RAW + "/h", exist_ok=True); os.makedirs(RAW + "/f", exist_ok=True)
    todo = [s for s in syms if not os.path.exists(f"{RAW}/h/{s}.npz")]
    print(len(syms), "symbols,", len(todo), "to fetch", flush=True)
    for k, s in enumerate(todo):
        ms = months(max(S[s][0], plan[s][0]), min(S[s][1], plan[s][1]))
        with ThreadPoolExecutor(16) as ex:
            kl = list(ex.map(one_klines, [(s, "1h", m) for m in ms]))
            fu = list(ex.map(one_fund, [(s, m) for m in ms]))
        rows = [r for _, rr in kl for r in rr]
        a = np.array([[float(r[0]), float(r[1]), float(r[2]), float(r[3]), float(r[4])] for r in rows]) if rows else np.zeros((0, 5))
        fr = [r for _, rr in fu for r in rr]
        f = np.array([[float(r[0]), float(r[2])] for r in fr]) if fr else np.zeros((0, 2))
        np.savez_compressed(f"{RAW}/f/{s}.npz", f=f)
        np.savez_compressed(f"{RAW}/h/{s}.npz", a=a)
        print(k, s, len(a), len(f), flush=True)

if __name__ == "__main__":
    if sys.argv[1] == "daily": do_daily()
    else: do_hourly(sys.argv[2])
