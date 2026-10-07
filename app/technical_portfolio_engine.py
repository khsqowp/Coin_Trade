"""Array portfolio engine: causal open allocations and entry-bar risk checks.

Same hold convention as volume_spike: entry index + hold_days, close exit.
Extensions are isolated so historical volume-spike results remain reproducible.
"""
import numpy as np
import pandas as pd


def simulate_research_portfolio(prepped, **kwargs):
    """Opt-in Round11 collateralized long/short and causal allocation policies.

    Historical simulate_portfolio remains unchanged. Shorts receive positive
    funding and pay negative funding; daily research accrual is an approximation.
    """
    from app.round11_portfolio import simulate
    return simulate(prepped, **kwargs)


def prepare(prepped):
    dates=sorted(set().union(*(df.index for df in prepped.values())))
    keys=sorted(prepped)
    fields=['Open','High','Low','Close','SIGNAL','VOL_RATIO','ATR14','STOP_LEVEL']
    arrays={f:np.array([prepped[k][f].reindex(dates).to_numpy(dtype=float) for k in keys]).T for f in fields}
    return dates,keys,arrays


def simulate_portfolio(prepped, top_k=8, hold_days=20, stop_pct=0., fee_pct_one_way=.04,
                       btc_ok=None, tp_pct=0., *, timing='next_open', stop='none',
                       tp='none', selection='rank', prepared=None,
                       dd_trigger=None, dd_resume=.10, return_trace=False,
                       resume_mode='equity', cooldown_days=20, btc_resume=None,
                       sizing='equal', target_vol=.40, weight_cap=.25,
                       symbol_trade_share_cap=None, entry_scale=None,
                       strategy_data=None, active_strategy=None,
                       strategy_holds=None, liquidate_on_switch=False):
    if (strategy_data is None) != (active_strategy is None):
        raise ValueError('strategy banks and historical schedule required together')
    if strategy_data is not None and (timing != 'next_open' or sizing != 'equal'):
        raise ValueError('strategy switching supports next_open/equal only')
    if strategy_data is not None and (not strategy_data or strategy_holds is None or
            any(k not in strategy_holds or not isinstance(strategy_holds[k], int) or strategy_holds[k] < 1
                for k in strategy_data)):
        raise ValueError('positive holding period required for every strategy')
    if symbol_trade_share_cap is not None and not 0 < symbol_trade_share_cap <= 1:
        raise ValueError('symbol trade share cap must be in (0, 1]')
    if dd_trigger is not None and not 0 <= dd_resume < dd_trigger < 1:
        raise ValueError('require 0 <= dd_resume < dd_trigger < 1')
    if resume_mode not in ('equity','cooldown','btc_sma50'):
        raise ValueError('unknown resume mode')
    if cooldown_days < 1 or sizing not in ('equal','inverse_vol') or not 0 < weight_cap <= 1 or target_vol <= 0:
        raise ValueError('invalid sizing/cooldown')
    if resume_mode == 'btc_sma50' and btc_resume is None:
        raise ValueError('BTC historical trend required')
    dates,keys,a=prepared or prepare(prepped)
    if strategy_data is not None:
        for bank in strategy_data.values():
            if bank[0] != dates or bank[1] != keys:
                raise ValueError('strategy bank calendars/universes differ')
            for field in ['Open','High','Low','Close']:
                if not np.array_equal(bank[2][field],a[field],equal_nan=True):
                    raise ValueError('strategy banks must share real execution prices')
    vol = None
    if sizing == 'inverse_vol':
        vol=np.array([prepped[k].Close.pct_change(fill_method=None).rolling(20).std(ddof=1).reindex(dates).to_numpy() for k in keys]).T

    fee=fee_pct_one_way/100; cash=1.; positions={}; curve=[]; trades=0
    completed_by_symbol=np.zeros(len(keys), dtype=int)
    share_log=[]
    # Last valid close preserves mark-to-market across missing bars.
    marks=np.zeros(len(keys)); stops=0; profits=0
    peak=1.; paused=False; events=0; resumes=0; blocked_days=0; trace=[]
    paused_since=None; grace_day=-1; event_log=[]; allocations=[]
    def observe(value):
        nonlocal peak,paused,events,resumes,paused_since
        peak=max(peak,value)
        drawdown=1-value/peak
        if dd_trigger is not None:
            if paused and resume_mode == 'equity' and drawdown <= dd_resume:
                paused=False; resumes+=1
            elif not paused and i != grace_day and drawdown >= dd_trigger:
                paused=True; events+=1; paused_since=i
                event_log.append(dict(kind='pause',index=i,date=str(d),drawdown=drawdown))
        return drawdown
    for i,d in enumerate(dates):
        selected = active_strategy.get(dates[i-1]) if strategy_data is not None and i>0 else None
        if strategy_data is not None and selected is not None:
            if selected not in strategy_data:
                raise ValueError('unknown active strategy')
            a=strategy_data[selected][2]
        op,hi,lo,cl=(a[f][i] for f in ['Open','High','Low','Close'])
        def sell(k,price):
            nonlocal cash,trades
            cash+=positions[k]['qty']*price*(1-fee); del positions[k]; trades+=1
            completed_by_symbol[k]+=1
        # Opening gap stops may free cash at open. Intraday exits never fund same-open entries.
        for k in list(positions):
            p=positions[k]
            if liquidate_on_switch and strategy_data is not None and p['strategy'] != selected and np.isfinite(op[k]):
                sell(k,op[k])
            elif np.isfinite(op[k]) and p['sl']>0 and op[k]<=p['sl']:
                sell(k,op[k]); stops+=1
        # Opening valuation is known before allocation; never read today's close here.
        opening=cash+sum(p['qty']*(op[k] if np.isfinite(op[k]) else marks[k]) for k,p in positions.items())
        # Only yesterday's completed BTC bar is available at today's open.
        if paused and resume_mode != 'equity' and i > paused_since:
            ready = (i-paused_since >= cooldown_days if resume_mode == 'cooldown'
                     else bool(btc_resume.get(dates[i-1],False)))
            if ready:
                paused=False; resumes+=1; grace_day=i
                event_log.append(dict(kind='resume',index=i,date=str(d),wait=i-paused_since))
        opening_dd=observe(opening)
        entry_paused=paused
        blocked_days+=int(entry_paused)
        s=i-(2 if timing=='confirm_open' else 1)
        entry_multiplier=float(entry_scale.get(dates[s],0.)) if entry_scale is not None and s>=0 else 1.
        if not np.isfinite(entry_multiplier) or not 0 <= entry_multiplier <= 1:
            raise ValueError('entry scale must be finite in [0,1]')
        if not entry_paused and s>=0 and entry_multiplier>0 and (strategy_data is None or selected is not None) and (btc_ok is None or btc_ok.get(dates[s],False)):
            candidates=[k for k in range(len(keys)) if k not in positions and a['SIGNAL'][s,k]==1 and np.isfinite(op[k]) and op[k]>0]
            if symbol_trade_share_cap is not None:
                # Only sales already executed at this point count. Outstanding
                # positions and today's later close exits never enter this ratio.
                allowed=[]
                for k in candidates:
                    blocked=trades > 0 and completed_by_symbol[k] > symbol_trade_share_cap*trades
                    if return_trace:
                        share_log.append(dict(date=str(d),symbol=keys[k],
                                              completed_total=trades,
                                              completed_symbol=int(completed_by_symbol[k]),
                                              blocked=bool(blocked)))
                    if not blocked:
                        allowed.append(k)
                candidates=allowed
            if timing=='confirm_open':
                candidates=[k for k in candidates if a['Close'][i-1,k]>a['Close'][s,k]]
            if selection=='rank':
                candidates.sort(key=lambda k:(-a['VOL_RATIO'][s,k],keys[k]))
                candidates=candidates[:max(0,top_k-len(positions))]
            # All: retain all candidates, equal split of free cash; no symbol ranking/cap.
            mtm=cash+sum(p['qty']*(op[k] if np.isfinite(op[k]) else marks[k]) for k,p in positions.items())
            budget=cash/len(candidates) if candidates and selection=='all' else mtm/top_k
            budgets={k:budget for k in candidates}
            if sizing == 'inverse_vol' and candidates:
                # Existing holdings remain fixed; estimate whole book risk using
                # perfect positive correlation (sum w*sigma), a conservative cap.
                known=i-1
                candidates=[k for k in candidates if np.isfinite(vol[known,k]) and vol[known,k]>0]
                sigmas={k:vol[known,k]*np.sqrt(365) for k in candidates}
                risk=sum(p['qty']*(op[k] if np.isfinite(op[k]) else marks[k])/mtm *
                         (vol[known,k]*np.sqrt(365) if np.isfinite(vol[known,k]) else target_vol/weight_cap)
                         for k,p in positions.items())
                inv=sum(1/sigmas[k] for k in candidates)
                # Reserve free slot capacity when few signals arrive.
                pool=min(cash/mtm, len(candidates)/top_k)
                weights={k:min(weight_cap,pool/sigmas[k]/inv) for k in candidates}
                proposed=sum(weights[k]*sigmas[k] for k in candidates)
                scale=min(1.,max(0.,target_vol-risk)/proposed) if proposed>0 else 0.
                budgets={k:mtm*weights[k]*scale for k in candidates}
            for k in candidates:
                alloc=min(cash,budgets[k]*entry_multiplier)
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
                duration=strategy_holds[selected] if strategy_data is not None else hold_days
                positions[k]={'qty':alloc*(1-fee)/price,'sl':sl,'target':target,'exit':i+duration,
                              'entry':i,'strategy':selected}
                cash-=alloc
                if return_trace:
                    allocations.append(dict(date=str(d),symbol=keys[k],weight=alloc/mtm,known_through=str(dates[i-1])))
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
        closing=cash+sum(p['qty']*marks[k] for k,p in positions.items())
        curve.append(closing)
        closing_dd=observe(closing)
        if return_trace:
            trace.append(dict(date=str(d),opening=opening,opening_dd=opening_dd,
                              entry_paused=entry_paused,closing=closing,peak=peak,
                              closing_dd=closing_dd,paused=paused,positions=len(positions)))
    equity=pd.Series(curve,index=dates); years=(dates[-1]-dates[0]).days/365.25
    daily=equity.pct_change().dropna()
    result=dict(cagr=(equity.iloc[-1]**(1/years)-1)*100,
                mdd=((equity.cummax()-equity)/equity.cummax()).max()*100,
                sharpe=daily.mean()/daily.std()*np.sqrt(365) if daily.std()>0 else 0.,
                trades=trades,stopped=stops,tp_hit=profits,final=equity.iloc[-1],
                start=str(dates[0]),end=str(dates[-1]),years=years,
                breaker_events=events,breaker_resumes=resumes,blocked_days=blocked_days,
                breaker_paused_final=paused)
    result['breaker_log']=event_log
    result['paused_age_final']=len(dates)-1-paused_since if paused and paused_since is not None else 0
    if return_trace:
        result['trace']=trace
        result['allocations']=allocations
        if symbol_trade_share_cap is not None:
            result['symbol_share_log']=share_log
    return result
