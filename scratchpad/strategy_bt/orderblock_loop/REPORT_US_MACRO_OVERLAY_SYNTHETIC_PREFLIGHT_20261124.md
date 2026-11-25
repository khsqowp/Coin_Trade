# US SPY 매크로 오버레이 합성 사전검사 — 2026-11-24

## 판정

`search_us_macro_overlay_v1.py`의 지정 합성 테스트 26개가 모두 통과했다. 이는 사전등록된 고정 ETF challenger의 입력 검증 코드가 합성 fixture를 통과했다는 뜻이다. **실제 SPY·VIX·COT 자료 적격성, 수익성, G 통과를 입증하지 않는다.** 실제 시계열 백테스트와 후보 판정은 0회다.

## 범위

- 실행 위치: `/Users/user/CODE/Coin_Trade/scratchpad/strategy_bt/orderblock_loop`
- 명령: `PYTHONDONTWRITEBYTECODE=1 /Users/user/CODE/trading_data/cache/orderblock/venv/bin/python -m unittest discover -s tests -p 'test_search_us_macro_overlay_v1.py' -v`
- 결과: **26 tests, 0 failures, 0 errors**.
- 테스트 파일: `tests/test_search_us_macro_overlay_v1.py`; 구현 파일: `search_us_macro_overlay_v1.py`.
- 테스트는 임시 디렉터리의 합성 입력과 가짜 장부를 사용했다. 실제 시세·CFTC 공개 데이터·공유 `TRAIN_TRIALS.csv`를 읽거나 고치지 않았고, 외부 API·네트워크 호출도 하지 않았다.

## 통과한 경계

- 12개 사전등록 ID와 등록 해시·설정 확인, 일부 ID 누락 시 고정 격자 차단.
- SPY의 다음 거래일 시가 체결, 분배금 현금 처리, 주식분할 비율, 기준선과 비용 창의 일치.
- CFTC 발표시각이 신호 기준시각보다 늦으면 당일 신호에 포함하지 않는 점, 조기 폐장 뒤 발표 차단, 시간대 미지정·컷오프 초과 자료 거부.
- VIX 선물 계약별 만기·정산 자료의 만기 전 검증 및 기준 폐장시각 이후 공개 자료 차단.
- 60/40 시간 분할에서 train prefix만 사용하는 점.
- 합성 cutoff manifest·정규화 입력 해시 검증, 스냅샷 변조·사후 행 추가·후기 slice 대체 차단.
- 합성 결과 저장 경로가 임시 데이터 루트 안에 머무르고 기존 산출물을 덮어쓰지 않는 점.

## 남은 선행 게이트

1. SPY, CBOE VIX 선물, CFTC COT, NYSE 정규·조기 폐장 달력 각각의 원천·개인 연구 권리·보존 권리·현지 파일 provenance가 아직 고정되지 않았다.
2. `EXPECTED_SOURCE_MANIFEST_SHA256`는 빈 문자열이며, 적격 cutoff-only manifest가 없다. 따라서 실제 입력으로 실행하면 안 된다.
3. VIX의 계약별 역사적 만기·정산 공개 시각, CFTC의 과거별 정확한 공개시각, NYSE 달력 검증은 아직 데이터 단위로 통과하지 않았다.
4. 사전등록 문서는 단일 SPY를 탐색용 challenger로 규정한다. 단일 ETF는 고정 G의 미사용 종목군 기준을 충족할 수 없으므로 미국 주식 최종 후보 2개 중 하나로 셀 수 없다.
5. 실제 데이터 TRAIN, OOS, 비용 2배, 1일 지연, 2018·2022 비교, 무작위·순환이동 귀무, SPA/Reality Check, 독립 재구현 및 포워드 결과는 수행하지 않았다.

## 다음 허용 단계

사용권이 확인된 cutoff-only 원본과 날짜별 공개시각·기업행위·거래일 달력이 확보된 뒤 별도 승인 절차를 거쳐서만 사전등록된 12개 TRAIN challenger를 실행할 수 있다. 본 보고서에서 실험 수나 통과 후보 수를 늘리지 않는다.
