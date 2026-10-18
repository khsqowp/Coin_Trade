"""Run with /opt/anaconda3/bin/python3 -m app.rs_alpha_run [--synthetic]."""
from __future__ import annotations
import argparse
import itertools
import json
import time
from dataclasses import asdict, replace
from pathlib import Path
import numpy as np
import pandas as pd
from app.rs_alpha_lib import ROOT, Config, Engine, load_daily, synthetic, signals, windows, metrics, no_lookahead_test, lookback_neighbors, accounting_test, loader_test

FOLDS=[('2022-01-01','2023-06-30','2023-07-01','2024-06-30'),('2022-07-01','2024-01-31','2024-02-01','2025-01-31'),('2023-01-01','2024-09-30','2024-10-01',None)]

def fast_metrics(bt,start='2022-01-01',end=None):
    """NumPy reductions for the exhaustive grid; same definitions as library metrics."""
    idx=bt.index; mask=(idx>=pd.Timestamp(start))
    if end: mask &= idx<=pd.Timestamp(end)
    a=bt.to_numpy()[mask]; dates=idx[mask]
    if not len(a): return {'Calmar':None,'CAGR':None,'MDD':None,'Sharpe':None,'days':0}
    r=a[:,0]; eq=np.cumprod(1+r); dd=float(np.max(1-eq/np.maximum.accumulate(np.r_[1.,eq])[1:])); years=len(a)/365
    cagr=float(eq[-1]**(1/years)-1) if eq[-1]>0 else -1.
    std=r.std(ddof=1)
    return dict(CAGR=cagr,MDD=dd,Calmar=cagr/dd if dd>0 else 0.,Sharpe=float(r.mean()/std*np.sqrt(365)) if std>0 else 0.,worst_day=float(r.min()),turnover=float(a[:,3].sum()/years),fee_drag=float(a[:,4].sum()/years),funding_drag=float(a[:,2].sum()/years),missing_return_exposure=float(a[:,5].sum()),funding_coverage=float(a[:,6].mean()),days=len(a),yearly={str(y):float(np.prod(1+r[dates.year==y])-1) for y in np.unique(dates.year)})

def evaluate(bt):
    return {'IS':fast_metrics(bt,'2022-01-01','2024-06-30'),'OOS':fast_metrics(bt,'2024-07-01'),'full':fast_metrics(bt)}

def val(record,window='IS'):
    m=record['metrics'][window]
    return m['Calmar'] if m.get('days',0)>0 and m['Calmar'] is not None and np.isfinite(m['Calmar']) else -np.inf

def table(records):
    head='|신호/구성|구간|Calmar|CAGR %|MDD %|Sharpe|회전/년|비용 %/년|\n|---|---|---:|---:|---:|---:|---:|---:|'
    rows=[head]
    for rec in records:
        label=json.dumps(rec['config'],ensure_ascii=False,sort_keys=True)
        for period in ['IS','OOS','full']:
            m=rec['metrics'][period]
            if not m.get('days'): rows.append(f'|{label}|{period}|자료 없음||||||'); continue
            rows.append(f"|{label}|{period}|{m['Calmar']:.2f}|{m['CAGR']*100:.2f}|{m['MDD']*100:.2f}|{m['Sharpe']:.2f}|{m['turnover']:.1f}|{m['fee_drag']*100:.2f}|")
    return '\n'.join(rows)

def corr_md(matrix):
    names=list(matrix)
    if not names:return '적격 슬리브 없음.'
    return '|슬리브|'+'|'.join(names)+'|\n|---|'+'---:|'*len(names)+'\n'+'\n'.join('|'+n+'|'+'|'.join(f'{matrix[n][m]:.3f}' if matrix[n][m] is not None else 'NA' for m in names)+'|' for n in names)

def clean(obj):
    if isinstance(obj,dict): return {str(k):clean(v) for k,v in obj.items()}
    if isinstance(obj,(list,tuple)): return [clean(v) for v in obj]
    if isinstance(obj,(float,np.floating)):return float(obj) if np.isfinite(obj) else None
    if isinstance(obj,np.integer):return int(obj)
    return obj

