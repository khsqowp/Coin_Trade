"""Small reusable robustness checks; functions accept caller-supplied signals/data."""
from __future__ import annotations
from collections import defaultdict
from typing import Callable, Sequence

def cost_x2(returns:Sequence[float], base_cost:float)->list[float]:
    return [r-base_cost for r in returns]

def delayed_entries(entries:Sequence[int])->list[int]: return [i+1 for i in entries]

def bear_year_check(yearly_returns:dict[int,float])->dict[int,bool|None]:
    return {year:(yearly_returns[year]>=0 if year in yearly_returns else None) for year in (2018,2022)}

def unused_symbol_group(returns:dict[str,float], group:Sequence[str])->dict[str,float|None]:
    return {s:returns.get(s) for s in group}

def yearly_concentration(daily_pnl:dict[int,float])->dict[int,float]:
    total=sum(daily_pnl.values())
    by=defaultdict(float)
    for stamp,value in daily_pnl.items():by[stamp//10000]+=value
    return {y:(v/total if total else float('nan')) for y,v in sorted(by.items())}

def flatness(neighbor_returns:Sequence[float], winner:float)->tuple[int,int,bool|None]:
    if not neighbor_returns:return (0,0,None)
    passed=sum(x>=winner*.5 for x in neighbor_returns)
    return passed,len(neighbor_returns),passed/len(neighbor_returns)>=.7

def causality(signal_fn:Callable, bars:Sequence, cutoff:int, mutate_future:Callable)->bool:
    """Return true iff prefix signals are invariant after arbitrary future mutation."""
    base=signal_fn(bars)
    changed=list(bars); mutate_future(changed,cutoff)
    altered=signal_fn(changed)
    before=lambda xs:[x for x in xs if getattr(x,'index',getattr(x,'signal_index',-1))<=cutoff]
    return before(base)==before(altered)
