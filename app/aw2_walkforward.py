"""Yearly expanding-window parameter selection and reporting for AW-2."""
from __future__ import annotations

import json
from pathlib import Path

import numpy as np
import pandas as pd


def score(curve: pd.Series) -> float:
    x=curve.dropna()
    if len(x)<50: return -np.inf
    r=x.pct_change().dropna(); dd=(x/x.cummax()-1).min()
    if -dd < .05: return float(r.mean()/r.std(ddof=1)*np.sqrt(252)) if r.std(ddof=1)>0 else -np.inf
    c=(x.iloc[-1]/x.iloc[0])**(252/len(r))-1
    return float(c/-dd)


def build(curves: list[pd.Series], params: list[dict], start_year: int, end_year: int) -> dict:
    dates=curves[0].index; yearly=[]; selected=[]; out_dates=[]; out_returns=[]
    for year in range(start_year,end_year+1):
        start=pd.Timestamp(year=year,month=1,day=1); prior=pd.Timestamp(year=year-1,month=12,day=31)
        selection_end=min(prior,pd.Timestamp("2022-12-31"))
        eligible=[i for i,c in enumerate(curves) if (c.index<=selection_end).sum()>=50]
        # Never inspect post-cutoff data to choose a parameter set. If there is
        # no adequate pre-2023 history, do not silently fall back to future data.
        if not eligible: continue
        choice=max(eligible,key=lambda i:score(curves[i].loc[curves[i].index<=selection_end]))
        span=(dates>=start)&(dates<pd.Timestamp(year=year+1,month=1,day=1))
        c=curves[choice]
        if span.any():
            vals=c.loc[span]
            returns=c.pct_change(fill_method=None).reindex(vals.index)
            for day, ret in returns.items():
                out_dates.append(day); out_returns.append(float(ret) if pd.notna(ret) else 0.0)
        yearly.append({"year":year,"selection_data_end":str(selection_end.date()),"selected_index":choice,"params":params[choice],"selection_score":score(curves[choice].loc[curves[choice].index<=selection_end]) if (curves[choice].index<=selection_end).sum()>=50 else None})
        selected.append(choice)
    wf=pd.Series((1+np.asarray(out_returns)).cumprod(),index=pd.DatetimeIndex(out_dates),dtype=float)
    endpoints=wf.groupby(wf.index.year).last(); returns=endpoints.pct_change();
    if len(returns): returns.iloc[0]=endpoints.iloc[0]-1.0
    daily=wf.pct_change().dropna(); mdd=float((wf/wf.cummax()-1).min()) if len(wf) else 0
    sharpe=float(daily.mean()/daily.std(ddof=1)*np.sqrt(252)) if len(daily)>1 and daily.std(ddof=1)>0 else None
    return {"start_year":start_year,"end_year":end_year,"yearly_selection":yearly,"annual_returns":{str(k):float(v) for k,v in returns.items()},"cagr":float(wf.iloc[-1]**(252/max(len(daily),1))-1) if len(wf)>1 else None,"mdd":abs(mdd),"sharpe":sharpe,"curve":{str(k.date()):float(v) for k,v in wf.items()},"unique_selected":len(set(selected))}


def write(path: Path, obj: dict):
    path.parent.mkdir(parents=True,exist_ok=True)
    path.write_text(json.dumps(obj,ensure_ascii=False,indent=2,allow_nan=False))
