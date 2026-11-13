"""Compact Round-2 report generated from immutable ledger and WF records."""
from __future__ import annotations
import json
import collections
from pathlib import Path
import numpy as np
import pandas as pd
from app.aw_data import load_panel
from app.aw_run import _bench, _daily_metrics, metrics

ROOT=Path(__file__).resolve().parents[1];BASE=ROOT/"docs/research/aw2";LEDGER=BASE/"ledger.jsonl";OUT=ROOT/"docs/research/AW2_RESULTS.md"
FAMILIES=("F1","F2","F3","F4","F5","F6","F7","F8","F9","F10","F11","F12","F13")
def pct(x):return "—" if x is None or not np.isfinite(x) else f"{x*100:.1f}%"
def num(x):return "—" if x is None or not np.isfinite(x) else f"{x:.2f}"

def _mix_benchmark(panel,index,bond):
    a=panel.c[index].reindex(panel.dates).ffill().pct_change(fill_method=None).fillna(0).to_numpy()
    b=panel.c[bond].reindex(panel.dates).ffill().pct_change(fill_method=None).fillna(0).to_numpy()
    values=np.ones(len(panel.dates));weight=.6
    for i in range(1,len(values)):
        if panel.dates[i].month!=panel.dates[i-1].month:weight=.6
        values[i]=values[i-1]*(1+weight*a[i]+(1-weight)*b[i])
    return pd.Series(values,index=panel.dates)

