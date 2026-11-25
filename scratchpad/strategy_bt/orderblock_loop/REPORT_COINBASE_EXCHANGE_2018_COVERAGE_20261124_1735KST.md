# Coinbase Exchange 현물 데이터 경로 검토

작성: 2026-11-24 17:35 KST  
범위: Coinbase 공식 Exchange 개발문서, Coinbase 공식 자산 상장 공지, 공식 Data Marketplace 안내와 Market Data 약관. API 호출, 계정/SSH 접속, 키 사용, 구매, 다운로드, 원시 샘플 수집은 하지 않았다.

## 결론

Coinbase Exchange는 OHLCV와 체결 데이터 종류를 제공하지만, **2018·2022에 공통으로 30개 이상의 자산을 확보하는 경로가 아니다.** 2018년에 공식 출처로 확인되는 지원 자산은 그보다 현저히 적고, 연중 연속 OHLCV·당시 상장 유니버스·상폐 자산의 보관 범위도 입증되지 않았다. 공개 API에는 요청당 300개 캔들 한도가 있고, 구매형 Marketplace 데이터는 현재 연구용 AI/알고리즘 개발에 대한 약관 충돌이 있어 승인된 무료 경로로 취급할 수 없다.

## OHLCV·체결 자료 경로

- 공식 Exchange REST 캔들 endpoint는 제품별 과거 OHLC와 거래량 자료를 내며, 1분·5분·15분·1시간·6시간·일 단위 granularity를 문서화한다. 한 요청은 최대 300개 캔들이며 더 넓은 구간은 여러 요청으로 나눠야 한다. 문서는 거래가 없던 interval은 행을 발행하지 않을 수 있고 과거 rates가 불완전할 수 있다고 명시한다. 2018년 earliest coverage 또는 전 심볼의 실제 연속성은 문서에서 보장하지 않는다.
- 공식 REST 체결 endpoint 설명은 “latest trades” 목록과 cursor pagination이다. 전체 거래 이력의 최초 시점 또는 상폐 상품의 전체 체결 보관을 보장한다고 쓰지 않는다.
- Coinbase Data Marketplace는 tick trade, hourly OHLCV, daily OHLCV 상품을 열거한다. 과거 일회성 구매가 가능하지만 데이터셋 범위·대상 자산을 계약으로 확정하고, 구매 후 SSH key로 SFTP에서 내려받는 구조다. 공식 안내 샘플은 2022-04-27 BTC 거래 파일 경로다. 이는 2018 자료 존재 또는 전 상품의 earliest date 증거가 아니다.

## 2018·2022 심볼 교집합 및 PIT

공식 Coinbase 공지는 2018년 말까지 단계적으로 확인되는 자산이 core BTC·ETH·LTC·BCH·ETC와 2018년 추가된 ZRX·BAT·USDC·ZEC·CVC·DNT·LOOM·MANA·DAI·GNT·MKR·ZIL임을 보여준다. 이 직접 확인 목록은 17개이며 일부는 특정 국가나 Coinbase Pro에서만 거래 가능했다. 여기에 Coinbase의 2018 Q4 회고는 그 분기에 추가한 자산이 회사의 그전 전체 역사에서 추가한 수보다 많다고 밝히며, Q4 추가 목록에는 USDC·ZEC·10개 Ethereum 계열 토큰, 총 12개가 열거돼 있다. **이 진술과 Q4 목록이 완전하다는 전제에서 계산하면**, 2018년 말 회사 전체 지원 자산 수도 24개 미만이다. 이는 Exchange 상품·지역별 거래 가능성이 더 좁을 수 있음을 고려하지 않은 상한 추론이다. 공식 공지는 XLM을 Coinbase Pro에서 거래 시작한 시점을 2019-03으로, XRP를 2019-02로 기록한다. 그러므로 2018/2022 교집합 30자산 조건은 성립하지 않는다. 여러 quote pair는 별도 자산으로 중복 계산하지 않는다.

Coinbase의 현재 `Get all known trading pairs` 문서는 제품 상태에 `online`, `offline`, `internal`, `delisted`를 포함하지만 이는 현재 반환 상태다. 문서는 각 상품의 과거 listing/delisting timestamp 또는 매 시점의 전체 universe 이력을 제공한다고 보장하지 않는다. 개별 공지는 상장 시점과 지역별 제한을 확인하는 데 도움은 되지만, 2018·2022 전체 시점별 상장/상폐 universe를 재구성하는 완전한 공식 이력으로는 부족하다.

