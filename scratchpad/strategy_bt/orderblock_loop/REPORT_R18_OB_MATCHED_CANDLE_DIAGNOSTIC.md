# R18 — BOS 방향정보 짝대조 진단 결과

## 판정

**검증불가(unscorable).** 고정된 매칭 규칙으로 complete pair가 0건이어서 BOS 대조 효과, 방향 적중률 차이, 신뢰구간, p값을 계산하지 않았다. 이를 BOS 효과가 없다는 증거나 전략 탈락으로 해석하지 않는다. 매칭 실패 원인은 별도 사전등록 진단 R19에서 분해한다.

## 사전등록과 재현

- 질문: 같은 심볼·방향·4h 추세 상태와 유사한 직전 지표를 가진 일반 캔들에 비해 `bos_origin` 사건이 24개 4h봉 후 방향 정보를 추가하는가.
- R18은 전략 수익률/M2 시험이 아니며 TRAIN 진단이다. 12bp는 보조 방향수익에서만 차감하도록 등록했지만, matched pair가 없어 보조 수익도 계산하지 않았다.
- 실행 당시: 고정 35심볼 중 TRAIN 봉이 존재한 심볼 32개. R18은 이 32개를 분석했고, 장기 PIT·상장폐지·데이터 이용권 게이트를 해결하지 않는다.
- 원시 BOS 사건: 56,447. 적격 사건(분모): 56,447. 252봉 이전 이력 부족: 3,065. feature 또는 EMA 상태 부족: 20,590. 나머지 중 고정 조건 대조 캔들 없음: 32,792. 매칭: 0. complete pair: 0. 매칭률: 0.00%.
- 내부 결측으로 분리된 gap 봉: 210. 제외된 불완성 봉: 25.
- 사전등록 N=1,675; R18 실행 행 1개. TRAIN 장부 총 1,675행으로 대조했다.
- Trial ID: `R18-crypto-2ccf1c0ef8f0482e8872d69f401ea3c1`.
- Input fingerprint: `c9b2dc43cbc5c5895608b1c3c6b345c8decdea1d1b8c1dc21af5ca39f2423592`.
- Code SHA-256: `59b0069f310ea3a2fcb4787f6b2fc6d98d05ba747d8090b1df679090eb52e176`.
- Grid SHA-256: `1e013d7beabaaee693f64699d82a88d0dcbede202c37efc46964b0db5b60b416`.
- 상세 사전등록 SHA-256: `87df5d28218da2277c61d8013ed505394ba2a9f70f3138ebe0c67516df5148d4`.
- Master 사전등록 SHA-256: `85dc21c3885500b7bca4e146f874b73c2fc677af9b7d3aaaf3de3e542a86d618`.
- 감사 CSV(저장소 밖): `/Users/user/CODE/trading_data/cache/orderblock/runs/r18/matched_events_c9b2dc43cbc5.csv`, 9,484,906 bytes, 56,447 data rows. 행은 처리 사건·대조 index, 사용한 feature, 완료·검열·미매칭 사유만 담고 원본 가격열은 담지 않는다.

재현 명령:

```sh
env TRADING_DATA_DIR=/Users/user/CODE/trading_data \
  PYTHONPATH=scratchpad/strategy_bt/orderblock_loop \
  PYTHONPYCACHEPREFIX=/tmp/cointrade-pycache \
  /opt/anaconda3/bin/python3 \
  scratchpad/strategy_bt/orderblock_loop/search_crypto_r18_ob_matched_candle.py
```

동일 설정·코드·입력·사전등록은 이미 장부에 있으므로 중복 실행은 금지한다.

## 해석과 다음 단계

- 32,792개 사건에서 252봉 선행이력과 처리군 상태가 있었지만, 매칭 가능한 control이 없었다. 이 합계만으로 최근 BOS 과다, 방향/추세 불일치, feature caliper, 표본 overlap 중 무엇이 병목인지 확정할 수 없다.
- R19는 이 실패 사유의 순차 후보 funnel만 고정 TRAIN에서 분해한다. R19에서도 방향 결과·수익률·목표 도달률은 계산하지 않고 매칭 문턱도 바꾸지 않는다. 그 funnel은 전략 후보나 추가 성과 증거가 아니다.
- R18은 80% M2나 OOS 최소표본을 평가하지 못했다. 코인 합격 후보 수는 증가하지 않았다.

## 테스트와 경계

- R18 합성 테스트 23/23, 공통 체결 엔진 38/38, R14 10/10, R15 8/8 통과. Python compile 통과.
- 레드팀은 252봉 사전이력, 모든 원시 BOS의 분모, 심볼별 segment를 가로지르는 전체 처리군·대조군 창 중첩 제한, 검열/미매칭 CSV, 실패 행 append 경계를 확인했다. 이는 구현 검토이지 실데이터 엣지 증거가 아니다.
- R18은 cutoff-aware TRAIN iterator와 추가 cutoff 가드만 사용했다. TEST/OOS와 2026-06-01 이후 행은 읽지 않았다. 공개 네트워크·유료 API·실거래는 사용하지 않았다.
