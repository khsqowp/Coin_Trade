"""Build the final AW-2 markdown report from the append-only ledger and WF artifacts."""
from __future__ import annotations

import json
from pathlib import Path

import numpy as np
import pandas as pd

from app.aw2_search import bench_curves
from app.aw_data import load_panel
from app.aw_run import _daily_metrics, metrics

ROOT=Path(__file__).resolve().parents[1]
BASE=ROOT/"docs/research/aw2"
LEDGER=BASE/"ledger.jsonl"
RESULTS=ROOT/"docs/research/AW2_RESULTS.md"
FAMS=("F1","F2","F3","F4","F5","F6","F7","F8","F9")


def _best_rows(rows, market, family):
    subset=[r for r in rows if r["market"]==market and r["family"]==family and "SURVIVOR_STRESS_TOP10_REMOVED" not in r["flags"]]
    if family=="F3": subset=[r for r in subset if "rebalance_threshold" in r["params"]]
    if family in ("F4","F6"): subset=[r for r in subset if "RISK_CAP_10PCT_ENFORCED" in r["flags"]]
    latest={}
    for r in subset:
        key=json.dumps(r["params"],sort_keys=True)
        if key not in latest or r["ts"]>latest[key]["ts"]: latest[key]=r
    return sorted(latest.values(),key=lambda r:r["search_metrics"]["calmar"] if r["search_metrics"]["calmar"] is not None else -1e9,reverse=True)


def _period_cagr(curve, years):
    r=curve.pct_change(fill_method=None)
    x=r.loc[r.index.year.isin(years)].dropna()
    return float((1+x).prod()**(252/len(x))-1) if len(x) and (1+x).prod()>0 else None


def _max_underwater(curve):
    under=curve<curve.cummax(); best=run=0
    for v in under:
        run=run+1 if v else 0; best=max(best,run)
    return best


def _pct(x): return "—" if x is None or not np.isfinite(x) else f"{x*100:.1f}%"
def _cost_pct(x): return "—" if x is None or not np.isfinite(x) else f"{x*100:.2f}%"
def _num(x,d=2): return "—" if x is None or not np.isfinite(x) else f"{x:.{d}f}"


