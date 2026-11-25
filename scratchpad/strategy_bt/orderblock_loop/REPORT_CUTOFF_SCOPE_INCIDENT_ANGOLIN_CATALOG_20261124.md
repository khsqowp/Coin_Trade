# Cutoff 범위 사고 기록 — Angolin Binance 카탈로그

기록일: 2026-11-24 KST
상태: 잠재 cutoff 범위 위반. 해당 조회 결과는 전략·유니버스·합격 판단에 사용하지 않음.

## 발생 내용

코인 데이터 경로를 조사하던 중 Angolin 문서에서 Binance 거래쌍 카탈로그가 무인증 공개이며 각 거래쌍의 첫·마지막 캔들 시각을 제공한다고 읽었다. 이후 `GET https://api.angolin.com/v1/exchange_pairs?exchange=binance&interval=1h`를 한 차례 호출하고 JSON 메타데이터를 메모리에서 집계했다.

요청에는 `end`나 사전등록 cutoff 필터가 없었다. 응답의 `last_close_ts`는 현재 카탈로그의 마지막 기록 시각이므로 2026-06-01 이후 정보를 포함할 수 있다. 집계 코드는 응답 전체에서 이 필드를 읽었으며, 호출 이후에야 이 시간 범위 위험을 인식했다. 그러므로 해당 집계는 이 저장소의 “2026-06-01 이후 데이터 금지” 경계에 부합한다고 입증할 수 없다.

사고 범위를 투명하게 남기되 cutoff 이후 시각이나 결과 숫자는 보고서에 복사하지 않는다. 응답 본문은 파일로 저장하지 않았으며, 가격·거래량·캔들 행은 읽거나 내려받지 않았다. 계정·API 키·유료 구독을 사용하지 않았고, 장부·전략 러너·시장 데이터 파일도 수정하지 않았다.

## 격리 조치

- 해당 응답의 모든 집계 수치를 무효 처리한다. 코호트 구성, 데이터 적격성, 시도 분모, 전략 선택, G 판정에 재사용하지 않는다.
- live catalog endpoint를 재호출하거나 해당 응답을 저장·복구하지 않는다.
- 공유 장부와 동결 후보 파일은 이 조사에서 변경하지 않았다.
- 이후 데이터 조사는 2026-05-31 이하로 명시적으로 한정된 로컬 메타데이터/스냅샷 또는 과거 시점에 고정된 공식 문서만 사용한다. live current metadata가 cutoff를 보장하지 않으면 조회하지 않는다.

## 관련 문서

- Angolin 카탈로그 문서는 첫·마지막 봉 시각을 실제 데이터 범위 설명으로 정의하고, 카탈로그 endpoint는 무인증 공개라고 설명한다: https://angolin.com/docs/endpoints/catalog
- Angolin 인증 문서는 가격/역사 universe endpoint가 API key와 구독 범위에 종속됨을 설명한다: https://angolin.com/docs/authentication
- Binance Public Data 저장소 Issue #479는 역사 시점의 완전한 Spot symbol manifest 및 archive 경계에 대한 질문을 제기하지만, 현재 공개 페이지에는 완전한 공식 답변이 없다: https://github.com/binance/binance-public-data/issues/479

## 검증

이 기록은 사건 경계와 격리 조치를 보존한다. 네트워크를 다시 호출하지 않았고, 가격 행·원자료·cutoff 이후 숫자는 재검증하지 않았다. 이 파일만 `git diff --no-index --check /dev/null`로 형식 점검한다.
