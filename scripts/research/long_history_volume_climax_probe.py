#!/usr/bin/env python3
"""Fixed 30m volume-climax failed-breakout probe on local Vision history."""
import sqlite3
import numpy as np
import pandas as pd

DB = 'chart_predictor/data/vision_dev.sqlite'
CUTOFF_MS = int(pd.Timestamp('2026-10-09T00:00:00Z').timestamp() * 1000)
SYMBOLS = ('BNBUSDT', 'BTCUSDT', 'DOGEUSDT', 'ETHUSDT')  # omit SOL/XRP gap-contaminated series
BAR_MS = 30 * 60_000
HORIZONS = (10, 20)
LEVERAGES = (10, 20)
COSTS = {'base': 0.001, 'stress': 0.003}


def main():
    db = sqlite3.connect(f'file:{DB}?mode=ro', uri=True)
    report = []
    for symbol in SYMBOLS:
        raw = pd.read_sql_query(
            'SELECT open_ms,open AS o,high AS h,low AS l,close AS c,volume AS v '
            'FROM candles WHERE symbol=? AND open_ms<? ORDER BY open_ms',
            db, params=(symbol, CUTOFF_MS),
        )
        raw['dt'] = pd.to_datetime(raw.open_ms, unit='ms', utc=True)
        raw = raw.set_index('dt')
        frame = raw.resample('30min', origin='epoch', label='left', closed='left').agg(
            {'o':'first','h':'max','l':'min','c':'last','v':'sum','open_ms':'first'}
        ).dropna()
        frame = frame[frame.open_ms + BAR_MS <= CUTOFF_MS].reset_index(drop=True)
        o,h,l,c,v = (frame[k].to_numpy(float) for k in ('o','h','l','c','v'))
        times = frame.open_ms.to_numpy(np.int64)
        prev_hi = pd.Series(h).rolling(20, min_periods=20).max().shift(1).to_numpy()
        prev_lo = pd.Series(l).rolling(20, min_periods=20).min().shift(1).to_numpy()
        vol_med = pd.Series(v).rolling(20, min_periods=20).median().shift(1).to_numpy()
        prev_close = np.r_[np.nan, c[:-1]]
        tr = np.maximum(h-l, np.maximum(np.abs(h-prev_close), np.abs(l-prev_close)))
        atr = pd.Series(tr).rolling(14, min_periods=14).mean().to_numpy()
        climax_high = (h > prev_hi) & (v >= 3 * vol_med)
        climax_low = (l < prev_lo) & (v >= 3 * vol_med)
        events = []
        rejects = {'no_failure':0,'double_extreme':0,'invalid_risk':0,'incomplete_horizon':0}
        for i in range(20, len(frame)-2):
            is_high, is_low = bool(climax_high[i]), bool(climax_low[i])
            if not (is_high or is_low):
                continue
            if is_high and is_low:
                rejects['double_extreme'] += 1
                continue
            side = -1 if is_high else 1
            # Climax bar must be followed by a completed close back inside its extreme.
            failed = c[i+1] <= h[i] if is_high else c[i+1] >= l[i]
            if not failed:
                rejects['no_failure'] += 1
                continue
            signal_i, entry_i = i+1, i+2
            stop = (max(h[i],h[signal_i]) + .25*atr[signal_i]) if side < 0 else (min(l[i],l[signal_i]) - .25*atr[signal_i])
            entry = o[entry_i]
            risk = stop-entry if side < 0 else entry-stop
            if not np.isfinite(risk) or risk <= 0 or not np.isfinite(atr[signal_i]):
                rejects['invalid_risk'] += 1
                continue
            events.append((signal_i,entry_i,side,entry,stop,risk))

        for horizon in HORIZONS:
            complete = [ev for ev in events if ev[1]+horizon <= len(frame)]
            rejects_h = len(events)-len(complete)
            rejects['incomplete_horizon'] += rejects_h
            for leverage in LEVERAGES:
                valid=[]; liq=0
                for ev in complete:
                    si,ei,side,entry,stop,risk = ev
                    if risk/entry >= 1/leverage-.005:
                        liq += 1
                    else:
                        valid.append(ev)
                for cost_name,cost in COSTS.items():
                    net_returns=[]; target_first=direction_correct=0
                    for si,ei,side,entry,stop,risk in valid:
                        target = entry + side*1.5*risk
                        exitp=c[ei+horizon-1]; reason='timeout'
                        for j in range(ei,ei+horizon):
                            hit_stop = l[j] <= stop if side > 0 else h[j] >= stop
                            hit_target = h[j] >= target if side > 0 else l[j] <= target
                            if hit_stop or hit_target:
                                exitp=stop if hit_stop else target
                                reason='stop' if hit_stop else 'target'
                                break
                        net = side*(exitp/entry-1)-cost
                        net_returns.append(net)
                        target_first += reason == 'target'
                        direction_correct += side*(c[ei+horizon-1]/entry-1) > 0
                    if net_returns:
                        n=len(net_returns)
                        report.append((symbol,horizon,leverage,cost_name,n,len(events),liq,
                                       target_first/n,float(np.mean(np.asarray(net_returns)>0)),
                                       direction_correct/n,float(np.mean(net_returns)*100)))
    db.close()
    print('symbol,horizon_bars,leverage,cost,n,signal_count,liq_rejected,target_first,net_positive,direction_correct_at_expiry,mean_net_pct')
    for row in report:
        print(','.join(map(str,row)))
    for horizon in HORIZONS:
        for leverage in LEVERAGES:
            for cost_name in COSTS:
                for side_name,include in (('both',lambda s:True),):
                    subset=[r for r in report if r[1]==horizon and r[2]==leverage and r[3]==cost_name and include(r[0])]
                    n=sum(r[4] for r in subset)
                    if n:
                        print('POOLED',horizon,leverage,cost_name,'n',n,
                              'target_first',sum(r[4]*r[7] for r in subset)/n,
                              'net_positive',sum(r[4]*r[8] for r in subset)/n,
                              'direction_correct',sum(r[4]*r[9] for r in subset)/n,
                              'weighted_mean_net_pct',sum(r[4]*r[10] for r in subset)/n)


if __name__ == '__main__':
    main()
