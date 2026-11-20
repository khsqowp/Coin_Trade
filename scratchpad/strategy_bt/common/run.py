"""Resumable isolated-process runner for archived strategy plugins."""
import argparse,csv,importlib.util,json,os,subprocess,sys,time,traceback
from concurrent.futures import ThreadPoolExecutor,as_completed
from pathlib import Path
import pandas as pd
from .protocol import evaluate,check_no_lookahead
from .compliance import audit
from .ledger import append_row
from .verdict import sidak_requirement

HERE=Path(__file__).resolve().parent; ROOT=HERE.parent
REPO=ROOT.parents[2]
def _load(path):
    spec=importlib.util.spec_from_file_location("strategy_plugin",path); mod=importlib.util.module_from_spec(spec); spec.loader.exec_module(mod); return mod
def _worker(payload):
    plugin=_load(payload["plugin"]); spec=json.loads(Path(payload["spec"]).read_text()); results=[]
    for tf in (plugin.TIMEFRAMES if not payload.get("tf_limit") else [x for x in plugin.TIMEFRAMES if x in payload["tf_limit"]]):
        for symbol in payload["symbols"]:
            cached=Path(payload["data_dir"])/f"{symbol}_{tf}.parquet"
            if cached.exists(): check_no_lookahead(plugin,pd.read_parquet(cached))
        result=evaluate(plugin,payload["symbols"],tf,Path(payload["data_dir"]),n_slice_strategies=payload["n_slice_strategies"],seed=payload["seed"],null_repetitions=payload["null_repetitions"],secondary_symbols=payload["secondary"])
        result.update(strategy_id=plugin.SPEC_ID,spec_path=payload["spec"],compliance=audit(payload["spec"],plugin)); results.append(result)
    return results
def _write_summary(path, rows):
    fields=["strategy_id","status","timeframe","reason","train_return","train_pf","train_win_rate","train_max_dd","train_trades","test_return","test_pf","test_win_rate","test_max_dd","test_trades","null_percentile","plateau","positive_symbols","symbols","raw_verdict","raw_reasons","adjusted_verdict","adjusted_reasons","params","secondary_return","n_candidates_tested","compliance","error"]
    with path.open("w",newline="",encoding="utf-8") as f:
        w=csv.DictWriter(f,fieldnames=fields);w.writeheader()
        for r in rows:w.writerow(r)
def _row(r):
    tr=r.get("train",{}); te=r.get("test",{}); return {"strategy_id":r.get("strategy_id"),"status":r.get("status"),"timeframe":r.get("timeframe"),"reason":r.get("reason",""),"train_return":tr.get("return"),"train_pf":tr.get("pf"),"train_win_rate":tr.get("win_rate"),"train_max_dd":tr.get("max_dd"),"train_trades":tr.get("trades",r.get("train_trades")),"test_return":te.get("return"),"test_pf":te.get("pf"),"test_win_rate":te.get("win_rate"),"test_max_dd":te.get("max_dd"),"test_trades":te.get("trades"),"null_percentile":r.get("null_percentile"),"plateau":r.get("plateau"),"positive_symbols":r.get("positive_symbols"),"symbols":r.get("symbols"),"raw_verdict":r.get("verdict",{}).get("verdict"),"raw_reasons":";".join(r.get("verdict",{}).get("reason_codes",[])),"adjusted_verdict":r.get("adjusted_verdict",{}).get("verdict"),"adjusted_reasons":";".join(r.get("adjusted_verdict",{}).get("reason_codes",[])),"params":json.dumps(r.get("params",{}),sort_keys=True),"secondary_return":r.get("secondary",{}).get("return"),"n_candidates_tested":r.get("n_candidates_tested",0),"compliance":json.dumps(r.get("compliance",{}),sort_keys=True),"error":r.get("error","" )}
def _render(out,rows):
    md=["# Strategy backtest report","","Verdicts are mechanical diagnostics, not evidence of future profitability.","","| Strategy | TF | Status | Test return | Null pct | Plateau | Raw | Adjusted |","|---|---:|---|---:|---:|---|---|---|"]
    for r in rows:md.append(f"| {r.get('strategy_id')} | {r.get('timeframe','')} | {r.get('status')} | {r.get('test_return','')} | {r.get('null_percentile','')} | {r.get('plateau','')} | {r.get('raw_verdict','')} | {r.get('adjusted_verdict','')} |")
    md.extend(["","## Compliance audit",""])
    for r in rows:md.append(f"- `{r.get('strategy_id')}` `{r.get('timeframe','')}`: {r.get('compliance','')}")
    (out/"REPORT.md").write_text("\n".join(md)+"\n",encoding="utf-8")
