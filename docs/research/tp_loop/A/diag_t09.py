import sys, os; sys.path.insert(0, os.path.dirname(__file__))
exec(open(os.path.join(os.path.dirname(os.path.abspath(__file__)), "run.py")).read().split("# ---------------------------------------------------------------- V0 replication")[0])
import collections
b = runs("A"); t = runs("A","T09")
for ph in range(3):
    eb, et = b[ph]["eq"].dropna(), t[ph]["eq"].dropna()
    yb = eb.groupby(eb.index.year).last().pct_change(); yt = et.groupby(et.index.year).last().pct_change()
    print(ph, "V0 yr", (eb.groupby(eb.index.year).last()/eb.groupby(eb.index.year).first()).round(2).to_dict())
    print(ph, "T09 yr", (et.groupby(et.index.year).last()/et.groupby(et.index.year).first()).round(2).to_dict())
    tr = t[ph]["trades"]; m = tr[:,4]==1
    c = collections.Counter(NAMES[int(j)] for j in tr[m,0]); print(" TP by symbol", c.most_common(8), "by year", collections.Counter(S.days[int(d)].year for d in tr[m,3]))
    print(" TP ret on notional: mean %.3f"%np.mean(tr[m,5]/tr[m,7]))
# per-phase windows
for env in "AB":
    for ph in range(3):
        for w in ("IS","OOS"):
            ab=WINS[w]; mb=window_metrics(runs(env)[ph],*ab); mt=window_metrics(runs(env,"T09")[ph],*ab)
            print(env,ph,w,"V0 cagr %.2f imdd %.2f cal %.2f | T09 cagr %.2f imdd %.2f cal %.2f"%(mb["cagr"],mb["imdd"],mb["cagr"]/mb["imdd"],mt["cagr"],mt["imdd"],mt["cagr"]/mt["imdd"]))
# short-trade extremes: how many short trades exceed 40% gain in V0 and what is their post-move
tr=np.vstack([r["trades"] for r in b]); sh=(tr[:,1]<0); gain=(tr[:,6]*0+ (tr[:,8]-tr[:,9])/tr[:,8])
print("V0 short trades with >=40%% gross gain at exit: %d of %d"%(((gain>=.4)&sh).sum(), sh.sum()))
