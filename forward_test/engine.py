"""SQLite-backed closed-candle forward-test engine; all prices are synthetic fills."""
from __future__ import annotations
import json, sqlite3, time
from pathlib import Path
import numpy as np
import pandas as pd
from .config import BOOKS, SYMBOLS, get_profile
from .strategy import signal_frame, is_coherent

SCHEMA = '''
CREATE TABLE IF NOT EXISTS candles(ts INTEGER,symbol TEXT,open REAL,high REAL,low REAL,close REAL,volume REAL,PRIMARY KEY(ts,symbol));
CREATE TABLE IF NOT EXISTS signals(ts INTEGER,symbol TEXT,long_flag INTEGER,short_flag INTEGER,bb_long INTEGER,stoch_long INTEGER,stc_long INTEGER,bb_short INTEGER,stoch_short INTEGER,stc_short INTEGER,live_ref_price REAL,PRIMARY KEY(ts,symbol));
CREATE TABLE IF NOT EXISTS trades(id INTEGER PRIMARY KEY,book TEXT,symbol TEXT,entry_ts INTEGER,exit_ts INTEGER,side TEXT,entry_px REAL,exit_px REAL,adds INTEGER,reason TEXT,net_pnl REAL,pct REAL,bars INTEGER,UNIQUE(book,symbol,entry_ts));
CREATE TABLE IF NOT EXISTS open_positions(book TEXT,symbol TEXT,side TEXT,entry_ts INTEGER,entry_i INTEGER,qty REAL,avg REAL,adds INTEGER,lastfill REAL,entry_cost REAL,entry_atr REAL,cash REAL,PRIMARY KEY(book,symbol));
CREATE TABLE IF NOT EXISTS equity_snapshots(ts INTEGER,book TEXT,symbol TEXT,equity REAL,PRIMARY KEY(ts,book,symbol));
CREATE TABLE IF NOT EXISTS meta(key TEXT PRIMARY KEY,value TEXT);
CREATE TABLE IF NOT EXISTS heartbeat(id INTEGER PRIMARY KEY CHECK(id=1),started_at REAL,last_run REAL,last_candle INTEGER,bars_processed INTEGER,last_error TEXT);
CREATE TABLE IF NOT EXISTS runs(ts REAL PRIMARY KEY,ok INTEGER,bars INTEGER,error TEXT);
'''