def main():
    p=argparse.ArgumentParser();p.add_argument("--slice-file");p.add_argument("--plugins-dir");p.add_argument("--out");p.add_argument("--workers",type=int,default=1);p.add_argument("--timeout",type=float,default=300);p.add_argument("--data-dir",default=str(ROOT.parent/"bb_stoch_stc"/"data"));p.add_argument("--ledger",default=str(ROOT/"results"/"ledger.csv"));p.add_argument("--tf-limit",nargs="+");p.add_argument("--force",action="store_true");p.add_argument("--_worker-payload")
    a=p.parse_args()
    if a._worker_payload:
        try: print(json.dumps(_worker(json.loads(a._worker_payload)),allow_nan=True))
        except Exception: print(json.dumps({"worker_error":traceback.format_exc()}));sys.exit(1)
        return
    out=Path(a.out);out.mkdir(parents=True,exist_ok=True);summary=out/"summary.csv";progress=out/"progress.log"
    rows=[]
    if summary.exists() and not a.force:
        with summary.open(newline="",encoding="utf-8") as f:rows=list(csv.DictReader(f))
    done={r.get("strategy_id") for r in rows if r.get("status") in ("DONE","INELIGIBLE","NO_PLUGIN","ERROR","TIMEOUT")}
    paths=[x.strip() for x in Path(a.slice_file).read_text().splitlines() if x.strip() and not x.lstrip().startswith("#")]; nstrat=len(paths); plugins=list(Path(a.plugins_dir).rglob("*.py")); started=time.monotonic()
    family_candidates=0
    for rel in paths:
        try:
            sp=Path(rel); sp=sp if sp.is_absolute() else REPO/"trading"/sp
            js=json.loads(sp.read_text()); ident=js.get("id",js.get("spec_id",sp.parent.name))
            mod=next((_load(str(f)) for f in plugins if f.stem in (ident,ident.replace("-","_")) or getattr(_load(str(f)),"SPEC_ID",None)==ident),None)
            if mod is not None: family_candidates+=len(getattr(mod,"TIMEFRAMES",[]))*len(__import__("common.protocol",fromlist=["validate_grid"]).validate_grid(getattr(mod,"PARAM_GRID",{})))
        except Exception: continue
    tasks=[]
    for i,rel in enumerate(paths,1):
        try:
            guess=Path(rel); guess=guess if guess.is_absolute() else REPO/"trading"/guess
            js=json.loads(guess.read_text()); ident=js.get("id",js.get("spec_id",guess.parent.name))
        except Exception: ident=Path(rel).stem
        if ident not in done: tasks.append((i,rel))
    def execute(i,rel):
        specpath=Path(rel); specpath=specpath if specpath.is_absolute() else REPO/"trading"/specpath
        try: spec=json.loads(specpath.read_text()); sid=spec.get("id",spec.get("spec_id",specpath.parent.name))
        except Exception as e:return i,specpath.stem,[_row({"strategy_id":specpath.stem,"status":"ERROR","error":str(e)})]
        pluginpath=None
        for f in plugins:
            try:
                if f.stem in (sid.replace("-","_"),sid) or getattr(_load(str(f)),"SPEC_ID",None)==sid: pluginpath=f;break
            except Exception: continue
        if pluginpath is None:return i,sid,[_row({"strategy_id":sid,"status":"NO_PLUGIN"})]
        payload={"plugin":str(pluginpath.resolve()),"spec":str(specpath.resolve()),"symbols":["BTCUSDT","ETHUSDT","BNBUSDT","SOLUSDT","XRPUSDT"],"secondary":["ADAUSDT","DOGEUSDT","LINKUSDT","LTCUSDT"],"data_dir":str(Path(a.data_dir).resolve()),"n_slice_strategies":nstrat,"seed":1729,"null_repetitions":200,"tf_limit":a.tf_limit}
        cmd=[sys.executable,"-m","common.run","--_worker-payload",json.dumps(payload)]
        try:
            proc=subprocess.run(cmd,cwd=ROOT,timeout=a.timeout,capture_output=True,text=True)
            if proc.returncode: raise RuntimeError(proc.stdout+proc.stderr)
            data=json.loads(proc.stdout.strip().splitlines()[-1]);
            if "worker_error" in data:raise RuntimeError(data["worker_error"])
            result_rows=[]
            for result in data:
                r=_row(result);result_rows.append(r);append_row(a.ledger,{"strategy_id":sid,"timeframe":r["timeframe"],"n_candidates_tested":family_candidates,"n_slice_strategies":nstrat,"raw_requirement_percentile":95,"adjusted_requirement_percentile":sidak_requirement(nstrat),"timestamp_utc":pd.Timestamp.now(tz="UTC").isoformat()})
            return i,sid,result_rows
        except subprocess.TimeoutExpired:return i,sid,[_row({"strategy_id":sid,"status":"TIMEOUT","error":f"exceeded {a.timeout}s"})]
        except Exception:return i,sid,[_row({"strategy_id":sid,"status":"ERROR","error":traceback.format_exc()[-4000:]})]
    with ThreadPoolExecutor(max_workers=max(1,a.workers)) as executor:
        futures=[executor.submit(execute,i,rel) for i,rel in tasks]
        for future in as_completed(futures):
            i,sid,produced=future.result(); rows.extend(produced)
            _write_summary(summary,rows);_render(out,rows)
            with progress.open("a",encoding="utf-8") as log:log.write(f"[{i}/{nstrat}] {sid} elapsed={time.monotonic()-started:.1f}s rows={len(rows)}\n")
    _write_summary(summary,rows);_render(out,rows)
if __name__=="__main__":main()
