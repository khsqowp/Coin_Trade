"""Offline ten-strategy full-product research; run with python3.12 -m app.crypto_technical_ict_research."""
import hashlib
import importlib
import itertools
import json
import sys
from pathlib import Path
import numpy as np
import pandas as pd
from app.momentum_rotation_loop import UNIVERSE
from app.param_grids import TECHNICAL_COARSE_GRID, TECHNICAL_FINE_GRID
from app.technical_signal_common import NAMES, ta
from app.technical_portfolio_engine import prepare, simulate_portfolio

ROOT=Path(__file__).resolve().parents[1]
SINCE='2019-01-01'; TOP_K=8; FEE_PCT_ONE_WAY=.04
HOLD={name:20 for name in NAMES}; HOLD.update(rsi=10,vwap=10,liquidity_sweep=10)


def load_data():
    frames={}; manifest=[]; skipped=[]
    for base in UNIVERSE:
        path=ROOT/'.screen_cache/binance_usdtm_1d'/f'{base}_1d_20190101T000000Z.csv'
        if not path.exists():
            skipped.append(base); print(f'{base}: cache miss; network disabled',flush=True); continue
        df=pd.read_csv(path,index_col='timestamp',parse_dates=True)
        df=df.sort_index(); df=df.loc[~df.index.duplicated()]
        # Last partial UTC day is excluded, irrespective of machine wall clock.
        df=df.loc[(df.index>=pd.Timestamp(SINCE,tz='UTC'))&(df.index<pd.Timestamp('2026-10-06',tz='UTC'))]
        if len(df)<201 or df[['Open','High','Low','Close','Volume']].isna().any().any():
            skipped.append(base); print(f'{base}: insufficient/invalid cache',flush=True); continue
        if (df[['Open','High','Low','Close']]<=0).any().any(): raise ValueError(base)
        frames[base]=df
        manifest.append(dict(symbol=base,bars=len(df),start=str(df.index[0]),end=str(df.index[-1]),sha256=hashlib.sha256(path.read_bytes()).hexdigest()))
    if 'BTC' not in frames: raise ValueError('BTC cache required')
    return frames,manifest,skipped


def combinations(grid):
    return [dict(zip(grid,values)) for values in itertools.product(*grid.values())]


def passes(result,btc):
    return bool(result['sharpe']>=1 and result['cagr']>btc)


def benchmark(frames):
    start=min(df.index[0] for df in frames.values()); end=max(df.index[-1] for df in frames.values())
    btc=frames['BTC'].loc[start:end]
    if btc.index[0]!=start or btc.index[-1]!=end: raise ValueError('BTC period mismatch')
    years=(end-start).days/365.25
    return ((btc.Close.iloc[-1]/btc.Open.iloc[0])*(1-FEE_PCT_ONE_WAY/100)**2)**(1/years)*100-100


def run_strategy(name, frames=None):
    if frames is None: frames,_,_=load_data()
    core=importlib.import_module(f'app.{name}_signal_core')
    prepped={s:core.find_signals(df) for s,df in frames.items()}
    data=prepare(prepped); btc=benchmark(frames)
    base_config=dict(timing='next_open',stop='none',tp='none',hold_days=HOLD[name],selection='rank')
    baseline=simulate_portfolio(prepped,prepared=data,**base_config)
    rows=[]
    if not passes(baseline,btc):
        for config in combinations(TECHNICAL_COARSE_GRID):
            rows.append(dict(stage=1,config=config,metrics=simulate_portfolio(prepped,prepared=data,**config)))
        best=max(rows,key=lambda r:(r['metrics']['sharpe'],r['metrics']['cagr']))
        for config in combinations(TECHNICAL_FINE_GRID):
            config={**best['config'],**config}
            rows.append(dict(stage=2,config=config,metrics=simulate_portfolio(prepped,prepared=data,**config)))
    result=dict(name=name,baseline_config=base_config,baseline=baseline,baseline_pass=passes(baseline,btc),
                signal_count=sum(int(df.SIGNAL.sum()) for df in prepped.values()),sweep=rows,
                winners=[r for r in rows if passes(r['metrics'],btc)])
    if baseline['trades']==0 or not np.isfinite(baseline['cagr']) or baseline['cagr']>1000:
        raise ValueError(f'abnormal baseline: {name}: {baseline}')
    print(name,json.dumps(baseline,ensure_ascii=False),f'sweep={len(rows)}, winners={len(result["winners"])}',flush=True)
    return result


def run():
    frames,manifest,skipped=load_data()
    output=dict(runtime=dict(python=sys.version, numpy=np.__version__, pandas=pd.__version__, indicators=ta.__name__), since=SINCE,cutoff_exclusive='2026-10-06',btc_cagr=benchmark(frames),manifest=manifest,skipped=skipped,strategies=[])
    path=ROOT/'docs/technical-ict-results-2026-10-06.json'
    for name in NAMES:
        output['strategies'].append(run_strategy(name,frames))
        path.write_text(json.dumps(output,ensure_ascii=False,indent=2))
    return output


if __name__=='__main__':
    run()
