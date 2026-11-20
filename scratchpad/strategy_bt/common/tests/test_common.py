import csv, importlib.util, multiprocessing, time
from pathlib import Path
import numpy as np
import pandas as pd
import pytest
from common.engine import simulate
from common.protocol import validate_grid,check_no_lookahead
from common.verdict import decide,adjusted_decide
from common.ledger import append_row
from common.run import _write_summary

BASE=Path(__file__).resolve().parents[1]
def frame(opens=(100,101,102,103), highs=(100,101,102,103), lows=(100,101,102,103), closes=(100,101,102,103)):
    return pd.DataFrame(dict(open=opens,high=highs,low=lows,close=closes),index=pd.date_range("2024-01-01",periods=len(opens),freq="4h",tz="UTC"))
def sig(n,entry=0,**extra):
    x=pd.DataFrame(False,index=range(n),columns=["long_entry","short_entry","long_exit","short_exit"]);x.loc[entry,"long_entry"]=True
    for k,v in extra.items():x[k]=v
    return x
def _ledger_worker(args):append_row(args[0],{"strategy_id":str(args[1]),"n_candidates_tested":args[1]})
def test_next_open_fee_slippage_hand_math():
    d=frame(opens=(100,100,110),highs=(100,100,110),lows=(100,100,110),closes=(100,100,110));s=sig(3)
    t,m=simulate(d,s,fee=0.0004,slippage=0.0002)
    entry=100*1.0002;q=1000/entry;exit=110*.9998
    expected=((exit-entry)*q-entry*q*.0004-exit*q*.0004)/10000*100
    assert t[0]["entry"]==1 and t[0]["pct"]==pytest.approx(expected)
def test_intrabar_stop_precedes_target_and_gap_stop_at_open():
    d=frame(opens=(100,90,100),highs=(100,110,100),lows=(100,80,100),closes=(100,100,100)); s=sig(3,stop_pct=[.05]*3,tp_pct=[.05]*3)
    t,_=simulate(d,s,fee=0,slippage=0);assert t[0]["reason"]=="stop" and t[0]["entry"]==1 and t[0]["pct"]<0
def test_signal_exit_fills_next_open():
    d=frame(opens=(100,100,120,120),highs=(100,101,121,121),lows=(100,99,119,119),closes=(100,100,110,110));s=sig(4);s.loc[1,"long_exit"]=True
    t,_=simulate(d,s,fee=0,slippage=0);assert t[0]["exit"]==2 and t[0]["net"]==pytest.approx(200)
def test_verdict_all_failure_branches_and_pass():
    assert decide(96,"ROBUST",30,1,3)=={"verdict":"PASS","reason_codes":[]}
    assert set(decide(10,"FRAGILE",2,-1,1)["reason_codes"])=={"NULL_PCTL","PLATEAU","TRADES","RETURN","SYMBOLS"}
    assert adjusted_decide(96,"ROBUST",30,1,3,10)["verdict"]=="FAIL"
def test_grid_caps():
    assert len(validate_grid({"a":[1,2],"b":[3]}))==2
    for g in ({"a":list(range(5))},{"a":[1],"b":[1],"c":[1],"d":[1]}):
        with pytest.raises(ValueError):validate_grid(g)
def test_ledger_append_concurrent(tmp_path):
    path=tmp_path/"ledger.csv"
    with multiprocessing.Pool(4) as pool:pool.map(_ledger_worker,[(path,i) for i in range(20)])
    with path.open() as f:rows=list(csv.DictReader(f))
    assert len(rows)==20 and len({r["strategy_id"] for r in rows})==20
def test_resume_summary_rows(tmp_path):
    path=tmp_path/"summary.csv";_write_summary(path,[{"strategy_id":"x","status":"DONE"}])
    with path.open() as f:assert list(csv.DictReader(f))[0]["strategy_id"]=="x"
def test_example_plugin_signals_and_no_lookahead():
    import common.examples.sma_cross as plugin
    d=frame(tuple(100+np.sin(np.arange(100)/5)),tuple(101+np.sin(np.arange(100)/5)),tuple(99+np.sin(np.arange(100)/5)),tuple(100+np.sin(np.arange(100)/5)))
    out=plugin.signals(d);assert set(["long_entry","short_entry","long_exit","short_exit"]).issubset(out.columns)
    assert check_no_lookahead(plugin,d)
def test_timeout_plugin_is_recorded_as_timeout(tmp_path):
    import subprocess,sys
    plugins=tmp_path/"plugins";plugins.mkdir();(plugins/"hang.py").write_text('''import time\nSPEC_ID="hang-plugin"\nPARAMS={}\nPARAM_GRID={}\nTIMEFRAMES=["1h"]\nDEVIATIONS=["test"]\ndef signals(df, **params):\n time.sleep(60)\n''')
    spec=tmp_path/"fake.json";spec.write_text('{"id":"hang-plugin"}')
    slice_file=tmp_path/"slice.txt";slice_file.write_text(str(spec)+"\n")
    data=tmp_path/"data";data.mkdir();d=frame();d.to_parquet(data/"BTCUSDT_1h.parquet")
    out=tmp_path/"out"
    subprocess.run([sys.executable,"-m","common.run","--slice-file",str(slice_file),"--plugins-dir",str(plugins),"--out",str(out),"--timeout","0.2","--data-dir",str(data),"--ledger",str(tmp_path/"ledger.csv")],cwd=BASE.parent,text=True,capture_output=True,timeout=10,check=True)
    with (out/"summary.csv").open() as f: row=list(csv.DictReader(f))[0]
    assert row["status"]=="TIMEOUT"
def test_resume_skips_completed_strategy(tmp_path):
    import subprocess,sys
    plugins=tmp_path/"plugins";plugins.mkdir();(plugins/"skip_me.py").write_text('''SPEC_ID="skip-me"\nTIMEFRAMES=["4h"]\nPARAM_GRID={}\ndef signals(df, **params): raise RuntimeError("must not run")\n''')
    spec=tmp_path/"skip.json";spec.write_text('{"id":"skip-me"}')
    slices=tmp_path/"slice.txt";slices.write_text(str(spec)+"\n");out=tmp_path/"out";out.mkdir()
    _write_summary(out/"summary.csv",[{"strategy_id":"skip-me","status":"DONE","timeframe":"4h"}])
    subprocess.run([sys.executable,"-m","common.run","--slice-file",str(slices),"--plugins-dir",str(plugins),"--out",str(out),"--timeout","2","--data-dir",str(tmp_path/"absent"),"--ledger",str(tmp_path/"ledger.csv")],cwd=BASE.parent,text=True,capture_output=True,timeout=5,check=True)
    with (out/"summary.csv").open() as f: rows=list(csv.DictReader(f))
    assert len(rows)==1 and rows[0]["status"]=="DONE"
