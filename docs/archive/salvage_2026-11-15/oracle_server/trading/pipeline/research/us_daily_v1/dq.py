"""Data-quality checks for the US daily cache (no strategy computation here)."""
import json
import sys

import numpy as np
import pandas as pd

from tp import usdata

ETFS = ["SPY", "QQQ", "DIA", "IWM", "MDY", "XLB", "XLE", "XLF", "XLI", "XLK", "XLP", "XLU", "XLV", "XLY"]
out = {}
spy = usdata.load("SPY")
ref = spy.index
for s in ETFS + ["^IRX", "^GSPC", "^SP500TR"]:
    d = usdata.load(s)
    rep = usdata.validate(d, ref_dates=ref if s in ETFS else None)
    if s in ("^IRX", "^GSPC", "^SP500TR"):
        rep.pop("adj_factor_jumps_gt_5pct", None)
    out[s] = rep

# SPY total return (adjclose) vs S&P 500 total-return index, calendar years
tr = usdata.load("^SP500TR")["close"]
sa = spy["adjclose"]
yr = pd.DataFrame({"SPY_adj": sa.resample("YE").last().pct_change(), "SP500TR": tr.resample("YE").last().pct_change()}).dropna()
yr["diff"] = yr["SPY_adj"] - yr["SP500TR"]
out["spy_vs_sp500tr_yearly"] = {str(i.year): [round(a, 4), round(b, 4), round(c, 4)] for i, (a, b, c) in yr.iterrows()}
out["spy_vs_sp500tr_mean_annual_diff"] = round(float(yr.loc["2000":, "diff"].mean()), 5)
j = pd.concat([sa.pct_change(), tr.pct_change()], axis=1).dropna()
j = j.loc["2000":]
out["spy_vs_sp500tr_daily_corr"] = round(float(j.corr().iloc[0, 1]), 6)
out["spy_vs_sp500tr_daily_absdiff_p99"] = round(float((j.iloc[:, 0] - j.iloc[:, 1]).abs().quantile(0.99)), 5)
# SPY split-adjusted close vs ^GSPC (price index): ratio should be smooth ~1/10
g = usdata.load("^GSPC")["close"]
ratio = (spy["close"] / g).dropna().loc["2000":]
out["spy_close_over_gspc_min_max"] = [round(float(ratio.min()), 5), round(float(ratio.max()), 5)]
# IRX sanity
irx = usdata.load("^IRX")["close"]
out["irx_range_pct"] = [round(float(irx.loc["1999":].min()), 3), round(float(irx.loc["1999":].max()), 3)]
out["irx_missing_vs_spy_since_1999"] = int(len(ref[ref >= "1999-01-01"].difference(irx.index)))
out["irx_nan"] = int(irx.isna().sum())
# implied dividend yield check of sector ETFs (adj factor drift per year should be ~1-4%)
dy = {}
for s in ETFS:
    d = usdata.load(s).loc["2000":]
    f = d["adjclose"] / d["close"]
    yrs = (d.index[-1] - d.index[0]).days / 365.25
    dy[s] = round(float((f.iloc[-1] / f.iloc[0]) ** (1 / yrs) - 1), 4)
out["implied_avg_div_yield_from_adj_factor"] = dy
json.dump(out, open(sys.argv[1], "w"), indent=1, default=str)
for k, v in out.items():
    if k != "spy_vs_sp500tr_yearly":
        print(k, v if not isinstance(v, dict) or len(str(v)) < 400 else {kk: {x: y for x, y in vv.items() if x not in ("extreme_moves",)} | {"n_extreme": len(vv.get("extreme_moves", []))} if isinstance(vv, dict) else vv for kk, vv in v.items()})
    else:
        print(k, {a: b for a, b in v.items() if abs(b[2]) > 0.003})
