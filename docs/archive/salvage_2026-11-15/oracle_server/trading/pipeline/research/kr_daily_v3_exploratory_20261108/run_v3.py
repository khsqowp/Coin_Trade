#!/usr/bin/env python3
"""Exploratory KR V3. Execute only after PREREG.md freeze; no live integrations."""
import argparse, csv, datetime as dt, hashlib, json, math, os, sys, time
from pathlib import Path

import numpy as np
import pandas as pd
import engine_v2copy as E

OUT = Path('/app/out')
KR = Path('/app/kr_daily_v2')
V1 = Path('/app/kr_daily_v1')
UNIVERSES = (50, 100, 200)
HOLDINGS_K = 20
CAPITAL = 100_000_000.0
COMMISSION = 0.00015
TAX = 0.002
GAP = -0.025
START = '2012-06-01'
END = '2026-11-03'
IS_END = '2019-12-31'
OOS_START = '2020-01-01'
PREREG_SHA256 = '889572bb770f81d9b821df8330738e7731cb9baf75734d4d110fc2ca4c319477'
INPUT_AGG_SHA256 = '8458fef56e4ec99b960a3194ebc6cf59ecea5f2a23ec633d64603474b3afbc79'
KODEX_SHA256 = '70f5c0f4681bd1548404ccb7cbc1ae6cfbdeb6d2a00ab886db7b2b41c06c106d'
REGIME_SHA256 = '5c1b7262df33a38ba2d388897161fd1055bf18ca1e4584d38c271fae8649b82d'
ADDENDA_SHA256 = {
 'A2.md':'d6aa88e04fdc4f33d673103bf4d0b73e6f32fcb24cbbc584056f0fab7fd8dff3',
 'A3.md':'89285241c66e49c6986fe28b313c1e8074a5a7cbdc3f56f4f47cc157f30850b1',
 'A4.md':'16052ff36eecbb3ecd437998353d3314c4a88d0374658e049070bab7feed17b2',
 'A5.md':'03efae0b93ce820f302a418755009e2b82c3ef423a2e433eb3815abaec84e06e',
 'A6.md':'ae903f54282dcd028ed548bb4d1e0be1f1f74505b6b07413240e514a2131374b',
 'A7.md':'491bf2093ab55490ae7ae7ca2b9e13068533757a42720bb206b170fb8be41eea'}
A8_PATH = OUT / 'A8.json'
A9_PATH = OUT / 'A9.json'
A10_PATH = OUT / 'A10.json'
A11_PATH = OUT / 'A11.json'
B1_REF = None
RULES = {
 'universe': 'eligible names ranked by close-t lagged 60-session median traded value; N=50/100/200; requires >=252 bars, traded t, >=55/60 sessions traded, median value>=KRW1bn',
 'holdings': 'fixed K=20 for each universe; each position is 1/K=5% NAV; fewer than 20 signals leaves unfilled weight in cash',
 'rsi2': 'Wilder RSI2 (alpha=1/2) <=10 and close>SMA200; daily signals; exit at close>SMA5 or completed age>=5; fills next tradable open',
 'gap': 'prior close top-N liquidity universe + prior close>SMA200; at next open require gap<=-2.5%; enter at that day close, exit at next session close; K=20; tradability defers exit',
 'residual': 'month-end top-N universe; trailing252 daily log return OLS with intercept vs KODEX200 (>=200 paired); score sum of prior126 daily residuals; positive score; top20; fill next open',
 'costs': '0.015% commission each side; 0.20% sell tax; 0.05/0.10/0.25/0.50% tier slippage by lagged 60-session median traded value',
 'benchmarks': 'KODEX200 buy-hold; monthly EW of contemporaneous top-N liquidity universe, same execution costs',
 'terminal_handling': 'only fetch-log confirmed delisted IDs get last-close proxy and costs; unknown data tails stay stale marked, unresolved exposure/PnL separate'
}


def audit():
    actual_prereg = hashlib.sha256((OUT/'PREREG.md').read_bytes()).hexdigest()
    checks = {
      'prereg hash matches actual file': actual_prereg == PREREG_SHA256,
      'addenda hashes match frozen manifest': {k:fhash(OUT/k) for k in ADDENDA_SHA256} == ADDENDA_SHA256,
      'universe sizes fixed': UNIVERSES == (50,100,200),
      'holdings fixed K20 and 5 percent allocation': HOLDINGS_K == 20 and abs(1.0/HOLDINGS_K-0.05)<1e-12,
      'gap close entry and next close exit': 'enter at that day close' in RULES['gap'] and 'next session close' in RULES['gap'],
      'residual log return with intercept': 'daily log return OLS with intercept' in RULES['residual'],
      'RSI exits wait for later signal': 'a not in exits' in open(__file__).read(),
      'costs fixed': COMMISSION == 0.00015 and TAX == 0.002,
      'aligned slice implementation present': 'def aligned()' in open(__file__).read(),
      'runtime provenance verifier present': 'def verify_provenance()' in open(__file__).read(),
      'trade-only marks and jump diagnostics': 'np.where(P.has, P.c, np.nan)' in Path(E.__file__).read_text() and 'ro = np.where(P.has[t], P.o[t], pc)' in Path(E.__file__).read_text() and 'rc = np.where(P.has[t], P.c[t], np.nan)' in Path(E.__file__).read_text() and 'P.last = np.where(P.has.any(0)' in Path(E.__file__).read_text() and 'traded_close=close.where(traded)' in open(__file__).read() and 'P.has[:,j]&np.isfinite(P.c[:,j])' in open(__file__).read() and 'P.has[t,a] and P.c[t,a] > sma5[t,a]' in open(__file__).read(),
      'exact US marker binding present': 'does not match exact A9 expected hash' in open(__file__).read(),
      'scope bounded': str(OUT) == '/app/out',
    }
    for k,v in checks.items(): print(('PASS' if v else 'FAIL') + ' | ' + k)
    if not all(checks.values()): raise SystemExit(2)
    print(json.dumps({'rules': RULES, 'actual_prereg_sha256':actual_prereg,
      'input_aggregate_sha256': INPUT_AGG_SHA256, 'kodex_sha256': KODEX_SHA256, 'regime_sha256': REGIME_SHA256}, indent=2))


