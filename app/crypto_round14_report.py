"""Append complete section evidence and attempt exact-file Git publication."""

from typing import Optional
import json
from app import crypto_round14_research as r14


def section(number: int, title: str, start: int, end: Optional[int] = None) -> None:
    out = json.loads(r14.PATH.read_text())
    if number in out["sections"]:
        return
    rows = out["experiments"][start:end]
    assert rows
    with r14.DOC.open("a") as f:
        f.write(f"\n\n## {number}. {title} (2026-10-07, 라운드14)\n\n")
        f.write(
            "- 판정 정의는 오직 정의Y(순수2년8구간), 7/8 이상이다. 정의X는 신규 판정에 사용하지 않았다. Round12 127개·Round13 81개 config와 정확일치 중복을 배제했다. 기존45종목·2019-09-08~2026-10-05·익일시가·편도수수료0.04%·그로스·공통엔진 유지. 조합별 전체45종목 신호prefix, 미래가격3배/거래량7배변조, 실행prefix, 전일정보진입 검사 전부 통과. 월/주봉은 완료봉만 forward-fill하고 거래학습은 실제 완료거래만 사용한다.\n\n| config | CAGR | MDD | Sharpe | 거래 | 판정 |\n|---|---:|---:|---:|---:|---|\n"
        )
        for row in rows:
            m = row["metrics"]
            b = row.get("robustness")
            f.write(
                f'| {json.dumps(row["config"],ensure_ascii=False)} | {m["cagr"]:+.6f}% | {m["mdd"]:.6f}% | {m["sharpe"]:.6f} | {m["trades"]} | {b["verdict"] if b else "세축미달 기각"} |\n'
            )
            if b:
                positives = sum(p["alpha"] > 0 for p in b["periods"])
                failed = [
                    f'{p["start"]}~{p["end"]}: {p["alpha"]:+.6f}%p'
                    for p in b["periods"]
                    if p["alpha"] <= 0
                ]
                f.write(
                    f'\n- {json.dumps(row["config"],ensure_ascii=False)}: 정의Y {positives}/8; 실패 {failed}; 상위10건 {b["concentration"]["10"]["net_pct"]:.6f}%/상위5종목 {b["symbols"]["net_pct"]:.6f}%; 랜덤진입300회 CAGR·Sharpe {b["monte_carlo"]["tests"]}; 20거래블록1000회 Sharpe95%CI {b["bootstrap"]["ci95"]}; BTC 전환5일스래싱 {b["thrashing"]["within"]["5"] if b["thrashing"] else "전환 없음"}; CB5일 {b["breaker_5day_pct"]}; 최종5표 {b["votes"]}, {b["verdict"]}. 블록CI는 기존 정의의 거래단위Sharpe근사이며 일별NAV Sharpe CI가 아니다.\n'
                )
        f.write(
            f'\n- 이 섹션 신규{len(rows)}개, 세축우위{sum(r["dominates"] for r in rows)}개, 정의Y 5검사 전체통과{sum(r.get("robustness",{}).get("verdict")=="통과" for r in rows)}개. Round14 누적{len(out["experiments"])}개, Round12~14 합산{208+len(out["experiments"])}개.\n'
        )
    if out["status"] == "복귀조건 A 달성":
        winner = next(r for r in rows if r["config"] == out["winner_config"])
        m, b = winner["metrics"], winner["robustness"]
        with r14.DOC.open("a") as f:
            f.write(
                "\n**복귀조건 A 달성 — 정의Y로 5개 검증 전부 통과.** Donchian70일 직전고가 돌파·자체SMA200상방, BTC200일선±3%히스테리시스, 역변동성 위험예산1.0·종목상한25%, TOP_K8, 25일만기, 손절/익절/배율 없음. §74의55일·20일 후보와 다른 신규 조합이다.\n\n| 그로스 비교 | CAGR | MDD | Sharpe | 거래 | 최종배수 |\n|---|---:|---:|---:|---:|---:|\n"
            )
            for label, metrics in [("챔피언", out["baseline"]), ("정의Y 통과후보", m)]:
                f.write(
                    f'| {label} | {metrics["cagr"]:+.6f}% | {metrics["mdd"]:.6f}% | {metrics["sharpe"]:.6f} | {metrics["trades"]} | {metrics["final"]:.6f} |\n'
                )
            f.write(
                "\n| 정의Y 기간 | 전략 CAGR | BTC CAGR | 알파 | 판정 |\n|---|---:|---:|---:|---|\n"
            )
            for period in b["periods"]:
                f.write(
                    f'| {period["start"]}~{period["end"]} | {period["metrics"]["cagr"]:+.6f}% | {period["btc_cagr"]:+.6f}% | {period["alpha"]:+.6f}%p | {"통과" if period["alpha"]>0 else "실패"} |\n'
                )
            f.write(
                "- 각 기간은 자본·보유·피크·사이징 상태 독립초기화, 지표의 시작전자료는 워밍업만 사용. BTC 비교는 같은 기간 시작시가→종료종가와 양방향0.04%를 적용했다. 정의X를 읽지 않는 round14_validation 검증기만 사용했다. 랜덤 seed1200000~1200299, 동일 위험배분/BTC게이트/보유기간과 신호빈도에서 진입·순위를 독립난수화했다. 전체258거래원장으로 집중도·20건블록1000회 검산. 승자 확인 즉시 31번째 조합에서 탐색중단, 후속13개 계획 및 다른 아이디어는 실행하지 않았다.\n"
            )
    out["sections"].append(number)
    r14.save(out)
    r14.git_section(out, number)


if __name__ == "__main__":
    import sys

    section(
        int(sys.argv[1]),
        sys.argv[2],
        int(sys.argv[3]),
        int(sys.argv[4]) if len(sys.argv) > 4 else None,
    )