class Engine:
    def __init__(self, db_path=None, profile=None):
        self.config = profile or get_profile()
        db_path = db_path or self.config.db_path
        self.path=Path(db_path); self.path.parent.mkdir(parents=True,exist_ok=True)
        self.db=sqlite3.connect(self.path); self.db.row_factory=sqlite3.Row; self.db.executescript(SCHEMA)
        self.db.execute("INSERT OR IGNORE INTO heartbeat(id,started_at,last_run,bars_processed) VALUES(1,?,?,0)",(time.time(),0)); self.db.commit()

    def put_candles(self,symbol,frame):
        rows=[]
        for idx,r in frame.iterrows():
            ts=int(pd.Timestamp(idx).timestamp()*1000); rows.append((ts,symbol,*[float(r[k]) for k in ('open','high','low','close','volume')]))
        self.db.executemany('INSERT OR REPLACE INTO candles VALUES(?,?,?,?,?,?,?)',rows); self.db.commit()

    def initialize_forward_start(self,now_ms=None):
        """Freeze the initial run boundary before the potentially long 2022 backfill."""
        if not self.db.execute("SELECT 1 FROM meta WHERE key='forward_start_ts'").fetchone():
            now_ms=now_ms or int(time.time()*1000); boundary=now_ms//self.config.interval_ms*self.config.interval_ms
            self.db.execute("INSERT INTO meta VALUES('forward_start_ts',?)",(str(boundary),)); self.db.commit()

    def frame(self,symbol):
        d=pd.read_sql_query('SELECT ts,open,high,low,close,volume FROM candles WHERE symbol=? ORDER BY ts',self.db,params=(symbol,))
        if len(d): d.index=pd.to_datetime(d.pop('ts'),unit='ms',utc=True); d.index.name='open_time'
        return d

    def run(self,ref_prices=None):
        startrow=self.db.execute("SELECT value FROM meta WHERE key='forward_start_ts'").fetchone()
        if not startrow:
            self.initialize_forward_start(); start=int(self.db.execute("SELECT value FROM meta WHERE key='forward_start_ts'").fetchone()[0])
        else: start=int(startrow[0])
        total=0; newest=None
        for symbol in SYMBOLS:
            d=self.frame(symbol)
            if d.empty: continue
            # Discard any candle that is not fully closed and reject duplicate/gapped series.
            now=int(time.time()*1000); d=d[[int(x.timestamp()*1000)+self.config.interval_ms<=now for x in d.index]]
            idx_ns=d.index.as_unit('ns').asi8
            if len(d)>1 and np.any(np.diff(idx_ns)!=self.config.interval_ms*1_000_000): raise ValueError(f"candle gap for {symbol}; repair required")
            sig=signal_frame(d,self.config.signal); ts=idx_ns//1_000_000
            previous=self.db.execute('SELECT MAX(ts) FROM signals WHERE symbol=?',(symbol,)).fetchone()[0]
            todo=np.flatnonzero((ts>=(previous+1 if previous is not None else start)) & (ts>=start))
            if not len(todo): continue
            for i in todo:
                row=d.iloc[i]; s=sig.iloc[i]; candle_ts=int(ts[i]); rp=(ref_prices or {}).get(symbol,float(row.close))
                self.db.execute('INSERT OR IGNORE INTO signals VALUES(?,?,?,?,?,?,?,?,?,?,?)',(candle_ts,symbol,int(s.long),int(s.short),int(s.bb_long),int(s.stoch_long),int(s.stc_long),int(s.bb_short),int(s.stoch_short),int(s.stc_short),rp))
                for book in BOOKS: self._step(book,symbol,d,sig,int(i),candle_ts)
                newest=candle_ts; total+=1
        now=time.time(); old=self.db.execute('SELECT last_run,bars_processed FROM heartbeat WHERE id=1').fetchone()
        self.db.execute('UPDATE heartbeat SET last_run=?,last_candle=COALESCE(?,last_candle),bars_processed=?,last_error=NULL WHERE id=1',(now,newest,int(old['bars_processed'])+total))
        self.db.execute('INSERT INTO runs VALUES(?,1,?,NULL)',(now,total)); self.db.commit(); self.write_status()
        return total

    def _step(self,book,symbol,d,sig,i,ts):
        row=self.db.execute('SELECT * FROM open_positions WHERE book=? AND symbol=?',(book,symbol)).fetchone()
        had_position=row is not None
        closed_this_bar=False
        o,h,l,c=(float(d.iloc[i][x]) for x in ('open','high','low','close'))
        cash=float(row['cash']) if row else float(self.db.execute('SELECT COALESCE(SUM(net_pnl),0) FROM trades WHERE book=? AND symbol=?',(book,symbol)).fetchone()[0]); pos=1 if row and row['side']=='long' else (-1 if row else 0)
        if pos:
            qty,avg,adds,lastfill,entry_cost,entry_atr,entry_i=(row[k] for k in ('qty','avg','adds','lastfill','entry_cost','entry_atr','entry_i'))
            adverse=l if pos>0 else h
            self.db.execute('INSERT OR REPLACE INTO equity_snapshots VALUES(?,?,?,?)',(ts,book,symbol,self.config.capital+cash+(adverse-avg)*qty*pos-entry_cost))
            stopdist=self.config.management['atr_mult']*entry_atr/avg if np.isfinite(entry_atr) else 999
            stop=avg*(1-pos*stopdist); tp=avg*(1+pos*self.config.management['tp_pct']/100)
            reason=None; px=None
            if (l<=stop if pos>0 else h>=stop): reason='stop'; px=o if (o<stop if pos>0 else o>stop) else stop
            elif (h>=tp if pos>0 else l<=tp): reason='tp'; px=o if (o>tp if pos>0 else o<tp) else tp
            elif i-entry_i>=self.config.management['max_hold_bars']: reason='time'; px=c
            if reason:
                exitpx=px*(1-self.config.slippage if pos>0 else 1+self.config.slippage); net=(exitpx-avg)*qty*pos-entry_cost-exitpx*qty*self.config.fee
                initial_fill=float(d.iloc[entry_i].open)*(1+pos*self.config.slippage)
                self.db.execute('INSERT OR IGNORE INTO trades(book,symbol,entry_ts,exit_ts,side,entry_px,exit_px,adds,reason,net_pnl,pct,bars) VALUES(?,?,?,?,?,?,?,?,?,?,?,?)',(book,symbol,int(d.index[entry_i].timestamp()*1000),ts,'long' if pos>0 else 'short',initial_fill,exitpx,adds,reason,net,net/self.config.capital*100,i-entry_i))
                self.db.execute('DELETE FROM open_positions WHERE book=? AND symbol=?',(book,symbol)); cash+=net; row=None
                closed_this_bar=True
            elif adds<self.config.management['n_adds']:
                level=lastfill*(1-pos*self.config.management['add_spacing_pct']/100)
                if (l<=level if pos>0 else h>=level):
                    addpx=(o if (o<level if pos>0 else o>level) else level)*(1+pos*self.config.slippage); aq=self.config.base_notional/addpx
                    avg=(avg*qty+addpx*aq)/(qty+aq);qty+=aq;entry_cost+=addpx*aq*self.config.fee;lastfill=addpx;adds+=1
                    self.db.execute('UPDATE open_positions SET qty=?,avg=?,adds=?,lastfill=?,entry_cost=? WHERE book=? AND symbol=?',(qty,avg,adds,lastfill,entry_cost,book,symbol))
        if not row and not closed_this_bar and i>0 and int(d.index[i-1].timestamp()*1000)>=int(self.db.execute("SELECT value FROM meta WHERE key='forward_start_ts'").fetchone()[0]):
            long=bool(sig.iloc[i-1].long); short=bool(sig.iloc[i-1].short)
            direction=(1 if long else 0) if book=='long_only' else ((-1 if short else 0) if book=='short_only' else (1 if long else (-1 if short else 0)))
            if direction:
                fill=o*(1+direction*self.config.slippage); atr=float(sig.iloc[i-1].atr); qty=self.config.base_notional/fill; cost=self.config.base_notional*self.config.fee
                if not is_coherent(self.config.management['n_adds'],self.config.management['add_spacing_pct'],self.config.management['sl_pct'],self.config.management['atr_mult'],100*atr/fill if np.isfinite(atr) else None):
                    return
                self.db.execute('INSERT INTO open_positions VALUES(?,?,?,?,?,?,?,?,?,?,?,?)',(book,symbol,'long' if direction>0 else 'short',ts,i,qty,fill,0,fill,cost,atr,cash))
                stopdist=self.config.management['atr_mult']*atr/fill if np.isfinite(atr) else 999
                stop=fill*(1-direction*stopdist); tp=fill*(1+direction*self.config.management['tp_pct']/100)
                adverse=l if direction>0 else h
                self.db.execute('INSERT OR REPLACE INTO equity_snapshots VALUES(?,?,?,?)',(ts,book,symbol,self.config.capital+cash+(adverse-fill)*qty*direction-cost))
                reason=None; px=None
                if (l<=stop if direction>0 else h>=stop): reason='stop'; px=o if (o<stop if direction>0 else o>stop) else stop
                elif (h>=tp if direction>0 else l<=tp): reason='tp'; px=o if (o>tp if direction>0 else o<tp) else tp
                else:
                    level=fill*(1-direction*self.config.management['add_spacing_pct']/100)
                    if (l<=level if direction>0 else h>=level):
                        addpx=(o if (o<level if direction>0 else o>level) else level)*(1+direction*self.config.slippage); aq=self.config.base_notional/addpx
                        avg=(fill*qty+addpx*aq)/(qty+aq); qty+=aq; cost+=addpx*aq*self.config.fee
                        self.db.execute('UPDATE open_positions SET qty=?,avg=?,adds=1,lastfill=?,entry_cost=? WHERE book=? AND symbol=?',(qty,avg,addpx,cost,book,symbol))
                if reason:
                    exitpx=px*(1-self.config.slippage if direction>0 else 1+self.config.slippage); net=(exitpx-fill)*qty*direction-cost-exitpx*qty*self.config.fee
                    self.db.execute('INSERT OR IGNORE INTO trades(book,symbol,entry_ts,exit_ts,side,entry_px,exit_px,adds,reason,net_pnl,pct,bars) VALUES(?,?,?,?,?,?,?,?,?,?,?,?)',(book,symbol,ts,ts,'long' if direction>0 else 'short',fill,exitpx,0,reason,net,net/self.config.capital*100,0))
                    self.db.execute('DELETE FROM open_positions WHERE book=? AND symbol=?',(book,symbol))
        # A just-opened position has no pre-branch mark; record its adverse entry-bar mark.
        if not had_position and not self.db.execute('SELECT 1 FROM equity_snapshots WHERE ts=? AND book=? AND symbol=?',(ts,book,symbol)).fetchone():
            realized=float(self.db.execute('SELECT COALESCE(SUM(net_pnl),0) FROM trades WHERE book=? AND symbol=?',(book,symbol)).fetchone()[0])
            self.db.execute('INSERT OR REPLACE INTO equity_snapshots VALUES(?,?,?,?)',(ts,book,symbol,self.config.capital+realized))

    def write_status(self):
        from .status import status_data
        p=self.path.parent/'status.json'; p.write_text(json.dumps(status_data(self.db,profile=self.config),indent=2,allow_nan=False))
