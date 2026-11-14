import sys, json
sys.path.insert(0, "/app/src")
from tp import bench
p, t = bench.dataqa_case()
print({k: t[k] for k in ("up_days", "avg_volume", "last_close", "window_return_pct")})
r = json.load(open("/app/runs/bench/claude-haiku-5-5/results.json"))["dataqa"]
for x in r: print({k: x["answer"][k] for k in ("up_days", "avg_volume", "window_return_pct")})
