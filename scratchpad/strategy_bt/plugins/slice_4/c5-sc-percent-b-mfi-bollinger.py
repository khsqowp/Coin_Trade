import numpy as np,pandas as pd
from common.indicators import bollinger
SPEC_ID="c5-sc-percent-b-mfi-bollinger"
PARAMS={"bb_len":20,"mfi_len":14,"sar_af":.02,"sar_max":.2}; PARAM_GRID={"bb_len":[20],"mfi_len":[14]}
TIMEFRAMES=["1h","4h"]
SIDES="both"
DEVIATIONS=["MFI period 14 is the archived implementation note assumption.","Parabolic SAR uses Wilder-style AF step .02/max .20 calculated from OHLC; no separate SAR library is in common.","No same-bar reversal is possible in the harness."]
IMPLEMENTED_FIELDS=["entry_long","entry_short","exit","stop_loss","timeframes","filters"]
def _sar(h,l,af_step,af_max):
 n=len(h); out=np.full(n,np.nan)
 if n<2:return out
 bull=(h[1]+l[1])>=(h[0]+l[0]); ep=h[0] if bull else l[0]; sar=l[0] if bull else h[0]; af=af_step
 for i in range(1,n):
  projected=sar+af*(ep-sar)
  if bull:
   projected=min(projected,l[i-1],l[i-2] if i>=2 else l[i-1])
   if l[i]<projected:
    bull=False; sar=ep; ep=l[i]; af=af_step
   else:
    sar=projected
    if h[i]>ep:ep=h[i]; af=min(af+af_step,af_max)
  else:
   projected=max(projected,h[i-1],h[i-2] if i>=2 else h[i-1])
   if h[i]>projected:
    bull=True; sar=ep; ep=h[i]; af=af_step
   else:
    sar=projected
    if l[i]<ep:ep=l[i]; af=min(af+af_step,af_max)
  out[i]=sar
 return out
def signals(df,bb_len=20,mfi_len=14,sar_af=.02,sar_max=.2,**kw):
 c=df.close.to_numpy(float); h=df.high.to_numpy(float); l=df.low.to_numpy(float); v=df.volume.to_numpy(float); mid,up,lo=bollinger(c,int(bb_len),2); b=(c-lo)/(up-lo); tp=(h+l+c)/3; flow=tp*v; pos=np.r_[False,tp[1:]>tp[:-1]]; neg=np.r_[False,tp[1:]<tp[:-1]]; ps=pd.Series(np.where(pos,flow,0.)).rolling(int(mfi_len),min_periods=int(mfi_len)).sum().to_numpy(); ns=pd.Series(np.where(neg,flow,0.)).rolling(int(mfi_len),min_periods=int(mfi_len)).sum().to_numpy(); mfi=100-100/(1+ps/ns); mfi=np.where(ns==0,100,mfi);
 hi=(b>.8)&(mfi>80); low=(b<.2)&(mfi<20); prevhi=np.r_[False,hi[:-1]]; prevlo=np.r_[False,low[:-1]]; le=hi&~prevhi; se=low&~prevlo; sar=_sar(h,l,float(sar_af),float(sar_max));
 return pd.DataFrame({"long_entry":le,"short_entry":se,"long_exit":low|((c<sar)&np.isfinite(sar)),"short_exit":hi|((c>sar)&np.isfinite(sar))},index=df.index).fillna(False)
