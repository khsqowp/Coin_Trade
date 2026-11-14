"""Data QC for the v2 panel (no strategy computed): coverage, delisted share, limit-breaching jumps (possible unadjusted corporate actions)."""
import json
from pathlib import Path
import numpy as np, pandas as pd

KR = Path("/app/kr")
U = pd.read_csv(KR / "universe" / "universe_raw.csv", dtype=str)
log = [json.loads(l) for l in open(KR / "fetch_log.jsonl")]
L = pd.DataFrame(log)
print("logged", len(L), "errors", int(L.get("error", pd.Series(dtype=str)).notna().sum()), "zero-row", int((L.get("rows") == 0).sum()))
print("by status:", L.groupby("status").size().to_dict())
jumps, rows = [], []
for p in sorted((KR / "data").glob("*.parquet")):
    d = pd.read_parquet(p)
    r = d["close"].pct_change()
    lim = np.where(d.index < "2015-06-15", 0.155, 0.305)
    bad = r.abs() > lim
    # the first session after a halt can legitimately gap: only count jumps where the previous session traded the day before
    gap = d.index.to_series().diff().dt.days.fillna(1) > 7
    bad = bad & ~gap.values
    if bad.any():
        jumps.append((p.stem, int(bad.sum()), str(r[bad].index[0].date()), round(float(r[bad].iloc[0]), 3)))
    rows.append((p.stem, len(d), (d["volume"] == 0).mean()))
print("files", len(rows), "names with limit-breaching non-gap jumps:", len(jumps))
for j in sorted(jumps, key=lambda x: -abs(x[3]))[:25]:
    print("  ", j)
# Addendum A2 market-transfer pairs share a code; a listed leg takes precedence over its delisted leg.
st = U.groupby("code")["status"].apply(lambda s: "listed" if (s == "listed").any() else "delisted")
dl = [r for r in rows if st.get(r[0]) == "delisted"]
print("delisted files", len(dl), "median rows", int(np.median([r[1] for r in dl])) if dl else 0)
