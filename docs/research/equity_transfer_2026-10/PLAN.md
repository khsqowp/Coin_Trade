# 미장·국장 전략 포팅 재실행 계획

## 목표와 범위

코인 전략 연구에서 도출된 전략을 미국·한국 주식 로컬 데이터에 적용한 현행 포팅 스크립트를 재실행하고, 전체 입력 결과·로그·근거 기반 보고서를 새 날짜별 디렉터리에 저장한다. 요청의 시작은 기존 주식 포팅 코드와 데이터 확인, 끝은 두 러너의 재실행·결과 검증·분석문 저장이다.

이 실행계획은 “코인 연구에 등장한 모든 전략이 주식으로 완전히 이식됐다”고 전제하지 않는다. 검증 기준은 소스에 실제 구현된 유한 그리드 전부가 평가됐는지, 두 실행이 정상 종료했는지, 결과 파일이 생성됐는지, 범위 밖 전략·시장별 정의 차이가 명시됐는지다.

## 단계 및 체크포인트

1. 기존 코드/로컬 캐시/사용자 변경 상태를 확인한다. [완료]
2. 미국·한국 runner의 전략군, 파라미터 그리드, 비용·체결·기간을 계수한다. [완료]
3. 사용자 작업 파일을 덮어쓰지 않고 날짜별 새 결과 폴더를 만든다. [완료]
4. 미국·한국 러너를 로컬 캐시로 각각 실행하고 JSON·로그를 저장한다. [완료, 양쪽 exit code 0]
5. JSON 구조·그리드 개수·핵심 성과·lookahead 검사 상태를 다시 읽어 보고서에 반영한다. [완료]
6. “코인 98패밀리 전수 이식”이 아니라는 범위와 미시험 범주를 분리해 최종 보고한다. [완료]

## 완료 기준

- 미국 및 한국 원시 JSON과 전체 실행 로그가 이 폴더에 존재한다.
- 실제 런너 코드가 평가한 전략·파라미터 조합 수를 구별해 기록한다.
- 기준/주요 결과를 OOS 또는 기간 분할, CAGR, MDD, 수수료 가정과 함께 보고한다.
- 코인 패밀리 전체와의 차이, 생존편향, 데이터/체결 가정, 미래참조 검사 커버리지를 숨기지 않는다.
- 기존 dirty/untracked 작업 파일은 수정·삭제·커밋하지 않는다.

## 실행 커맨드

```sh
US_OUT=docs/research/equity_transfer_2026-10/us.json python3.12 -m app.rs_us_run
python3.12 -m app.rs_kr_run docs/research/equity_transfer_2026-10/kr.json
```

명령은 저장소 `trading/` 하위 디렉터리에서 실행한다. 네트워크/API 사용과 실거래 주문은 없다.

## 2026-10-14 추가 범위: 등록 패밀리 일봉 전이시험

