"""Regime scan on 069500 ONLY (benchmark path; no strategy computed). Zigzag 20% swings + monthly closes + data QC on all fetched files."""
import pandas as pd
from pathlib import Path

D = Path("/app/kr/data")
x = pd.read_parquet(D / "069500.parquet")["close"]
x.index = x.index.tz_convert(None)
# zigzag with 20% reversal threshold
piv, mode, ext_i = [], None, x.index[0]
for t, v in x.items():
    if mode is None:
        if v >= x[ext_i] * 1.2: mode = "up"; piv.append(("trough", ext_i, x[ext_i])); ext_i = t
        elif v <= x[ext_i] * 0.8: mode = "dn"; piv.append(("peak", ext_i, x[ext_i])); ext_i = t
        continue
    if mode == "up":
        if v > x[ext_i]: ext_i = t
        elif v <= x[ext_i] * 0.8: piv.append(("peak", ext_i, x[ext_i])); mode = "dn"; ext_i = t
    else:
        if v < x[ext_i]: ext_i = t
        elif v >= x[ext_i] * 1.2: piv.append(("trough", ext_i, x[ext_i])); mode = "up"; ext_i = t
piv.append(("last-extreme(" + mode + ")", ext_i, x[ext_i]))
prev = None
for k, t, v in piv:
    ch = "" if prev is None else "  %+.1f%% over %d days" % ((v / prev[1] - 1) * 100, (t - prev[0]).days)
    print("%-22s %s %9.0f%s" % (k, t.date(), v, ch)); prev = (t, v)
m = x.resample("ME").last()
print("\nmonth-end closes (2011+):")
yr = m.loc["2011":]
for y in sorted(set(yr.index.year)):
    s = yr[yr.index.year == y]
    print(y, " ".join("%6.0f" % v for v in s.values))
# 12-month rolling band test: max/min within +/-15% of mean
print("\n12m windows where (max/mean-1)<=0.15 and (1-min/mean)<=0.15 (start months):")
mm = m.loc["2011":]
ok = []
for i in range(len(mm) - 11):
    w = mm.iloc[i:i + 12]
    if w.max() / w.mean() - 1 <= 0.15 and 1 - w.min() / w.mean() <= 0.15:
        ok.append(str(mm.index[i].date())[:7])
print(" ".join(ok))
print("\nQC:")
for p in sorted(D.glob("*.parquet")):
    d = pd.read_parquet(p)
    r = d["close"].pct_change().abs()
    print(p.stem, len(d), d.index[0].date(), d.index[-1].date(), "zero/neg close:", int((d["close"] <= 0).sum()),
          "open==0:", int((d["open"] <= 0).sum()), "max|ret|: %.3f on %s" % (r.max(), r.idxmax().date()), "dup:", int(d.index.duplicated().sum()))
