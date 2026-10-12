"""Preserve interruption, explicit-period correction, accepted candidate and proofs."""

import hashlib
import json
import platform
import subprocess
import sys
from pathlib import Path
from app import crypto_round13_research as r13


def finish_section(out, number):
    out["sections"].append(number)
    r13.save(out)
    r13.git_section(out, number)


def run():
    out = json.loads(r13.PATH.read_text())
    assert out["status"] == "복귀조건 A 달성"
    winner = next(r for r in out["experiments"] if r["config"] == out["winner_config"])
    assert all(winner["robustness"]["votes"]) and len(winner["costs"]) == 2
    if 73 not in out["sections"]:
        rows = [r for r in out["experiments"] if "online_sizing" in r["config"]]
        with r13.DOC.open("a") as f:
            f.write(
                "\n\n## 73. 운용북 완료거래 온라인 사이징과 탐색중단 기록 (2026-10-07, 라운드13)\n\n"
            )
            f.write(
                "- §69의 기준북 학습과 달리 운용북 자체가 실제 청산한 거래만 학습했다. 공통엔진의 entry_scale.get 호출에서 전일까지 사라진 고정만기 포지션을 확인하고 진입시가·직전완료종가로 양방향 수수료후 단위수익률을 계산한다. 손절/익절/전략교체는 지원하지 않으며 해당 정책은 사용하지 않았다. 펀딩은 학습통계에서 제외하고 비용판 NAV에는 반영한다. 매 기간분리·랜덤대조군·재현 실행마다 학습상태도 초기화한다. Beta(10,10) 승률, 평균이익/손실 각각 가상10건×2%, 마지막40/80건, 승률·페이오프 배율공식은 §69 정의를 적용했다. 공통엔진 소스 변경 없음.\n"
            )
            f.write(
                "- 실제 원장 완료거래수·배율 산술, 반복 실행 초기화, 보유기간1/3/20일·결측종가 청산지연, 비용0 전체trace 일치, 실행prefix를 검증했다. 완료한5조합만 아래에 집계한다. 여섯번째 OBV/온라인페이오프80건은 MC 도중 기존 완료 후보의 지정경계 통과를 확인해 중단했고 완료조합수에 넣지 않았다. 계획했던 추가 위험예산/보유기간 조합은 실행하지 않았다.\n\n| config | CAGR | MDD | Sharpe | 거래 | 판정 |\n|---|---:|---:|---:|---:|---|\n"
            )
            for row in rows:
                m = row["metrics"]
                f.write(
                    f'| {json.dumps(row["config"],ensure_ascii=False)} | {m["cagr"]:+.6f}% | {m["mdd"]:.6f}% | {m["sharpe"]:.6f} | {m["trades"]} | {row.get("robustness",{}).get("verdict","세축미달 기각")} |\n'
                )
                if row["dominates"]:
                    b = row["robustness"]
                    f.write(
                        f'\n- 온라인OBV 승률40건: 지정기간 {sum(p["alpha"]>0 for p in b["legacy_periods"])}/8; 집중도 {b["concentration"]["10"]["net_pct"]:.6f}%/{b["symbols"]["net_pct"]:.6f}%; 랜덤300회 {b["monte_carlo"]["tests"]}; 20건블록1000회CI {b["bootstrap"]["ci95"]}; 전환 없음; 5검사 {b["votes"]}, 기각.\n'
                    )
        finish_section(out, 73)
    if 74 not in out["sections"]:
        b = winner["robustness"]
        m = winner["metrics"]
        base = out["baseline"]
        with r13.DOC.open("a") as f:
            f.write(
                "\n\n## 74. 지정기간 경계 재검산과 복귀조건 A 달성 (2026-10-07, 라운드13)\n\n"
            )
            f.write(
                "**복귀조건 A 달성.** Donchian55일 돌파·자체SMA200상방 + BTC200일선 ±3% 히스테리시스 + 역변동성 위험예산1.0·종목비중상한25%가 사용자 지정5검사를 모두 통과했다. TOP_K8·20일만기·익일시가·배율없음·손절/익절없음·편도수수료0.04%·기존45종목·2019-09-08~2026-10-05.\n\n"
            )
            f.write(
                "- **판정정정의 근거:** 이번 사용자 지시는 “알파기준 기간분리 8구간(Round4/6 경계) 중 7/8 이상”이다. Round4 JSON과 Round6 JSON 경계는 정확히 일치한다. 재사용한 Round12 함수는 그8구간에 더해 Round9의 별도8구간에서도7/8을 요구했다. 이 요청외 추가필수조건 때문에 §67에서 기각으로 기록됐다. §64~72의 당시 기록은 보존한다. 현재 JSON에는 당시 votes/verdict를 round12_extra_gate에 보존하고, 지정된 Round4/6의7/8을 적용한 현재5판정을 별도로 기록했다. 7/8·103%/88%·p<0.05·CI하한>0·스래싱≤50% 임계값은 변경하지 않았다. Round9 별도기간은 참고검증으로 남기며6/8이어서 민감성이 존재한다.\n"
            )
            f.write(
                "- §67 후보는 당시 필수라고 추가한 Round9 기간을 제외한4검사와 지정기간7/8을 이미 통과했다. 최종 기준대조에서 이 불일치를 발견한 직후 탐색프로세스를 중단했다. 따라서 이번81개 완료조합, Round12와 합산208개이며 이후 새 탐색은 없다. 완료후 검증·비용판은 새 조합 탐색수가 아니다.\n\n| 그로스 비교 | CAGR | MDD | Sharpe | 거래 | 최종배수 |\n|---|---:|---:|---:|---:|---:|\n"
            )
            for label, v in [("챔피언", base), ("통과후보", m)]:
                f.write(
                    f'| {label} | {v["cagr"]:+.6f}% | {v["mdd"]:.6f}% | {v["sharpe"]:.6f} | {v["trades"]} | {v["final"]:.6f} |\n'
                )
            f.write(
                "\n| 지정 Round4/6 구간 | 전략 CAGR | BTC B&H CAGR | 알파 차이 | 판정 |\n|---|---:|---:|---:|---|\n"
            )
            for p in b["legacy_periods"]:
                f.write(
                    f'| {p["start"]}~{p["end"]} | {p["metrics"]["cagr"]:+.6f}% | {p["btc_cagr"]:+.6f}% | {p["alpha"]:+.6f}%p | {"통과" if p["alpha"]>0 else "실패"} |\n'
                )
            f.write(
                f'\n- ① 지정기간 알파양수7/8: 통과. 시작자본·보유·피크 독립초기화, 시작전자료는 지표워밍업만 사용. BTC는 해당구간 시작시가→종료종가·양방향0.04%를 독립계산했다.\n- ② 집중도: 상위10거래 {b["concentration"]["10"]["net_pct"]:.6f}%≤103%, 상위5종목 {b["symbols"]["net_pct"]:.6f}%≤88%: 통과. 손익원장289건으로 재계산했고 최종NAV−1과 원장합 일치. 상위5종목 {b["symbols"]["top5"]}.\n- ③ 랜덤진입300회: CAGR p={b["monte_carlo"]["tests"]["cagr"]["p"]:.9f}, Sharpe p={b["monte_carlo"]["tests"]["sharpe"]["p"]:.9f}: 둘다<0.05, 통과. seed1200000~1200299, 동일 위험배분/BTC게이트/보유기간, SIGNAL과순위는 독립난수, 확률=실제완료거래/유효종목일.\n- ④ 20거래블록1000회 Sharpe95%CI [{b["bootstrap"]["ci95"][0]:.6f}, {b["bootstrap"]["ci95"][1]:.6f}]: 하한>0, 통과. 원장정렬·수익률·연환산은§19 정의다. 포트폴리오 일별NAV Sharpe CI가 아닌 거래단위근사임을 유지한다.\n- ⑤ BTC게이트 5일스래싱 {b["thrashing"]["within"]["5"]["count"]}건, {b["thrashing"]["within"]["5"]["pct"]:.6f}%≤50%: 통과. 서킷브레이커는 사용하지 않았다.\n'
            )
            f.write(
                "\n| §29 비용참고판: 펀딩 연10.95% | 편도 슬리피지 | CAGR | MDD | Sharpe | 거래 |\n|---|---:|---:|---:|---:|---:|\n"
            )
            for c in winner["costs"]:
                v = c["metrics"]
                f.write(
                    f'| 동일정책 | {c["slippage"]*100:.2f}% | {v["cagr"]:+.6f}% | {v["mdd"]:.6f}% | {v["sharpe"]:.6f} | {v["trades"]} |\n'
                )
            f.write(
                "- 비용어댑터는 공통엔진과 분리했다. 슬리피지 진입시가상향·청산가격하향, 일별펀딩은 전일마크·진입일시가에2/3일을 적용(§29 규칙), 현금에서 지급하며 이후 NAV/위험예산/수량을 다시 계산한다. 펀딩·슬리피지0에서 후보의 지표만 아니라 전체trace·배분까지 공통엔진과 정확히 일치했다. 판정기준은 요청대로 그로스이며 비용판은 참고용이다.\n"
            )
            f.write(
                "- Round9 참고기간 실패는2022-09-08~2024-09-07과2023-10-06~2025-10-05다. 지정기간의유일실패는2022-09-08~2024-09-07다. 선택한기간에대한민감성, 반복선택편향, 생존편향, 미관측OOS 부재는 해소된것으로 주장하지 않는다. 요청5검사의통과와 실거래 검증은 구분한다.\n"
            )
        finish_section(out, 74)
    if 75 not in out["sections"]:
        replay = (r13.ROOT / "docs/round13-replay-2026-10-07.txt").read_text()
        assert (
            "REPLAY 81/81" in replay and "PASS Round13 81 unique experiments" in replay
        )
        logs = sorted((r13.ROOT / "docs").glob("round13-*-regression-2026-10-07.txt"))
        assert len(logs) == 12
        for p in logs:
            text = p.read_text()
            assert "PASS" in text and "Traceback" not in text
        sources = sorted((r13.ROOT / "app").glob("*round13*.py"))
        out["source_hashes"] = {
            str(p.relative_to(r13.ROOT)): hashlib.sha256(p.read_bytes()).hexdigest()
            for p in sources
        }
        out["runtime"] = dict(
            python=sys.version, executable=sys.executable, platform=platform.platform()
        )
        out["next"] = []
        original_doc = subprocess.check_output(
            ["git", "show", "HEAD:docs/전략-백테스트-종합.md"], cwd=r13.ROOT
        )
        assert r13.DOC.read_bytes().startswith(original_doc)
        for name in [
            "app/technical_portfolio_engine.py",
            "app/round11_portfolio.py",
            "app/round12_signals.py",
            "app/crypto_round12_research.py",
            "app/verify_round12.py",
            "docs/round12-results-2026-10-07.json",
        ]:
            assert (r13.ROOT / name).read_bytes() == subprocess.check_output(
                ["git", "show", f"HEAD:{name}"], cwd=r13.ROOT
            )
        with r13.DOC.open("a") as f:
            f.write("\n\n## 75. 라운드13 최종 검산과 현재 결론 (2026-10-07)\n\n")
            f.write(
                "- 완료조합81개·Round12와합산208개. 새일봉지표7종·완료월봉·완료주봉지표확인·히스테리시스·기준북/운용북완료거래축소추정·신호합집합을탐색했다. 미완료MC1조합과미실행계획은집계제외. 지정5검사를모두통과한후보1개로복귀조건A달성, 이후탐색중단. §38의 “미발견”은당시Round1~11의기록이며 현재조사범위에서는§74후보가새로확인됐다.\n"
            )
            f.write(
                "- 원캐시전체45종목을81조합모두실제재실행하여저장지표오차1e-10이내재현, 전체유니버스prefix·미래가격3배/거래량7배변조·실행prefix·전일정보진입검사재실행통과. 신규7신호군합성prefix, 저장원장집중도·랜덤p값·블록CI분위·5표·기존추가기간판정산술검산통과. 비용0 전체후보trace 정확일치 및2일펀딩독립산술통과. 온라인학습의실제완료원장산술·반복초기화·기간prefix 통과.\n"
            )
            f.write(
                "- Round1~12 회귀검증 재실행: verify_technical_ict, verify_hybrid_drawdown, verify_round3/4/5/6/7/8/10/11/12의11스크립트exit0. Round9는원연구함수의출력경로를임시파일로바꾸어전체기간·8구간·CB없는비교·스래싱·판정을독립재실행하고원JSON과일치확인했다. 원시Round12결과·신호·공통엔진·Round11엔진과기존문서prefix는HEAD와바이트동일.\n"
            )
            f.write(
                "- 신규/수정9모듈 python3 -m py_compile, black --check, pylint E/F, git diff --check 통과. 독립python-reviewer는월봉합집합적용순서·확장재현·승자보존/비용·온라인인과성·지정경계검사를검토했다. 리뷰발견결함은해당배치실행전수정했다. 연구중단KeyboardInterrupt는승자기준대조후탐색중단기록이며완료결과의검증실패가아니다.\n"
            )
            f.write(
                "- **현재결론: 지정Round4/6 8구간과나머지4검사를모두통과하는그로스후보를발견했다. Round9별도기간은6/8이므로경계민감성은남는다. 실거래승격이나미관측성능보장은하지않는다.** 비용판은§74에기록했고세션복귀조건A충족으로종료한다. Git권한제한과연구검증완료는분리하며각섹션의실제성공/실패로그를보존한다.\n"
            )
        finish_section(out, 75)


if __name__ == "__main__":
    run()
