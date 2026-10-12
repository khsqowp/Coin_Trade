"""Run local-only overlays and write the <=150-line Korean research report."""
from __future__ import annotations
import os
import sys
from pathlib import Path
# Suppress bytecode/cache writes to existing repo files (including imported numba cores).
os.environ.setdefault('NUMBA_CACHE_DIR', '/private/tmp/rs_profit_numba')
sys.dont_write_bytecode = True
import itertools
import numpy as np
from app.rs_final_data import load_panel
from app.rs_final_engine import Sim as Reference
from app.rs_profit_engine import Sim

BASE = dict(rebal=3, K=8, lev=2., deploy=1., kill=.35, cool=14,
            cost=.001, fund=1, minn=0., eq0=1.)


def metrics(r, mask):
    ids = np.flatnonzero(mask); a, b = ids[0], ids[-1]
    s = r['wealth'][ids]; start = r['wealth'][a-1] if a else r['eq0']
    hw = np.maximum.accumulate(np.r_[start, s])[1:]
    dd = 1-s/hw
    previous = np.r_[start, hw[:-1]]
    # Hourly extremes precede close actions; compare to preceding close high,
    # plus the actual closing equity after actions, never a future close high.
    imdd = np.maximum(1-r['total_worst'][ids]/previous, dd).max()
    traded = r['eq'][ids]; ts = r['eq'][a-1] if a else r['eq0']
    tdd = (1-traded/np.maximum.accumulate(np.r_[ts, traded])[1:]).max()
    run = longest = 0
    for x in dd:
        run = run+1 if x > 1e-12 else 0
        longest = max(longest, run)
    wealth = s[-1]/start; cagr = wealth**(365/len(ids))-1 if wealth > 0 else -1.
    return dict(wealth=wealth, cagr=cagr, dd=dd.max(), idd=imdd, tdd=tdd,
                uw=longest, flat=np.mean(r['expo'][ids] == 0),
                trig=r['events'][ids].sum()*365/len(ids),
                kills=r['loss'][ids].sum()*365/len(ids),
                calmar=cagr/dd.max() if dd.max() > 0 else 0.)


def episodes(r):
    """>=25% rise then any fall; end at trough before recovery/censor."""
    w=r['wealth']; start=peak=0; trough=0; out=[]; falling=False
    for t in range(1,len(w)):
        if not falling:
            if w[t] < w[start]:
                start=peak=t
            if w[t] >= w[peak]:
                peak=t
            elif w[peak] >= 1.25*w[start]:
                falling=True; trough=t
        else:
            if w[t] < w[trough]:
                trough=t
            if w[t] > w[peak]:
                out.append((start,peak,trough)); start=trough
                peak=t; falling=False
    if falling:
        out.append((start,peak,trough))
    return out


def retained(r, ep):
    out=[]
    for a,p,t in ep:
        den=r['wealth'][p]-r['wealth'][a]
        out.append(float(np.clip((r['wealth'][t]-r['wealth'][a])/den,-1,2)) if den>1e-12 else np.nan)
    return out


def giveup(r):
    ids=np.flatnonzero(r['days'].year==2024)
    w=r['wealth']; a=ids[0]; start=w[a-1] if a else r['eq0']
    p=ids[np.argmax(w[ids])]; gain=w[p]-start
    if gain <= 0: return np.nan,np.nan
    return (w[p]-w[ids[-1]])/gain,(w[p]-w[p:ids[-1]+1].min())/gain


def meanms(rs, masks):
    out={}
    for label,mask in masks.items():
        mm=[metrics(r,mask) for r in rs]
        out[label]={k:float(np.mean([m[k] for m in mm])) for k in mm[0]}
        out[label]['dd_wp']=max(m['dd'] for m in mm)
        out[label]['wealth_wp']=min(m['wealth'] for m in mm)
        out[label]['uw_wp']=max(m['uw'] for m in mm)
        out[label]['idd_wp']=max(m['idd'] for m in mm)
    return out