def universe(P, t, n):
    if t < 0 or t >= len(P.cal): return np.array([], dtype=int)
    eligible = P.elig[t] & np.isfinite(P.med60[t]) & (P.med60[t] >= 1e9)
    ix = np.flatnonzero(eligible)
    if len(ix) > n:
        ix = ix[np.argsort(-P.med60[t, ix], kind='stable')[:n]]
    return ix


def rsi2(P):
    cf = pd.DataFrame(P.cf, index=P.cal)
    delta = cf.diff()
    gains = delta.clip(lower=0).ewm(alpha=0.5, adjust=False, min_periods=2).mean()
    losses = (-delta.clip(upper=0)).ewm(alpha=0.5, adjust=False, min_periods=2).mean()
    rs = gains / losses.replace(0, np.nan)
    rsi = 100.0 - 100.0 / (1.0 + rs)
    rsi = rsi.where(losses > 0, 100.0).where(gains > 0, 0.0)
    rsi = rsi.mask((gains == 0) & (losses == 0), 50.0)
    rsi = rsi.to_numpy(np.float32)
    sma5 = cf.rolling(5, min_periods=5).mean().to_numpy(np.float32)
    sma200 = cf.rolling(200, min_periods=200).mean().to_numpy(np.float32)
    return rsi, sma5, sma200


def build_rsi(P, N, rsi, sma5, sma200, maxhold=5):
    sig, held = {}, {}
    for t in range(P.t0 - 1, len(P.cal)-1):
        # Age advances once a position has passed its signal-close entry and subsequent sessions.
        if t > P.t0 - 1:
            for a in list(held): held[a] += 1
        exits = {a for a, age in held.items() if (P.has[t,a] and P.c[t,a] > sma5[t,a]) or age >= maxhold or t >= P.last[a]}
        for a in exits: held.pop(a, None)
        u = universe(P, t, N)
        cand = [int(a) for a in u if a not in held and a not in exits and np.isfinite(rsi[t,a]) and rsi[t,a] <= 10.0 and P.cf[t,a] > sma200[t,a]]
        cand.sort(key=lambda a: (float(rsi[t,a]), -float(P.med60[t,a])))
        for a in cand:
            if len(held) >= HOLDINGS_K: break
            held[a] = 0
        sig[t] = {a:1.0/HOLDINGS_K for a in held} if held else {}
    return sig


RESIDUAL_SCORE_CACHE = {}

def residual_scores(P):
    key=id(P)
    if key in RESIDUAL_SCORE_CACHE: return RESIDUAL_SCORE_CACHE[key]
    cal=P.cal
    me=sorted(E.month_end_idx(cal))
    close_log=np.log(np.maximum(P.cf,1e-20))
    slog=np.full_like(P.cf,np.nan,dtype=np.float64)
    slog[1:]=np.diff(close_log,axis=0)
    slog=np.where(P.has,slog,np.nan)
    ilog=np.full(len(cal),np.nan,dtype=np.float64)
    ilog[1:]=np.diff(np.log(np.maximum(P.idx_close,1e-20)))
    out={}
    for t in me:
        if t<max(P.t0-1,253,127) or t+1>=len(cal): continue
        w0=t-251; x=ilog[w0:t+1]; Y=slog[w0:t+1]
        good=np.isfinite(x)
        if good.sum()<200: continue
        xg=x[good]; ym=Y[good]; paired=np.isfinite(ym)
        sy=np.sum(np.where(paired,ym,0.0),axis=0)
        sx=np.sum(paired*xg[:,None],axis=0)
        sx2=np.sum(paired*(xg[:,None]**2),axis=0)
        syx=np.sum(np.where(paired,ym*xg[:,None],0.0),axis=0)
        nn=paired.sum(axis=0)
        denom=sx2-np.divide(sx*sx,nn,out=np.full_like(sx,np.nan),where=nn>0)
        beta=np.divide(syx-np.divide(sx*sy,nn,out=np.zeros_like(sx),where=nn>0),denom,out=np.full_like(sy,np.nan),where=denom>0)
        alpha=np.divide(sy-beta*sx,nn,out=np.full_like(sy,np.nan),where=nn>0)
        r0=t-125; x126=ilog[r0:t+1]; y126=slog[r0:t+1]
        complete=np.isfinite(y126).all(axis=0)&np.isfinite(x126).all()
        score=np.sum(y126-(alpha[None,:]+x126[:,None]*beta[None,:]),axis=0)
        score[~complete|(nn<200)|~np.isfinite(beta)]=np.nan
        out[t]=score
    RESIDUAL_SCORE_CACHE[key]=out
    return out

def build_residual(P,N):
    out={}
    for t,score in residual_scores(P).items():
        cand=universe(P,t,N)
        valid=cand[np.isfinite(score[cand])&(score[cand]>0)]
        if len(valid):
            take=valid[np.argsort(-score[valid],kind='stable')[:HOLDINGS_K]]
            out[t]={int(a):1.0/HOLDINGS_K for a in take}
        else: out[t]={}
    return out

def build_universe_bench(P,N):
    out={}
    for t in sorted(E.month_end_idx(P.cal)):
        if t < P.t0-1 or t+1 >= len(P.cal): continue
        ix=universe(P,t,N)
        out[t]={int(a):1.0/len(ix) for a in ix} if len(ix) else {}
    return out


def regimes(P, nav, b1):
    return E.regimes(nav,b1)


