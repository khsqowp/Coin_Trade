"""Human and JSON status report for the PAPER-only forward test."""
import argparse, json, sqlite3, time
from datetime import datetime, timezone
from .config import BOOKS, SYMBOLS, get_profile

def status_data(db,book=None,since=None,trades_n=None,profile=None):
    profile=profile or get_profile()
    db.row_factory=sqlite3.Row
    meta=db.execute("SELECT value FROM meta WHERE key='forward_start_ts'").fetchone(); start=int(meta[0]) if meta else None
    hb=db.execute('SELECT * FROM heartbeat WHERE id=1').fetchone()
    last=hb['last_run'] if hb else 0; age=time.time()-last if last else None
    result={'forward_start':datetime.fromtimestamp(start/1000,timezone.utc).isoformat() if start else None,'elapsed_days':max(0,(time.time()*1000-start)/86400000) if start else 0,'bars_processed':hb['bars_processed'] if hb else 0,'last_candle_time':datetime.fromtimestamp(hb['last_candle']/1000,timezone.utc).isoformat() if hb and hb['last_candle'] else None,'last_run_time':datetime.fromtimestamp(last,timezone.utc).isoformat() if last else None,'health':'STALE' if age is None or age>profile.interval_ms/1000*1.25 else 'HEALTHY','books':{}}
    books=[('long_only' if profile.kind=='plugin' and book=='combined' else book)] if book else profile.books
    for b in books:
        clause=' AND exit_ts>=?' if since else ''; args=[b]+([int(pd_timestamp(since))] if since else [])
        ts=db.execute('SELECT * FROM trades WHERE book=?'+clause+' ORDER BY exit_ts DESC',args).fetchall()
        if trades_n: ts=ts[:trades_n]
        pnl=sum(t['net_pnl'] for t in ts); wins=sum(t['net_pnl']>0 for t in ts); profits=sum(max(0,t['net_pnl']) for t in ts); losses=sum(min(0,t['net_pnl']) for t in ts)
        opens=db.execute('SELECT * FROM open_positions WHERE book=? ORDER BY symbol',(b,)).fetchall()
        positions=[]; floating=0.0
        for p in opens:
            latest=db.execute('SELECT close,ts FROM candles WHERE symbol=? ORDER BY ts DESC LIMIT 1',(p['symbol'],)).fetchone()
            px=latest['close'] if latest else p['avg']; direction=1 if p['side']=='long' else -1
            upnl=(px-p['avg'])*p['qty']*direction-p['entry_cost']; floating+=upnl
            positions.append({'symbol':p['symbol'],'side':p['side'],'avg':p['avg'],'adds':p['adds'],'unrealized_pct':upnl/(p['avg']*p['qty'])*100,'bars_held':max(0,(latest['ts']-p['entry_ts'])//profile.interval_ms) if latest else 0})
        syms={}
        for s in SYMBOLS:
            q=[t for t in ts if t['symbol']==s]; syms[s]={'closed':len(q),'net_pnl':sum(t['net_pnl'] for t in q)}
        eq=db.execute('SELECT ts,SUM(equity-?) FROM equity_snapshots WHERE book=? GROUP BY ts ORDER BY ts',(profile.capital,b)).fetchall(); peak=profile.capital*len(SYMBOLS); dd=0
        for r in eq:
            v=profile.capital*len(SYMBOLS)+r[1]; peak=max(peak,v); dd=min(dd,(v-peak)/peak*100)
        result['books'][b]={'open_positions':positions,'closed_trades':len(ts),'win_rate_pct':wins/len(ts)*100 if ts else 0,'profit_factor':profits/abs(losses) if losses else None,'total_return_pct':(pnl+floating)/profile.capital*100,'max_drawdown_pct':dd,'average_hold_bars':sum(t['bars'] for t in ts)/len(ts) if ts else 0,'by_symbol':syms}
    count_book='long_only' if profile.kind=='plugin' else 'combined'
    count=db.execute('SELECT COUNT(*) FROM trades WHERE book=?',(count_book,)).fetchone()[0]; days=result['elapsed_days']; backtest=profile.backtest
    reference_trades=backtest['test_trades']; reference_days=backtest.get('test_days',1)
    expected=reference_trades/reference_days*days
    min_trades,min_days=(100,60) if profile.name=='jbb_1h' else (30,90)
    result['books']['combined']=result['books'].get('long_only') if profile.kind=='plugin' else result['books'].get('combined')
    verdict='INSUFFICIENT DATA' if count<min_trades or days<min_days else ('NEGATIVE' if result['books'].get('combined',{}).get('total_return_pct',0)<0 else ('UNDERPERFORMING' if count<expected*.5 else 'ON TRACK'))
    rules=f'INSUFFICIENT DATA until both 30 trades and 90 days; then NEGATIVE if combined net return < 0; UNDERPERFORMING if trades < 50% of the {reference_trades}/{reference_days:.2f}-day expectation; otherwise ON TRACK.'
    if profile.name=='jbb_1h':
        reference=backtest
        result['profile']=profile.name
        rules='INSUFFICIENT DATA until both 100 closed long-only trades and 60 elapsed days; then NEGATIVE if net return < 0; UNDERPERFORMING if trades are below half the historical-rate expectation; otherwise ON TRACK.'
    elif profile.name=='l5_4h':
        reference={'test_trades':reference_trades,'test_days_approx':reference_days,'summed_return_pct':backtest['test_return_pct']}
        rules=f'INSUFFICIENT DATA until both 30 trades and 90 days; then NEGATIVE if combined net return < 0; UNDERPERFORMING if trades < 50% of the 255/693.98-day expectation; otherwise ON TRACK.'
    else:
        reference=backtest
        result['profile']=profile.name
    result['progress']={'trades':count,'minimum_trades':min_trades,'days':days,'minimum_days':min_days,'expected_trades_at_backtest_rate':expected,'backtest_reference':reference,'verdict':verdict,'rules':rules}
    if profile.name=='jbb_1h':
        result['progress']['caveat']=("Candidate, not a proven edge. Reference: train +35.6% (1,414 trades), test +13.8% (885 trades), null percentile 100, ROBUST plateau. "
            "Caveats: test return +3.2% at 2x costs; secondary coins +1.7%; selected after testing about 149 strategies.")
    if profile.name=='l5_12h': result['progress']['caveat']='Historical reference is fragile: walk-forward return -10.2%; plateau FRAGILE.'
    return result
def pd_timestamp(x):
    from datetime import datetime
    return int(datetime.fromisoformat(x).replace(tzinfo=timezone.utc).timestamp()*1000)
def main():
    p=argparse.ArgumentParser(); p.add_argument('--json',action='store_true'); p.add_argument('--profile',choices=('l5_4h','l5_12h','jbb_1h')); p.add_argument('--book',choices=(*BOOKS,'long_only')); p.add_argument('--since'); p.add_argument('--trades',type=int); p.add_argument('--db'); a=p.parse_args()
    profile=get_profile(a.profile)
    from .engine import Engine
    db=Engine(a.db or profile.db_path,profile=profile).db; data=status_data(db,a.book,a.since,a.trades,profile)
    if a.json: print(json.dumps(data,indent=2,allow_nan=False));return
    print(f"Forward start: {data['forward_start']} | elapsed {data['elapsed_days']:.1f} days | bars {data['bars_processed']} | last candle {data['last_candle_time']} | last run {data['last_run_time']} | {data['health']}")
    for b,v in data['books'].items():
        print(f"\n{b}: open={len(v['open_positions'])} closed={v['closed_trades']} win={v['win_rate_pct']:.1f}% PF={v['profit_factor']} return={v['total_return_pct']:.2f}% maxDD={v['max_drawdown_pct']:.2f}% avg_hold={v['average_hold_bars']:.1f} bars")
        for o in v['open_positions']: print(f"  {o['symbol']} {o['side']} avg={o['avg']:.6g} adds={o['adds']} unrealized={o['unrealized_pct']:.2f}% held={o['bars_held']}")
        print('  SYMBOL  CLOSED  NET_PNL')
        for s,x in v['by_symbol'].items(): print(f"  {s:<8} {x['closed']:>6} {x['net_pnl']:>9.2f}")
    x=data['progress']; print(f"\nPROGRESS: trades {x['trades']}/{x['minimum_trades']} | days {x['days']:.1f}/{x['minimum_days']} | expected at historical rate {x['expected_trades_at_backtest_rate']:.1f} | verdict: {x['verdict']}\n{x['rules']}")
    if x.get('caveat'): print(x['caveat'])
if __name__=='__main__':main()
