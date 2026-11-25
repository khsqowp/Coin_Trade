import csv, json, sys, statistics as st
from collections import defaultdict
csv.field_size_limit(sys.maxsize)
rows = [r for r in csv.DictReader(open(sys.argv[1], encoding="utf-8")) if r["status"] == "scored"]
cfg_keys = ["timeframe", "trigger", "smoothing", "ratio_source", "mode", "reward_r", "horizon_bars", "funding_threshold", "z_threshold", "oi_window_bars", "premium_window_bars", "imbalance_window_bars", "oi_drop_threshold", "compression_percentile", "oi_z_threshold"]
def fl(v):
    try: return float(v)
    except Exception: return None
for fam in sorted({r["family"] for r in rows}):
    rs = [r for r in rows if r["family"] == fam]
    print("==", fam)
    for key in cfg_keys:
        vals = {}
        for r in rs:
            d = json.loads(r["definition"]) if "definition" in r and r.get("definition") else None
            v = r.get(key)
            if v in (None, ""): continue
            vals.setdefault(v, []).append(fl(r["expectancy_bps"]) or 0)
        if len(vals) > 1:
            print("  ", key, {k: (len(v), round(st.median(v), 1), sum(1 for x in v if x > 0)) for k, v in vals.items()})
