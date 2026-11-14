"""Fetch long daily history via tp.kis.fetch_daily (read-only quotation path) into /app/kr/data. No store.save, data/ohlcv untouched."""
import hashlib, json, sys, time
from pathlib import Path
from tp import kis

OUT = Path("/app/kr/data"); OUT.mkdir(exist_ok=True)
codes = sys.argv[1].split(",")
days = int(sys.argv[2]) if len(sys.argv) > 2 else 4800
log = {}
for c in codes:
    p = OUT / (c + ".parquet")
    if p.exists():
        print(c, "exists, skip", flush=True); continue
    t0 = time.time()
    try:
        df = kis.fetch_daily(c, days=days)
        df.to_parquet(p)
        log[c] = {"rows": len(df), "first": str(df.index[0].date()), "last": str(df.index[-1].date()),
                  "sha256": hashlib.sha256(p.read_bytes()).hexdigest(), "sec": round(time.time() - t0, 1)}
    except Exception as e:
        log[c] = {"error": str(e)[:200]}
    print(c, json.dumps(log[c]), flush=True)
with open(OUT / ("fetchlog_%d.json" % int(time.time())), "w") as f:
    json.dump(log, f, indent=1)
