"""A1 step 1: per-row TEST daily PnL series (pct of capital, summed over symbols, bucketed by exit date, UTC)."""
import sys, json
from multiprocessing import Pool
import pandas as pd
from lib import *

def one(r):
    sid, tf = r["strategy_id"], r["timeframe"]
    try:
        params = json.loads(r["params"])
        res, _ = run_row(sid, tf, params)
        recs = [(ts[t["exit"]].floor("D"), t["pct"]) for tr, _, ts in res.values() for t in tr]
        s = pd.Series(dict(), dtype=float) if not recs else pd.DataFrame(recs).groupby(0)[1].sum()
        return (sid, tf), s, total_pct(res), float(r["test_return"]), None
    except Exception as e:
        return (sid, tf), None, None, float(r["test_return"] or 0), repr(e)

if __name__ == "__main__":
    rows = [r for r in load_summary() if r["status"] == "DONE"]
    with Pool(6) as p:
        out = p.map(one, rows, chunksize=1)
    series, meta = {}, []
    for k, s, tot, ref, err in out:
        meta.append(dict(strategy_id=k[0], timeframe=k[1], rerun_test_return=tot, summary_test_return=ref, error=err))
        if s is not None:
            series[f"{k[0]}|{k[1]}"] = s
    cal = pd.date_range(min(s.index.min() for s in series.values()), max(s.index.max() for s in series.values()), freq="D")
    M = pd.DataFrame({k: s.reindex(cal).fillna(0.0) for k, s in series.items()})
    M.index.name = "date"; M.to_csv(HERE / "a1_daily_pnl_matrix.csv")
    pd.DataFrame(meta).to_csv(HERE / "a1_rows_reproduction.csv", index=False)
    print(M.shape, "errors:", sum(m["error"] is not None for m in meta))