def verify_mechanics():
    from app.rs_profit_engine import _sim, profit_params
    from app.rs_final_engine import params
    def toy(profit,prices,kill=.35,cost=0.,minn=0.,eq0=1.):
        n=len(prices); C=np.full((n,24,2),100.); C[:,:,0]=np.array(prices)[:,None]
        return _sim(C,C,C,np.zeros((n,2)),np.tile([1.,0.],(n,1)),np.zeros(n),
                    params(rebal=99,K=1,lev=2,kill=kill,cool=14,cost=cost,minn=minn,eq0=eq0),
                    np.zeros(2),np.zeros(2),0,n,profit_params(**profit))
    prices=[100,130,110,110,110,110,110,110]
    a=toy(dict(mode=1,activation=.2,drop=.1,pause=3),prices)
    assert a[5][2]==1 and a[2][3]==0 and a[2][5]==0 and a[2][6]>0
    b=toy(dict(mode=1,activation=.2,drop=.1,pause=3),prices,cost=.001)
    # Entry .002, then close notional 2.1 * .001.
    np.testing.assert_allclose(b[0][2],1.1-.002-.0021,atol=1e-12)
    c=toy(dict(mode=1,activation=.2,drop=.1),[100,150,90,90])
    assert c[6][2]==1 and c[5][2]==0  # loss kill takes precedence
    v2=toy(dict(mode=2,drop=.1,scale=.5),[100,130,110,110,180,180,180])
    assert v2[5][2]==1 and v2[2][3]<1.01 and v2[2][5]>1.99
    floor=toy(dict(mode=2,drop=.1,scale=.25),[100,130,110,110,110],minn=5.,eq0=10.)
    np.testing.assert_allclose(floor[2][3]*floor[0][3],10.)  # two positions >=5 each
    v3=toy(dict(mode=3,scale=.3),prices)
    v3cut=toy(dict(mode=3,scale=.3,proportional=True),prices)
    np.testing.assert_allclose(v3[0][1]+v3[4][1],1.3)
    np.testing.assert_allclose(v3cut[0][1]+v3cut[4][1],1.3)
    np.testing.assert_allclose(v3[4][1],.09)
    assert v3[2][2]>v3cut[2][2]
    v4=toy(dict(mode=4,window=4,threshold=.1),[100,130,130,130,130,130,130,130])
    assert v4[5][1]==1 and v4[2][2]==0 and v4[2][4]==0 and v4[2][5]>0
    print("mechanics assertions PASS", flush=True)