def research(p,info):
    started=time.monotonic(); e=Engine(p); s=signals(p)
    test=no_lookahead_test(p)
    test.update(accounting=accounting_test(),loader=loader_test())
    baseline_cfg=Config('ret_14'); baseline=e.backtest(e.weights(s['ret_14'],baseline_cfg)); baseline_record={'config':asdict(baseline_cfg),'metrics':evaluate(baseline)}
    reproduction=e.backtest(e.weights(s['ret_14'],baseline_cfg),.0004)
    # Fixed grid declared before any OOS evaluation or ensemble selection.
    grid=[Config(name,k,r,liq,weight) for name,k,r,liq,weight in itertools.product(s,[4,6,8,10],[1,3,5,7],[0.,.2,.33],['equal','inverse_vol','score'])]
    records=[]; fold_best=[None]*3; net_series={}
    print(f'[2/3] fixed grid {len(grid)} configurations; no-lookahead PASS',flush=True)
    for i,cfg in enumerate(grid):
        bt=e.backtest(e.weights(s[cfg.signal],cfg)); rec={'config':asdict(cfg),'metrics':evaluate(bt)}
        records.append(rec)
        for f,fold in enumerate(FOLDS):
            train=fast_metrics(bt,fold[0],fold[1])
            if train.get('days',0)>0 and (fold_best[f] is None or train['Calmar']>fold_best[f]['train']['Calmar']):
                fold_best[f]={'config':asdict(cfg),'train':train}
        if (i+1)%1000==0: print(f'  {i+1}/{len(grid)} ({time.monotonic()-started:.0f}s)',flush=True)
    ranked=sorted([x for x in records if x['metrics']['IS'].get('days',0)>0 and x['metrics']['IS']['MDD']<=.25],key=val,reverse=True)
    # Report best configuration for EVERY signal, selected only on IS.
    singles=[]
    for name in s:
        choices=[r for r in ranked if r['config']['signal']==name]
        if choices: singles.append(choices[0])
        else:
            choices=[r for r in records if r['config']['signal']==name]
            singles.append(max(choices,key=val))
    singles.sort(key=val,reverse=True)
    # Greedy low-correlation sleeves use only IS returns; full/OOS correlations are reports.
    sleeves=[]; sleeve_bt={}; sleeve_w={}; iscorr={}
    for rec in sorted([x for x in singles if x in ranked],key=val,reverse=True):
        cfg=Config(**rec['config']); w=e.weights(s[cfg.signal],cfg); bt=e.backtest(w)
        eligible=True
        for other in sleeves:
            rho=bt.net.loc['2022-01-01':'2024-06-30'].corr(sleeve_bt[other].net.loc['2022-01-01':'2024-06-30'])
            if not np.isfinite(rho) or abs(rho)>.7: eligible=False; break
        if eligible:
            sleeves.append(cfg.signal); sleeve_bt[cfg.signal]=bt; sleeve_w[cfg.signal]=w
        if len(sleeves)==4: break
    nets=pd.DataFrame({n:b.net for n,b in sleeve_bt.items()})
    corr={period:nets.loc[start:end].corr().to_dict() for period,start,end in [('IS','2022-01-01','2024-06-30'),('full','2022-01-01',None),('OOS','2024-07-01',None)]}
    ensembles=[]; ensemble_bts={}
    for count in range(2,len(sleeves)+1):
        names=sleeves[:count]
        ranks=[s[n].where(e.eligible).rank(axis=1,pct=True)-.5 for n in names]
        # Complete-case blend avoids varying future-selected components across dates.
        blend=sum(ranks)/count
        cfg=Config('score_blend_'+str(count))
        bt=e.backtest(e.weights(blend,cfg)); rec={'config':dict(asdict(cfg),components=names),'metrics':evaluate(bt)}
        ensembles.append(rec); ensemble_bts[cfg.signal]=bt
        for method in ['equal','inverse_vol_60']:
            allocation=pd.DataFrame(1/count,index=e.close.index,columns=names)
            if method!='equal':
                risk=nets[names].rolling(60,min_periods=60).std().replace(0,np.nan)
                inv=1/risk
                allocation=inv.div(inv.sum(axis=1),axis=0).fillna(1/count)
            # Allocation observed at close t controls holdings from t+1; turnover of
            # aggregate instrument weights includes allocation changes, netting, fees.
            w=sum(sleeve_w[n].mul(allocation[n],axis=0) for n in names)
            bt=e.backtest(w); name=f'sleeve_{method}_{count}'
            rec={'config':{'signal':name,'components':names,'gross':'<=1 due to netting','allocation':method},'metrics':evaluate(bt)}
            ensembles.append(rec); ensemble_bts[name]=bt
    ensemble_candidates=[x for x in ensembles if x['metrics']['IS']['MDD']<=.25]
    best=max(ranked+ensemble_candidates,key=val) if ranked+ensemble_candidates else baseline_record
    robustness=[]; neighbor_count=0
    for rec in ranked[:5]:
        cfg=Config(**rec['config']); alternatives=[]
        for label,score in lookback_neighbors(p,cfg.signal):
            alternatives.append((replace(cfg,signal=label),score))
        for k in sorted(set([max(1,cfg.k-2),max(1,cfg.k-1),cfg.k+1,cfg.k+2])): alternatives.append((replace(cfg,k=k),s[cfg.signal]))
        for r in sorted(set([max(1,cfg.r-1),cfg.r+1])-{cfg.r}): alternatives.append((replace(cfg,r=r),s[cfg.signal]))
        neighbors=[]
        for nc,score in alternatives:
            nr={'config':asdict(nc),'metrics':evaluate(e.backtest(e.weights(score,nc)))}; neighbors.append(nr)
        neighbor_count+=len(neighbors)
        robustness.append({'selected':rec['config'],'neighbors':neighbors,'fraction_beating_baseline':{period:float(np.mean([val(nr,period)>val(baseline_record,period) for nr in neighbors])) for period in ['IS','OOS']},'comparison':'Calmar','lookback_applicable':True})
    folds=[]
    for selected,fold in zip(fold_best,FOLDS):
        if selected is None: folds.append({'window':fold,'failure':'No train data'}); continue
        cfg=Config(**selected['config']); bt=e.backtest(e.weights(s[cfg.signal],cfg))
        folds.append(dict(selected,window=fold,test=fast_metrics(bt,fold[2],fold[3]),baseline_test=fast_metrics(baseline,fold[2],fold[3]),note='Continuous positions at boundaries; later training intentionally includes dates in global OOS. Not an independent global-OOS selection.'))
    # Best single is the most direct survivorship comparison; ensemble recommendation separate.
    selected=ranked[0] if ranked else baseline_record; sc=Config(**selected['config'])
    first=p['close'].apply(lambda x:x.first_valid_index())
    early=list(first[first<=pd.Timestamp('2022-01-01')].index)
    # Ex-post return uses first/last observable close during the full research sample.
    sample=p['close'].loc['2022-01-01':]
    ex_post=sample.apply(lambda x:x.dropna().iloc[-1]/x.dropna().iloc[0]-1 if len(x.dropna())>=2 else np.nan)
    dropped=list(ex_post.nlargest(5).index)
    survivor={}
    for label,allowed in [('all',list(e.close)),('listed_by_2022',early),('drop_top5',list(e.close.columns.difference(dropped)))]:
        survivor[label]={'symbols':allowed,'baseline':evaluate(e.backtest(e.weights(s['ret_14'],baseline_cfg,allowed))),'selected':evaluate(e.backtest(e.weights(s[sc.signal],sc,allowed)))}
    return clean({'metadata':info,'test':test,'start':str(e.close.index.min().date()),'end':str(e.close.index.max().date()),'symbols':list(e.close),'grid_count':len(grid),'neighbor_count':neighbor_count,'ensemble_count':len(ensembles),'total_evaluations':len(grid)+neighbor_count+len(ensembles),'baseline':baseline_record,'baseline_004':evaluate(reproduction),'singles':singles,'all_grid':records,'top_is':ranked[:5],'correlation':corr,'sleeves':sleeves,'ensembles':ensembles,'walk_forward':folds,'robustness':robustness,'survivorship':survivor,'dropped_top5':dropped,'recommendation':best,'runtime_seconds':time.monotonic()-started})

