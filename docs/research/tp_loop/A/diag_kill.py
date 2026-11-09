import sys, os; sys.path.insert(0, os.path.dirname(__file__))
exec(open(os.path.join(os.path.dirname(os.path.abspath(__file__)), "run.py")).read().split("# ---------------------------------------------------------------- V0 replication")[0])
def kill_days(r):
    tr = r["trades"]; return sorted(set(int(d) for d in tr[tr[:,4]==3,3]))
for env in "AB":
  for nm,rl in (("V0",runs(env)),("T09",runs(env,"T09"))):
    for ph in range(3):
        print(env,nm,ph,[str(S.days[d].date()) for d in kill_days(rl[ph])])
tr=runs("A","T09")[0]["trades"]; m=tr[:,4]==1
for row in tr[m][:12]: print(S.days[int(row[3])].date(), NAMES[int(row[0])], "entry",S.days[int(row[2])].date(), "hr",int(row[10]), "pnl/eq %.4f"%(row[5]/row[6]))
