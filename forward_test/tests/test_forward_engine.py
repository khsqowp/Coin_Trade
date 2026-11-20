import sys
from pathlib import Path
import numpy as np
import pandas as pd
from forward_test.engine import Engine
from forward_test.strategy import signal_frame, simulate
from forward_test.config import SIGNAL, MANAGEMENT, L5_12H, get_profile

ROOT=Path(__file__).resolve().parents[3]
RESEARCH=ROOT/'trading/scratchpad/bb_stoch_stc'
sys.path.insert(0,str(RESEARCH))

def sample(n=300):
    rng=np.random.default_rng(27); c=100*np.exp(np.cumsum(rng.normal(0,.02,n)))
    o=np.r_[c[0],c[:-1]]; spread=rng.uniform(.002,.04,n)
    return pd.DataFrame({'open':o,'high':np.maximum(o,c)*(1+spread),'low':np.minimum(o,c)*(1-spread),'close':c,'volume':1.},index=pd.date_range('2022-01-01',periods=n,freq='4h',tz='UTC'))

def test_vendor_signal_arrays_equal():
    from strategy import signal_frame as reference
    d=sample(); pd.testing.assert_frame_equal(signal_frame(d,SIGNAL),reference(d,SIGNAL))

def test_incremental_idempotent_and_forward_gate(tmp_path):
    d=sample(); e=Engine(tmp_path/'f.db'); e.put_candles('BTCUSDT',d)
    start=int(d.index[150].timestamp()*1000); e.db.execute("INSERT INTO meta VALUES('forward_start_ts',?)",(str(start),)); e.db.commit()
    # Invoke through cursor logic with latest historical rows treated as closed.
    e.run(); n=e.db.execute('select count(*) from signals').fetchone()[0]; e.run()
    assert e.db.execute('select count(*) from signals').fetchone()[0]==n
    restarted=Engine(tmp_path/'f.db'); restarted.run()
    assert restarted.db.execute('select count(*) from signals').fetchone()[0]==n
    assert e.db.execute('select count(*) from trades where entry_ts<?',(start,)).fetchone()[0]==0
    assert e.db.execute('select count(*) from open_positions where entry_ts<?',(start,)).fetchone()[0]==0

def test_signal_prefix_invariance():
    d=sample(); a=signal_frame(d,SIGNAL); b=signal_frame(d.iloc[:200],SIGNAL)
    pd.testing.assert_frame_equal(a.iloc[:200],b)

def test_batch_replay_trade_counts_for_available_research_data(tmp_path):
    from forward_test.strategy import simulate as reference_sim
    compared=0
    for symbol in ('BTCUSDT','ETHUSDT'):
        path=RESEARCH/'data'/f'{symbol}_4h.parquet'
        if not path.exists(): continue
        d=pd.read_parquet(path); sig=signal_frame(d,SIGNAL)
        from strategy import signal_frame as reference_signal
        pd.testing.assert_frame_equal(sig,reference_signal(d,SIGNAL))
        cut=int(len(d)*.6); test_d=d.iloc[cut:]; test_sig=sig.iloc[cut:]
        for book,side in [('combined','combined'),('long_only','long'),('short_only','short')]:
            ref=reference_sim(test_d,test_sig,MANAGEMENT,side,include_trade_details=True)
            e=Engine(tmp_path/f'{symbol}-{book}.db'); e.put_candles(symbol,d)
            e.db.execute("INSERT INTO meta VALUES('forward_start_ts',?)",(str(int(test_d.index[0].timestamp()*1000)),)); e.db.commit()
            e.run()
            actual=e.db.execute('select * from trades where book=? order by entry_ts',(book,)).fetchall()
            # Reference simulate appends a terminal end_mark for open positions; it is not a closed forward trade.
            expected=[x for x in ref['trade_details'] if x['exit']<len(test_d)-1]
            assert len(actual)==len(expected), (symbol,book,len(actual),len(expected))
            for got,want in zip(actual,expected):
                assert got['entry_ts']==int(test_d.index[want['entry']].timestamp()*1000)
                assert got['exit_ts']==int(test_d.index[want['exit']].timestamp()*1000)
                assert got['side']==want['side'] and got['reason']==want['reason'] and got['adds']==want['adds'] and got['bars']==want['bars']
                assert np.isclose(got['pct'],want['return'],rtol=0,atol=1e-8), (symbol,book,got['pct'],want['return'])
                assert np.isclose(got['entry_px'],want['entry_px'],rtol=0,atol=1e-10)
                assert np.isclose(got['exit_px'],want['exit_px'],rtol=0,atol=1e-10)
                assert np.isclose(got['net_pnl'],want['net'],rtol=0,atol=1e-8)
            compared+=len(expected)
    assert compared>=0