따라서 구분 판정은 다음과 같다.

| 항목 | 판정 |
|---|---|
| 2018년 자산 수로 30개 공통 자산 가능 여부 | 불가. 17개 직접 확인 목록이며, Q4 recap 진술을 적용한 회사 전체 상한도 24개 미만(상한은 명시적 계산 추론) |
| 2018 full-year OHLCV 연속성 | 확인 안 됨. 공식 API는 요청한도와 무거래 interval 누락을 밝히지만 실제 full-year 자료를 확인하지 않음 |
| 2022 full-year OHLCV·체결 범위 | 상품 종류는 있으나 자산별 최초일·연속성은 구매 없는 문서 조사로 확인 안 됨 |
| 상폐 심볼 보존 | 현재 API 모델은 `delisted` 상태를 표현하지만 과거 데이터 보존·기간은 확인 안 됨 |
| 시점별 universe/PIT | 현재 상품 목록과 개별 공지만으로 완전 재구성 불가 |
| 현재 무료·개인 AI 전략연구 사용권 | 명확히 적합하다고 확인할 수 없음. 아래 약관 충돌 참고 |

## 이용조건

Coinbase Data Marketplace 안내는 데이터 구매·라이선스 계약, Sales 문의, 구매 후 SFTP용 공개키 제공 절차를 요구한다. AGENTS.md의 유료 자료 미구매 경계에 따라 이 경로는 사용하지 않는다.

현재 Coinbase Market Data Terms(2026-08-07)는 개인 또는 연구 목적의 제한 라이선스를 표현하는 한편, 별도 사전 서면 동의가 없으면 데이터를 AI/ML 모델이나 알고리즘 개발·훈련·검증·개선에 쓰는 것을 금지한다. 본 작업은 AI agent를 이용한 주문블록 전략 분석과 알고리즘 백테스트 기반을 위한 것이므로, 이 금지 조항과 직접 충돌할 가능성이 높다. 따라서 “개인 연구” 조항만으로 허용된다고 판정하지 않는다. Coinbase의 서면 허가와 허용 범위가 명확해지기 전에는 공개 API든 Marketplace든 이 전략연구 입력으로 채택하지 않는 것이 맞다. 여기서 법률 자문이나 약관의 최종 해석을 제공하는 것은 아니다.

## 연구 경로 판정

이 경로는 **30자산/2018 요건에서 탈락**하므로 가격자료를 확보해도 기존 코인 G 기준을 충족하지 못한다. 공개 API의 소량 캔들 조회를 통해 특정 제품의 2018 자료를 확인하는 것은 문서만으로 완전히 배제되지는 않지만, 30심볼 불가와 AI/알고리즘 이용약관 불확실성을 해결하지 못한다. 추가 API 확인·구매·허가 요청을 진행하지 않는다. Coinbase 데이터는 현재 캠페인의 후보 검증 근거로 채택하지 않는다.

## 공식 출처

- Coinbase Exchange 캔들 문서(최대 300개, 무거래 interval 생략 및 불완전 가능): https://docs.cdp.coinbase.com/api-reference/exchange-api/rest-api/products/get-product-candles
- Coinbase Exchange 최신 체결 문서: https://docs.cdp.coinbase.com/api-reference/exchange-api/rest-api/products/get-product-trades
- 현재 알려진 거래쌍 및 status 문서: https://docs.cdp.coinbase.com/api-reference/exchange-api/rest-api/products/get-all-known-trading-pairs
- Coinbase Data Marketplace 상품·스키마: https://help.coinbase.com/en/data-marketplace/getting-started/data-marketplace-products
- Coinbase Marketplace 구매·계약·SFTP 접근: https://help.coinbase.com/en/data-marketplace/getting-started/coinbase-data-marketplace
- Coinbase Market Data Terms (updated 2026-08-07, §§2–3): https://www.coinbase.com/legal/market_data
- 2018년 Q4 추가 자산 요약: https://www.coinbase.com/blog/what-we-accomplished-at-coinbase-in-q4-2018
- 2018년 말 Pro listing batch 및 jurisdiction 범위: https://www.coinbase.com/blog/ethereum-tokens-dai-dai-golem-gnt-maker-mkr-and-zilliqa-zil-are-launching-on-coinbase
- XLM Pro listing(2019-03): https://www.coinbase.com/blog/stellar-lumens-xlm-is-launching-on-coinbase-pro
- XRP Coinbase listing(2019-02): https://www.coinbase.com/blog/xrp-is-now-available-on-coinbase
