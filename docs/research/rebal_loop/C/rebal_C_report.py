"""Summarize the frozen 1..72h grid and write the Korean research report."""
import json
from pathlib import Path
import numpy as np
from scipy.stats import t, norm

HERE=Path(__file__).resolve().parent
Z=json.load(open(HERE/'results.json'))
GRID=Z['grid']; LAM=.15
def cell(p,lam=LAM): return next(x for x in GRID if x['period']==p and x['lambda_']==lam)
def vals(p,key,lam=LAM): return np.array([x[key] for x in cell(p,lam)['phases']],float)
def boot(d,seed=29,B=20000):
 rng=np.random.default_rng(seed); d=np.asarray(d,float); n=len(d)
 ix=rng.integers(0,n,size=(B,n)); bm=d[ix].mean(axis=1); centered=(d-d.mean())[ix].mean(axis=1)
 return float(d.mean()),float(np.quantile(bm,.025)),float(np.quantile(bm,.975)),float((centered>=d.mean()).mean())
def holm(ps):
 ix=np.argsort(ps); out=np.ones(len(ps)); run=0
 for rank,k in enumerate(ix): run=max(run,(len(ps)-rank)*ps[k]); out[k]=min(1.,run)
 return out

base=cell(72); basephase=base['phases']
blocks=Z.get('oos_90d_blocks',{}).get('windows',[])
deltas=[]; pvals=[]; cis=[]
for p in range(1,72):
 ds=[]
 for b in blocks:
  a=np.array(b['annualized_log_growth'][p-1],float); q=np.array(b['annualized_log_growth'][71],float)
  ds.append(float(a.mean()-q.mean()))
 d=np.array(ds); m,lo,hi,pv=boot(d,100+p); deltas.append((p,m,lo,hi,pv)); pvals.append(pv)
adj=holm(np.array(pvals)) if pvals else np.array([])
for i,row in enumerate(deltas): cis.append((*row, float(adj[i])))
sig=[p for p,m,lo,hi,pv,pa in cis if m>0 and pa<.05]
plateaus=[]
for p in sig:
 if not plateaus or p>plateaus[-1][-1]+1: plateaus.append([p])
 else: plateaus[-1].append(p)
isolated_sig=sum(len(g)<3 for g in plateaus)
plateaus=[g for g in plateaus if len(g)>=3]
medmde=float(np.median([(t.ppf(1-.05/71,8)+t.ppf(.8,8))*np.std([b['annualized_log_growth'][p-1][r]-b['annualized_log_growth'][71][r] for b in blocks for r in range(min(len(b['annualized_log_growth'][p-1]),len(b['annualized_log_growth'][71])))],ddof=1)/np.sqrt(9) for p in range(1,72)])) if blocks else float('nan')

sens=Z['cost_failure_sensitivity_oos']
def sens_cell(p,slip,fail): return next(x for x in sens if x['period']==p and x['slippage_bp']==slip and x['fill_failure']==fail)
def sens_summary(p,slip,fail):
 v=sens_cell(p,slip,fail)['phases']; finals=np.array([x['final'] for x in v]); return finals.mean(),np.mean([x['mdd'] for x in v]),np.mean([x['kills'] for x in v]),np.mean([x['rebals'] for x in v]),np.mean([x['attempts'] for x in v]),np.mean([x['failures'] for x in v])

# Independently label 90-day trend and crash states; categories may overlap.
import numpy as np, pandas as pd
npz=np.load(Path(Z['meta']['panel']),allow_pickle=True); days=pd.DatetimeIndex(npz['days'],tz='UTC'); cc=npz['C']; names=[str(x) for x in npz['names']]; btc=names.index('BTC' if 'BTC' in names else 'BTCUSDT'); close=cc[:,23,btc]
reg=[]
for b in blocks:
 a=int(days.searchsorted(pd.Timestamp(b['start'],tz='UTC'))); e=int(days.searchsorted(pd.Timestamp(b['end'],tz='UTC')))+1
 r90=(close[e-1]/close[a]-1) if np.isfinite(close[a]) and np.isfinite(close[e-1]) else 0
 r14=np.full(e-a,np.nan)
 for k,i in enumerate(range(a,e)):
  if i>=14 and np.isfinite(close[i]) and np.isfinite(close[i-14]): r14[k]=close[i]/close[i-14]-1
 trend='상승' if r90>.20 else ('하락' if r90<-.20 else '횡보')
 crash=bool(np.nanmin(r14)<-.10)
 event=bool(a <= int(days.searchsorted(pd.Timestamp('2025-10-10',tz='UTC'))) < e)
 reg.append((trend,crash,event,b,a,e,r90,float(np.nanmin(r14))))

