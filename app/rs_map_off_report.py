"""Offline map: renders docs/research/map_offline.md + map_off_family_summary.json from the saved result files."""
from __future__ import annotations
import json, os
import numpy as np, pandas as pd
from app.rs_map_off_data import SCRATCH
OUT = os.path.join(SCRATCH, "mapoff"); DOCS = os.path.join(os.path.dirname(os.path.dirname(os.path.abspath(__file__))), "docs", "research")
P = lambda x: "-" if x is None else f"{100 * x:.1f}"
def cm(m): return "-" if not m else f"{P(m['cagr'])}/{P(m['mdd'])}"
def tot(m): return None if not m else (1 + m["cagr"]) ** (m["n"] / 365.0) - 1


def short(o):
    p = o["params"]; ps = ",".join(f"{k}={v}" for k, v in p.items())
    return f"{o['family']}[{o['tf']}] {o['cons']}" + (f" K{o['K']}" if o["cons"] in ("LS", "LO_TOPN") else "") + (f" {o['mode']}" if o["cons"] == "OVL" else "") + f" c{o['cad']}d; {ps}"


def main():
    E = json.load(open(os.path.join(DOCS, "map_off_finalists_eval.json")))
    F = json.load(open(os.path.join(DOCS, "map_off_finalists.json")))
    fs = pd.read_csv(os.path.join(OUT, "family_summary.csv"))
    base = pd.read_csv(os.path.join(OUT, "base_cases.csv.gz")); base["mode"] = base["mode"].fillna("")
    rot = E["rotation"]; mb = E["multi_blend"]
    json.dump(fs.round(4).to_dict("records"), open(os.path.join(DOCS, "map_off_family_summary.json"), "w"), ensure_ascii=False)
    L = []
    a = L.append
    a("# 오프라인 전략 지도 (동일 하네스, 98개 패밀리 x 4개 구성 x 파라미터 = 1,826,496 케이스)")
    a("")
    a("작성 2026-10-13, 오프라인(로컬 .rs_cache/vision만, 네트워크/주문/커밋 없음). 코드: app/rs_map_off_{data,core,run,final,perturb,legacy,report}.py + 패밀리 구현 rs_map_off_fam_{a,b,c}.py(코덱스 작성, 원본 스크립트 대조).")
    a("용어: **연수익률**=CAGR, **낙폭**=고점 대비 최악 하락(MDD), **Calmar**=연수익률/낙폭(높을수록 좋음), **보류구간**=선택에 한 번도 안 쓴 마지막 구간(2026-06-12~10-09, 120일), "
      "**널(null)**=신호를 시간축으로 무작위 이동시킨 가짜 신호 300회 분포.")
    a("")
    a("## 0. 한 줄 결론")
    a("- 같은 저울(0.10%+펀딩, 같은 유니버스/창)에 올리면 **라이브 로테이션을 단독으로 이기는 전략은 없다**(롱숏 12.7만 케이스 중 전 구간 동시 승리 9건, 모두 우연 범위/보류구간 붕괴).")
    a("- 롱전용 상위N+BTC 200일선 게이트 슬리브(Keltner, 거래량 lookback)는 로테이션과 **같은 수준의 수익/낙폭 + 낮은 상관(0.3~0.5)**: 50/50로 섞으면 낙폭 19.4%->16~18%(Calmar 2.03->2.3~2.6)인 *보완 후보*. 단 2024 한 해 비중이 55~62%, 2024 제외 연수익 16~18%라 증거는 약함.")
    a("- 보류 120일: 롱숏 단독 후보 5개 중 4개가 -3~-18%로 붕괴, 롱전용 슬리브는 +27~28%(같은 기간 균등보유 +61%, BTC +30%라 '알트 강세 덕'일 가능성). 50/50 섞은 포트폴리오의 보류구간 낙폭은 8.7%->10.9%로 오히려 커졌음.")
    a("")
    a("## 1. 실험 매트릭스 (실제로 전부 실행)")
    a("| 항목 | 값 |")
    a("|---|---|")
    a("| 패밀리 | 98 (A 추세/돌파 41, B 차트/ICT 15, C 이벤트/지표/눌림 42) |")
    a("| 단위 = 패밀리 x 타임프레임(1d,4h) x 파라미터 점 | 6,342 |")
    a("| 구성 | (i) 종목별 롱전용 균등 LO_EW x{균등,역변동성} x 케이던스4 = 8, (ii) 달러중립 롱숏 LS = K5 x 케이던스4 = 20, (iii) 상위N 롱전용+BTC>200일선 LO_TOPN = K5 x 케이던스4 x 가중2 = 40, (iv) 로테이션 오버레이 OVL = 4모드(tilt0.5/tilt1.0/agree/gate) |")
    a("| 케이던스 {1,2,3,7}일 / K {4,6,8,10,12} / 비용 {0.10%+실펀딩, 0.04%무펀딩} / 사이징 {1x, 변동성타깃 20%(cap1.5)} | 위치(phase) 전부 평균 |")
    a("| **총 케이스** = 6,342 x 72 x 4(비용x사이징) | **1,826,496 (전부 실행, 오류 0)**; 핵심(0.10%+펀딩,1x) 456,624 |")
    a("| 충실도 | exact 15 / partial 33 / approx 50 (approx = 종가 체결, 종가기준 손절, quote volume 사용, 4h는 일 단위 x6 확장) |")
    a("| 재현 불가(구현 안 함) | 1분봉 필요: 오프닝레인지(#91,#98), 1만원룰, 볼린저 다이버전스 분봉; TJR 재량/세션/킬존/MSS/BOS(기계 정의 없음); 계좌 단위 서킷/사이징 정책(a_advanced_*, c_volume_account_circuit 등: 신호 인터페이스 밖); PSAR native(라이브러리 버전); best-partner 페어(전구간 상관으로 파트너 선택=미래누수) |")
    a("| 근사 주의 | 페어/통계차익은 BTC 대비 잔차 z-점수(단일 다리, 진짜 페어 아님). Dual Thrust/Dynamic Breakout/Ichimoku strict(카탈로그)는 이벤트스터디 조건을 종가 상태로 쓴 partial. FRVP/VWAP/HA는 일봉 근사 원본 정의 재현. 실제 청산/OI 데이터 없음(프록시) |")
    a("| 미래참조 검사 | 98개 전부 통과: 기준일 이후 데이터를 쓰레기로 바꿔 재계산해도 이전 행이 동일(패밀리당 3 파라미터 x 3 날짜 x tf) |")
    a("")
    a("## 2. 공정 조건")
    a("- 엔진: 롱숏(ii,iv)은 `rs_final_engine._sim` 그대로(수정 없음; 패밀리는 constant-weight 모드, 오버레이/대조군은 라이브식 수량유지 모델 A). 롱전용(i,iii)은 `_simw`: 같은 일봉 종가 체결/편도 0.10%/실펀딩을 쓰는 가중치 시뮬레이터이며 엔진 constant-weight와 **최종자산까지 일치**(2.8565=2.8565, 일수익률 상관 0.9997)로 검증.")
    a("- 체결: 일봉 종가에서 신호 계산 -> 같은 종가(=다음날 시가 부근) 체결. 선택창 2022-01-01~2026-06-11, 폴드 3개(2022-01~2023-04 / 2023-05~2024-08 / 2024-09~2026-06). 보류 2026-06-12~10-09는 1회만 평가(확정 파일 `map_off_finalists.json` 이후).")
    a("- 데이터는 2021-06부터(옛 문서는 2019-09부터)라 옛 숫자와 창이 다름. 45종목은 현재 생존종목(2022초 28종목): 아래 '2022전 상장만' 열이 생존편향 점검.")
    a("")
    a("## 3. 대조군 (라이브 로테이션 변형, 0.10%+펀딩, 위상평균)")
    a("| 설정 | 선택창 연/낙폭/Calmar | 보류 120일 수익/낙폭 |")
    a("|---|---|---|")
    for k, v in rot["controls"].items():
        s = v["sel"]; h = v["hold"]
        a(f"| {k.replace('|', ' ')} | {P(s['cagr'])}/{P(s['mdd'])}/{s['calmar']:.2f} | {P(tot(h))}/{P(h['mdd'])} |")
    r = mb["refs"]
    a(f"| 참고 BTC 보유 | {P(r['btc_sel']['cagr'])}/{P(r['btc_sel']['mdd'])}/{r['btc_sel']['calmar']:.2f} | {P(r['btc_hold_total'])}/- |")
    a(f"| 참고 45종목 균등보유 | {P(r['ew_sel']['cagr'])}/{P(r['ew_sel']['mdd'])}/{r['ew_sel']['calmar']:.2f} | {P(r['ew_universe_hold_total'])}/- |")
    a("(보류구간은 알트 강세: 균등보유 +61%. 로테이션은 +4%에 그침 -> 롱전용 후보가 상대적으로 좋아 보이는 구간.)")
    a("")
    a("## 4. 구성별 결과 분포 (핵심 비용 0.10%+펀딩, 1x, 선택창)")
    a("| 구성 | 케이스 | CAGR>0 비율 | 중앙 Calmar | 상위10% Calmar | 최대 Calmar | 기준 초과(선택창) | 기준 초과(선택창+3폴드 전부) |")
    a("|---|---|---|---|---|---|---|---|")
    for c, g in base.groupby("cons"):
        a(f"| {c} | {len(g):,} | {100*(g.cagr>0).mean():.0f}% | {g.calmar.median():.2f} | {g.calmar.quantile(.9):.2f} | {g.calmar.max():.1f} | {100*g.beat_sel.mean():.2f}% | {int(g.beat_all.sum())} ({100*g.beat_all.mean():.2f}%) |")
    a("기준 = 같은 모델의 라이브 로테이션+급락필터(롱숏/롱전용은 모델B, 오버레이는 모델A, 케이스와 같은 위상평균 방식).")
    a("0.04%/무펀딩으로 되돌리면 LS 중앙 CAGR -6.2%(0.10%+펀딩 -7.8%), OVL 중앙 +38.8%(+30.7%): 비용 효과는 OVL 약 8%p, LS 약 1.6%p: 비용이 결과를 뒤집지는 않음.")
    a("")
    a("## 5. 확정 후보 20 (선택창 내 규칙만으로 확정, 이후 보류구간 1회 평가)")
    a("규칙: 패밀리x구성별 min(선택창, 폴드1~3 Calmar) 최대, 이웃(파라미터/K/케이던스 한 칸) 75% 이상이 0.8배 Calmar 이상. 구성별 5패밀리.")
    a("| 후보 | 선택창 연/낙폭 | 폴드 Calmar | 보류 수익/낙폭 | 0.04%만 연수익 | vt20 연/낙폭 | 2022전 상장만 연/낙폭 | 로테이션 상관(선택/보류) | 널 상위% / 최선N 95%초과 | 2024 비중 |")
    a("|---|---|---|---|---|---|---|---|---|---|")
    seen = set()
    for o in E["finalists"]:
        key = (o["cons"], round(o["sel"]["cagr"], 6), round(o["sel"]["mdd"], 6))
        if key in seen:
            continue
        seen.add(key)
        a(f"| {short(o)} | {cm(o['sel'])} | {'/'.join(f'{x['calmar']:.1f}' for x in o['folds'])} | {P(o['hold_total'])}/{P(o['hold']['mdd'] if o['hold'] else None)} | "
          f"{P(o['c04']['cagr'])} | {cm(o['vt20'])} | {cm(o['pre2022_subset'])} | {o['corr_A_sel']:.2f}/{o['corr_A_hold'] if o['corr_A_hold'] is None else round(o['corr_A_hold'], 2)} | "
          f"{100*o['null']['pct_calmar']:.0f}% / {'예' if o['null']['beats_bestofN_p95'] else '아니오'} | {P(o['share_2024'])}% |")
    a(f"로테이션 기준(같은 방식): 선택창 {cm(rot['A']['sel'])}, 보류 {P(tot(rot['A']['hold']))}/{P(rot['A']['hold']['mdd'])}. 중복 신호(Keltner btc=catalog, volume_stop_regime=month_cap)는 1행만 표시.")
    a("")
    a("## 6. 섞기 (로테이션 A 대비, 일 단위 리밸런스 슬리브 합성; 낙폭 변화)")
    a("| 구성 | 선택창 연/낙폭/Calmar | 낙폭 변화 | 보류 수익/낙폭 |")
    a("|---|---|---|---|")
    rs = rot["A"]["sel"]
    a(f"| 로테이션 단독 | {P(rs['cagr'])}/{P(rs['mdd'])}/{rs['calmar']:.2f} | - | {P(tot(rot['A']['hold']))}/{P(rot['A']['hold']['mdd'])} |")
    for o in E["finalists"]:
        if o["cons"] in ("LO_TOPN",) and o["family"] in ("a_keltner_btc_ls", "c_volume_lookback", "c_volume_month_cap"):
            for md in ("5050", "ivol"):
                b = o["blend"][md]; s = b["sel"]
                a(f"| 로테이션+{o['family']} K{o['K']} ({md}) | {P(s['cagr'])}/{P(s['mdd'])}/{s['calmar']:.2f} | {100*(s['mdd']-rs['mdd']):+.1f}%p | {P(tot(b['hold']))}/{P(b['hold']['mdd'])} |")
    for nm, k in (("균등(25%x4)", "eq"), ("역변동성", "ivol"), ("위험균등(ERC)", "erc")):
        b = mb["nonovl"][k]; s = b["sel"]
        a(f"| 로테이션+Keltner TOPN+Keltner EW+거래량lookback TOPN, {nm} | {P(s['cagr'])}/{P(s['mdd'])}/{s['calmar']:.2f} | {100*(s['mdd']-rs['mdd']):+.1f}%p | {P(b['hold_total'])}/{P(b['hold']['mdd'])} |")
    a("(4슬리브 구성은 첫 평가를 본 뒤 추가한 정의: 선택창 Calmar 상위 비-오버레이 3개. 슬리브 선택 자체가 표본 내라 낙폭 개선은 낙관 편향.)")
    a("")
    a("## 7. 옛 문서에선 좋아 보였지만 공정 규칙에서 죽는 것")
    a("| 대상 | 옛 주장(연/낙폭) | 공정 하네스(상위8 롱전용, 0.10%+펀딩, 2022-01~2026-06) | 이유 |")
    a("|---|---|---|---|")
    LG = {r["label"]: r for r in json.load(open(os.path.join(DOCS, "map_off_legacy_recon.json")))}
    rows = {}
    for r in json.load(open(os.path.join(DOCS, "map_off_legacy_recon.json"))):
        rows.setdefault(r["label"], {})[(r["cons"], r["cost"])] = r
    why = {"Donchian70/25 +BTC히스테리시스(R14)": "2020-21 대세상승이 빠지고 비용/펀딩 반영 -> 수익 절반 이하(29 vs 69), 낙폭은 그대로",
           "거래량폭증 챔피언 3x/무반응/20일": "집중 상위8에서 수익 절반(31 vs 62), 낙폭 동일; 균등화하면 수익 19%/낙폭 22%",
           "하이킨아시 기본(20일보유)": "2022 이후 마이너스: 옛 +71%는 2019-21 강세장 의존 + 선택편향",
           "FRVP 기본(20일보유)": "마이너스(-10%, 낙폭 76%): 옛 수치는 거래 140건 집중",
           "VWAP 기본(20일보유)": "마이너스, 낙폭 74~88%: 옛 108%는 사실상 파산 직전 설계",
           "TRX 골든크로스+와이드스탑 9/21/12%": "단일종목(TRX) 결과를 45종목에 일반화 불가; 포트폴리오에선 0 근처, 낙폭 78%"}
    for lab, d in rows.items():
        t = d[("top8_nogate", "0.10%+fund")]; t4 = d[("top8_nogate", "0.04%")]
        a(f"| {lab} | {t['claim']} | {t['2022-01~2026-06'][0]}/{t['2022-01~2026-06'][1]} (0.04%만: {t4['2022-01~2026-06'][0]}/{t4['2022-01~2026-06'][1]}; 2021-07~: {t['2021-07~2026-06'][0]}/{t['2021-07~2026-06'][1]}) | {why.get(lab, '')} |")
    a("(구성 = 신호 ON 종목 중 상위8 균등, 일 단위, BTC 게이트 없음 = 옛 구성에 가장 가까움. 옛 창 2019-09~는 데이터가 없어 직접 재현 불가.)")
    a("")
    a("## 8. 통계 보정")
    nul = [o["null"] for o in E["finalists"]]
    a(f"- 평가 케이스 {E['n_total_cases']:,}(핵심 {E['n_trials_base']:,}, 독립 단위 {E['n_units']:,}). 다중검정 보정 후 **전부 약함**: 확정 20개 디플레이티드 샤프 확률 0.00~0.06(시행 샤프 분산이 커서 SR0가 높음 = 이 풀에서 우연한 최고값 기대치가 큼).")
    a("- 기준 이기기: 핵심 케이스 중 선택창+3폴드 전부에서 라이브 로테이션을 이긴 것은 881건(0.19%)이고 그중 780건이 로테이션 오버레이(기준 자체에 약간 가감한 것), 단독 구성은 LS 9/LO_EW 7/LO_TOPN 85. 오버레이는 선택창 기준 초과 21%인데 이전 연구에서 '무작위 귀무에서도 25~37%'였으므로 우연과 구분 어려움.")
    a("- 널 300회(신호 시간이동, 회전율 동일): 단독 후보 대부분 상위 100%에 위치하지만 오버레이 5개는 95~100%에 몰려 있고 '패밀리 크기 N 중 최선' 95%선을 못 넘는 것이 5개 중 4개(오버레이=로테이션 자체가 널의 대부분이라 변별력 낮음).")
    a("- 이웃 검사: 확정 후보는 이웃(파라미터/K/케이던스 한 칸) 75% 이상이 0.8배 Calmar 이상(선택 규칙으로 보장).")
    a("- 연도 편중: 확정 후보 상당수가 2024 한 해가 총 로그수익의 34~64%. 2024 제외 연수익은 LO_TOPN Keltner 16%, 거래량lookback 18%, 오버레이 7~25%.")
    a("")
    a("## 9. 다음 단계 (가치/비용 순)")
    a("1. [싸다] 로테이션 + Keltner TOPN(K6/2일/BTC200 게이트) + 거래량lookback TOPN을 **페이퍼 90일**(코드/데이터 이미 있음). 증거가 가장 얇은 부분(2024 비중, 보류 120일 알트 강세)을 전향 데이터로 확인.")
    a("2. [싸다] 파트너 에이전트의 신규 데이터(2019~2021, 상장폐지 종목)로 같은 하네스 재실행: 2022 이전 약세/강세 모두 포함해 슬리브의 2022 '게이트=현금' 의존을 검증.")
    a("3. [중간] 슬리브 위험배분(ERC/역변동성)의 실제 현금 운용(최소 주문, 142 USDT 소액)에서 스킵률 점검.")
    a("4. [비싸다] 분봉/실청산 데이터가 필요한 항목(1만원룰, ICT 세션, 청산 히트맵)은 데이터 확보 전 보류.")
    a("")
    a("## 10. 가정과 확인하지 못한 것")
    a("- 롱숏 구성에서 롱전용 규칙의 '숏 레그'는 신호가 같은 종목 중 무작위 고정 타이브레이크: 헤지 효과 확인용일 뿐 원전략이 아님.")
    a("- 4h는 일 1회 종가에서만 거래(분 단위 체결 아님). 유니버스 생존편향(2022전 상장만 열로 점검). 보류 120일은 단일 국면이라 연율화 수치는 노이즈가 큼(총수익률로 표시).")
    a("- 페이퍼/라이브 체결 슬리피지 없음(수수료 0.10%에 포함 가정). 패밀리 코드는 코덱스가 작성했고 원본과의 일부 직접 대조(HA/FRVP 등)만 코덱스가 수행, 나머지는 위 근사 표기와 미래참조 테스트로만 확인.")
    open(os.path.join(DOCS, "map_offline.md"), "w").write("\n".join(L) + "\n")
    print(len(L), "lines")


if __name__ == "__main__":
    main()