def metrics_record(P, name, sig, mode='full', slip_mult=1.0, tax=TAX, jump_exclude=()):
    nav, ex = E.simulate(P, sig, mode=mode, full_rebal=name.startswith('B_'),
                         slip_mult=slip_mult, tax=tax, capital=CAPITAL, exclude=jump_exclude)
    yrs = len(nav) / 252
    parts = np.asarray(ex.get('parts', []), dtype=float)
    pnl = np.asarray(ex['pnl'], dtype=float)
    pnl_sum = float(pnl.sum())
    top = np.argsort(pnl)[-10:][::-1] if len(pnl) else np.array([], dtype=int)
    rec = {
      'name': name, 'split': E.split(nav), 'round_trips': len(ex['trades']),
      'win_rate': float(np.mean(np.asarray(ex['trades']) > 0)) if ex['trades'] else None,
      'total_cost_fraction_initial': float(ex['costs']),
      'cost_drag_fraction_initial_per_year': float(ex['costs'] / yrs),
      'gross_turnover_x_initial_per_year': float(ex.get('traded_notional', 0.0) / yrs),
      'decision_count': len(sig), 'days_in_market': float((nav.expo > 0.01).mean()),
      'capacity_order_to_median_value_ratio_100m': {
        'p50': float(np.percentile(parts,50)) if len(parts) else None,
        'p95': float(np.percentile(parts,95)) if len(parts) else None,
        'max': float(np.max(parts)) if len(parts) else None,
        'scaled_10m_p95': float(np.percentile(parts,95)*0.1) if len(parts) else None,
        'scaled_1bn_p95': float(np.percentile(parts,95)*10) if len(parts) else None},
      'regime_types': E.regimes(nav, B1_REF)[1],
      'terminal_liquidations': int(ex.get('terminal_liquidations', 0)),
      'unresolved_ended_positions': int(ex.get('unresolved_position_count',0)),
      'unresolved_stale_marked_value_nav_units': float(ex.get('unresolved_marked_value',0.0)),
      'unresolved_marked_pnl_nav_units': float(ex.get('unresolved_pnl',0.0)),
      'open_positions_at_end': int(ex.get('open_end_position_count',0)),
      'top10_pnl_share': float(pnl[top].sum()/pnl_sum) if pnl_sum > 0 else None,
      'top10_pnl_symbols': [P.syms[int(a)] for a in top]
    }
    return rec, nav, ex


def gap_sim(P, N, slip_mult=1.0, tax=TAX, jump_exclude=()):
    excluded = set(jump_exclude)
    T, start = len(P.cal), P.t0
    cash = CAPITAL
    pos = {}
    navs, expos, orders, roundtrips = [], [], [], []
    costs = notional = 0.0
    pnl_by_sym = {}
    deferred_exit_count = terminal_count = empty_budget_signals = 0
    for t in range(start, T):
        if t > start:
            for a, p in list(pos.items()):
                prev_c, cur_c = float(P.cf[t-1,a]), float(P.cf[t,a])
                if np.isfinite(prev_c) and np.isfinite(cur_c) and prev_c > 0 and cur_c > 0:
                    p['value'] *= cur_c / prev_c
                if t >= p['exit_t'] and P.trad[t,a]:
                    x = p['value']; med = float(P.med60[t-1,a])
                    fee = x * (E.slip_of(med, slip_mult) + COMMISSION + tax)
                    cash += x - fee; costs += fee; notional += x
                    orders.append(x / max(med,1.0))
                    net_pnl = x - fee - p['basis']
                    sym = P.syms[a]; pnl_by_sym[sym] = pnl_by_sym.get(sym,0.0) + net_pnl
                    roundtrips.append(net_pnl / p['basis'] if p['basis'] > 0 else 0.0)
                    if t > p['exit_t']: deferred_exit_count += 1
                    del pos[a]
        if t > 0:
            prior = t - 1
            candidates = []
            for a in universe(P, prior, N):
                a = int(a)
                if a in excluded or a in pos or not P.trad[t,a] or not np.isfinite(P.o[t,a]) or P.o[t,a] <= 0: continue
                if not np.isfinite(P.cf[prior,a]) or P.cf[prior,a] <= 0 or not np.isfinite(P.med60[prior,a]): continue
                if prior < 199: continue
                hist = P.cf[prior-199:prior+1,a]
                if not np.isfinite(hist).all() or P.cf[prior,a] <= np.mean(hist): continue
                gap = float(P.o[t,a] / P.cf[prior,a] - 1.0)
                if gap <= GAP: candidates.append((gap,a))
            candidates.sort(key=lambda z: (z[0], -float(P.med60[prior,z[1]])))
            slots = max(0, HOLDINGS_K - len(pos))
            for _,a in candidates[:slots]:
                if not P.has[t,a] or not np.isfinite(P.c[t,a]) or P.c[t,a] <= 0: continue
                nav_pre = cash + sum(p['value'] for p in pos.values())
                budget = min(cash, nav_pre / HOLDINGS_K)
                if not np.isfinite(budget) or budget <= 0:
                    empty_budget_signals += 1; continue
                med = float(P.med60[prior,a])
                buy_rate = E.slip_of(med,slip_mult) + COMMISSION
                spend = min(cash, budget * (1.0 + buy_rate))
                principal = spend / (1.0 + buy_rate)
                if not np.isfinite(principal) or principal <= 0:
                    empty_budget_signals += 1; continue
                fee = spend - principal
                cash -= spend; costs += fee; notional += principal
                orders.append(principal / max(med,1.0))
                pos[a] = {'value':principal, 'basis':spend, 'exit_t':t+1}
        nav = cash + sum(p['value'] for p in pos.values())
        navs.append(nav)
        expos.append(sum(p['value'] for p in pos.values()) / nav if nav > 0 else 0.0)
    # Terminal close proxy only for confirmed delistings; unknown tails remain stale-marked.
    unresolved_positions=[]
    if T>start:
        for a,p in list(pos.items()):
            if P.confirmed_delisted[a]:
                x=p['value']; med=float(P.med60[P.last[a],a])
                fee=x*(E.slip_of(med,slip_mult)+COMMISSION+tax)
                cash+=x-fee; costs+=fee; notional+=x; terminal_count+=1
                net_pnl=x-fee-p['basis']; sym=P.syms[a]
                pnl_by_sym[sym]=pnl_by_sym.get(sym,0.0)+net_pnl
                roundtrips.append(net_pnl/p['basis'] if p['basis']>0 else 0.0)
                orders.append(x/max(med,1.0))
            else:
                unresolved_positions.append((a,p))
                if P.unresolved_ended[a]:
                    sym=P.syms[a]
                    pnl_by_sym[sym]=pnl_by_sym.get(sym,0.0)+p['value']-p['basis']
        navs[-1]=cash+sum(p['value'] for _,p in unresolved_positions)
        expos[-1]=sum(p['value'] for _,p in unresolved_positions)/navs[-1] if navs[-1]>0 else 0.0
    ix=P.cal[start:T]
    df=pd.DataFrame({'nav':navs,'expo':expos},index=ix)
    df['ret']=df.nav.pct_change().fillna(0.0)
    yrs=len(df)/252; parts=np.asarray(orders,dtype=float)
    pnl_sum=sum(pnl_by_sym.values())
    top=sorted(pnl_by_sym.items(),key=lambda kv:kv[1],reverse=True)[:10]
    rec={'name':f'GAP_REVERSAL_K20_TOP{N}','split':E.split(df),
         'round_trips':len(roundtrips),'win_rate':float(np.mean(np.asarray(roundtrips)>0)) if roundtrips else None,
         'total_cost_fraction_initial':costs/CAPITAL,'cost_drag_fraction_initial_per_year':costs/CAPITAL/yrs,
         'gross_turnover_x_initial_per_year':notional/CAPITAL/yrs,'decision_count':len(parts),
         'days_in_market':float((df.expo>0.01).mean()),'empty_budget_signals':empty_budget_signals,
         'capacity_order_to_median_value_ratio_100m':{
           'p50':float(np.percentile(parts,50)) if len(parts) else None,
           'p95':float(np.percentile(parts,95)) if len(parts) else None,
           'max':float(np.max(parts)) if len(parts) else None,
           'scaled_10m_p95':float(np.percentile(parts,95)*0.1) if len(parts) else None,
           'scaled_1bn_p95':float(np.percentile(parts,95)*10) if len(parts) else None},
         'regime_types':E.regimes(df,B1_REF)[1],'terminal_liquidations':terminal_count,
         'unresolved_ended_positions':sum(bool(P.unresolved_ended[a]) for a,_ in unresolved_positions),
         'unresolved_stale_marked_value':sum(p['value'] for a,p in unresolved_positions if P.unresolved_ended[a]),
         'unresolved_marked_pnl':sum(p['value']-p['basis'] for a,p in unresolved_positions if P.unresolved_ended[a]),
         'open_positions_at_end':len(unresolved_positions),
         'top10_pnl_share':sum(v for _,v in top)/pnl_sum if pnl_sum>0 else None,
         'top10_pnl_symbols':[k for k,_ in top], 'deferred_exit_count':deferred_exit_count}
    return rec,df,{'costs':costs,'roundtrips':roundtrips,'pnl_by_sym':pnl_by_sym}