lines=[]
meta=Z['meta']; parity=Z['parity']
lines += [
 '# 리밸런스 주기 백테스트 C — 결과 보고서', '',
 f"작성일: 2026-11-01. 실행 구간: {meta['range'][0]}~{meta['range'][1]} (UTC)", '', '## 판정', '',
 f"**(2) 구분 불가.** 수치 격자는 실제 실행했으나, 72h 엔진 parity가 통과하지 못했다. 신규 엔진 최종자산은 시작자산 1.0 기준 {parity['hourly_final']:.2f}x, R2C는 {parity['r2c_final']:.2f}x이며 상대오차 {parity['relative_error']:+.1%}, 킬 횟수 {int(parity['hourly_kills'])}회 대 {int(parity['r2c_kills'])}회다. 허용오차 2%와 킬 횟수 일치 기준을 벗어나 주기 효과의 우열 판정은 보류한다. 아래 수치는 엔진 불일치가 있는 탐색값이다.", '',
 '## 표본·검증 게이트', '', '| 항목 | 결과 |', '|---|---|',
 f"| OLD 생존자 패널 | {meta['n_symbols']}종목, {meta['range'][0]}~{meta['range'][1]}, 일×24 시간봉 |",
 '| IS / OOS | IS 2022-01-01~2024-06-30, OOS 2024-07-01~2026-10-09 |',
 '| OLD-PIT | hourly panel 없음. 별도 비교 불가 |',
 '| NEW PIT | hourly NEW panel 2020-03~2021-12로 IS/OOS와 겹치지 않음 |',
 '| 2025-10-10 flash | 날짜가 OLD 패널 안에 있음. 해당 날짜가 포함된 블록을 아래 국면 표에 반영 |',
 f"| 72h parity | 신규 {parity['hourly_final']:.2f}, R2C {parity['r2c_final']:.2f}; 상대오차 {parity['relative_error']:+.1%}; 킬 {int(parity['hourly_kills'])} 대 {int(parity['r2c_kills'])} — 실패 |", '',
 '수정 과정의 다섯 탐색 run은 `exploratory_invalid_run*.json/.log`로 보존했다. 모두 parity 실패 run이므로 최종 grid inference에서 제외했다.', '',
 '## 1~72h 전체 격자 (lambda=0.15, OOS)', '',
 '최종자산은 시작자산 1 기준 배수이며 phase 평균·최솟값·최댓값이다. 1~7h는 가능한 모든 위상을 사용했다. parity 실패로 아래 값은 탐색값이다.', '',
 '| h | OOS final 평균 [최소,최대] | MDD 평균 | kill 평균 | 리밸런스 평균 |', '|---:|---:|---:|---:|---:|'
]
for p in range(1,73):
 f=vals(p,'oos_final'); m=vals(p,'oos_mdd'); k=vals(p,'oos_kills'); r=vals(p,'oos_rebals')
 lines.append(f'| {p} | {f.mean():.3f} [{f.min():.3f},{f.max():.3f}] | {m.mean():.1%} | {k.mean():.2f} | {r.mean():.1f} |')