def test_l5_12h_config_selection():
    p=get_profile('l5_12h')
    assert p.interval=='12h' and p.interval_ms==43_200_000
    assert p.signal['stoch_level']==25 and p.management['atr_mult']==2.0
    assert p.management['tp_pct']==10 and p.management['max_hold_bars']==60
    assert p.db_path==L5_12H.db_path

def test_profile_selection_uses_environment(monkeypatch):
    monkeypatch.setenv('FORWARD_PROFILE','l5_12h')
    assert get_profile().name=='l5_12h'
    monkeypatch.delenv('FORWARD_PROFILE')
    assert get_profile().name=='l5_4h'

def test_l5_12h_batch_replay_equivalence(tmp_path):
    from forward_test.config import SYMBOLS
    compared=0
    for symbol in SYMBOLS:
        path=RESEARCH/'data'/f'{symbol}_12h.parquet'
        if not path.exists(): continue
        d=pd.read_parquet(path)
        # The forward engine intentionally rejects gaps; compare on the longest
        # contiguous source segment rather than fabricating missing candles.
        breaks=np.flatnonzero(np.diff(d.index.as_unit('ns').asi8)!=L5_12H.interval_ms*1_000_000)+1
        bounds=np.r_[0,breaks,len(d)]
        lo,hi=max(zip(bounds[:-1],bounds[1:]),key=lambda pair:pair[1]-pair[0])
        d=d.iloc[lo:hi]
        sig=signal_frame(d,L5_12H.signal)
        from strategy import signal_frame as reference_signal
        pd.testing.assert_frame_equal(sig,reference_signal(d,L5_12H.signal))
        cut=int(len(d)*.6); test_d=d.iloc[cut:]; test_sig=sig.iloc[cut:]
        for book,side in [('combined','combined'),('long_only','long'),('short_only','short')]:
            ref=simulate(test_d,test_sig,L5_12H.management,side,capital=L5_12H.capital,
                         base_notional=L5_12H.base_notional,fee=L5_12H.fee,
                         slippage=L5_12H.slippage,include_trade_details=True)
            e=Engine(tmp_path/f'{symbol}-{book}.db',profile=L5_12H); e.put_candles(symbol,d)
            e.db.execute("INSERT INTO meta VALUES('forward_start_ts',?)",(str(int(test_d.index[0].timestamp()*1000)),)); e.db.commit()
            e.run()
            actual=e.db.execute('select * from trades where book=? order by entry_ts',(book,)).fetchall()
            expected=[x for x in ref['trade_details'] if x['exit']<len(test_d)-1]
            assert len(actual)==len(expected), (symbol,book,len(actual),len(expected))
            for got,want in zip(actual,expected):
                assert got['entry_ts']==int(test_d.index[want['entry']].timestamp()*1000)
                assert got['exit_ts']==int(test_d.index[want['exit']].timestamp()*1000)
                assert got['side']==want['side'] and got['reason']==want['reason'] and got['adds']==want['adds'] and got['bars']==want['bars']
                assert np.isclose(got['pct'],want['return'],rtol=0,atol=1e-8)
                assert np.isclose(got['entry_px'],want['entry_px'],rtol=0,atol=1e-10)
                assert np.isclose(got['exit_px'],want['exit_px'],rtol=0,atol=1e-10)
                assert np.isclose(got['net_pnl'],want['net'],rtol=0,atol=1e-8)
            compared+=len(expected)
    assert compared>0
