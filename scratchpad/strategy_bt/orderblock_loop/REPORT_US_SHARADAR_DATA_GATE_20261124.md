# 미국 주식 Sharadar / Nasdaq Data Link 데이터 게이트 — 2026-11-24

## 결론

Nasdaq Data Link의 Sharadar Equity Prices(SEP)는 현재 살핀 미국 주식 자료 중 PIT·상장폐지 가격 요건을 가장 많이 충족할 가능성이 있는 유료 후보 경로다. 공식 자료는 1998년부터 20,000개 이상 활성·상장폐지 미국 종목의 일봉 OHLCV, corporate actions와 ticker metadata를 설명한다. 그러나 Premium 구독·API key가 필요하고 이용료는 로그인 뒤에 있어 현재 작업에서 취득하거나 사용할 수 없다. 실제 시점별 종목군과 상폐/합병 정산 완전성도 아직 입증되지 않아 G 통과 자료가 아니다.

## 공식 제품 설명

- Nasdaq Data Link의 SEP 문서는 Daily, Premium 제품으로 표시하고, 1998년 1월 이후 20,000개가 넘는 미국 공기업의 조정·비조정 EOD 가격을 설명한다. 이 제품 설명에는 OHLCV, 분할·배당 조정 가격, 분할·배당·분사·인수·상폐 사유·티커 변경 등 corporate action 데이터가 적혀 있다.
- Sharadar의 Stock Prices 문서는 활성·상폐 종목의 EOD OHLCV와 세 가지 조정 형태(비조정, 분할 조정, 분할·현금배당·분사 조정)를 설명하고, 현재 약 21,000개 티커와 1997년 12월부터의 이력을 표시한다.
- Sharadar의 Corporate Actions 문서는 활성·상폐 종목에 대해 티커 변경, 분할, 현금배당, 분사, ADR 비율 변경, 상장일·상폐일, 상폐 사유, 인수 상대방 및 관련 증권을 설명한다.
- Sharadar API 사용에는 API key가 필요하다. Nasdaq 제품 가격은 계정 로그인 뒤 공개된다고 안내한다. 제품 목록과 공개 페이지만으로 연구용 보관 기간·개인 이용권·데이터 취소 후 보존 조건은 확인되지 않았다.
- Nasdaq Daily List는 1998년 12월 이후 Nasdaq 상장 증권의 추가·삭제·명칭/심볼변경 및 일부 배당·기업행위를 제공하는 별도 Premium 자료다. 이는 Nasdaq 상장 자료이므로 미국 전체 거래소 유니버스의 단독 근거로 볼 수 없다.

## 고정 G 적합성

| 기준 | 현재 확인 | 판정 |
|---|---|---|
| 2018·2022 가격 범위 | 제품 설명상 가격 이력은 1997/1998년 시작 | 날짜 범위는 충족 가능성 높음; 샘플 행 미확인 |
| 활성·상폐 종목 가격 | 20,000+ active/delisted 및 OHLCV 설명 | 제품 주장만 확인; 실제 coverage 미검증 |
| Corporate actions | 배당·분할·분사·인수·상폐 관련 필드 설명 | terminal proceeds·현금/주식 대가의 완전성 미검증 |
| 시점별 PIT universe | ticker metadata와 역사적 구성 자료 언급이 있으나 실제 effective-date membership 전체 범위 확인 안 됨 | 미입증 |
| 연구 사용권·가격 | Premium, API key, 가격은 계정 로그인 뒤 표시 | 현재 미승인·미확인 |
| G 최종 판정 | 실제 자료·정확한 유니버스·권리·청산금액 샘플 불변성 점검 없음 | 불충족/미입증 |

## 취득 전 필요한 증거

1. Nasdaq/Sharadar 이용약관 또는 계약서에서 개인 내부 전략연구, 로컬 보관, 파생 백테스트, 결과물 보존·공유 가능 범위와 구독 종료 뒤 보유 조건을 확인한다.
2. 가격, actions, tickers 및 필요한 historical S&P500 membership 제품을 함께 쓸 때의 총비용·갱신조건을 확인한다. 가격은 공개 페이지에서 확인되지 않았다.
3. 구매 전에 제공되는 허용 샘플/스키마로 2018·2022 시점별 membership의 effective date, 상폐·합병 대가, 식별자 연결, 분사·배당 반영을 독립 대사한다.
4. 적격이면 cutoff-only 데이터 스냅샷·manifest를 먼저 고정하고, 사전등록과 공용 시도 장부 절차가 승인되기 전에는 백테스트하지 않는다.

## 조사 경계

Nasdaq Data Link와 Sharadar 공개 제품 문서, 공식 Nasdaq Daily List 문서만 검토했다. 로그인, API key, 샘플 열람, 견적 요청, 계정 생성, 다운로드, API 요청, 가격행 접근, 전략 실험, 사전등록·장부 변경은 하지 않았다. 원제품 설명은 실제 계약·커버리지·데이터 품질의 증거를 대신하지 않는다.

## 공식 출처

- [Nasdaq Data Link — Sharadar Equity Prices (SEP)](https://data.nasdaq.com/databases/SEP/documentation?anchor=sample-data)
- [Sharadar — Stock Prices](https://sharadar.com/docs/stocks)
- [Sharadar — Corporate Actions](https://sharadar.com/docs/actions)
- [Sharadar — API authentication](https://sharadar.com/docs/auth)
- [Nasdaq Data Link — Nasdaq Daily List](https://data.nasdaq.com/databases/NDL/documentation?anchor=product-overview)