def qc(P):
    files=sorted((KR/'data').glob('*.parquet'))
    jumps=[]
    for p in files:
        d=pd.read_parquet(p)
        close=d['close'].astype(float)
        traded=np.isfinite(close)&(close>0)&(pd.to_numeric(d['volume'],errors='coerce').fillna(0)>0)
        traded_close=close.where(traded)
        prev=traded_close.ffill().shift(1)
        ret=traded_close.div(prev.where(np.isfinite(prev)&(prev>0))).sub(1)
        lim=np.where(pd.to_datetime(d.index)<pd.Timestamp('2015-06-15'),0.155,0.305)
        dates=pd.Series(pd.to_datetime(d.index),index=d.index)
        prev_traded_date=dates.where(traded).ffill().shift(1)
        gap=(dates-prev_traded_date).dt.days.fillna(1).to_numpy()>7
        bad=traded.to_numpy()&(ret.abs().to_numpy()>lim)&~gap
        if bad.any(): jumps.append((p.stem,int(bad.sum())))
    post_repair_jumps=[]
    for j,sym in enumerate(P.syms):
        ii=np.flatnonzero(P.has[:,j]&np.isfinite(P.c[:,j])&(P.c[:,j]>0))
        for pidx,tidx in zip(ii[:-1],ii[1:]):
            if (P.cal[tidx]-P.cal[pidx]).days>7: continue
            ret=float(P.c[tidx,j]/P.c[pidx,j]-1)
            lim=0.155 if P.cal[tidx]<pd.Timestamp('2015-06-15') else 0.305
            if abs(ret)>lim: post_repair_jumps.append((sym,str(P.cal[tidx].date()),ret))
    log=[]
    lp=KR/'fetch_log.jsonl'
    if lp.exists():
        for line in lp.read_text().splitlines():
            try: log.append(json.loads(line))
            except Exception: pass
    ticker_reuse=[]
    raw_universe=pd.read_csv(KR/'universe'/'universe_raw.csv',dtype=str)
    fetch_by_code={str(x.get('code')):x for x in log if x.get('code')}
    for old_path in files:
        if not old_path.stem.endswith('_old'): continue
        base=old_path.stem[:-4]
        new_path=KR/'data'/f'{base}.parquet'
        if not new_path.exists(): continue
        old_df=pd.read_parquet(old_path); new_df=pd.read_parquet(new_path)
        old_code=fetch_by_code.get(old_path.stem,{}); new_code=fetch_by_code.get(base,{})
        universe_rows=raw_universe[raw_universe['code'].astype(str)==base]
        required_identity=['name','market','code','status']
        missing_identity=[c for c in required_identity if c not in raw_universe.columns]
        if missing_identity: raise ValueError(f'universe_raw.csv missing required identity columns: {missing_identity}; actual={list(raw_universe.columns)}')
        date_identity=[c for c in ('listed','delisted','listed_date','delisted_date') if c in raw_universe.columns]
        identity_cols=required_identity+date_identity
        ticker_reuse.append({'old_instrument':old_path.stem,'new_instrument':base,
          'old_schema':list(old_df.columns),'new_schema':list(new_df.columns),
          'old_rows':len(old_df),'old_start':str(old_df.index.min().date()),'old_end':str(old_df.index.max().date()),
          'new_rows':len(new_df),'new_start':str(new_df.index.min().date()),'new_end':str(new_df.index.max().date()),
          'overlap_dates':len(old_df.index.intersection(new_df.index)),
          'old_fetch_status':old_code.get('status'),'new_fetch_status':new_code.get('status'),
          'universe_columns':list(raw_universe.columns),'universe_records':universe_rows[identity_cols].fillna('').to_dict('records')})
    return {'files':len(files),'loaded_symbols':len(P.syms),'confirmed_delisted_loaded':int(P.confirmed_delisted.sum()),
      'ended_early_instruments':int(P.ended_early.sum()),
      'unresolved_ended_instruments':int(P.unresolved_ended.sum()),
      'unresolved_ended_symbols':[P.syms[i] for i in np.flatnonzero(P.unresolved_ended)],
      'ticker_reuse_identity_splits':ticker_reuse,
      'fetch_log_rows':len(log),'fetch_errors':sum(bool(x.get('error')) for x in log),
      'zero_rows':sum(x.get('rows')==0 for x in log),'no_row_markers':len(list((KR/'data').glob('*.none'))),
      'raw_jump_symbols':len(jumps),'raw_jump_events':sum(x[1] for x in jumps),'raw_jump_symbol_list':[x[0] for x in jumps],
      'repair_names':len(E.REPAIRS),'repair_events':sum(len(x[1]) for x in E.REPAIRS),
      'invalid_ohlc_rows':len(E.INVALID_PX_ROWS),'invalid_ohlc_sample':E.INVALID_PX_ROWS[:50],
      'invalid_repair_ratio_events':len(E.INVALID_RATIO_EVENTS),'invalid_repair_ratio_sample':E.INVALID_RATIO_EVENTS[:50],
      'post_repair_jump_events':len(post_repair_jumps),'post_repair_jump_symbols':len(set(x[0] for x in post_repair_jumps)),
      'post_repair_jump_sample':post_repair_jumps[:50],
      'avg_eligible_by_year':{str(y):float(np.mean([P.elig[t].sum() for t,d in enumerate(P.cal) if d.year==y])) for y in range(2012,2027)}}