def build():
    rows=[json.loads(s) for s in LEDGER.read_text(encoding="utf-8").splitlines() if s.strip()]
    all_attempts=len(rows); by_count={(m,f):sum(r["market"]==m and r["family"]==f for r in rows) for m in ("KR","US") for f in FAMS}
    wf_data={}; panels={}; benchmarks={}
    for market in ("KR","US"):
        panels[market]=load_panel(market,include_stocks=True)
        benchmarks[market]=bench_curves(panels[market])
        for family in FAMS:
            p=BASE/"wf"/f"{market}_{family}.json"
            if p.exists():
                item=json.loads(p.read_text(encoding="utf-8"))
                curve=pd.Series(item.get("curve",{}),dtype=float)
                if len(curve):
                    curve.index=pd.to_datetime(curve.index)
                    idx_curve=benchmarks[market]["index_hold"].reindex(curve.index).ffill()
                    idx_metrics=metrics(idx_curve)
                    hold_idx=benchmarks[market]["index_hold"].loc[lambda s:s.index>=pd.Timestamp("2023-01-01")]
                    hold_idx_sharpe=_daily_metrics(hold_idx)["sharpe"] if len(hold_idx)>1 else None
                    hold_strategy_sharpe=_daily_metrics(curve.loc[curve.index>=pd.Timestamp("2023-01-01")])["sharpe"]
                    a_gates={"wf_cagr_ge_index":item.get("cagr",-np.inf)>=idx_metrics["cagr"],"wf_mdd_le_60pct_index":item.get("mdd",np.inf)<=idx_metrics["mdd"]*.6,"holdout_sharpe_ge_index":hold_strategy_sharpe is not None and hold_idx_sharpe is not None and hold_strategy_sharpe>=hold_idx_sharpe,"neighbor_stability":False}
                    y22=item.get("annual_returns",{}).get("2022")
                    b_gates={"wf_cagr_ge_70pct_index":item.get("cagr",-np.inf)>=idx_metrics["cagr"]*.7,"wf_mdd_le_50pct_index":item.get("mdd",np.inf)<=idx_metrics["mdd"]*.5,"2022_ge_minus8":y22 is not None and y22>=-.08,"neighbor_stability":False}
                    failed_a=[k for k,v in a_gates.items() if not v]; failed_b=[k for k,v in b_gates.items() if not v]
                    item["grade_gates"]={"A":a_gates,"B":b_gates,"failed_A":failed_a,"failed_B":failed_b,"index_holdout_sharpe":hold_idx_sharpe,"wf_holdout_sharpe":hold_strategy_sharpe}
                    item["decision_reason"]="A failed: "+", ".join(failed_a)+"; B failed: "+", ".join(failed_b)
                    p.write_text(json.dumps(item,ensure_ascii=False,indent=2,allow_nan=False)+"\n",encoding="utf-8")
                wf_data[(market,family)]=item
    lines=["# AW-2 국장·미장 전략 탐색 결과", "", "작성 기준: 2026-11-13. AW-2 명세의 탐색 종료일은 2026-11-11이며, 검색 선택·순위에는 2022-12-31 이후 데이터가 들어가지 않았다.", "",
      "## 판정", "", "양 시장에서 A/B 등급 전략은 없다. 모든 실행 가능한 전략군은 C로 거부했고, F9 앙상블은 통과한 A/B 구성요소가 없어 실행하지 않았다.", "",
      f"- 원장 백테스트 행: **{all_attempts}회**. 개별 설정 실행과 스트레스 실행, 수정 후 재실행을 모두 보존했다.",
      "- 전체 탐색 설정 상한은 전략군·시장별 400개이며 어떤 그룹도 상한을 넘지 않았다.",
      "- F5는 현 업종 기준 섹터-종목 정적 매핑을 뒷받침할 자료가 없어 0회 실행 후 거부했다. F8은 국장 전용이며 미장은 해당 없음.",
      "- 워크포워드 파라미터는 연도별 expanding window로 선택하되, 2023년부터는 선택 데이터 종료일을 2022-12-31로 고정했다. 매년 선택된 세부 값은 각 `wf/<시장>_<가족>.json`의 `yearly_selection`에 있다.",
      "- A/B 필수 이웃 안정성(이웃 WF Sharpe 중앙값 ≥ 후보 Sharpe의 60%)은 격자 이웃을 완전하게 만들지 못해 통과 판정을 내리지 않았다. 이 검증 미실행은 채택 금지 사유다.", "",
      "## WF 결과 및 벤치마크", "", "WF CAGR/MDD/Sharpe는 가족별 WF 기간에 맞춘 지수 ETF 보유, 월간 지수 60%·단기채 40%, 현금과 비교했다. 아래 ‘최고 IS’ 값은 2022-12-31까지 검색한 최고 Calmar 후보이며 채택된 finalist를 뜻하지 않는다.", ""]
    for market in ("KR","US"):
        idx="069500" if market=="KR" else "SPY"
        lines += [f"### {market}", "", "| 순위 | 가족 | 등급/결정 | 설정 수(원장 행) | 최고 IS 설정 요약 | WF CAGR / MDD / Sharpe | 지수 CAGR / MDD | 60/40 CAGR | 홀드아웃 Sharpe(후보/지수) |", "|---:|---|---|---:|---|---:|---:|---:|---:|"]
        summaries=[]
        for family in FAMS:
            if family=="F9": continue
            wf=wf_data.get((market,family),{})
            if market=="US" and family=="F8":
                summaries.append((family,"N/A",0,None,None,wf)); continue
            bests=_best_rows(rows,market,family); best=bests[0] if bests else None
            decision=wf.get("decision","REJECTED" if wf.get("reason") else "C_REJECTED")
            summaries.append((family,wf.get("grade","C"),by_count[(market,family)],best,bests,wf,decision))
        # Rank executable families by WF CAGR; rejected/no-data cases follow.
        summaries.sort(key=lambda x:(x[1] in ("A","B"),x[5].get("cagr") or -99),reverse=True)
        for rank,item in enumerate(summaries,1):
            if len(item)==6 and item[1]=="N/A":
                fam=item[0]; lines.append(f"| {rank} | {fam} | N/A, 국장 전용 | 0 | — | — | — | — | — |")
                continue
            fam,grade,count,best,bests,wf,decision=item
            curve=pd.Series(wf.get("curve",{}),dtype=float) if wf.get("curve") else pd.Series(dtype=float)
            curve.index=pd.to_datetime(curve.index) if len(curve) else curve.index
            wf_metrics={k:wf.get(k) for k in ("cagr","mdd","sharpe")}
            wf_dates=curve.index
            ix=benchmarks[market]["index_hold"].reindex(wf_dates).ffill() if len(wf_dates) else pd.Series(dtype=float)
            mix=benchmarks[market].get("index60_bond40",pd.Series(dtype=float)).reindex(wf_dates).ffill() if len(wf_dates) else pd.Series(dtype=float)
            bm=metrics(ix) if len(ix)>1 else {}; mixm=metrics(mix) if len(mix)>1 else {}
            hold_ix=benchmarks[market]["index_hold"].loc[lambda s:s.index>=pd.Timestamp("2023-01-01")]
            hold_idx_sh=_daily_metrics(hold_ix)["sharpe"] if len(hold_ix)>1 else None
            hold_sh=wf.get("holdout_sharpe")
            psummary="—"
            if best:
                p=best["params"]
                keys=("basket","weighting","lookback","k","cadence","core","trends","moms","min_exposure","max_exposure","rebalance_threshold","skip_recent","satellite","rsi","threshold","slots","stop")
                psummary="; ".join(f"{k}={p[k]}" for k in keys if k in p)
            cagr=wf_metrics["cagr"]
            sortkey=0
            stress=wf.get("survivor_stress")
            info={"family":fam,"grade":grade,"count":count,"params":psummary,"wf_cagr":cagr,"wf_mdd":wf_metrics["mdd"],"wf_sharpe":wf_metrics["sharpe"],"index_cagr":bm.get("cagr"),"index_mdd":bm.get("mdd"),"mix_cagr":mixm.get("cagr"),"hold_sharpe":hold_sh,"index_hold_sharpe":hold_idx_sh,"best":best,"bests":bests,"wf":wf,"curve":curve,"stress":stress}
            lines.append(f"| {rank} | {fam} | {grade} / {decision} | {count} | {psummary} | {_pct(cagr)} / {_pct(wf_metrics['mdd'])} / {_num(wf_metrics['sharpe'])} | {_pct(bm.get('cagr'))} / {_pct(bm.get('mdd'))} | {_pct(mixm.get('cagr'))} | {_num(hold_sh)} / {_num(hold_idx_sh)} |")
            item_obj=info
            # Add family detail immediately after ranking table later.
        lines += ["", "#### 설정·연도별 수익·거부 사유", ""]
        # Emit detail in family ID order for consistent lookup.
        for family in FAMS:
            if family=="F9" or (market=="US" and family=="F8"): continue
            wf=wf_data.get((market,family),{}); bests=_best_rows(rows,market,family); best=bests[0] if bests else None
            count=by_count[(market,family)]
            if not best:
                reason=wf.get("reason","설정 없음")
                lines += [f"**{family} — C, 거부.** {reason}. 실제 검색 설정 {count}회.", ""]
                continue
            params=best["params"]; wf_curve=wf.get("annual_returns",{})
            wf_equity=pd.Series(wf.get("curve",{}),dtype=float)
            if len(wf_equity): wf_equity.index=pd.to_datetime(wf_equity.index)
            annual=", ".join(f"{y}:{float(v)*100:+.1f}%" for y,v in wf_curve.items())
            search=best["search_metrics"]; full=best["full_metrics"]; hold=best["holdout_metrics"]
            lines += [f"**{family} — {wf.get('grade','C')}, 거부.** 최고 IS 값은 2022년 말 이전 최고 Calmar 단일 설정이다: `{json.dumps(params,ensure_ascii=False,sort_keys=True)}`.",
              f"- WF 연도별 수익: {annual or '—'}. WF JSON: [`{market}_{family}.json`](aw2/wf/{market}_{family}.json). 연도별 자동 선택은 해당 파일의 `yearly_selection`을 따른다.",
              f"- 최고 IS 지표: CAGR {_pct(search.get('cagr'))}, MDD {_pct(search.get('mdd'))}, Sharpe {_num(search.get('sharpe'))}; 연 회전율 {_num(full.get('turnover'))}배, 연 비용 {_cost_pct(full.get('cost'))}. 홀드아웃 CAGR {_pct(hold.get('cagr'))}, Sharpe {_num(hold.get('sharpe'))}.",
              f"- 최고 IS 설정의 기간 CAGR: 2011–2016 {annual_period(best,2011,2016)}, 2015–2016 {annual_period(best,2015,2016)}, 2018 {annual_period(best,2018,2018)}, 2022 {annual_period(best,2022,2022)}. 최고 연간 손실 {worst_year(best)}.",
              f"- WF 곡선 최장 고점 회복 대기: {_max_underwater(wf_equity)} 거래일. 결정 제한: {wf.get('decision_reason','성능 기준 미달 또는 검증 미완료')}."]
            if family in ("F4","F6") and wf.get("survivor_stress"):
                st=wf["survivor_stress"]
                lines.append(f"- SURVIVOR 스트레스: 사후 전체기간 수익 상위 10종목 제외. 제외 목록 {', '.join(st['excluded_top10'])}; 검색 CAGR/MDD {_pct(st['search_metrics']['cagr'])}/{_pct(st['search_metrics']['mdd'])}, 홀드아웃 CAGR {_pct(st['holdout_metrics']['cagr'])}.")
            lines.append("")
    lines += ["## 데이터·구현 한계", "",
      "- `KR_005930.csv`는 2018-01-02 시작으로 2010년 확장 데이터가 도착하지 않았다. 개별주 F4/F6의 WF는 실제 주식 데이터 시작일+3년인 2021년부터 평가했다.",
      "- 기준 종료일은 2026-11-11이다. 추가 캐시 누락 ETF는 현재 단계에서 스킵했다. US의 WMT도 없어서 제외했다. 누락 심볼 전체는 `AW2_LOG.md`에 라운드별 기록했다.",
      "- 개별주 F4/F6는 현재 대형주 유니버스에 의존하므로 생존편향을 가진다. 상위 10종목 제거 스트레스가 이를 제거하지 못하므로 결과는 탐색적이다.",
      "- KIS 비용은 미장 왕복 체결 시 편도 0.36%를 적용했다. 미장 듀얼 모멘텀은 연 비용이 높게 발생했다.",
      "- F3 최초 실험은 재조정 임계치를 적용하지 않은 결함이 있어 보존 후 수정 실행을 추가했다. F4/F6 최초 실험도 10% 종목 상한을 적용하지 않아 최신 상한 적용 실행으로 대체했다. 원장 행은 삭제하지 않았다.",
      "- WF 이웃 안정성 게이트가 미검증이므로 성과 숫자가 일부 기준을 넘더라도 등급 A/B를 부여하지 않았다. F9은 미실행·거부했다.", "",
      "## 총 시도 수", "", f"원장 총 행은 **{all_attempts}**다. 아래 값은 가족·시장별 기록 행이며 후보 설정 재실행과 SURVIVOR 스트레스 행을 포함한다.", "",
      "| 가족 | KR 행 | US 행 |", "|---|---:|---:|"]
    for f in FAMS: lines.append(f"| {f} | {by_count[( 'KR',f)]} | {by_count[( 'US',f)]} |")
    lines += ["", "등급 A/B가 없어 채택 가능한 앙상블 구성요소가 0개다. F9은 이에 따라 거부되었다.", ""]
    RESULTS.write_text("\n".join(lines),encoding="utf-8")


def annual_period(row, start, end):
    p=row.get("full_metrics",{}).get("peryear",{})
    vals=[float(p[str(y)]) for y in range(start,end+1) if str(y) in p]
    if len(vals)<end-start+1: return "—"
    return _pct(float(np.prod([1+x for x in vals])**(1/len(vals))-1))


def worst_year(row):
    vals=row.get("full_metrics",{}).get("peryear",{})
    if not vals:return "—"
    y,v=min(vals.items(),key=lambda kv:kv[1]);return f"{y} {_pct(v)}"


if __name__=="__main__": build()
