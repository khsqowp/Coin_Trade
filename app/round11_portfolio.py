"""Unlevered research book. Locked collateral is never reused as short proceeds.

Stops use yesterday's completed high/ATR, then gap/intraday adverse execution.
Long/short batches start dollar neutral; drifting books are NOT beta neutral.
Funding is a daily notional approximation, not reconstructed 8-hour mark prices.
"""
import numpy as np
import pandas as pd
from app.technical_portfolio_engine import prepare


def simulate(prepped, *, prepared=None, top_k=8, hold_days=20,
             long_short=False, trailing=0., calendar=None, scales=None,
             dynamic_k=None, clusters=None, cluster_cap=1.,
             funding_annual=0., slippage=0., fee=.0004, return_trace=False):
    if long_short and trailing:
        raise ValueError('chandelier is a long-only policy in this research')
    if top_k < 1 or hold_days < 1 or trailing < 0 or not 0 < cluster_cap <= 1:
        raise ValueError('invalid capacity/holding/trailing/cluster limit')
    if not 0 <= fee < 1 or not 0 <= slippage < 1 or not np.isfinite(funding_annual):
        raise ValueError('invalid execution cost')
    dates, keys, a = prepared or prepare(prepped)
    cash = 1.
    positions = {}
    marks = np.zeros(len(keys))
    curve, records, trace, allocations = [], [], [], []
    stopped = 0

    def value(p, price):
        return p['principal'] + p['direction']*p['qty']*(price-p['price'])-p['funding']

    def sell(k, price, i):
        nonlocal cash
        p = positions.pop(k)
        executed = price*(1-p['direction']*slippage)
        proceeds = value(p, executed)-p['qty']*executed*fee
        cash += proceeds
        records.append(dict(id=len(records), symbol=keys[k], entry=p['entry'], exit=i,
                            entry_date=str(dates[p['entry']]), exit_date=str(dates[i]),
                            direction=p['direction'], qty=p['qty'], cost=p['cost'],
                            proceeds=proceeds, pnl=proceeds-p['cost'],
                            funding=p['funding'], return_pct=(proceeds/p['cost']-1)*100))

    for i, d in enumerate(dates):
        op, hi, lo, cl = (a[f][i] for f in ['Open', 'High', 'Low', 'Close'])
        # Today's gap may hit a stop fixed at the previous completed close.
        for k in list(positions):
            p = positions[k]
            if p['stop'] > 0 and np.isfinite(op[k]) and op[k] <= p['stop']:
                sell(k, op[k], i)
                stopped += 1
        opening = cash+sum(value(p, op[k] if np.isfinite(op[k]) else marks[k])
                           for k, p in positions.items())
        s = i-1
        cap = int(dynamic_k.get(dates[s], top_k)) if dynamic_k is not None and s >= 0 else top_k
        scale = float(scales.get(dates[s], 0.)) if scales is not None and s >= 0 else 1.
        if cap < 1 or not 0 <= scale <= 1:
            raise ValueError('invalid causal capacity/scale')
        allowed = calendar is None or calendar.get(d, False)
        if s >= 0 and allowed and scale > 0 and opening > 0:
            available = [k for k in range(len(keys)) if k not in positions
                         and np.isfinite(op[k]) and op[k] > 0
                         and np.isfinite(a['VOL_RATIO'][s, k])]
            longs = [k for k in available if a['SIGNAL'][s, k] == 1]
            longs.sort(key=lambda k: (-a['VOL_RATIO'][s, k], keys[k]))
            if long_short:
                shorts = [k for k in available if a['SHORT_SIGNAL'][s, k] == 1]
                shorts.sort(key=lambda k: (a['VOL_RATIO'][s, k], keys[k]))
                # Paired openings/exits: same expiry, each side same collateral.
                n = min(len(longs), len(shorts), max(0, (cap-len(positions))//2))
                candidates = [(k, 1) for k in longs[:n]]+[(k, -1) for k in shorts[:n]]
                paired_budget = min(opening/cap*scale, cash/(2*n)) if n else 0.
            else:
                candidates = [(k, 1) for k in longs]
            admitted = 0
            for k, direction in candidates:
                if len(positions) >= cap:
                    break
                alloc = min(cash, opening/cap*scale)
                if long_short:
                    alloc = min(cash, paired_budget)
                label = clusters.get(dates[s], {}).get(keys[k], keys[k]) if clusters else None
                if clusters:
                    used = sum(max(0., value(p, op[j] if np.isfinite(op[j]) else marks[j]))
                               for j,p in positions.items()
                               if clusters.get(dates[s], {}).get(keys[j], keys[j]) == label)
                    alloc = min(alloc, max(0., opening*cluster_cap-used))
                if alloc <= 1e-12:
                    continue
                price = op[k]*(1+direction*slippage)
                atr = a['ATR14'][s, k]
                if trailing and (not np.isfinite(atr) or atr <= 0):
                    continue
                principal = alloc*(1-fee)
                positions[k] = dict(qty=principal/price, principal=principal, cost=alloc,
                                    price=price, direction=direction, funding=0., entry=i,
                                    expiry=i+hold_days, high=price,
                                    stop=max(0., price-trailing*atr) if trailing else 0.)
                cash -= alloc
                admitted += 1
                if return_trace:
                    allocations.append(dict(date=str(d), symbol=keys[k], direction=direction,
                                            weight=alloc/opening, capacity=cap,
                                            known_through=str(dates[s]), cluster=label))
        for k in list(positions):
            p = positions[k]
            # Approximate notional: previous close; entry day uses entry open
            # and two remaining 8-hour payments. Shorts reverse the sign.
            fraction = 2/3 if p['entry'] == i else 1.
            notional = p['qty']*(op[k] if p['entry'] == i else marks[k])
            p['funding'] += p['direction']*notional*funding_annual/365*fraction
            if not np.isfinite(cl[k]):
                continue
            if p['stop'] > 0 and lo[k] <= p['stop']:
                sell(k, min(op[k], p['stop']), i)
                stopped += 1
            elif i >= p['expiry'] or i == len(dates)-1:
                sell(k, cl[k], i)
            elif trailing:
                # New high and today's completed ATR become tomorrow's stop.
                p['high'] = max(p['high'], hi[k])
                atr = a['ATR14'][i, k]
                if np.isfinite(atr):
                    p['stop'] = max(p['stop'], p['high']-trailing*atr)
        valid = np.isfinite(cl)
        marks[valid] = cl[valid]
        closing = cash+sum(value(p, marks[k]) for k,p in positions.items())
        curve.append(closing)
        if return_trace:
            trace.append(dict(date=str(d), opening=opening, closing=closing,
                              positions=len(positions), capacity=cap))
        if closing <= 0:
            # Insolvency cannot be silently reset or reported as a valid strategy.
            for k in list(positions):
                sell(k, marks[k], i)
            closing = cash
            curve[-1] = closing
            if return_trace:
                trace[-1]['closing'] = closing
                trace[-1]['positions'] = 0
            curve.extend([closing]*(len(dates)-len(curve)))
            break
    equity = pd.Series(curve, index=dates)
    years = (dates[-1]-dates[0]).days/365.25
    daily = equity.pct_change().dropna()
    insolvent = bool((equity <= 0).any())
    result = dict(cagr=-100. if insolvent else (equity.iloc[-1]**(1/years)-1)*100,
                  mdd=((equity.cummax()-equity)/equity.cummax()).max()*100,
                  sharpe=float(daily.mean()/daily.std()*np.sqrt(365)) if daily.std()>0 else 0.,
                  trades=len(records), final=float(equity.iloc[-1]), years=years,
                  stopped=stopped, insolvent=insolvent)
    result['insolvency_date'] = str(equity[equity<=0].index[0]) if insolvent else None
    assert not positions
    assert abs(sum(r['pnl'] for r in records)-(result['final']-1)) < 1e-8
    if return_trace:
        result.update(trace=trace, allocations=allocations, records=records,
                      equity=[float(v) for v in curve])
    return result
