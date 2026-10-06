"""Array portfolio engine: causal open allocations and entry-bar risk checks.

Same hold convention as volume_spike: entry index + hold_days, close exit.
Extensions are isolated so historical volume-spike results remain reproducible.
"""
import numpy as np
import pandas as pd


def prepare(prepped):
    dates=sorted(set().union(*(df.index for df in prepped.values())))
    keys=sorted(prepped)
    fields=['Open','High','Low','Close','SIGNAL','VOL_RATIO','ATR14','STOP_LEVEL']
    arrays={f:np.array([prepped[k][f].reindex(dates).to_numpy(dtype=float) for k in keys]).T for f in fields}
    return dates,keys,arrays


def simulate_portfolio(prepped, top_k=8, hold_days=20, stop_pct=0., fee_pct_one_way=.04,
                       btc_ok=None, tp_pct=0., *, timing='next_open', stop='none',
                       tp='none', selection='rank', prepared=None):
    dates,keys,a=prepared or prepare(prepped)
    fee=fee_pct_one_way/100; cash=1.; positions={}; curve=[]; trades=0
    # Last valid close preserves mark-to-market across missing bars.
    marks=np.zeros(len(keys)); stops=0; profits=0
    for i,d in enumerate(dates):
        op,hi,lo,cl=(a[f][i] for f in ['Open','High','Low','Close'])
        def sell(k,price):
            nonlocal cash,trades
            cash+=positions[k]['qty']*price*(1-fee); del positions[k]; trades+=1
        # Opening gap stops may free cash at open. Intraday exits never fund same-open entries.
        for k in list(positions):
            p=positions[k]
            if np.isfinite(op[k]) and p['sl']>0 and op[k]<=p['sl']:
                sell(k,op[k]); stops+=1
        s=i-(2 if timing=='confirm_open' else 1)
        if s>=0 and (btc_ok is None or btc_ok.get(dates[s],False)):
            candidates=[k for k in range(len(keys)) if k not in positions and a['SIGNAL'][s,k]==1 and np.isfinite(op[k]) and op[k]>0]
            if timing=='confirm_open':
                candidates=[k for k in candidates if a['Close'][i-1,k]>a['Close'][s,k]]
            if selection=='rank':
                candidates.sort(key=lambda k:(-a['VOL_RATIO'][s,k],keys[k]))
                candidates=candidates[:max(0,top_k-len(positions))]
            # All: retain all candidates, equal split of free cash; no symbol ranking/cap.
            mtm=cash+sum(p['qty']*(op[k] if np.isfinite(op[k]) else marks[k]) for k,p in positions.items())
            budget=cash/len(candidates) if candidates and selection=='all' else mtm/top_k
            for k in candidates:
                alloc=min(cash,budget)
                if alloc<=1e-12: break
                price=op[k]; sl=price*(1-stop_pct) if stop_pct else 0.
                if stop.startswith('pct'): sl=price*(1-float(stop[3:])/100)
                elif stop.startswith('atr'): sl=price-float(stop[3:])*a['ATR14'][s,k]
                elif stop=='structure': sl=a['STOP_LEVEL'][s,k]
                if (stop != 'none' or stop_pct > 0) and (not np.isfinite(sl) or sl <= 0):
                    continue  # unavailable protective level must not become an unprotected trade
                if sl>=price: continue  # invalid protective structure, skip entry
                target=price*(1+tp_pct) if tp_pct else 0.
                if tp.startswith('pct'): target=price*(1+float(tp[3:])/100)
                positions[k]={'qty':alloc*(1-fee)/price,'sl':sl,'target':target,'exit':i+hold_days}
                cash-=alloc
        for k in list(positions):
            if not np.isfinite(cl[k]): continue
            p=positions[k]
            if p['sl']>0 and lo[k]<=p['sl']:
                sell(k,min(op[k],p['sl'])); stops+=1
            elif p['target']>0 and hi[k]>=p['target']:
                sell(k,max(op[k],p['target'])); profits+=1
            elif i>=p['exit'] or i==len(dates)-1:
                sell(k,cl[k])
        valid=np.isfinite(cl); marks[valid]=cl[valid]
        curve.append(cash+sum(p['qty']*marks[k] for k,p in positions.items()))
    equity=pd.Series(curve,index=dates); years=(dates[-1]-dates[0]).days/365.25
    daily=equity.pct_change().dropna()
    return dict(cagr=(equity.iloc[-1]**(1/years)-1)*100,
                mdd=((equity.cummax()-equity)/equity.cummax()).max()*100,
                sharpe=daily.mean()/daily.std()*np.sqrt(365) if daily.std()>0 else 0.,
                trades=trades,stopped=stops,tp_hit=profits,final=equity.iloc[-1],
                start=str(dates[0]),end=str(dates[-1]),years=years)
