"""R2C descriptive universe / survivorship statistics (no strategy results)."""
import os, sys
sys.path.insert(0, "/Users/user/Desktop/CODE/Ochestration/trading"); sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import numpy as np, pandas as pd
HERE = os.path.dirname(os.path.abspath(__file__))
d = pd.read_csv(os.path.join(HERE, "data/daily_1d.csv.gz"), parse_dates=["date"]); last = d.groupby("sym").date.max(); first = d.groupby("sym").date.min()
m = pd.read_csv(os.path.join(HERE, "data/pit_membership.csv.gz"))
print("USDT-perp symbols with 1d klines (ascii):", d.sym.nunique(), "| ever PIT members:", m.sym.nunique(), "| member-months:", len(m))
dead = sorted([s for s in set(m.sym) if last[s] < pd.Timestamp("2026-08-31")], key=lambda s: last[s])
print("PIT members whose data ended before 2026-08-31 (delisted/renamed/migrated):", len(dead))
print([(s, str(last[s].date())) for s in dead])
m["dead"] = m.sym.isin(dead)
m["yr"] = m.month.str[:4]
print("share of PIT member-months by year belonging to symbols that later died/delisted:")
print(m.groupby("yr").dead.mean().round(3).to_dict())
mm = m[m.month < "2022-01"]
print("NEW period (<2022-01): member-months", len(mm), "dead-later share", round(mm.dead.mean(), 3), "distinct members", mm.sym.nunique(), "dead", mm[mm.dead].sym.nunique())
# lookahead in OLD 45: fraction of OLD symbol-months in which the symbol was NOT a PIT member that month
old = ["BTC","ETH","BNB","XRP","SOL","TRX","DOGE","ZEC","LINK","XMR","ADA","XLM","BCH","LTC","HBAR","AVAX","SUI","UNI","NEAR","TAO","AAVE","ONDO","THETA","DOT","ENA","WLD","ICP","ETC","POL","QNT","ALGO","ATOM","RENDER","JUP","ARB","FIL","VET","CAKE","LDO","CRV","INJ","OP","APT","IMX","STX"]
oldu = {o + "USDT" for o in old}
mo = m[(m.month >= "2022-01") & (m.month <= "2026-09")]
print("OLD 45 vs PIT top-45 in 2022-01..2026-09: PIT member-months that are in OLD 45:", round(mo.sym.isin(oldu).mean(), 3), "| OLD 45 that were ever PIT members 2022+:", len(oldu & set(mo.sym)), "of 45")
avg_overlap = mo.groupby("month").apply(lambda g: g.sym.isin(oldu).sum()).describe()
print("per-month overlap |PIT45 ∩ OLD45|: min/median/max", int(avg_overlap["min"]), int(avg_overlap["50%"]), int(avg_overlap["max"]))
for mon in ("2022-01", "2023-01", "2024-01", "2025-01", "2026-01"):
    g = mo[mo.month == mon]; print(mon, "overlap", int(g.sym.isin(oldu).sum()), "PIT not in OLD (sample):", list(g[~g.sym.isin(oldu)].sym.head(8)))