new=Z['new_historical_sample']; ng=[x for x in new['grid'] if x['lambda_']==.15]
lines += ['', '## NEW PIT 역사 표본 (비교 표본, OOS 아님)', '', f"NEW 패널 전체 {new['period_days']}일 {new['symbols']}열이고, 실제 전략 실행 구간은 {new['range'][0]}~{new['range'][1]}이다. IS/OOS 기간 밖의 독립 역사 맥락으로만 본다. 아래는 lambda=0.15 전체 1~72h 격자이며 72h parity 미검증 때문에 탐색값이다.", '', '| h | final 평균 [최소,최대] | MDD 평균 | kill 평균 |','|---:|---:|---:|---:|']
for p in range(1,73):
 x=next(v for v in ng if v['period']==p)['phases']; f=np.array([a['final'] for a in x]); m=np.array([a['mdd'] for a in x]); k=np.array([a['kills'] for a in x]); lines.append(f'| {p} | {f.mean():.3f} [{f.min():.3f},{f.max():.3f}] | {m.mean():.1%} | {k.mean():.2f} |')

lines += ['', '## 사전등록 비교 요약 (lambda=0.15)', '', '| 주기 | OOS 최종자산 평균 | OOS MDD | 킬/경로 | 리밸런스/경로 | 72h 대비 phase 평균 log차 |', '|---:|---:|---:|---:|---:|---:|']
for p in (1,6,12,24,48,72):
 f=vals(p,'oos_final'); m=vals(p,'oos_mdd'); k=vals(p,'oos_kills'); r=vals(p,'oos_rebals')
 d=np.log(np.maximum(f,1e-12))-np.log(np.maximum(vals(72,'oos_final'),1e-12))[:len(f)]
 lines.append(f'| {p}h | {f.mean():.3f} ({f.min():.3f}~{f.max():.3f}) | {m.mean():.1%} | {k.mean():.2f} | {r.mean():.1f} | {d.mean():+.3f} |')
is_days=Z['meta']['is_end']-Z['meta']['d0']; oos_days=Z['meta']['d1']-Z['meta']['is_end']
base_is=np.log(np.maximum(vals(72,'is_final'),1e-12))*365/is_days
base_oos=np.log(np.maximum(vals(72,'oos_final'),1e-12))*365/oos_days
lines += ['', '### IS/OOS 짝비교 (phase 평균, exploratory)', '', '| h | IS 연율 log 성장 | IS 72h 대비 | OOS 연율 log 성장 | OOS 72h 대비 |', '|---:|---:|---:|---:|---:|']
for p in (1,6,12,24,48,72):
 gi=np.log(np.maximum(vals(p,'is_final'),1e-12))*365/is_days; go=np.log(np.maximum(vals(p,'oos_final'),1e-12))*365/oos_days
 di=gi.mean()-base_is[:len(gi)].mean(); do=go.mean()-base_oos[:len(go)].mean()
 lines.append(f'| {p} | {gi.mean():+.3f} | {di:+.3f} | {go.mean():+.3f} | {do:+.3f} |')
plateau_text = '없음' if not plateaus else ', '.join(str(x[0])+'–'+str(x[-1])+'h' for x in plateaus)
lines += ['', '### OOS 90일 block bootstrap / 다중검정', '',
 f"- OOS 비중첩 90일 블록 {len(blocks)}개, 71개 단축 주기와 72h 대비 연율 log 성장차이를 비교했다. phase 평균을 먼저 취해 phase를 독립 표본으로 세지 않았다.",
 f"- Holm 보정 후 양(+) 차이가 유의한 단일 가설: {len(sig)}/71. 사전 정의한 3시간 이상 연속 plateau: {plateau_text}; 길이 3 미만 고립 결과 {isolated_sig}개는 주기 추천으로 해석하지 않는다.",
 f"- family-wise 5%, 80% 검정력의 대략적 MDE 중앙값: {medmde:.3f} 연율 log 단위. 9개 블록이라 검정력은 낮다.",
 '- PBO/DSR은 일별·거래별 수익률과 조합 IS/OOS 분할이 보존되지 않아 산출하지 않았다.',
 '- parity 실패 때문에 bootstrap/Holm 결과는 엔진 내 연관성에 그치며 전략 효과 검증으로 해석하지 않는다.', '', '## lambda / 위상·국면 민감도', '',
 '| lambda | 72h OOS final 평균 | 72h MDD 평균 | 72h kill 평균 | p24 OOS final 평균 | p24 MDD 평균 |', '|---:|---:|---:|---:|---:|---:|']
