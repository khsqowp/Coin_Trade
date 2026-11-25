# R22 — sweep 뒤 BOS 경계 수용 필터 결과

## 판정

**반려.** 다음 완료 4h봉의 OB 경계 수용을 요구했지만 R21 기준선보다 M2와 순손익 품질이 좋아지지 않았다. 코인 G 통과 전략은 계속 0개다.

## 고정 실행 및 장부 대사

- 사전등록: `PREREG_R22_BOS_ACCEPTANCE.md`
- 코드: `search_crypto_r22_bos_acceptance.py`
- 합성 테스트: `tests/test_search_crypto_r22_bos_acceptance.py`
- trial ID: `R22-crypto-680074230a3c438a8cb1e6c90dfc4468`
- code SHA-256: `575dad0db452466149be2db09ae5319157ee8294717a28f1f54488c7181f6ac4`
- grid SHA-256: `ce522ac28b44c42a923c928325d6a3216102225c6fa1a12d241811f39050d574`
- TRAIN fingerprint: `b69101d9a136043f8d34eb077a203fc6ec97826a9225d5036c99843e8d00592e`
- R22 prereg SHA-256: `ee393c94166657b5a6bcdc607011b8654b6b3ce343f78a557724bf7d489f7f7b`
- master prereg SHA-256: `9153e6d7b6c7fe3b34b367d0c63bfbbd1ad2b1d5462ebc336a172bf6f283e113`
- 실행 전 장부 1,678행, 완료 후 1,679행으로 한 건이 append됐다. 실행 stdout와 해당 ledger metric의 결과 및 코드·grid·prereg 지문을 대조해 일치함을 확인했다.
- 첫 실행 시도는 ledger preflight의 헤더 오프바이원 버그로 1,678행을 1,677행으로 오인해 cutoff 데이터 접근 전에 중단됐다. 가격 데이터와 실행 결과는 읽지 않았고 행도 추가하지 않았다. `_ledger_rows()`를 DictReader의 단일 헤더/본문 순회로 고쳐 1행 합성 회귀 테스트를 추가했다. 같은 사전등록·분모를 유지한 뒤 6개 합성 테스트를 통과하고 한 차례 데이터 실행했다.
- R21 레드팀 지적 중 monkeypatch 연결 주장은 별도 실제 zone-mapping 합성 테스트로 반증됐다. Python 모듈 전역 `r14.r4_zones` 참조를 R21 wrapper가 교체하면 R14 mapper가 그 필터를 호출한다. 실행 당시 R21 원본 단위 테스트 파일을 복원했을 때 R21 code SHA가 장부 기록과 재일치함도 확인했다. 이 검증은 R21 성과를 재실행하지 않았다.

## 수치

| 항목 | R21 기준선 | R22 결과 |
|---|---:|---:|
| 원시 BOS 구역 | 56,447 | 56,447 |
| BOS 전 sweep 통과 | 878 | 878 |
| 다음봉 경계 수용 | 해당 없음 | 782; 거부 96, 확인 불가 0 |
| 첫 1h 접촉 / 체결 | 203 / 196 | 158 / 153 |
| 전체·비중복 M2 | 124/196 = 63.27% | 96/153 = **62.75%** |
| M2 Wilson 95% 하한 | 56.32% | 54.86% |
| 승률 | 69.39% | 67.97% |
| 비용 후 EV | +50.55bp | **+7.59bp** |
| Profit factor | 1.548 | **1.069** |
| 연환산 Sharpe | 0.875 | 0.134 |
| 누적 순수익 | +3.10% | +0.36% |
| MDD | 0.71% | 1.48% |

R21 기준선 수치는 기존 R21 결과행에서만 인용했다. R22는 원 결과를 비교할 때 승격·합격 조건인 M2≥80%, N≥200, EV≥15bp, PF≥1.30에 모두 미달했다.

## 실패 원인

acceptance 조건 자체는 878개 sweep zone 가운데 782개(89.1%)를 통과시켜 대부분을 제거하지 않았다. 그러나 확인봉이 완성될 때까지 activation을 지연하자 첫 접촉·체결이 196건에서 153건으로 43건(21.9%) 줄었다. 남은 집합은 M2가 0.52%p 낮았고 비용 후 기대값은 42.96bp 하락했다. 관측상 다음봉 종가 수용은 첫 재방문 반응을 개선하지 않았으며, 지연으로 기존 진입 기회를 놓친 것이 표본·EV 저하와 일치한다. 이는 단일 TRAIN 구간의 기술적 귀속이지 인과효과 증명은 아니다.

## 검증 경계와 다음 단계

- 합성 테스트: `python -m unittest discover -s scratchpad/strategy_bt/orderblock_loop/tests -p 'test_search_crypto_r22_bos_acceptance.py' -v` — 사전등록 후 **6/6 통과**. strict boundary, 다음봉 부재, future mutation, activation 지연, 행수 회귀를 확인했다.
- R22는 TRAIN 선별이며 OOS, 비용 2배, 1봉 지연, 귀무검정·plateau, 약세장/미사용 심볼, 다중검정 보정된 p값은 수행하지 않았다. 이 항목은 확인 안 됨이다.
- 사후 선택으로 R22 구조를 더 조정하지 않는다. 다음 전략은 R21의 비용 후 양수 성과를 설명하는 진입 구조를 새로 제시하거나, R21 단일 결과의 방향·시간대 귀속을 별도 사전등록 진단으로 분리한다. 어떤 선택도 고정 G·데이터 출처·PIT·이용권 문턱을 낮추지 않는다.
