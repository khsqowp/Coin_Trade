"""R2C step 2: point-in-time (PIT) universe from daily klines (data/daily_1d.csv.gz).
RULE (frozen in prereg.md): on the first UTC day M of each month, eligible = USDT-M perps with first daily bar <= M - AGE_MIN=14 days and
>= 5 daily bars in [M-30, M-1], excluding index/basket perps; ranked by mean daily quote volume over [M-30, M-1] (missing day = 0);
member for all days of month M = top N=45. Uses only data strictly before M (no look-ahead). Dead/delisted symbols are included while
they still have data. Outputs data/pit_membership.csv.gz (month,sym,rank,adv30) and data/pit_symbols.json."""
import gzip, json, os, sys
import numpy as np, pandas as pd
HERE = os.path.dirname(os.path.abspath(__file__))
N_TOP, AGE_MIN = 45, 14
EXCL = {"BTCDOMUSDT", "DEFIUSDT", "USDCUSDT", "FOOTBALLUSDT", "BLUEBIRDUSDT"}

def main(first="2020-02-01", last="2026-09-01"):
    d = pd.read_csv(os.path.join(HERE, "data/daily_1d.csv.gz"), parse_dates=["date"])
    d = d[~d.sym.isin(EXCL)]
    qv = d.pivot_table(index="date", columns="sym", values="qv", aggfunc="last")
    qv = qv.reindex(pd.date_range(qv.index.min(), qv.index.max(), freq="D"))
    first_day = d.groupby("sym").date.min()
    rows = []
    for M in pd.date_range(first, last, freq="MS"):
        w = qv.loc[M - pd.Timedelta(days=30): M - pd.Timedelta(days=1)]
        cnt = w.notna().sum()
        ok = [s for s in w.columns if cnt[s] >= 5 and first_day[s] <= M - pd.Timedelta(days=AGE_MIN)]
        adv = w[ok].fillna(0).mean().sort_values(ascending=False).head(N_TOP)
        for r, (s, v) in enumerate(adv.items()):
            rows.append((M.strftime("%Y-%m"), s, r + 1, float(v), len(ok)))
    out = pd.DataFrame(rows, columns=["month", "sym", "rank", "adv30", "n_eligible"])
    out.to_csv(os.path.join(HERE, "data/pit_membership.csv.gz"), index=False)
    syms = sorted(out.sym.unique())
    # hourly fetch plan: per symbol month range = [first member month - 1, last member month + 1] (lookback / ffill margin)
    plan = {}
    for s_, g_ in out.groupby("sym"):
        ms = sorted(g_.month)
        a = (pd.Period(ms[0], "M") - 1).strftime("%Y-%m"); b = (pd.Period(ms[-1], "M") + 1).strftime("%Y-%m")
        plan[s_] = [a, b]
    json.dump(plan, open(os.path.join(HERE, "data/pit_symbols.json"), "w"), indent=0, sort_keys=True)
    g = out.groupby("month").size()
    print("months", len(g), "distinct PIT symbols", len(syms))
    print(out.groupby("month").agg(n=("sym", "size"), nel=("n_eligible", "first")).iloc[[0, 1, 2, 3, 4, 6, 9, 12, 18, 24, 36, 48, 60, 72]].T.to_string())
if __name__ == "__main__":
    main()