def report(result,synthetic_mode=False):
    r=result
    parts=['# 암호화폐 무기한 선물 횡단면 신호 연구',
        '## setup',
        f"자료: {'합성 파이프라인 검증용 — 투자 성과 근거로 사용 금지' if synthetic_mode else '로컬 Binance vision CSV'}; {r['start']}~{r['end']}; {len(r['symbols'])}개. IS=2022-01-01~2024-06-30, OOS=2024-07-01~자료 끝. UTC 일봉, 24개 시간봉이 없는 날짜 제외. 60일 연속 유효 종가를 확보한 종목만 적격.",
        f"고정 격자 {r['grid_count']}개, 이웃 {r['neighbor_count']}개, 앙상블 {r['ensemble_count']}개: 총 {r['total_evaluations']}회 평가. 최고 단일 구성은 IS Calmar와 IS MDD≤25%로 선택. OOS는 선택에 사용하지 않는다. 격자: K=4/6/8/10, R=1/3/5/7, 유동성 제외=0/20/33%, 가중=동일/30일 역변동성/순위 강도. 표의 신호별 최고값은 다중검정 결과이며 유의성 검정을 통과한 알파라는 뜻이 아니다.",
        '누락 및 펀딩 자료: `'+json.dumps(r['metadata'],ensure_ascii=False)+'`',
        '## baseline reproduction',table([r['baseline']]),
        '0.04% 비용 비교: `'+json.dumps(r['baseline_004'],ensure_ascii=False)+'`',
        '사용자 제시 기대값은 CAGR +28.9%, MDD 18.6%, Sharpe 1.2다. 다음 차이 때문에 강제 일치시키지 않는다: 45종목 루프 유니버스와 probe 유니버스 차이, 로컬 일봉과 기존 수집기 자료 차이, 60일 적격 조건, 달력 기준 리밸런스 시작 위상, 펀딩 포함, 비용을 포함한 일별 낙폭 산출. probe는 비용을 일별 daily_returns에 기록하지 않아 Sharpe/낙폭과 최종 equity의 비용 처리가 일치하지 않는다.',
        '## single-signal table',table(r['singles']),
        '모든 격자의 세부 결과·연도별 수익률·최악 일간 수익률은 JSON all_grid에 포함한다. 신호별 IS MDD 제한을 통과한 구성이 없으면 해당 신호의 제한 없는 최고 IS Calmar를 표에 포함하되 추천 후보에서 제외한다.',
        '## correlation','IS만 이용해 절대 상관≤0.7인 서로 다른 신호 슬리브를 순차 선택한다. 전체/OOS 행렬은 보고용이다.','### 전체',corr_md(r['correlation']['full']),'### OOS',corr_md(r['correlation']['OOS']),
        '## ensembles',table(r['ensembles']) if r['ensembles'] else '상관 조건을 만족하는 슬리브가 두 개 미만이므로 앙상블을 구성하지 않는다.',
        '점수 앙상블은 단면 백분위 순위 평균이다. 슬리브 앙상블은 기존 목표 비중을 합산하며 60일 수익률 변동성은 close t까지 관측한 값으로 다음 날 배분을 결정한다. 합산 종목 비중의 회전율에 비용을 부과한다. 중복 롱/숏이 상쇄되므로 총 노출은 1 이하이고, 앙상블 간 성과 차이는 순노출 감소 효과를 포함한다. 60일 변동성 미확보 시 동일 배분을 사용한다.',
        '## walk-forward',
        '고정 단일 신호 격자에서 각 훈련 구간 Calmar 최대 구성을 선택하고 동일 테스트 구간의 기준 전략과 비교한다. 구간 경계에서 포지션을 리셋하지 않는다. 두 번째·세 번째 폴드 훈련에는 전역 OOS 일부가 들어가므로 별도의 순차 실험이며 전역 OOS의 독립 검증을 대체하지 않는다.',
        '```json\n'+json.dumps(r['walk_forward'],ensure_ascii=False,indent=2)+'\n```',
        '## robustness',
        'IS MDD≤25% 후보의 상위 5개에 대해 한 번에 한 파라미터를 바꾼다: 각 신호의 lookback ±3일(최소 1일), K ±1/2, R ±1. rankblend는 각 구성 기간을 개별 ±3일, volume은 7일 분자와 30일 분모를 개별 ±3일, revmom은 반전과 모멘텀 기간을 개별 ±3일 변경한다. 승리 비율은 기준 전략 대비 Calmar 초과 비율이다. 이웃 결과를 보고 선택을 변경하지 않는다.',
        '```json\n'+json.dumps(r['robustness'],ensure_ascii=False,indent=2)+'\n```',
        '## survivorship',
        '```json\n'+json.dumps({'comparisons':r['survivorship'],'dropped_top5':r['dropped_top5']},ensure_ascii=False,indent=2)+'\n```',
        '현재 고정된 45종목은 상장폐지·실패 종목이 누락된 생존자 집합일 수 있다. 과거 상장 조건은 미래 상장을 미리 거래하는 오류를 막지만 상장폐지 생존자 편향을 제거하지 못한다. 모멘텀 롱의 성과를 상향 편향시킬 가능성이 있고, 숏에서 실패 종목이 빠지는 효과는 반대 방향이므로 달러중립 전략의 순 편향 방향은 자료 없이 확정할 수 없다. 2022년 이전 상장 부분집합도 생존자 집합이다. 사후 최고 수익 5종목 제거는 미래 정보를 쓰는 스트레스이며 실행 가능한 선택 규칙이 아니다.',
        '## failures',
        '소스 누락은 metadata에 보고한다. 가격 결측 구간은 수익률 0으로 계산하고 관측 결측 시 비중을 청산한다. 청산된 종목은 다음 적격 리밸런스까지 제외하며, 남은 양측 비중 재정규화로 달러중립을 유지한다. 실제 상장폐지·거래정지 청산가격이 없으므로 이 처리는 손실을 과소평가할 수 있다. JSON missing_return_exposure로 영향 구간의 보유 노출 합계를 보고한다. 펀딩 누락=0은 carry와 비용 추정에 편향을 줄 수 있다. funding_coverage는 실제 펀딩 관측이 있는 일자의 보유 절대비중 평균이며 지급 이벤트 전체의 완전성을 보장하지 않는다.',
        '## recommendation',
        '합성 검증 결과로 전략 추천을 하지 않는다.' if synthetic_mode else 'IS 기준 선택 구성: `'+json.dumps(r['recommendation']['config'],ensure_ascii=False)+'`. 실제 운용 승인 근거는 아니다. OOS·이웃 안정성·생존자 스트레스와 누락 노출을 함께 확인해야 한다.',
        '## assumptions',
        'close t 신호로 w[t]를 결정하고 일자 t+1 수익과 펀딩에는 w[t]를 적용한다. 당일 종가 리밸런스 비용은 당일 equity에 반영한다. 비용=편도 거래대금 0.05% 수수료+0.05% 슬리피지; 기준 재현만 0.04%. 단일 전략 롱·숏 각각 0.5, 표본 부족 시 K=min(요청 K, 적격 수/2 내림), 결측 강제 청산 시 생존 종목을 롱·숏 각각 0.5로 재정규화하며 한쪽이 비면 전체를 현금화한다. 이는 R일 일정 외 예외적 거래이고 비용에 포함한다. 일별 비중은 리밸런스 사이 고정하는 목표비중 근사이며 가격에 따른 실제 비중 drift·수량 고정·증거금·청산·시장충격은 모형에 없다. 회전율은 목표비중 변화의 절대합으로 반회전이 아니다. 수익률은 (1+가격수익−펀딩)×(1−비용×회전율)−1. Sharpe는 무위험수익 0, sqrt(365), CAGR은 일수/365, 낙폭은 초기 equity=1 포함. fee drag는 연환산 단순 비용합이며 총성과 차이와 일치할 필요가 없다. skip-N은 close[t-1]/close[t-N]−1. BTC beta는 60일 일수익 공분산/분산으로 산출하고 잔차 일수익을 N일 합산한다. breakout은 close/60일 최고 종가−1이다. 동일 점수는 유니버스 열 순서로 결정한다.',
        f"미래 변경 테스트: {json.dumps(r['test'],ensure_ascii=False)}. 라이브러리 metrics와 NumPy grid metrics의 일치, 합성 전체 실행을 검증한다. 실행 시간 {r['runtime_seconds']:.1f}초."]
    return '\n\n'.join(parts)+'\n'

