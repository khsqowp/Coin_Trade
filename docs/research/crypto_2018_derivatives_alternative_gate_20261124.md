# 2018년 코인 파생상품 대체 거래소 게이트 — 2026-11-24

## 결론

추가로 확인한 HTX/Huobi, KuCoin, Bitget, Bitfinex 경로는 Binance USDⓈ-M의 2018년 데이터 공백을 메우는 대체 자료로 적격하다고 입증되지 않았다. 제품 출시일이 늦거나 2018년 말 초기 계약 수가 적고, 2018·2022 동일 30자산 코호트, 전체 시계열 완전성, funding/mark 정합, 재사용 권한이 확인되지 않았다. 데이터 호출·다운로드·백테스트는 하지 않았다.

## 공식 근거

| 거래소 | 확인된 출시·자료 범위 | 기존 게이트 판정 |
|---|---|---|
| HTX/Huobi DM | 공식 2018년 11월 월간 회고는 Huobi Derivative Market 출시를 기록한다. 2018-12-28 Huobi 제공 발표는 당시 BTC·ETH 계약이 운영 중이고 EOS 계약을 추가했다고 명시한다. 공식 HTX 발표는 perpetual swaps를 2020-04-01에 출시했으며, 당시 BTC 스왑부터 시작했다고 설명한다. | 2018년 말 계약 범위가 3개 수준이라는 직접 자료라 30개 코호트를 충족하지 못한다. 현재 perp 전략과 delivery/quarterly futures는 상품 정의가 다르다. 공개자료의 2018 객체 범위·완전성·사용권은 확인되지 않았다. |
| KuCoin | KuCoin 공식 발표는 2019-07-08 KuMEX 공개 베타와 BTC perpetual 최초 계약을 명시한다. | 2018년 코호트 자료가 아니다. |
| Bitget | Bitget 공식 백서의 연혁은 USDT-M futures 출시를 2019년 5월로 기록한다. | 2018년 코호트 자료가 아니다. |
| Bitfinex | Bitfinex 공식 2019 연말 회고는 파생상품 거래 플랫폼 출시를 2019년 9월로 기록한다. | 2018년 코호트 자료가 아니다. |
| BitMEX, Deribit, Bybit, Binance, OKEx, Huobi | 미국 연방관보에 공개된 2021년 거래소 비교 신청서는 BTC futures 계열의 자료 시작 월을 BitMEX 2017-12, Deribit 2018-08, OKEx 2018-10, Huobi 2019-08, Binance 2019-09, Bybit 2019-10으로 표기한다. 이는 비교 대상 BTC 계약의 자료 기간이지 전체 거래소 유니버스의 완전한 상장 이력은 아니다. | 2018년 BTC 자료가 있다는 이유만으로 30개 코인의 과거 자료나 2022 동일 코호트를 증명하지 못한다. |

## 연구상 의미

- 확인된 자료로는 한 거래소·한 계약 규격에서 2018년과 2022년을 아우르는 고정 30자산 파생상품 집합을 입증하지 못했다.
- venue를 섞거나 현물을 파생상품으로 대체하면 거래소별 가격·비용·펀딩·상장시점이 달라지므로 기존 USDⓈ-M 사전등록 결과와 합산하지 않는다. 그런 연구는 별도 정의, 독립적인 PIT 코호트, 비용·funding 모델, 새 사전등록이 필요하다.
- 주문블록 구역 계산에는 OHLC가 사용될 수 있지만, 호가 깊이 기반 실행·슬리피지 주장을 검증하려면 과거 호가 자료와 거래 ID 연결이 추가로 필요하다. 확인한 HTX 과거자료 README는 내려받는 시장자료 파일 형식을 설명하지만, 2018 계약별 파일 완전성이나 역사적 호가 깊이 자료를 입증하지 않는다.
- 공개 접근 또는 API key 불필요는 영구 보관·변환·파생 통계 이용권과 동일하지 않다. HTX 자료의 명시적인 연구 재사용 허가는 확인하지 못했다.

## 다음 판정

현재 Coin_Trade의 고정 USDⓈ-M 코호트는 2018 검증불가 상태를 유지한다. 2018/2022 동일 코호트와 적법한 자료 이용권이 공식 근거로 확인되기 전에는 이 대체 경로를 실험 입력으로 사용하지 않는다. 게이트 기준을 낮추거나 다른 venue를 기존 결과에 끼워 넣지 않는다.

## 출처

- [Huobi 2018년 11월 회고](https://square.htx.com/huobi-monthly-recap-november-2018/)
- [Huobi 제공 2018-12-28 EOS 계약 추가 발표](https://www.prnewswire.com/news-releases/huobi-dm-expands-cryptocurrency-contract-service-to-include-eos-300771224.html)
- [HTX perpetual swaps 출시 발표, 2020-04-01](https://square.htx.com/huobi-launches-perpetual-swaps-to-help-traders-exploit-market-volatility/)
- [KuCoin KuMEX 출시 발표, 2019-07-08](https://www.kucoin.com/announcement/en-kucoin-derivatives-trading-platform-kumex-goes-live-offering-20x-leverage-bitcoin-perpetual-contract)
- [Bitget 공식 연혁 백서](https://www.bitget.com/cdnstatic/files/BGB-whitepaper-en.pdf)
- [Bitfinex 2019 연말 회고](https://blog.bitfinex.com/announcements/bitfinex-2019-a-year-in-review/)
- [미국 연방관보에 공개된 거래소별 BTC 선물 자료 시작 기간](https://public-inspection.federalregister.gov/2023-15127.pdf?1689597922=)
- [HTX/Huobi 공개 자료 파일 형식 안내](https://github.com/hbdmapi/huobi_public_data/blob/master/README.md)

## 수행하지 않은 작업

이 보고서는 공식 출시·자료 문서만 대조했다. API 호출·계정/키 사용·다운로드·가격 행 열람·유료 이용·공용 사전등록·공용 장부 수정·전략 실행은 하지 않았다.