def fhash(path):
    return hashlib.sha256(Path(path).read_bytes()).hexdigest()

def verify_inputs():
    lines=[]
    for f in sorted((KR/'data').glob('*.parquet'), key=lambda p:p.name.encode('utf-8')):
        h=hashlib.sha256(f.read_bytes()).hexdigest()
        lines.append(f"{h}  research/kr_daily_v2/data/{f.name}\n")
    agg=hashlib.sha256(''.join(lines).encode()).hexdigest()
    kodex=fhash(V1/'data'/'069500.parquet'); regime=fhash(V1/'REGIMES.json')
    prereg=fhash(OUT/'PREREG.md')
    addenda={k:fhash(OUT/k) for k in ADDENDA_SHA256}
    provenance=verify_provenance()
    actual={'input_aggregate_sha256':agg,'kodex_sha256':kodex,'regime_sha256':regime,'prereg_sha256':prereg,'prereg_addendum_sha256':addenda}
    expected={'input_aggregate_sha256':INPUT_AGG_SHA256,'kodex_sha256':KODEX_SHA256,'regime_sha256':REGIME_SHA256,'prereg_sha256':PREREG_SHA256,'prereg_addendum_sha256':ADDENDA_SHA256}
    if actual!=expected: raise SystemExit('frozen input/prereg hash mismatch: '+json.dumps({'actual':actual,'expected':expected}))
    return {**actual, **provenance}


