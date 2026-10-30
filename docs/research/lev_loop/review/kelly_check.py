import numpy as np, pandas as pd
import indep_sim as s
d0=int(s.DAYS.searchsorted(pd.Timestamp("2022-01-01",tz="UTC")))
oos=int(s.DAYS.searchsorted(pd.Timestamp("2024-07-01",tz="UTC")))
F=np.arange(0.5,12.01,0.25)
R=[]
for ph in range(3):
    r=s.run(lev=1.0,dep=1.0,phase=ph,kill=1.0,cool=0)
    e=r["eq"]; R.append(e)
E=np.array(R)
def stats(a,b):
    out=[]
    for e in E:
        x=e[a:b]; x=x[np.isfinite(x)]; out.append(np.diff(x)/x[:-1])
    r=np.concatenate(out); 
    mu=r.mean()*365; var=r.var()*365
    g=np.array([365*np.mean(np.log1p(np.clip(f*r,-0.999999,None))) for f in F])
    return mu,np.sqrt(var),mu/var,F[g.argmax()],{f:round(float(g[list(F).index(f)]),3) for f in (1,2,3,4,5,6,8)}
for nm,(a,b) in (("IS",(d0,oos)),("OOS",(oos,s.ND)),("FULL",(d0,s.ND))):
    mu,sd,fc,fs,gg=stats(a,b); print(nm,f"mu {mu:.3f} sigma {sd:.3f} f_cont {fc:.2f} f* {fs}",gg)
