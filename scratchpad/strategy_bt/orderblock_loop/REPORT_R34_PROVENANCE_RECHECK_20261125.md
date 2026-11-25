# R34 결과와 실행 출처 재확인 — 2026-11-25

## 결론

R34 완료행의 결과값과 실행 지문은 `TRAIN_TRIALS.csv` 및 결과 보고서 사이에서 일치한다. 다만 실행 코드·세부 사전등록 SHA와 현재 워크트리 파일 SHA가 달라 현재 파일로 실행 내용을 재현할 수 없다. R34 성과는 장부에 기록된 TRAIN 실패로 보존하고, 현재 소스로 재현된 결과라고 부르지 않는다.

## writer 사전확인 및 범위

- 장부를 읽기 전에 `/Users/user/CODE/trading_data/cache/orderblock/runs/.cointrade_train_trials.lock` 및 `.ob_attrition_train_trials.lock`이 없음을 확인했다.
- `lsof -nP -- TRAIN_TRIALS.csv` 조회에서 writable FD는 없었다. 열린 항목은 `txt` 매핑뿐이었다. 시스템 프로세스 목록은 `ps`/`pgrep`에서 `sysmond service not found`로 조회되지 않았다.
- 확인 후 장부를 스트리밍해 헤더 제외 4,191행과 R33/R34 행을 대사했다. 원시 가격행과 큰 거래 ID 문자열은 결과로 출력하지 않았다.
- 테스트·백테스트·API 호출·다운로드·장부 쓰기·R12 실행은 하지 않았다.

## R34 완료행 대사

trial `R34-crypto-ba84a72cadb845fea367bc1d650f5b56`는 R34 round에 정확히 1행 있고 상태는 `completed`다. 장부와 `REPORT_R34_OB_FUNDING_POLARITY.md`의 코드 SHA, grid SHA, prereg/master prereg SHA, split SHA, TRAIN 입력 지문 및 denominator 4,191이 일치한다.

| 항목 | 장부 확인값 |
|---|---:|
| cutoff-safe 종목 | 32 |
| scoreable 거래 | 2,965 |
| 목표 선도달 | 1,846/2,965 = 62.2597% |
| Wilson 95% 하한 | 60.5001% |
| 거래당 비용 후 기대값 | −18.5127bp |
| PF | 0.84169 |
| 연환산 Sharpe | −1.34939 |
| 누적순수익 | −17.1532% |
| 최대낙폭 | 18.3629% |
| funding 후보 / 통과 | 8,490 / 2,966 |
| 방향 불일치 / 중립 / 표시가 무효 | 5,269 / 204 / 51 |

보고서에 기록된 62.26%, −18.51bp, PF 0.842, Sharpe −1.349, −17.15% 누적손익, 18.36% MDD 및 funding funnel과 일치한다. 사전 TRAIN 선별선 M2≥75%, EV≥+15bp, PF≥1.30에 모두 미달한다. 이 실험은 자격 표본 수만 충족했고 후보가 아니다.

## 현재 파일과 실행 소스 지문 차이

| 파일 | 실행 시 장부/보고서 SHA | 현재 파일 SHA | 상태 |
|---|---|---|---|
| `search_crypto_r34_ob_funding_polarity.py` | `119cc683f8c8791771945bff21914302903bdbad51f71bee820e19fa84869188` | `34eea6da7d644ad352839d8db2487b9d97599cd3e994885a85daed6d7e4a23a7` | 불일치 |
| `PREREG_R34_OB_FUNDING_POLARITY.md` | `feb23f6c869e1e296a3278a98bf62ca1a9a80c0feaea8899ce12b4b013acb173` | `1ee3b69592d40a23ca676f187555b87f6ae07e666f35fe4ae8d175ab3d465bc7` | 불일치 |
| `PREREG.md` | `474456db9c221ebfee3222c27abfc62ecd14d0a1b40992d0970c451a518e9d00` | `474456db9c221ebfee3222c27abfc62ecd14d0a1b40992d0970c451a518e9d00` | 일치 |

R34 코드·세부 사전등록·결과 보고서는 현재 Git 추적 파일이 아니며 이 작업공간에서 run snapshot 파일명을 찾지 못했다. 그러므로 장부가 기록한 실행 지문과 성과는 확인됐지만, 실행 당시 원본 소스가 보존돼 현재 코드로 독립 재현 가능한 상태인지는 입증되지 않았다.

## 연구 판단

- funding 부호 필터는 표본을 2,965건까지 남겼으나 비용 후 기대값과 PF가 음수/1 미만이고 M2도 선별선보다 12.74%p 낮다. 부호·신선도·추가 threshold를 다시 튜닝하지 않는다.
- R33 지연 sweep은 M2 62.50%, EV +0.73bp, PF 1.007로 별도 TRAIN 실패행이다. R34는 R14에 종속된 하위집단이므로 두 실험을 독립 검증 두 건처럼 세지 않는다.
- OOS, 비용 2배, 1봉 지연, 귀무검정, Reality Check/SPA, Deflated Sharpe, 포워드 검증 및 데이터 권리·2018/PIT 게이트는 두 결과로도 입증되지 않았다. 후보는 코인 0/2, 한국 0/2, 미국 0/2다.