def main():
    parser=argparse.ArgumentParser(); parser.add_argument('--synthetic',action='store_true'); parser.add_argument('--out',default='/tmp/rs_alpha_results.json'); args=parser.parse_args()
    # Explicit --out is supported, but workspace artifact policy takes precedence.
    out=Path(args.out).expanduser().resolve()
    if args.synthetic: out=Path('/tmp/rs_alpha_synthetic_results.json')
    elif out == (ROOT/'docs/research/alpha_results.json').resolve():
        out=Path('/tmp/rs_alpha_results.json')
        print('Three-file workspace restriction: JSON redirected to '+str(out),flush=True)
    if not str(out).startswith('/tmp/') and not str(out).startswith('/private/tmp/'):
        parser.error('--out must be under /tmp: only the three named workspace files may be created')
    if not args.synthetic and not (ROOT/'.rs_cache/vision/READY').exists():
        parser.error('READY absent; no partial-data findings written. Run --synthetic or rerun after data completion.')
    print('[1/3] local panel load',flush=True)
    p,info=synthetic() if args.synthetic else load_daily()
    e=Engine(p); bt=e.backtest(e.weights(signals(p)['ret_14'],Config('ret_14')))
    for period,start,end in [('IS','2022-01-01','2024-06-30'),('OOS','2024-07-01',None),('full','2022-01-01',None)]:
        a,b=metrics(bt,start,end),fast_metrics(bt,start,end)
        for key in ['CAGR','MDD','Calmar','Sharpe','turnover','fee_drag']: np.testing.assert_allclose(a[key],b[key],rtol=1e-10,atol=1e-12)
    result=research(p,info)
    out.parent.mkdir(parents=True,exist_ok=True); out.write_text(json.dumps(result,ensure_ascii=False,indent=2,allow_nan=False))
    doc=Path('/tmp/rs_alpha_synthetic.md') if args.synthetic else ROOT/'docs/research/alpha.md'
    doc.write_text(report(result,args.synthetic))
    print('[3/3] complete: '+str(out)+'; '+str(doc),flush=True)
    concise=[]
    for rec in [result['baseline']]+result['singles'][:5]:
        concise.append({'signal':rec['config']['signal'],'K':rec['config'].get('k'),'R':rec['config'].get('r'),'IS Calmar':val(rec),'OOS Calmar':val(rec,'OOS'),'OOS CAGR':rec['metrics']['OOS']['CAGR'],'OOS MDD':rec['metrics']['OOS']['MDD']})
    print(pd.DataFrame(concise).to_string(index=False))

if __name__=='__main__': main()