- 98개 등록 패밀리 × 3,171개 파라미터 신호 단위를 미국·한국 각각 실행했다. 각 신호는 공통 72개 구성을 비용 2종·사이징 2종으로 평가했다. 각 시장 913,248행 저장 및 전체 청크 검증 완료.
- 전체 3,171개 일봉 파라미터 단위 각각을 3개 cutoff에서 양 시장 검사했다. 시장별 9,513회, 합계 19,026회 미래 OHLCV 교란 검사에서 과거 신호 변경은 0건이었다.
- 상세 결과와 제한은 `FULL_TRANSFER_REPORT.md`에 기록했다.
- 2026-10-14 보충: 거래량 R01–R16 계좌기반 16개 라운드를 미국·한국에 별도 이식해 64개 결과행으로 저장했다. `VOLUME_PORTFOLIO_TRANSFER.md`와 `full_runs/volume_portfolio_transfer.json` 참조.
- 2026-10-14 추가 보충: Mach7 원본 72개 포트폴리오 조합을 시장별 2개 비용으로 이식해 288행과 일별 자산곡선을 저장했다. `MACH7_PORTFOLIO_TRANSFER.md`와 `full_runs/mach7_portfolio_transfer.json` 참조.
- 2026-10-14 추가 보충: Round12 §§45–51 47개와 Round13 §§64–68 41개 정책을 시험해 352행을 저장했다. 후속으로 Round12 §§53–57 36개, §§59–61 23개를 시험해 236행을 저장했다. Round12 §§45–61의 선언 그룹 설정은 총 106개다. `ROUND12_13_POLICY_TRANSFER.md`, `ROUND12_EXTENSION_TRANSFER.md` 및 각 `full_runs/*.json` 참조.
- 2026-10-14 추가 보충: Round13 §§69–72 35개, §§73–76 36개 정책도 양 시장·2비용으로 실행해 284행을 저장했다. 71개 설정 전체의 future-prefix 교란 결과는 `full_runs/round13_prefix_validation.json`, 성과·방법은 `ROUND13_POLICY_TRANSFER.md` 및 `full_runs/round13_policy_transfer.json` 참조.
- 2026-10-14 재인벤토리 보충: Round14 `crypto_round14_research.plans()`의 현재 계획 44개를 양 시장·2비용으로 실행해 176행을 저장했다. 미래교란 검증은 `full_runs/round14_prefix_validation.json`, 상세는 `ROUND14_POLICY_TRANSFER.md` 참조.
- 2026-10-14 Round16 보충: `crypto_round16_liquidation_research.plans()`의 397개 설정을 미국·한국 각각 2비용으로 실행해 총 1,588행을 저장했다. 모든 곡선 지표를 재계산해 대조했고, 양 시장 397개 설정 각각의 future-prefix 교란 검사에서 과거 신호 변경은 0건이었다. 이 라운드의 청산대는 실제 주식 청산 데이터가 아니라 가정 레버리지 티어와 OHLC 앵커로 만든 합성 프록시다. `ROUND16_LIQUIDATION_PROXY_TRANSFER.md`와 `full_runs/round16_*` 참조.
- 2026-10-14 범위 감사 보충: 원천 PSAR가 `pandas-ta==0.4.71b0`으로 고정됨을 확인해 native PSAR 일봉 신호를 양 시장·2비용으로 별도 시험했다(4행). 곡선 지표 재계산과 미래 prefix 교란 검사를 통과했다. 원본의 intrabar trailing-stop·risk-sized 수량과는 차이가 남는다. [PSAR_NATIVE_TRANSFER.md](PSAR_NATIVE_TRANSFER.md).
- 2026-10-14 범위 감사 보충: 원본 `trx_dca_swing_backtest.py`의 EMA 교차·3% DCA·RSI 되돌림 부분익절·데드크로스 청산을 양 시장에 이식했다(시장별 2비용, 총 4곡선). 전일 종가 신호 다음 시가 실행, 종목당 1/8 및 8슬롯으로 포트폴리오화했다. 재실행 곡선·미래교란 검사를 통과했다. [TRX_DCA_SWING_TRANSFER.md](TRX_DCA_SWING_TRANSFER.md).
- 2026-10-14 pair 보충: `c_pairs_best_partner`의 누출된 고정 코인 파트너 규칙은 재사용하지 않았다. 대신 주식 유니버스에서 과거 180일 상관으로 peer를 매 시점 선택하는 별도 두 다리 달러중립 적응 가설을 사전 선언 그리드 288개(양 시장·비용 포함)로 시험했다. 곡선 288개 지표 재계산 및 36개 신호 설정 미래 prefix 검증을 통과했으며 CAGR 중앙값은 양 시장 모두 음수다. 원본 코인 전략 결과와 혼동하지 않도록 [EQUITY_PEER_PAIRS_TRANSFER.md](EQUITY_PEER_PAIRS_TRANSFER.md)에 분리 기록했다.
- 2026-10-14 전략 인벤토리 후속: Round10 §§25–27 원본 grid 136개를 미장·국장 2비용으로 실행해 544개 곡선을 추가했다. 저장곡선 재계산과 544개 계좌 prefix 검증, 590개 종목·신호가족 prefix 비교를 통과했다. [ROUND10_POLICY_TRANSFER.md](ROUND10_POLICY_TRANSFER.md)와 round10 결과 파일 참조.
- 2026-10-14 전략 인벤토리 후속: Round11 `configs()` 34개 정책을 두 시장·두 비용으로 실행해 136개 곡선을 저장했다. 지표 재계산과 미래 OHLC 3배·거래량 7배 교란에서 354개 신호 피처 및 136개 계좌곡선의 과거 prefix가 모두 일치했다. `ROUND11_POLICY_TRANSFER.md`와 `full_runs/round11_*` 참조.
- 2026-10-14 전략 인벤토리 후속: `crypto_strategy_showdown.py`의 레짐·손실제한·레버리지 조합 112개를 주식에 적용해 양 시장·2비용 총 448곡선을 추가했다. 곡선 지표를 재계산하고 미래구간 교란에서 448개 과거 prefix가 모두 일치했다. 선물 유지증거금 청산은 주식의 실제 브로커 규칙이 아닌 합성 스트레스 계산으로 분리 표기했다. `SHOWDOWN_POLICY_TRANSFER.md`와 `full_runs/showdown_*` 참조.
- 2026-10-14 Round3 보충: 정책 실험 53개와 기준선 3개를 양 시장·2비용으로 실행해 224곡선을 저장했다. 590개 신호 피처 및 224개 계좌곡선 prefix 변형 검사를 통과했다. `ROUND3_POLICY_TRANSFER.md`, `full_runs/round3_*` 참조.
- 2026-10-14 Round4 보충: 코인에서 선별된 고정 승자 5개에 대해 8기간 독립 재실행, 손실 임계값 민감도 6개, 거래·종목 집중도, 상위거래 제외 분석을 양 시장·비용으로 수행했다. 전체 204 replay 중 20개 일별곡선, 160기간 결과, 24민감도 결과를 저장했다. 거래원장 재구성 및 236개 신호/20개 곡선 미래 prefix 검증이 통과했다. `ROUND4_ROBUSTNESS_TRANSFER.md` 및 `full_runs/round4_*` 참조.
- 2026-10-14 Round5 보충: Champion, N2/N3 고정초기자본 구성을 양 시장·2비용으로 이식했다. 12개 전체 포트폴리오 감사, 96개 독립 기간, 36개 고유 champion 민감도 실행, 20개 가중치 재조합, 4개 합성 주식 프록시 확인 곡선을 저장했다. 미래 OHLCV 교란 prefix에서 1,298개 신호 피처, 12개 계좌곡선, 96개 기간지표, 4개 확인곡선이 통과했다. 결과·판정·원장 한계는 `ROUND5_POLICY_TRANSFER.md`와 `full_runs/round5_*`에 기록했다.
- 2026-10-14 Round6 보충: 원본 고정 전략 6개의 주식 프록시 상대성과와 Champion 거래비중 제한 10/15/20%를 평가했다. 전체 전략·제한 곡선 40개, 독립 기간 320개를 저장하고 재실행 결과가 일치했다. 12개 제한곡선과 708개 신호 피처 미래 prefix 교란이 통과했다. BTC 대신 합성 동일가중 주식 프록시를 쓴 근사와 결과는 `ROUND6_POLICY_TRANSFER.md`, `full_runs/round6_*` 참조.
- 현지 데이터 차단 근거: KIS 캐시 118개 파일(미국 54, 한국 64)을 확인했다. 249,592행에서 intraday timestamp가 0개이며 로더의 `b4`도 비어 있다. 4h/1m 자료를 합성하지 않았고, 데이터 가용성 인벤토리를 [DATA_AVAILABILITY.md](DATA_AVAILABILITY.md)에 저장했다.
- 누적 보충시험: 감사표에 17개 계좌/연구 보충군, 5,368개 replay 결과행이 기록돼 있다. 이 수는 결과행 합계이며 독립 전략 수가 아니다. 등록 98패밀리 일봉 시험과 별도 보충 결과를 합산해도 “모든 전략” 완료를 의미하지 않는다.
- 미재현 소스 범위는 현재 16개로 정리됐다. 다섯 advanced 전략은 지표 입력 규칙이 누락·모순되고, ICT/TJR 규칙 일부는 기계 판정 규칙이 없으며, ORB/10,000원/분봉 발산 계열은 분봉·세션 자료가 없다. c_pairs_best_partner의 전표본 파트너 선택은 누출이라 그대로 실행하지 않았고, c_sma_wide_original에는 원본 SMA 규칙이 확인되지 않았다. 상세 이유는 `strategy_scope_audit.json`에 유지한다.
- 미완료 경계: 주식 4시간 데이터가 없어 시간대 단위 3,171개/시장(총 6,342개) 미평가. 감사표의 `NOT_REPRODUCED` 16개와 등록 패밀리 내부의 근사 fidelity가 남아 있다. 과거시점 상장폐지·편입 유니버스 복원은 하지 않았다.
- 기존 `.git` 변경 및 untracked 파일은 수정·삭제·커밋하지 않았다. 작업 파일과 연구 결과는 미커밋 상태다.