def verify_provenance():
    """Verify A8-A11 and all source/code hashes before strategy calculations."""
    if not A8_PATH.is_file() or not A9_PATH.is_file():
        raise SystemExit('A8/A9 provenance file is missing')
    a8_sha=fhash(A8_PATH)
    expected_a8=os.environ.get('KR_V3_EXPECTED_A8_SHA256','').lower()
    if len(expected_a8)!=64 or any(c not in '0123456789abcdef' for c in expected_a8):
        raise SystemExit('KR_V3_EXPECTED_A8_SHA256 must be supplied by the reviewed launcher')
    if a8_sha!=expected_a8:
        raise SystemExit('A8 provenance file hash does not match reviewed launcher expectation')
    a8=json.loads(A8_PATH.read_text())
    a9_sha=fhash(A9_PATH)
    expected_a9=os.environ.get('KR_V3_EXPECTED_A9_SHA256','').lower()
    if len(expected_a9)!=64 or any(c not in '0123456789abcdef' for c in expected_a9):
        raise SystemExit('KR_V3_EXPECTED_A9_SHA256 must be supplied by the reviewed launcher')
    if a9_sha!=expected_a9:
        raise SystemExit('A9 provenance file hash does not match reviewed launcher expectation')
    if not A10_PATH.is_file() or not A11_PATH.is_file(): raise SystemExit('A10/A11 QC provenance addendum is missing')
    a10_sha=fhash(A10_PATH)
    expected_a10=os.environ.get('KR_V3_EXPECTED_A10_SHA256','').lower()
    if len(expected_a10)!=64 or any(c not in '0123456789abcdef' for c in expected_a10):
        raise SystemExit('KR_V3_EXPECTED_A10_SHA256 must be supplied by the reviewed launcher')
    if a10_sha!=expected_a10: raise SystemExit('A10 QC addendum hash does not match reviewed launcher expectation')
    a10=json.loads(A10_PATH.read_text())
    a11_sha=fhash(A11_PATH)
    expected_a11=os.environ.get('KR_V3_EXPECTED_A11_SHA256','').lower()
    if len(expected_a11)!=64 or any(c not in '0123456789abcdef' for c in expected_a11):
        raise SystemExit('KR_V3_EXPECTED_A11_SHA256 must be supplied by the reviewed launcher')
    if a11_sha!=expected_a11: raise SystemExit('A11 QC addendum hash does not match reviewed launcher expectation')
    a11=json.loads(A11_PATH.read_text())
    a9=json.loads(A9_PATH.read_text())
    expected=a9.get('expected_sha256',{})
    actual={
      'fetch_log.jsonl':fhash(KR/'fetch_log.jsonl'),
      'universe_raw.csv':fhash(KR/'universe'/'universe_raw.csv'),
      'run_v3.py':fhash(Path(__file__)),
      'engine_v2copy.py':fhash(Path(E.__file__)),
    }
    if expected.get('fetch_log.jsonl')!=actual['fetch_log.jsonl'] or expected.get('universe_raw.csv')!=actual['universe_raw.csv']:
        raise SystemExit('A9 data-source provenance hash mismatch: '+json.dumps({'actual':actual,'expected':expected}))
    if expected.get('run_v3.py')!=a10.get('prior_runner_sha256') or a9_sha!=a10.get('prior_a9_sha256'):
        raise SystemExit('A10 prior-code/A9 binding mismatch')
    if a10.get('runner_sha256')!=a11.get('prior_runner_sha256') or a10_sha!=a11.get('prior_a10_sha256') or expected.get('engine_v2copy.py')!=a11.get('prior_engine_sha256'):
        raise SystemExit('A11 prior-code/A10 binding mismatch')
    if a11.get('runner_sha256')!=actual['run_v3.py'] or a11.get('engine_sha256')!=actual['engine_v2copy.py']:
        raise SystemExit('A11 runner or engine provenance hash mismatch: '+json.dumps({'actual':actual,'expected_runner':a11.get('runner_sha256'),'expected_engine':a11.get('engine_sha256')}))
    if a11.get('notes_sha256')!=fhash(OUT/'A11.md'):
        raise SystemExit('A11 notes hash mismatch')
    return {'a8_sha256':a8_sha,'a9_sha256':a9_sha,'a10_sha256':a10_sha,'a11_sha256':a11_sha,'fetch_log_sha256':actual['fetch_log.jsonl'],
      'universe_raw_sha256':actual['universe_raw.csv'],'code_sha256':{
      'run_v3.py':actual['run_v3.py'],'engine_v2copy.py':actual['engine_v2copy.py']},
      'us_a3_expected_sha256':a9.get('us_a3_expected_sha256',{})}


def aligned():
    verify_inputs()
    marker=OUT/'US_A3_FINALIZED.json'
    if not marker.exists():
        raise SystemExit('aligned calculation paused: verified US_A3_FINALIZED.json marker is required')
    payload=json.loads(marker.read_text())
    a9=json.loads(A9_PATH.read_text())
    expected_us=a9.get('us_a3_expected_sha256',{})
    required={'prereg_sha256','script_sha256','aligned_end','review_status'}
    if not required.issubset(payload): raise SystemExit('US marker missing required fields')
    for key in ('prereg_sha256','script_sha256'):
        value=payload[key]
        if not isinstance(value,str) or len(value)!=64 or any(c not in '0123456789abcdef' for c in value.lower()):
            raise SystemExit(f'invalid US marker hash: {key}')
        if value.lower()!=str(expected_us.get(key,'')).lower():
            raise SystemExit(f'US marker {key} does not match exact A9 expected hash')
    if payload['aligned_end']!='2026-08-18' or payload['review_status']!='NO-BLOCKER':
        raise SystemExit('US A3 cutoff/reviewer gate does not match required final state')
    nav=pd.read_csv(OUT/'nav.csv',index_col=0,parse_dates=True)
    nav=nav.loc[:'2026-08-18']
    records={}
    for name in nav.columns:
        series=nav[name].dropna(); returns=series.pct_change().fillna(0.0)
        records[name]={
          'IS':E.stats(returns.loc[:IS_END].values),
          'ALIGNED_REUSED_OOS':E.stats(returns.loc[OOS_START:'2026-08-18'].values),
          'ALIGNED_FULL':E.stats(returns.loc[:'2026-08-18'].values)}
    for name in nav.columns:
        if name.startswith('B_'): continue
        n=int(name.rsplit('TOP',1)[1])
        bench=nav['B_KODEX200'].pct_change().fillna(0.0).loc[OOS_START:'2026-08-18']
        ew=nav[f'B_EW_TOP{n}'].pct_change().fillna(0.0).loc[OOS_START:'2026-08-18']
        ret=nav[name].pct_change().fillna(0.0).loc[OOS_START:'2026-08-18']
        records[name]['ALIGNED_REUSED_OOS_EXCESS_ANN_VS_KODEX200']=float((ret-bench).mean()*252)
        records[name]['ALIGNED_REUSED_OOS_EXCESS_ANN_VS_TOPN_EW']=float((ret-ew).mean()*252)
    result={'cutoff':'2026-08-18','us_a3_prereg_sha256':payload['prereg_sha256'],
      'us_a3_script_sha256':payload['script_sha256'],'us_review_status':payload['review_status'],'records':records}
    (OUT/'aligned_results.json').write_text(json.dumps(result,indent=2,default=str))
    rows=[]
    for key,values in records.items():
        for split,metrics in values.items(): rows.append({'strategy':key,'split':split,**metrics} if isinstance(metrics,dict) else {'strategy':key,split:metrics})
    pd.DataFrame(rows).to_csv(OUT/'aligned_summary.csv',index=False)
    (OUT/'ALIGNED_REPORT.md').write_text('# KR-US aligned comparison window\n\nCutoff: 2026-08-18. US preregistration SHA-256: '+payload['prereg_sha256']+'\nUS script SHA-256: '+payload['script_sha256']+'\nReview status: '+payload['review_status']+'\n\nThis retrospective slice is contaminated. It reuses equity curves that include prior state through the cutoff; no next-session signal after 2026-08-18 enters the aligned metrics.\n')
    print(json.dumps({'cutoff':'2026-08-18','us_prereg_sha256':payload['prereg_sha256'],'us_script_sha256':payload['script_sha256'],'aligned_records':len(records)},indent=2))