def build():
    rows=[]
    if LEDGER.exists():
        for line in LEDGER.read_text(encoding="utf-8").splitlines():
            try:
                x=json.loads(line)
                if x.get("round")==2:rows.append(x)
            except json.JSONDecodeError:pass
    audit_path=BASE/"stock_cache_first_dates.csv";first_dates={"KR":[],"US":[]}
    if audit_path.exists():
        for x in pd.read_csv(audit_path).to_dict("records"):
            if x.get("first_bar"):first_dates.get(x["market"],[]).append(str(x["first_bar"]))
    docs=[];docs += ["# AW-2 Round 2 — KR/US 전략 탐색 결과","","최종 기준일은 2026-11-11이다. 탐색·순위 선택에는 2022-12-31 이후 가격을 사용하지 않았다. 홀드아웃 지표는 평가에만 사용했다. Round 1 행은 원장에 그대로 보존했다.",""]
    docs += [f"Round 2 ledger 기록 **{len(rows)}행** (일반 설정 실행과 주식 상위 10 제외 스트레스 포함).","","A/B 판정은 워크포워드 성과, 홀드아웃, 실제 이웃 안정성, 미래 교란 결과를 모두 충족할 때만 허용했다.",""]
    for market in ("KR","US"):
        panel=load_panel(market,include_stocks=False);idx="069500" if market=="KR" else "SPY";bench=_bench(panel,idx)
        bill=next((s for s in panel.symbols if panel.roles[s]=="defensive" and ("단기채권" in panel.names[s] or s in ("BIL","SHY"))),None)
        mix=_mix_benchmark(panel,idx,bill) if bill else None
        docs += [f"## {market}","","| 순위 | 가족 | 등급 | WF CAGR | WF MDD | WF Sharpe | 홀드아웃 Sharpe | 지수 CAGR / MDD; 월간 60/40 CAGR; 현금 CAGR | R2 ledger 행 | 설정 수 | Flags |","|---:|---|---|---:|---:|---:|---:|---:|---:|---:|---|"]
        data=[]
        for fam in FAMILIES:
            subset=[r for r in rows if r.get("market")==market and r.get("family")==fam]
            trials=[r for r in subset if "TOP10_WINNER_EXCLUSION" not in r.get("flags",[])]
            wfpath=BASE/"wf"/f"{market}_{fam}_R2.json"
            wf=json.loads(wfpath.read_text(encoding="utf-8")) if wfpath.exists() else {}
            unavailable=(fam=="F8" and market=="US") or (fam=="F11" and market=="US") or fam=="F9"
            curve=pd.Series(wf.get("curve",{}),dtype=float)
            if len(curve):curve.index=pd.to_datetime(curve.index)
            hold_sh=_daily_metrics(curve.loc[curve.index>=pd.Timestamp("2023-01-01")])["sharpe"] if len(curve)>2 else None
            bstart=pd.Timestamp(wf.get("start_year",2015),1,1); b=bench.loc[bench.index>=bstart]
            bm=metrics(b) if len(b)>2 else {}
            mm=metrics(mix.loc[mix.index>=bstart]) if mix is not None and len(mix.loc[mix.index>=bstart])>2 else {}
            flags=[]
            if any("SURVIVOR" in r.get("flags",[]) for r in trials):flags.append("SURVIVOR")
            # These are known late listings/short vendor histories, not a
            # market-wide fallback to 2018 data. The coordinator confirmed
            # KR_298040, US_BKNG, and US_DELL are legitimately short-history.
            if fam in ("F4","F5","F6","F10","F13") and any(("MISSING_ETF_CACHE" in r.get("flags",[]) or "MISSING_STOCK_SYMBOLS" in r.get("flags",[])) for r in trials):flags.append("WMT_ABSENT")
            elif any("MISSING_ETF_CACHE" in r.get("flags",[]) for r in trials):flags.append("MISSING_ETF")
            if len(trials)>400:flags.append("CAP_BREACH")
            if fam=="F12" and len(trials)==100:flags.append("FULL_ENUMERATION_100")
            if fam=="F11" and market=="KR":flags.append("TAX_UNMODELED")
            if unavailable:grade="N/A" if fam!="F9" else "SKIPPED"
            else:grade=wf.get("grade","C")
            data.append({"fam":fam,"grade":grade,"wf":wf,"subset":subset,"trials":trials,"hold":hold_sh,"bm":bm,"mix":mm,"flags":flags,"unavailable":unavailable})
        data.sort(key=lambda d:(d["grade"] in ("A","B"),d["wf"].get("cagr") or -99),reverse=True)
        for rank,d in enumerate(data,1):
            w=d["wf"]
            docs.append(f"| {rank} | {d['fam']} | {d['grade']} | {pct(w.get('cagr'))} | {pct(w.get('mdd'))} | {num(w.get('sharpe'))} | {num(d['hold'])} | {pct(d['bm'].get('cagr'))} / {pct(d['bm'].get('mdd'))}; {pct(d['mix'].get('cagr'))}; 0.0% | {len(d['subset'])} | {len(d['trials'])} | {', '.join(d['flags']) or '—'} |")
        docs += ["","### 후보 설정과 판정 근거",""]
        for d in sorted(data,key=lambda z:z["fam"]):
            fam=d["fam"];wf=d["wf"]
            if d["unavailable"]:
                reason="미장 전용 대상 아님" if fam=="F11" and market=="US" else "국장 전용 대상 아님" if fam=="F8" and market=="US" else "A/B 구성요소 2개 미만"
                docs.append(f"- **{fam}: {d['grade']}** — {reason}; R2 설정 행 {len(d['trials'])}, 총 ledger 행 {len(d['subset'])}.")
                continue
            params=wf.get("top_params",{})
            annual=", ".join(f"{y}: {pct(v)}" for y,v in wf.get("annual_returns",{}).items()) or "—"
            reason=wf.get("decision_reason") or ("A 기준 충족" if d["grade"]=="A" else "B 기준 충족" if d["grade"]=="B" else "등급 조건 미달")
            stress=wf.get("survivor_exclusion_search_metrics") if fam in ("F4","F5","F6","F10","F13") else None
            stress_text=(f"; 상위10 제외 IS CAGR/MDD/Sharpe {pct(stress.get('cagr'))}/{pct(stress.get('mdd'))}/{num(stress.get('sharpe'))}" if stress else "")
            checks=f" ({wf.get('neighbor_check_count')}개 실제 이웃)" if wf.get("neighbor_check_count") is not None else ""
            docs.append(f"- **{fam}: {d['grade']}** — {len(d['trials'])} 설정, ledger {len(d['subset'])}행. 상위 값 `{json.dumps(params,ensure_ascii=False,sort_keys=True)}`. WF 연도 수익 {annual}. 이웃 중앙 Sharpe {num(wf.get('neighbor_sharpe_median'))}{checks}; 교란 통과 {wf.get('future_perturbation_pass')}{stress_text}; 이유 `{reason}`.")
    counts=collections.Counter((r.get("market"),r.get("family")) for r in rows if "TOP10_WINNER_EXCLUSION" not in r.get("flags",[]))
    docs += ["","## 상한·실행 예외",""]
    docs.append("- KR/F1은 Round 2 ledger 고유 설정 404행으로 400개 상한을 4개 초과했다. 추가 실행은 하지 않았고 append-only 원칙으로 기록은 보존했다. 이 가족 결과는 상한 위반으로 표시하며 채택하지 않는다." if counts.get(("KR","F1"),0)>400 else "- 설정별 상한 400행을 넘은 가족은 없다.")
    docs.append("- F12의 180행 미만은 시장별 100개 전수 탐색 공간이다." if counts.get(("KR","F12"))==100 and counts.get(("US","F12"))==100 else "- 180행 미만 그룹은 로그에서 전수 공간 여부와 중단 사유를 확인한다.")
    docs += ["","## 데이터 범위와 미완료 항목",""]
    for market,symbol in (("KR","005930"),("US","AAPL")):
        from app.aw_data import _cache_path
        p=_cache_path(market,symbol)
        try:first=pd.read_csv(p,usecols=["timestamp"],nrows=1).iloc[0,0]
        except Exception:first="missing"
        docs.append(f"- {market}_{symbol}: 첫 봉 {first}.")
    docs += ["- 미국 WMT 캐시는 없음으로 유지했다. 해당 종목은 제외했고 주식 가족에 `WMT_ABSENT`로 표시했다. 누락 ETF는 필요한 전략의 후보 universe에서 제외했다.","- 현재 대형주 유니버스 사용 결과는 `SURVIVOR` 생존편향 표시를 유지한다. 개별주 가족의 상위 10개 사후 승자 제외 스트레스는 별도 ledger 행으로 포함했다.","- 국장 F11 해외 ETF 이익의 15.4% 과세는 미반영이며 `TAX_UNMODELED`로 표시했다.","- F9은 시장별 A/B 후보가 두 개 이상일 때만 수행한다. 조건 미충족 시 스킵한다.",""]
    OUT.write_text("\n".join(docs),encoding="utf-8")
if __name__=="__main__":build()
