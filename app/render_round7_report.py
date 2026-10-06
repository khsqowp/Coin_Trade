"""Render only section 19 and the terminal first-series conclusion."""

import json
import numpy as np
from app.crypto_round7_research import ROOT, PATH


def run() -> None:
    d = json.loads(PATH.read_text())
    mc = d["monte_carlo"]
    b = d["bootstrap"]
    loo = d["leave_one_out"]
    trials = mc["trials"]
    rows = loo["rows"]
    lines = [
        "## 19. 챔피언 엣지 통계적 유의성 검증 (2026-10-07, 라운드7)",
        "",
        f"**{d['verdict']}** — 요청한 3개 검증 중 {sum(d['votes'])}/3개 통과. 현재까지 조사범위에 한정한 판정이다.",
        "",
        "§12 cap5%/신엔진 하나만 검사했다. 3배·cap5%·20일 보유·TOP_K=8·손절/익절/CB 없음·편도수수료0.04%·45종목·2019-09-08~2026-10-05를 고정했다. 기존 volume_prep·ledger_run·simulate_portfolio를 재사용했고 Round 5의 468건 원장 전체 필드 및 2,585일 NAV를 대조했다. 새 전략·조합 탐색은 수행하지 않았다.",
        "",
        "실행: `python3.12 -m app.crypto_round7_research`. 원시 결과: `docs/round7-results-2026-10-07.json`. 로그: `docs/round7-execution-2026-10-07.log`. 검증: `python3.12 -m app.verify_round7`, `docs/round7-verification-2026-10-07.txt`. 문서 생성: `python3.12 -m app.render_round7_report`.",
        "",
        "### 19-1. 랜덤진입 대조군(몬테카를로 500회) 결과",
        "",
        f"- 독립 seed 700000~700499, 매 종목·매일 Bernoulli 후보 확률={mc['probability']:.8f}=468/{mc['eligible_symbol_days']} 거래가능 종목일. 전일 봉 존재와 다음 실행일 시가 존재를 합산한 빈도만 전체기간에서 고정했으며 수익을 보고 조정하지 않았다. 최초 슬롯 점유 보정식은 거래규모 검사에 실패하여 폐기했고 최종 대조군은 직접 빈도식을 사용했다. 이는 역사적 조건부 대조군 설계이며 온라인 추정 확률이 아니다.",
        "- 실제 SIGNAL·VOL_RATIO를 읽지 않는다. 날짜→종목→후보/순위 순서로 독립 난수를 생성해 전일 후보를 다음날 시가에 실행한다. 보유 종목 제외·빈 8슬롯·가용현금/NAV 배분·20일 후 종가 청산·최종일 강제청산은 공통 엔진 그대로다. 후보 간 무작위 순위로 슬롯을 채우며 미래 가격·미래 거래를 후보 선택에 쓰지 않는다.",
        f"- 완료 거래수 평균 {np.mean([t['trades'] for t in trials]):.2f}건, 최소~최대 {min(t['trades'] for t in trials)}~{max(t['trades'] for t in trials)}건. 원본 468건과 비슷한 규모이며 개별 거래날짜·시장노출까지 일치시키지는 않았다.",
        "",
        "| 지표 | 챔피언 | 랜덤 중앙값 | 랜덤 95백분위 | 챔피언 백분위 | 단측 p | 판정 |",
        "|---|---:|---:|---:|---:|---:|---|",
    ]
    for k, label in [("cagr", "CAGR (%)"), ("sharpe", "Sharpe")]:
        t = mc["tests"][k]
        lines.append(
            f"| {label} | {d['baseline'][k]:.6f} | {t['quantiles'][2]:.6f} | {t['q95']:.6f} | {t['percentile']:.2f}% | {t['p']:.6f} | {'랜덤보다 유의미하게 낫다' if t['significant'] else '랜덤과 구분 안 됨'} |"
        )
    lines += [
        "",
        "- 백분위=챔피언보다 작은 랜덤 결과 비율×100. 단측 몬테카를로 p=(챔피언 이상인 랜덤 횟수+1)/501로 0을 보고하지 않는다. CAGR·Sharpe 모두 95백분위 초과 및 p<0.05여야 이 검증을 1표 통과로 센다.",
        "",
        "### 19-2. Leave-one-out 민감도(종목5+연도) 결과",
        "",
        "- 종목은 §17 손익 상위5 ZEC·ARB·VET·XLM·WLD를 하나씩 제외하여 44종목으로 재실행했다. 연도는 원장 청산일에서 완료 거래 발생 연도를 추출하고 해당 연도의 실제 신규 진입만 차단했다. 전년 말 신호→차단 연도 첫날 진입도 차단하며 기존 포지션은 정상 청산한다. 연도 제거 후 달력을 압축하거나 수익률을 삭제하지 않는다.",
        "- 원본의 50% 임계값: CAGR 31.176851%, Sharpe 0.582289. 어떤 단일 제외라도 둘 중 하나가 이 값 미만이면 취약이다. 슬롯·현금·후속 진입은 매 실행 재계산한다.",
        "",
        "| 제외 | CAGR | MDD | Sharpe | 거래수 | 50% 유지 |",
        "|---|---:|---:|---:|---:|---|",
    ]
    for r in rows:
        label = ("종목 " if r["kind"] == "symbol" else "진입연도 ") + str(r["excluded"])
        lines.append(
            f"| {label} | {r['cagr']:+.2f}% | {r['mdd']:.2f}% | {r['sharpe']:.3f} | {r['trades']} | {'통과' if r['pass'] else '실패'} |"
        )
    lines += [
        "",
        "| 제외 범위 | CAGR 최소~최대 | Sharpe 최소~최대 | 판정 |",
        "|---|---:|---:|---|",
    ]
    for kind, label in [("symbol", "종목5"), ("year", "연도"), (None, "전체")]:
        rr = [r for r in rows if kind is None or r["kind"] == kind]
        lines.append(
            f"| {label} | {min(r['cagr'] for r in rr):+.2f}%~{max(r['cagr'] for r in rr):+.2f}% | {min(r['sharpe'] for r in rr):.3f}~{max(r['sharpe'] for r in rr):.3f} | {'분산되어 있음' if all(r['pass'] for r in rr) else '취약'} |"
        )
    lines += [
        "",
        "- 이 검사는 단일 종목·연도 의존성 스트레스다. p값을 추정하는 유의성 검정은 아니며 요청한 종합 투표 규칙에서만 통과 여부를 사용한다. 단일 제외 통과는 다중 제외나 §17 수익집중도 해소를 의미하지 않는다.",
        "",
        "### 19-3. 블록부트스트랩 Sharpe 95% 신뢰구간",
        "",
        "- 원장 468건을 (진입 인덱스, 청산 인덱스, 원장 id) 순으로 정렬했다. 수익률 r=pnl/cost=proceeds/cost−1이며 양방향 수수료 포함이다. 절대 pnl 자체를 표준화 없이 수익률로 사용하지 않았다.",
        "- Moving-block bootstrap: 시작 인덱스 0~448에서 길이20 연속 거래 블록을 균등 복원추출하여 24블록을 연결하고 앞의468건을 사용한다. 블록 내부 시간순서는 보존되며 블록 간 원래 순서는 재표본화된다. seed710000, 1,000회. 마지막 부분 블록을 줄여 추출하지 않고 완전한20건 블록을 뽑은 후 전체 길이를 자른다.",
        "- 거래단위 Sharpe 근사=평균(r)/표본표준편차(r)×√(468/전체기간 연수). 위험무수익0, 거래빈도 연환산 고정. 중첩 포지션·현금 대기·일별 평가손익을 재구축하지 않으므로 포트폴리오 일별 Sharpe1.165의 신뢰구간이 아니다. 거래단위 엣지의 조건부 근사이며 종목 간 동시 상관을 완전히 보존하지 않는다.",
        f"- 원본 거래단위 Sharpe 근사 **{b['original_trade_sharpe']:.6f}**; 95% percentile 신뢰구간 **[{b['ci95'][0]:.6f}, {b['ci95'][1]:.6f}]**. 하한 {'>0이므로 유의미' if b['significant'] else '≤0이므로 엣지가 통계적으로 0과 구분 안 됨'}.",
        "",
        "### 19-4. 종합 판정",
        "",
        "| 검증 | 판정 | 종합 투표 |",
        "|---|---|---|",
    ]
    labels = ["랜덤대조군", "Leave-one-out", "블록부트스트랩"]
    descriptions = [
        "랜덤보다 유의미하게 낫다" if d["votes"][0] else "랜덤과 구분 안 됨",
        "분산되어 있음" if d["votes"][1] else "취약",
        "유의미" if d["votes"][2] else "0과 구분 안 됨",
    ]
    lines += [
        f"| {a} | {c} | {'통과' if v else '실패'} |"
        for a, c, v in zip(labels, descriptions, d["votes"])
    ]
    conclusion = (
        "현재까지 조사범위 내에서 통계적 근거가 있는 진짜 신호로 인정한다."
        if sum(d["votes"]) >= 2
        else "현재 조사범위 내에서 통계적으로 유의미한 엣지를 확인하지 못했다. 완전 기각이 아닌 증거불충분이다."
    )
    lines += [
        "",
        f"**{conclusion}** 요청한 2/3 규칙에 따른 결론이며, 세 검사는 독립적인 p검정이 아니고 종합 판정 자체에 p<0.05를 부여하지 않는다.",
        "- §17 상위10건 순손익기여103.00%·상위5종목87.85%는 여전히 남는다. 통계적 유의성과 집중도·종목쏠림 운용 리스크는 별개다. 반복 탐색 후 선택한 챔피언에 대한 조건부 검사로 다중탐색 선택편향을 보정하지 않았고 진짜 미관측 OOS도 아니다. 비용·생존편향 한계는 유지한다.",
        "- 검증: 원본 원장468건·NAV·지표 일치, 랜덤 prefix/미래가격변형 2절단점×2비교, seed3개 실제 엔진 재실행·슬롯/과거 타임스탬프, 종목5+모든 연도 제외 독립 재실행, 1,000개 블록 시퀀스 독립 산술 대조, 유한 성과·거래규모·MDD 범위, 신규 모듈 python3 -m py_compile, Round1~6 기존 회귀검증 재실행 통과.",
        "- 회귀 로그: "
        + ", ".join(
            f"`docs/round7-round{n}-regression-2026-10-07.txt`" for n in range(1, 7)
        )
        + ".",
        "",
        "---",
        "",
    ]
    docpath = ROOT / "docs/전략-백테스트-종합.md"
    text = docpath.read_text()
    if "## 19." in text:
        text = text[: text.index("## 19.")] + text[text.index("## 결론") :]
    if "## 20." in text:
        text = text[: text.index("## 20.")].rstrip() + "\n"
    text = text.replace("## 결론", "\n".join(lines) + "\n## 결론", 1)
    timeline = [
        "Round1(§13): 10종 신호 베이스라인과 스윕.",
        "Round2(§14): 하이브리드와 서킷브레이커 최초 구현.",
        "Round3(§15): 서킷브레이커 재진입 수정·변동성사이징, 목표충족5조합 발견.",
        "Round4(§16): 5조합 워크포워드·강건성 검증, 대표 승자4/5 항목 불안정으로 기각.",
        "Round5(§17): 챔피언 자체3/4 항목 불안정, N=2·N=3 앙상블 기각.",
        "Round6(§18): 절대기준→알파기준 교체·베어마켓 효과 분리, 챔피언 기간분리 전구간 통과, 쏠림완화 실패.",
        "Round7(§19): 챔피언 하나의 통계검증, "
        + d["verdict"]
        + f"({sum(d['votes'])}/3 통과).",
    ]
    text += "\n## 20. 라운드1~7 종합 결론 (2026-10-07)\n\n"
    text += "\n".join("- " + t for t in timeline) + "\n"
    text += "- 최종 판정: 지금까지 조사한 범위 내에서 §12 거래량폭증 챔피언을 CAGR/MDD/Sharpe 세 축 전부에서 지배하면서 강건성 검증(기간분리/집중도/민감도/쏠림)까지 통과하는 대체 전략은 발견되지 않았다.\n"
    text += (
        "- 챔피언 신뢰도: "
        + conclusion
        + " 통계적 유의성과 별개로 상위10건103.00%·상위5종목87.85% 집중이라는 운용 리스크는 남는다. 실거래 승격을 뜻하지 않는다.\n"
    )
    text += "- 1차 탐색은 여기까지다. Round8+는 선택사항이다: ①규칙·유니버스·비용 동결 후 전향적 모의운용 ②베타중립·시장노출 조정 검증 ③펀딩비·슬리피지·시장충격 반영 재검증.\n"
    docpath.write_text(text)


if __name__ == "__main__":
    run()
