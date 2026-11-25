# Bitfinex 현물 캔들 데이터 경로 게이트 — 2026-11-24

## 결론

Bitfinex 공개 문서는 무료 현물 캔들 접근 가능성을 보여주는 새 challenger 경로다. 그러나 2018·2022년의 30개 이상 동일 PIT 자산, 과거 상장·폐지 전체, 실제 캔들 보존범위와 API 데이터 사용권을 함께 증명하지 못한다. 기존 Binance USDⓈ-M 선물 코호트나 고정 G를 대체할 수 없으며, 현재 데이터 게이트는 열지 않는다.

## 공식 자료에서 확인한 내용

- Bitfinex Terminal 약관(표시된 최종 개정일 2021-01-04)은 Terminal 피드의 시장 데이터를 내부 목적에 한해 사용하도록 하는 라이선스를 기재한다. Basic 항목의 Trading/Candle Market Data 요금은 Free이며, Advanced historical order-book snapshots는 유료다. 약관은 시장데이터를 재배포·재판매하지 못하게 하고, 미국인 및 제재·제한 대상자 등 `Prohibited Person`을 정의한다. 계정자의 관할·자격은 확인하지 않았다.
- 별도 REST Candles 문서는 공개 URL, `start`/`end` 시각 필터, 1분~월봉 주기, 호출당 최대 10,000행을 기재한다. 이 설명만으로 어느 심볼의 가장 이른 보존일, 폐지 심볼 지원, 전 기간 연속성을 보장하지 않는다.
- Bitfinex API 문서는 공개 endpoint 접근에 계정이 필요하지 않다고 설명하면서 API 사용에는 별도 API Terms of Service 준수가 필요하다고 명시한다. Terminal 피드 약관의 내부 목적 무료 라이선스가 공개 REST endpoint에도 동일하게 적용되는지는 이 문서 검토로 확정되지 않았다.
- REST 캔들 자료는 OHLCV다. 주문블록 신호의 차트 입력으로 쓸 수 있는 가능성은 있지만, 과거 L2를 이용한 호가·체결·슬리피지 검증은 Advanced 유료 자료이며 이 G의 비용 검증을 대신하지 않는다.

## 고정 G 판정

| 기준 | 관측한 근거 | 상태 |
|---|---|---|
| 비용 없는 접근 | Terminal Basic candle 피드가 Free로 표시됨 | 잠재 경로. REST 적용 여부와 이용 자격 미확인 |
| 2018·2022 캔들 | REST가 시각 범위 조회를 지원하지만 최저 보존시각은 명시하지 않음 | 미입증 |
| 동일 30개 PIT 자산 | 현재/역사적 전체 pair 목록과 당시 활성구간 근거가 문서에 없음 | 미입증 |
| 상장폐지 처리 | 해당 REST 설명에서 상폐 데이터 보존/마지막 정산을 보증하지 않음 | 미입증 |
| 시장데이터 권리 | Terminal 약관은 내부 사용을 허가하지만 REST 적용 범위·현재 약관·이용자 자격이 별도 | 미확인 |
| 오더북 검증 | 역사적 오더북 스냅샷은 유료 Advanced 항목 | 현재 무료 경로로는 불충족 |

## 조사 경계

Bitfinex 공식 문서와 약관 공개 페이지만 확인했다. API 호출, 시세 조회, 파일 다운로드, 계정 로그인, 약관 수락, 결제, 코드·사전등록·장부 변경은 하지 않았다. REST API Terms의 세부 조항은 이번 자료 검토만으로 확인하지 못했다.

## 다음에 필요한 증거

1. Bitfinex 데이터 약관과 API 약관 중 실제 사용될 경로에 적용되는 버전 및 내부 연구·로컬 보관·파생 백테스트 권리를 확인한다. Terminal 약관을 REST API에 자동 적용하지 않는다.
2. 허용이 확인된 뒤에만 API 메타데이터를 통해 사전 고정한 30개 이상 기준 자산의 2018·2022 캔들 이용가능 범위와 earliest timestamp를 확인한다. 현재 pair 목록은 역사적 PIT universe가 아니다.
3. 당시 상장·폐지 일자, 티커 재사용·리브랜딩 규칙, 폐지 후 청산 처리를 독립 공식 자료로 확인한다.
4. 위 조건이 충족되면 별도 spot preregistration을 검토한다. Binance 파생상품 결과·코호트·거래비용을 Bitfinex spot에 복사하거나 현재 G를 완화하지 않는다.

## 공식 출처

- [Bitfinex Terminal Terms of Use](https://github.com/bitfinexcom/bitfinex-terminal/blob/master/terms-of-use/README.md)
- [Bitfinex REST Public Candles](https://docs.bitfinex.com/reference/rest-public-candles)
- [Bitfinex API Introduction and Terms notice](https://docs.bitfinex.com/docs/introduction)
- [Bitfinex API Requirements and Limitations](https://docs.bitfinex.com/docs/requirements-and-limitations)