def main():
    for p in ('app/rs_profit_engine.py','app/rs_profit_run.py'):
        compile(Path(p).read_text(),p,'exec')
    verify_mechanics()
    S=Sim(load_panel()); R=Reference(S.P)
    configs={'V0':{}}
    families={'V1':[], 'V1orig':[], 'V2':[], 'V3':[], 'V3cut':[], 'V4':[], 'V4roll':[]}
    for A,X,C in itertools.product((.1,.2,.3),(.1,.15,.2,.25),(3,7,14)):
        for orig,fam in ((False,'V1'),(True,'V1orig')):
            name=f'{fam}_{A:g}_{X:g}_{C}'
            configs[name]=dict(mode=1,activation=A,drop=X,pause=C,original_base=orig); families[fam].append(name)
    for X,f in itertools.product((.1,.15),(.5,.25)):
        name=f'V2_{X:g}_{f:g}'; configs[name]=dict(mode=2,drop=X,scale=f); families['V2'].append(name)
    for f,cut in itertools.product((.3,.5),(False,True)):
        fam='V3cut' if cut else 'V3'; name=f'{fam}_{f:g}'
        configs[name]=dict(mode=3,scale=f,proportional=cut); families[fam].append(name)
    for W,T,rolling in itertools.product((7,14),(.1,.15),(False,True)):
        fam='V4roll' if rolling else 'V4'; name=f'{fam}_{W}_{T:g}'
        configs[name]=dict(mode=4,window=W,threshold=T,rolling=rolling); families[fam].append(name)
    results={}; summaries={}
    for k,(name,cfg) in enumerate(configs.items()):
        rs=[S.run(profit=cfg,phase=p,**BASE) for p in range(3)]
        if name=='V0':
            for p,r in enumerate(rs):
                ref=R.run(lbs=(14,),crash_flat=True,phase=p,**BASE)
                np.testing.assert_array_equal(r['eq'],ref['eq'].to_numpy()[S.d_start():])
                np.testing.assert_array_equal(r['worst'],ref['worst'].to_numpy()[S.d_start():])
                np.testing.assert_array_equal(r['expo'],ref['expo'].to_numpy()[S.d_start():])
            print('ASSERT V0: eq/worst/exposure exact, phases 0..2 PASS',flush=True)
            days=rs[0]['days']
            masks={'IS':days<'2024-07-01','OOS':days>='2024-07-01','full':np.ones(len(days),bool)}
            masks.update({str(y):days.year==y for y in sorted(set(days.year))})
            eps=[episodes(r) for r in rs]
        results[name]=rs; summaries[name]=meanms(rs,masks)
        if k%15==0: print(f'grid {k+1}/{len(configs)} {name}',flush=True)
    baseline=summaries['V0']; robust={}; reps={}; verdicts={}
    for fam,names in families.items():
        robust[fam]={}
        for period in ('IS','OOS','full'):
            robust[fam][period]=tuple(np.mean([summaries[n][period][metric]>baseline[period][metric] for n in names]) for metric in ('wealth','calmar'))
        helps=np.mean([all(summaries[n][p]['calmar']>baseline[p]['calmar'] and summaries[n][p]['wealth']>=.85*baseline[p]['wealth'] for p in ('IS','OOS')) for n in names])
        hurts=np.mean([all(summaries[n][p]['calmar']<baseline[p]['calmar'] for p in ('IS','OOS')) for n in names])
        verdicts[fam]='helps' if helps>=.8 else ('hurts' if hurts>=.8 else 'noise')
        # Choose on IS only, subject to <=15% IS wealth sacrifice. OOS is diagnostic.
        eligible=[n for n in names if summaries[n]['IS']['wealth']>=.85*baseline['IS']['wealth']] or names
        reps[fam]=max(eligible,key=lambda n:summaries[n]['IS']['calmar'])
    selected=['V0']+list(reps.values())
    # Descriptive sleep-better pick: best full daily DD, within 15% wealth cost.
    eligible=[n for n in configs if summaries[n]['full']['wealth']>=.85*baseline['full']['wealth'] and n!='V0']
    sleep=min(eligible or list(configs),key=lambda n:summaries[n]['full']['dd'])
    kept=lambda n: float(np.nanmean([np.nanmean(retained(r, ep))
                      for r,ep in zip(results[n],eps)]))
    keeps=max(eligible or list(configs),key=kept)
    for n in (sleep,keeps):
        if n not in selected:
            selected.append(n)
    family_for=lambda n: next((f for f, names in families.items() if n in names),None)
    small=[S.run(profit=configs[sleep],phase=p,**(BASE|dict(minn=5.,eq0=142.))) for p in range(3)]
    sm=meanms(small,masks)['full']
    lines=['# 모멘텀 로테이션 수익 보호 백테스트',
           f'실행: 오프라인 로컬 패널, {days[0].date()}~{days[-1].date()}, {len(S.names)}종목, {len(configs)}설정 × 3위상.',
           '## 정의와 검증',
           '- 기본: lb14/rebal3/K8/lev2/deploy1, BTC14일<-10% flat, kill35%/cool14일, 편도0.1%, 실제 펀딩, min0, 초기자산1. 코드는 app/rs_profit_engine.py·app/rs_profit_run.py, 원본 규약은 app/rs_final_engine.py·app/rs_final_design.py·app/rs_final_data.py·docs/research/final_integration.md에서 확인했다.',
           '- V0: 원본 _sim 복제. 위상0~2 eq/worst/exposure 일별 완전 일치 ASSERT 통과. 같은 방향 수량 유지·시그널 종가 체결·일중 동시 극단값 규약 유지.',
           '- kill은 거래자산 HWM 기준이며 보호 트리거보다 먼저 검사한다. 손실 halt 동안 보호 동작을 멈춘다. 손실 재무장 시 HWM만 리셋한다.',
           '- V1: peak/base-1≥A 뒤 X하락 종가 전량청산(원본 kill의 실현·비용 경로), C일 정지; 재무장 peak/HWM=현재자산. 기본 base도 리셋, orig는 최초1 고정.',
           '- V2: peak수익20% 이후 X하락 시 목표총명목 ×f, 당일 강제 리사이즈; 축소 중 매 리밸런스 재조정, 새 최고점이면1 복원. 정수배율 미사용. min>0 잔존명목은 종목별 하한 보장(로트절삭은 신규만).',
           '- V3: 최초 lock=base; 새 고점이 직전 lock의1.2배 이상이면 (eq-lock)×f 인출, W차감·withdrawn누적·lock/HWM=인출후eq. 기본 수량 유지(잔여 레버리지 상승), cut은 비례청산 비용을 내고 비용 전 기존 레버리지 유지(소액은 최소명목 하한 우선).',
           '- V3 인출금은 수익률0·계좌밖 안전자산, 재투입 없음. 청산되면 거래자산0, 인출금만 보존. 보고 자산·DD는 총자산, 거래자산DD 별도.',
           '- V4: 최초일 기준 비중첩 W일 경계에서 기준자산 갱신, T수익 시 청산하고 다음 경계까지 정지. roll은 트리거일부터 W일 기다리는 이벤트 정렬 변형이다.',
           '- 종가 eq_c는 원본처럼 일반 리밸런스/kill 비용 전 기록(비용은 다음날 반영); 보호청산/인출은 그날 반영. 마지막날 일반 거래 없음. flat은 당일 가격경로 진입 시 무포지션 비율이다.',
           '- IS/OOS/연도는 연속 경로 절단, 구간 수익 기준은 직전일 총자산(최초1). 구간DD/UW는 경계에서 초기화; 연365일 CAGR. IS로 대표 선택(자산손실≤15% 필터 후 Calmar), OOS는 사후 진단.',
           '- Calmar=CAGR/종가총자산DD. 일중DD는 전일 최고총자산 대비 시간봉 최악+당일 종가DD의 최대; 시간봉 동시 극단은 보수적 가정이다.',
           '- giveback: V0 위상별 시작대비 상승≥25% 뒤 첫 하락부터 고점재돌파까지를 에피소드로 잡는다(추가 낙폭필터 없음). 끝은 고점 재돌파 직전 최저점, 미회복은 표본말까지 최저점.',
           '- 시작은 최초일/직전 채택 에피소드 저점, 상승 전 더 낮은 저점이면 갱신. 모든 변형은 해당 위상의 V0 시작/고점/저점 날짜로 평가한다.',
           '- retained=(변형저점-변형시작)/(변형고점-변형시작), [-100%,200%] 제한; 분모≤0은 NA(제외), NA 개수 명시, 유지율은 위상별 에피소드 평균의 산술평균. 2024 giveup=고점이익 대비 연말/고점이후최저점 반납, 음의 시작-고점 이익은NA.',
           '- 판정: helps=격자80% 이상이 IS·OOS 모두 Calmar개선+각 구간자산손실≤15%; hurts=80% 이상이 두 구간 모두 Calmar악화; 나머지 noise. 모든 결과는 탐색 표본·생존편향 영향이 있다.',
           '## 대표 설정별 지표 (위상 지표 산술평균; 괄호=최악위상)',
           '|설정|구간|자산배수(최저)|CAGR%|종가DD%(최악)|일중DD%(최악)|거래DD%|UW일(최장)|flat%|보호/년|kill/년|',
           '|---|---|---:|---:|---:|---:|---:|---:|---:|---:|---:|']
    for n in selected:
        for p in ('IS','OOS','full'):
            m=summaries[n][p]
            lines.append(f"|{n}|{p}|{m['wealth']:.2f}({m['wealth_wp']:.2f})|{m['cagr']*100:.1f}|{m['dd']*100:.1f}({m['dd_wp']*100:.1f})|{m['idd']*100:.1f}({m['idd_wp']*100:.1f})|{m['tdd']*100:.1f}|{m['uw']:.0f}({m['uw_wp']:.0f})|{m['flat']*100:.1f}|{m['trig']:.2f}|{m['kills']:.2f}|")
    lines+=['## 연도별 (자산배수 / CAGR% / 종가DD% / UW일; 2026은 부분연도)', '|설정|'+ '|'.join(str(y) for y in sorted(set(days.year)))+'|', '|---|'+'---|'*len(set(days.year))]
    for n in selected:
        lines.append('|'+n+'|'+ '|'.join(f"{summaries[n][str(y)]['wealth']:.2f}/{summaries[n][str(y)]['cagr']*100:.1f}/{summaries[n][str(y)]['dd']*100:.1f}/{summaries[n][str(y)]['uw']:.0f}" for y in sorted(set(days.year)))+'|')
    lines+=['## 반납과 이웃 견고성', '|대표|2024반납 연말/저점%|giveback유지% / NA|자산승률 IS/OOS/full%|Calmar승률 IS/OOS/full%|판정|', '|---|---:|---:|---:|---:|---|']
    for n in selected:
        gg=np.array([giveup(r) for r in results[n]])
        rr=np.array([v for r,ep in zip(results[n],eps) for v in retained(r,ep)])
        fam=family_for(n)
        robuststr=lambda k: '/'.join(f'{robust[fam][p][k]*100:.0f}' for p in ('IS','OOS','full')) if fam else '—'
        lines.append(f"|{n}|{np.nanmean(gg[:,0])*100:.1f}/{np.nanmean(gg[:,1])*100:.1f}|{kept(n)*100:.1f} / {np.isnan(rr).sum()}|{robuststr(0)}|{robuststr(1)}|{verdicts.get(fam,'기준')}|")
    lines+=['## 전체 격자 (각 셀=전구간 자산배수/종가DD%; 순서 고정)', '|V1 A,C|X=.10/.15/.20/.25 base리셋|X=.10/.15/.20/.25 최초base고정|', '|---|---|---|']
    fmt=lambda n:f"{summaries[n]['full']['wealth']:.2f}/{summaries[n]['full']['dd']*100:.1f}"
    for A,C in itertools.product((.1,.2,.3),(3,7,14)):
        lines.append(f'|{A:g},{C}|'+ '|'.join(' ; '.join(fmt(f'{f}_{A:g}_{X:g}_{C}') for X in (.1,.15,.2,.25)) for f in ('V1','V1orig'))+'|')
    lines+=['|가족|설정=자산/DD|', '|---|---|']
    for f in ('V2','V3','V3cut','V4','V4roll'):
        lines.append('|'+f+'|'+' ; '.join(n+'='+fmt(n) for n in families[f])+'|')
    lines+=['## V0 날짜 기준 에피소드별 유지율 (%)', '|위상 시작/고점/저점|'+ '|'.join(selected)+'|', '|---|'+'---:|'*len(selected)]
    erows=[]
    for phase,ep in enumerate(eps):
        for i,(a,p,t) in enumerate(ep):
            vals=[retained(results[n][phase],ep)[i] for n in selected]
            erows.append([f'{phase} {days[a].date()}/{days[p].date()}/{days[t].date()}']+
                         ['NA' if not np.isfinite(v) else f'{v*100:.0f}' for v in vals])
    # Multiple chronological episodes per table row; <br> aligns dates and values.
    chunk=max(1,int(np.ceil(len(erows)/max(1,140-len(lines)))))
    for a in range(0,len(erows),chunk):
        lines.append('|'+ '|'.join('<br>'.join(row[c] for row in erows[a:a+chunk])
                                    for c in range(len(selected)+1))+'|')
    best=max(configs,key=lambda n:summaries[n]['full']['wealth'])
    cost=(1-summaries[sleep]['full']['wealth']/baseline['full']['wealth'])*100
    lines+=['## 결론', f"- 총자산 최고: {best}, {summaries[best]['full']['wealth']:.2f}배; V0 {baseline['full']['wealth']:.2f}배. 최적 셀은 사후 선택이며 실전 우위 증거가 아니다.",
            '- 가족 판정: '+', '.join(f'{f}={verdicts[f]}' for f in families)+'.',
            f"- 잠을 편하게 자는 후보(전구간 사후, V0자산의85% 이상 중 최저DD): {sleep}; DD {baseline['full']['dd']*100:.1f}%→{summaries[sleep]['full']['dd']*100:.1f}%, 자산 비용 {cost:.1f}%, UW {baseline['full']['uw']:.0f}→{summaries[sleep]['full']['uw']:.0f}일.",
            f"- 수익 유지 후보(동일 자산85% 필터·사후): {keeps}; giveback 유지 {kept('V0')*100:.1f}%→{kept(keeps)*100:.1f}%, 최종자산 비용 {(1-summaries[keeps]['full']['wealth']/baseline['full']['wealth'])*100:.1f}%.",
            f"- 소액 sanity({sleep}, min5/초기142, 3위상): 총자산 {sm['wealth']:.2f}배, CAGR {sm['cagr']*100:.1f}%, DD {sm['dd']*100:.1f}%, 최악위상 {sm['dd_wp']*100:.1f}%, 신규스킵 {np.mean([r['stats'][1]/max(r['stats'][0],1) for r in small])*100:.1f}%.",
            '- 주문·네트워크·Docker·.env 접근 없음. 새 Python compile/py_compile 및 합성 경로 ASSERT(청산비용·재무장·kill우선·축소/복원·최소명목·인출보존·창경계) 통과. 기존 파일 수정 없음. 이웃 승률은 검정 유의확률이 아니다.']
    assert len(lines)<=150, len(lines)
    Path('docs/research/profit_protection.md').write_text('\n'.join(lines)+'\n')
    print('\nVARIANT                         IS wealth/DD  OOS wealth/DD FULL wealth/DD verdict')
    for n in selected:
        fam=family_for(n)
        print(f"{n:31s} "+' '.join(f"{summaries[n][p]['wealth']:6.2f}/{summaries[n][p]['dd']*100:4.1f}%" for p in ('IS','OOS','full'))+' '+verdicts.get(fam,'baseline'))
    print(f'Report {len(lines)} lines; episodes {sum(map(len,eps))}; sleep={sleep}; cost={cost:.1f}%')


if __name__=='__main__':
    main()