for lam in (0,.15,.30):
 f72=vals(72,'oos_final',lam); f24=vals(24,'oos_final',lam); lines.append(f'| {lam:.2f} | {f72.mean():.3f} | {vals(72,"oos_mdd",lam).mean():.1%} | {vals(72,"oos_kills",lam).mean():.2f} | {f24.mean():.3f} | {vals(24,"oos_mdd",lam).mean():.1%} |')
lines += ['', '### 킬 없는 고정노출 대조 (OOS)', '', '초기 equity 기준 gross notional 3.8배를 고정하고 kill을 비활성화했다. 수익이 누적돼도 주문 notional은 늘지 않는다. 위상 평균값이며 parity 실패와 minimum-order 미반영 한계는 동일하다.', '', '| h | 고정노출 final 평균 [최소,최대] | MDD 평균 |', '|---:|---:|---:|']
fixed=Z['oos_kill_free_fixed_exposure']['windows']
for p in (1,6,12,24,48,72):
 x=next(a for a in fixed if a['period']==p)['phases']; f=np.array([a['final'] for a in x]); m=np.array([a['mdd'] for a in x]); lines.append(f'| {p} | {f.mean():.3f} [{f.min():.3f},{f.max():.3f}] | {m.mean():.1%} |')
lines += ['', '최악·최선 phase 산포를 보고한다. 72h 대비 phase 변화가 큰지 여부는 비교 가능한 실효 독립 표본이 8개 미만(1h=1, 2~7h는 cadence만큼)인 주기들이 있어 격자 전역으로 판정하지 않는다. p24의 lambda 0.15 OOS final 범위는 %.3f~%.3f이며, 이 phase 산포는 단일 OOS 구간의 블록 수 9보다 작은 독립 표본 해석의 한계를 가진다.'%(vals(24,'oos_final').min(),vals(24,'oos_final').max()),'', '| OOS 90일 블록 국면 | 블록 수 | p24 평균 연율 log 성장 | p72 평균 연율 log 성장 | 해석 |','|---|---:|---:|---:|---|']
for label in ('상승','하락','횡보','급락(14d BTC < -10%)','2025-10-10 포함'):
 rr=[x for x in reg if (x[0]==label if label in ('상승','하락','횡보') else (x[1] if label.startswith('급락') else x[2]))]
 if not rr: lines.append(f'| {label} | 0 | — | — | 해당 블록 없음 |'); continue
 aa=[]; bb=[]
 for item in rr:
  b=item[3]
  a=np.array(b['annualized_log_growth'][23]); q=np.array(b['annualized_log_growth'][71]); aa.append(a.mean()); bb.append(q.mean())
 lines.append(f'| {label} | {len(rr)} | {np.mean(aa):+.3f} | {np.mean(bb):+.3f} | 90일 블록 탐색값; trend/crash 중복 허용 |')

lines += ['', '## 꼬리위험·운영량','', 'lambda=0.15, 비용 0.05%/편도, 기본 failure 0%, OOS 경로 평균. liquidation cushion은 3% flat maintenance 근사이며 실제 tier/청산 수수료·보험기금·마크 가격은 반영하지 않았다.','', '| 주기 | 최소 증거금 여유 평균 [경로 최저] | 최악 wick 평가 자산 최솟값 | attempted leg orders | 실제 리밸런스 횟수 |', '|---:|---:|---:|---:|---:|']
for p in (1,6,12,24,48,72):
 row=cell(p); vv=row['phases']; mc=[x['min_cushion'] for x in vv]; lines.append(f"| {p}h | {np.mean(mc):+.2%} [{np.min(mc):+.2%}] | {np.min([x['worst_wick_eq'] for x in vv]):.4g} | {np.mean([x['oos_attempts'] for x in vv]):.0f} | {np.mean([x['oos_rebals'] for x in vv]):.0f} |")