def run():
    global B1_REF
    OUT.mkdir(parents=True,exist_ok=True)
    input_hashes=verify_inputs()
    run_id='KR-V3-EXPLORATORY-'+dt.datetime.now(dt.timezone.utc).strftime('%Y%m%dT%H%M%SZ')
    manifest={'run_id':run_id,'created_utc':dt.datetime.now(dt.timezone.utc).isoformat(),'prereg_sha256':input_hashes['prereg_sha256'],'prereg_addendum_sha256':input_hashes['prereg_addendum_sha256'],'a8_sha256':input_hashes['a8_sha256'],'a9_sha256':input_hashes['a9_sha256'],'a10_sha256':input_hashes['a10_sha256'],'a11_sha256':input_hashes['a11_sha256'],'fetch_log_sha256':input_hashes['fetch_log_sha256'],'universe_raw_sha256':input_hashes['universe_raw_sha256'],'code_sha256':input_hashes['code_sha256'],
      'input_aggregate_sha256':INPUT_AGG_SHA256,'kodex_sha256':KODEX_SHA256,'regime_sha256':REGIME_SHA256,
      'protocol':RULES,'start':START,'end':END,'is_end':IS_END,'reused_oos_start':OOS_START,'aligned_end_after_US_prereg_final':'2026-08-18','contamination':'same panel and market path previously examined; not untouched OOS'}
    (OUT/'run_manifest.json').write_text(json.dumps(manifest,indent=2))
    P=E.load_panel(); b1=E.b1_nav(P); B1_REF=b1; qc_rec=qc(P)
    rsi,sma5,sma200=rsi2(P)
    results={}; navs={'B_KODEX200':b1}; extras={}
    # Main fixed rules
    for N in UNIVERSES:
      bench=build_universe_bench(P,N)
      br,bnav,bex=metrics_record(P,f'B_EW_TOP{N}',bench)
      results[f'B_EW_TOP{N}']=br; navs[f'B_EW_TOP{N}']=bnav; extras[f'B_EW_TOP{N}']=bex
      rsig=build_rsi(P,N,rsi,sma5,sma200)
      rr,rnav,rex=metrics_record(P,f'RSI2_MR_K20_TOP{N}',rsig)
      results[f'RSI2_MR_K20_TOP{N}']=rr; navs[f'RSI2_MR_K20_TOP{N}']=rnav; extras[f'RSI2_MR_K20_TOP{N}']=rex
      msig=build_residual(P,N)
      mr,mnav,mex=metrics_record(P,f'RESIDUAL_MOM_K20_TOP{N}',msig)
      results[f'RESIDUAL_MOM_K20_TOP{N}']=mr; navs[f'RESIDUAL_MOM_K20_TOP{N}']=mnav; extras[f'RESIDUAL_MOM_K20_TOP{N}']=mex
      gr,gnav,gex=gap_sim(P,N)
      results[f'GAP_REVERSAL_K20_TOP{N}']=gr; navs[f'GAP_REVERSAL_K20_TOP{N}']=gnav; extras[f'GAP_REVERSAL_K20_TOP{N}']=gex
      print('MAIN',N,flush=True)
    # Benchmarks
    results['B_KODEX200']={'split':E.split(b1),'regime_types':E.regimes(b1,b1)[1]}
    for key in list(results):
      if key.startswith('B_'): continue
      nav=navs[key]; br=b1['ret'].reindex(nav.index).fillna(0.0)
      n=int(key.rsplit('TOP',1)[1]); ur=navs[f'B_EW_TOP{n}']['ret'].reindex(nav.index).fillna(0.0)
      oos=nav.loc[OOS_START:]
      rr=oos['ret'].values; bret=br.reindex(oos.index).values; uret=ur.reindex(oos.index).values
      results[key]['oos_mean_excess_ann_vs_kodex200']=float(np.mean(rr-bret)*252) if len(rr) else None
      results[key]['oos_mean_excess_ann_vs_topN_ew']=float(np.mean(rr-uret)*252) if len(rr) else None
    # Cost sensitivities of each fixed strategy and universe benchmark, all rules unchanged.
    sens={}
    for key in list(results):
      if key=='B_KODEX200': continue
      if key.startswith('GAP_REVERSAL'):
        N=int(key.rsplit('TOP',1)[1]); sig_runner=lambda sm,tx: gap_sim(P,N,slip_mult=sm,tax=tx)
      else:
        if key.startswith('B_EW_TOP'): sig=build_universe_bench(P,int(key.rsplit('TOP',1)[1]))
        elif key.startswith('RSI2'): sig=build_rsi(P,int(key.rsplit('TOP',1)[1]),rsi,sma5,sma200)
        elif key.startswith('RESIDUAL'): sig=build_residual(P,int(key.rsplit('TOP',1)[1]))
        else: continue
        sig_runner=lambda sm,tx: metrics_record(P,key,sig,slip_mult=sm,tax=tx)
      sens[key]={}
      for label,sm,tx in [('slip_x2',2.0,TAX),('tax_0.30',1.0,0.003)]:
        rec,_,_=sig_runner(sm,tx); sens[key][label]=rec['split']
    # Data-quality exclusion sensitivity: omit all symbols with raw limit-breaching non-gap jumps.
    jump_exclude=qc_rec['raw_jump_symbol_list']; qcsens={}
    P2=E.load_panel(exclude=jump_exclude)
    rsi2a,sma5a,sma200a=rsi2(P2)
    for N in UNIVERSES:
      for family,sig in [('RSI2',build_rsi(P2,N,rsi2a,sma5a,sma200a)),('RESIDUAL',build_residual(P2,N))]:
        rec,_,_=metrics_record(P2,f'{family}_K20_TOP{N}_EXCLUDE_RAW_JUMP_NAMES',sig)
        qcsens[f'{family}_TOP{N}']=rec['split']
      gr,_,_=gap_sim(P2,N,jump_exclude=jump_exclude)
      qcsens[f'GAP_TOP{N}']=gr['split']
    (OUT/'results.json').write_text(json.dumps({'run_id':run_id,'results':results,'cost_sensitivity':sens,'raw_jump_symbol_exclusion_sensitivity':qcsens,'qc':qc_rec},indent=2,default=str))
    pd.DataFrame({k:v['nav'] for k,v in navs.items()}).to_csv(OUT/'nav.csv')
    rows=[]
    for k,v in results.items():
      for split,met in v.get('split',{}).items():
        rows.append({'strategy':k,'split':split,**met,'turnover_x_initial_per_year':v.get('gross_turnover_x_initial_per_year'),'cost_drag_per_year':v.get('cost_drag_fraction_initial_per_year'),'round_trips':v.get('round_trips'),'unresolved_ended_positions':v.get('unresolved_ended_positions'),'unresolved_marked_pnl':v.get('unresolved_marked_pnl',v.get('unresolved_marked_pnl_nav_units')),'oos_excess_vs_kodex200_ann':v.get('oos_mean_excess_ann_vs_kodex200'),'oos_excess_vs_topN_ew_ann':v.get('oos_mean_excess_ann_vs_topN_ew'),'time_in_market':v.get('days_in_market'),'top10_pnl_share':v.get('top10_pnl_share'),'terminal_liquidations':v.get('terminal_liquidations')})
    pd.DataFrame(rows).to_csv(OUT/'summary.csv',index=False)
    report=['# KR Daily V3 exploratory results','',f'Run ID: `{run_id}`','', 'Exploratory only. Reuses the previously examined KRX price panel and index path; OOS is contaminated, and no strategy is promoted.', '', '## Gate and coverage', '', '```json',json.dumps(qc_rec,indent=2), '```','', '## Rules','']
    report += [f'- {k}: {v}' for k,v in RULES.items()]
    report += ['', '## Results by fixed universe, all dates and splits','', '| Strategy | Split | CAGR | Sharpe | MDD | Total return | Cost/year (initial) | Turnover x/year | Round trips | Top10 PnL share |','|---|---|---:|---:|---:|---:|---:|---:|---:|---:|' ]
    for row in rows:
      report.append(f"| {row['strategy']} | {row['split']} | {row.get('cagr','')} | {row.get('sharpe','')} | {row.get('mdd','')} | {row.get('total_return','')} | {row.get('cost_drag_per_year','')} | {row.get('turnover_x_initial_per_year','')} | {row.get('round_trips','')} | {row.get('top10_pnl_share','')} |")
    report += ['', '## Cost sensitivity (OOS Sharpe / CAGR)','', '| Strategy | Sensitivity | OOS Sharpe | OOS CAGR |','|---|---|---:|---:|']
    for k,variants in sens.items():
      for lab,sp in variants.items(): report.append(f"| {k} | {lab} | {sp.get('OOS',{}).get('sharpe')} | {sp.get('OOS',{}).get('cagr')} |")
    report += ['', '## Data-quality exclusion sensitivity','', '| Strategy | OOS Sharpe | OOS CAGR | FULL Sharpe | FULL CAGR |','|---|---:|---:|---:|---:|']
    for k,sp in qcsens.items(): report.append(f"| {k} | {sp.get('OOS',{}).get('sharpe')} | {sp.get('OOS',{}).get('cagr')} | {sp.get('FULL',{}).get('sharpe')} | {sp.get('FULL',{}).get('cagr')} |")
    report += ['', '## Terminal and unresolved positions','', 'Only exact fetch-log `status=delisted` IDs receive a last-valid-close liquidation proxy and sell costs. Other missing tails stay stale-marked without a fictitious sale; counts, marked value, and PnL are in `results.json` and QC. Period-end positions are also left open.', '', '## Sensitivities and QC exclusions','', 'Full records are in `results.json`; dollar-capacity ratios scale from the KRW100m order profile. Jump-name exclusion is not a repair and is reported as a diagnostic.','', '## Limitations','', '- Market capitalization history unavailable; top-N means trailing median traded-value liquidity rank.', '- RSI2/gap overlap with the prior short-term reversal family; residual momentum overlaps prior momentum trials.', '- Regime windows are hindsight descriptive slices only.', '- Daily OHLC cannot model closing-auction queue priority, exact fills, or intraday path.', '- Existing v2 QC found fetch errors, zero-row data, and possible corporate-action jumps; inspect QC section and exclusion sensitivity before interpreting returns.', '- No untouched holdout exists in this reused dataset; follow-up requires a new preregistration and untouched forward-paper evidence.']
    (OUT/'REPORT.md').write_text('\n'.join(report)+'\n')
    print(json.dumps({'run_id':run_id,'result_keys':list(results),'qc':{k:v for k,v in qc_rec.items() if k!='raw_jump_symbol_list'}},indent=2),flush=True)

if __name__=='__main__':
    ap=argparse.ArgumentParser(); ap.add_argument('--audit',action='store_true'); ap.add_argument('--run',action='store_true'); ap.add_argument('--aligned',action='store_true'); args=ap.parse_args()
    if args.audit: audit()
    elif args.run: run()
    elif args.aligned: aligned()
    else: ap.error('select --audit, --run, or --aligned')