lines += ['', '위 wick 수치는 포트폴리오 equity 절대값이며, 심볼별 시간봉 최저/최고를 같은 시각의 포트폴리오에 보수적으로 동시 적용한다. 거래소 강제청산 여부를 검증한 값이 아니다. hourly-bar 보정 lambda 0/0.15/0.30은 위 표로 민감도만 제공한다.','', '## 비용·주문 실패 시나리오 (OOS, p=1/6/12/24/48/72, lambda=.15)','', '실패 주문은 해당 leg 미체결 후 다음 정기 실행까지 이월하는 공통 (timestamp,symbol) 난수다. 대표 cadence만 계산했으므로 72-grid 전체에 대한 비용 조정 통계는 아니다.','', '| h | slip bp | 실패율 | final 평균 | MDD | kill | 실패 주문 평균 |', '|---:|---:|---:|---:|---:|---:|---:|']
for p in (1,6,12,24,48,72):
 for slip in (0,2,5,10):
  for fail in (0,.02,.05):
   f,m,k,r,a,fl=sens_summary(p,slip,fail); lines.append(f'| {p} | {slip} | {fail:.0%} | {f:.3f} | {m:.1%} | {k:.2f} | {fl:.0f} |')
lines += ['', '### API/체결·소액계좌 한계','', '- 주기별 `rebals`는 예약 실행 횟수 근사, `attempts`는 바뀐 leg 주문 시도 수다. HTTP 요청은 이외 계좌조회·포지션동기화·취소·재시도 등도 포함해 실측 호출 수가 아니다.', '- 418, recvWindow, rate-limit 응답, 부분체결, 거래소 정밀도·최소수량·QNT 최소주문 오류는 로컬 패널만으로 추정하지 않았다. 거래소 인증 호출 및 규칙 조회는 없었다.', '- 수수료는 지정 0.05%/편도. 소액계좌 슬리피지 0/2/5/10bp는 시나리오뿐이고, 시장충격 체결 자료로 보정되지 않았다.', '- 1h cadence는 OOS에 평균 약 %.0f회 리밸런스와 %.0f leg 주문시도를 냈고, 72h는 약 %.0f회와 %.0f회였다. 호출 한도/실패 확률로 변환하는 것은 근거가 없어 하지 않았다.'%(vals(1,'oos_rebals').mean(),vals(1,'oos_attempts').mean(),vals(72,'oos_rebals').mean(),vals(72,'oos_attempts').mean()),'', '## 결론과 확신도','', '**최종 분류: (2) 구분 불가.** 모델 내 수치에서 p24 및 넓은 중간 주기 구간이 72h보다 높은 OOS terminal wealth를 보였지만, parity가 2% 기준을 크게 초과하고 킬 시점/횟수도 달라졌다. 이는 유효한 cadence 효과의 증거로 승격할 수 없다.','', '- 성과 방향 확신도: **매우 낮음**. parity 미통과, OLD survivor 편향, OLD-PIT 부재, NEW 표본 비중첩이 주 원인이다.', '- 운영 부담 방향: **정성 확신 높음**. 짧은 주기는 체결 leg 수를 늘린다. 실제 API/레이트리밋 위험도 크기는 계정·엔드포인트 로그가 없어 미측정이다.', '- 더 긴 검증에 필요한 조건: hourly V0 엔진이 72h R2C와 <=2% final error 및 동일 kill path를 재현하고, 전체 OOS block/phase별 경로를 저장한 뒤 Holm·PBO/DSR·고정노출 비교를 다시 실행해야 한다.', '', '## 산출물','', '- `prereg.md`, `hashes.log`: 사전등록 amendment와 해시 이력.', '- `rebal_C_engine.py`, `rebal_C_run.py`, `rebal_C_blocks.py`, `rebal_C_fixed.py`, `rebal_C_new.py`, `rebal_C_report.py`: 오프라인 엔진·실행·bootstrap·보고서 생성 코드.', '- `results.json`, `run.log`: 최종 parity 실패 run, OLD/NEW 72 cadence × 3 lambda, OOS 90일 blocks, 고정노출 및 대표 비용 민감도 결과.', '- `exploratory_invalid_run*.json/.log`: parity 수정 중 격리한 무효 탐색 출력.']
(HERE/'report.md').write_text('\n'.join(lines)+'\n',encoding='utf8')
print(f"report written: {HERE/'report.md'}; OOS blocks={len(blocks)}; Holm-positive={len(sig)}; plateau={plateaus}; MDE80 median={medmde:.3f}")
