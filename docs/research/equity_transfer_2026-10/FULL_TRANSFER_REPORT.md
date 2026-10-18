# 코인 전략 패밀리의 미국·한국 주식 전이시험 보고서

작성일: 2026-10-14 (Asia/Seoul)

## 결론

코인 오프라인 레지스트리에 등록된 98개 패밀리의 일봉 파라미터 그리드 3,171개를 미국·한국 주식 일봉 자료에 각각 적용하고, 시장별 288개 포트폴리오·비용·사이징 조건을 평가했다. 미국 913,248행, 한국 913,248행, 합계 1,826,496행이 생성됐으며 두 시장의 전략 신호 예외는 0건이다. 원시 청크 전체의 행수, 신호별 288조건 완전성, 중복 키, 필수 지표 결측을 재검사해 통과했다.

이 작업은 **코인 전략의 완전한 주식 재현이 아니다.** 주식 캐시는 일봉뿐이므로 4시간봉 파라미터-시간대 단위 3,171개/시장(총 6,342개)은 시험할 수 없었다. 등록 신호 시험 외에 Round3 정책 실험 53개와 기준선 3개, Round4의 고정 winner 강건성·기간·집중도 진단, Round5 champion/N2/N3 이관, Round6 BTC 상대성과 및 종목 거래집중 제한, Round10 §§25–27의 136개 메타정책, Round11 §§29–38의 34개 정책, showdown의 112개 레짐·손실제한·레버리지 조합, 거래량·Mach7 포트폴리오 조합, Round12 §§45–61의 선언 조합 106개, Round13 §§64–76의 112개, Round14의 현재 `plans()` 44개를 보충시험했다. Round16 청산근접 프록시, PSAR, TRX DCA, 인과적 주식 peer-pair 가설도 별도 보충시험했다. Round11 §29 선물 funding/slippage 비용 시나리오는 주식으로 직접 등가 이식하지 않았다. 현 신호 감사표의 미재현 분류 16개는 등록 family 신호 인터페이스 범위만 뜻하며 저장소의 전체 연구실험 미완료 수가 아니다.

## 범위와 재현

| 항목 | 미국 | 한국 |
|---|---:|---:|
| 평가 기간 | 2019-01-02–2026-10-12 | 2019-01-02–2026-10-02 |
| 로컬 종목 수 | 54 | 64 |
| 패밀리 | 98 | 98 |
| 일봉 신호/파라미터 단위 | 3,171 | 3,171 |
| 포트폴리오 구성/신호 | 72 | 72 |
| 비용 케이스 | 2 | 2 |
| 사이징 케이스 | 2 | 2 |
| 결과행 | 913,248 | 913,248 |
| 신호 실행 오류 | 0 | 0 |
| 중복 결과 키 / 필수 지표 결측 | 0 / 0 | 0 / 0 |

각 신호 단위당 72개 전략 구성(LS 20, 롱온리 균등 8, 상위 N 40, 오버레이 4) × 비용 2 × 사이징 2 = 288개 평가다. 케이던스는 1·2·3·7일, K는 4·6·8·10·12다. 전체·IS·OOS·2022년 이후·3개 시간 폴드에 CAGR, MDD, Calmar, Sharpe를 계산했다. IS/OOS는 시작 후 거래일 수 기준 60/40 순차 분할이다.

- 입력은 기존 `.kis-cache` 로컬 OHLCV다. 네트워크/API 접근, 주문, 계좌 접근은 없었다.
- 미국 비용은 편도 KIS 0.36% 및 저비용 0.08%다. 한국은 기본 슬리피지 및 슬리피지 2배를 썼고, 거래 수수료 0.015%, 매도세 0.18%를 적용했다.
- 한국 공매도 연 3%, 미국 공매도 연 1% 대차 비용은 가정치다.
- 미국 신호는 다음 종가 체결, 한국은 다음 시가 체결로 구현했다. 한국은 기존 보유분에 갭 수익을 반영하고 새 보유분에 당일 장중 수익을 반영한다.
- 20% 변동성 타깃 사이징의 레버리지 상한은 1.5배다. 주식 가격·수익률로 계산했으며 코인 펀딩은 적용하지 않았다.
- 랭크 동점은 로컬 종목 순서로 안정적으로 해소한다.
- 시장 프록시는 실제 지수가 아니라 해당 로컬 유니버스의 일별 동일가중 수익률로 만든 합성 지수다. BTC 의존 필터의 대체값으로만 사용되며 거래 대상이 아니다.

재현 명령:

```bash
/opt/anaconda3/bin/python -m app.rs_equity_map_run US
/opt/anaconda3/bin/python -m app.rs_equity_map_run KR
```

## 4시간봉 자료 확보 경로 확인

- 현재 저장소·상위 프로젝트에서 확인한 시장자료는 `.kis-cache` 일봉 CSV뿐이다. OHLCV 저장소 전체에서 주식 4시간/분봉 이력 파일은 찾지 못했다.
- 미국 대안으로 Alpaca 공식 historical bars API는 1–23시간 단위 aggregation과 여러 티커/기간 조회를 지원한다. 공식 데이터 안내는 주식 이력이 2016년부터라고 적고 있으나, 기본 요금제는 과거 이력도 최신 15분까지만 조회 가능하고 무제한 이력은 Algo Trader Plus(문서상 월 $99)다. 데이터 계약·계정·adjustment·ticker coverage 확인 전에는 현재 KIS 자료와 동일하다고 간주하거나 다운로드하지 않았다. [API 사양](https://docs.alpaca.markets/us/reference/stockbars), [시장 데이터 요금·이력 범위](https://docs.alpaca.markets/us/docs/about-market-data-api)
- 한국투자증권 공식 `open-trading-api`의 국내 과거 분봉 provider는 분봉을 단일 날짜 조회로 설명하고 “당일 또는 최근 1년” 범위를 주석으로 명시한다. 이 API만으로 2019년부터의 전체 구간을 확보할 수 있다는 근거는 확인되지 않았다. 1년 분봉을 받으려면 64종목×거래일 단위 대량 호출과 호출제한 검토도 필요하다. [KIS 공식 샘플 구현](https://github.com/koreainvestment/open-trading-api/blob/main/backtester/kis_backtest/providers/kis/data.py)
- 따라서 미국은 과거 데이터 구독/인증, 한국은 장기 분봉 이력 제공자 선정이 선행조건이다. 제공자·조정 방식·시장범위가 정해지지 않은 상태에서 데이터를 임의로 섞지 않았다.

## 분포와 핵심 관찰

아래 중앙값은 각 시장의 전체 913,248개 개별 결과행에서 계산했다. 전략 파라미터·구성·비용·사이징 변형을 모두 섞은 분포이므로 “전략 기대수익” 추정치가 아니다.

| 시장 | OOS CAGR 중앙값 | OOS MDD 중앙값 | OOS CAGR 양수 비율 | OOS CAGR이 기존 바스켓 CAGR 초과 |
|---|---:|---:|---:|---:|
| 미국 | 2.6% | 21.6% | 63.9% | 3.0% |
| 한국 | 0.2% | 29.5% | 51.1% | 5.8% |

비교 바스켓은 이전 시장별 재실행 결과의 미국 28.8%, 한국 19.9% CAGR이다. 서로 다른 시점·유니버스·비용 조건의 기준이라 엄밀한 동시 대조 실험은 아니다. 이 비교에서 대부분의 개별 변형은 기존 바스켓 CAGR을 넘지 못했다.

전략 구성별 OOS 중앙값은 단순 상위 랭킹보다 더 유용한 구조를 보인다.

- 롱온리 균등(LO_EW)은 미국 저비용에서 OOS CAGR 중앙값 4.5%, MDD 4.2%; KIS 비용에서 2.1%, 5.1%였다. 한국 기본 비용에서 3.8%, 6.2%; 슬리피지 2배에서 3.1%, 6.6%였다. 비교적 낮은 낙폭이지만 수익도 낮고, 신호별 세부 차이가 크다.
- 상위 N(LO_TOPN)은 미국 저비용 OOS CAGR 중앙값 11.6%, MDD 18.5%; KIS 비용에서는 CAGR 중앙값 0.1%, MDD 24.2%였다. 한국은 기본 비용에서 4.8%, 28.0%; 슬리피지 2배에서 1.5%, 30.1%였다. 농축 포트폴리오의 비용 민감성이 두드러진다.
- 롱숏(LS)은 OOS 중앙값이 양 시장 대부분 음수이고 최대낙폭이 컸다. 단순 주식 OHLCV 신호를 이 공매도 가정으로 운용하는 방식은 이 실험에서 지지되지 않는다.
- 오버레이(OVL)는 모드와 비용에 따라 편차가 크다. 미국·한국 저비용/기본 조건의 일부 결과가 높지만, 합성 시장 프록시·사후 선택·현금 대기·가정 비용의 영향을 강하게 받는다.

가장 높은 OOS Calmar 사례를 무비판적으로 승자로 취급하면 안 된다. 미국 상위 일부 `c_bollinger_riding`은 오버레이 `gate`가 대부분 노출을 차단해 MDD가 0.08–0.14%에 불과했다. 작은 분모 때문에 Calmar가 25 이상으로 튀었지만 OOS CAGR은 0.8–3.1% 수준이다. 이는 “좋은 매매전략”의 증거라기보다 현금 비중이 큰 게이트가 만든 비율 효과다. 반대로 OOS CAGR 최고는 미국 `a_trix_native` 상위N/저비용에서 65.1%, 한국 `a_trix_r13` 상위N/기본 비용에서 83.1%였으나, 각각의 OOS MDD는 25.9%, 27.7%였고 수천 개 변형을 평가한 뒤 고른 극단값이다. 선택편향 보정이나 별도 전향 검증 없이 기대수익으로 해석하지 않는다.

OOS 성과 분포의 중앙 50% 범위도 넓다. 미국 OOS CAGR 25백분위는 -4.3%, 75백분위는 10.5%였고, 한국은 -9.3%, 8.0%였다. 상위 극단이 전체 결론을 대표하지 않는다.

## 재현 충실도와 제한

1. 98개는 코인 코드 레지스트리에 실제 등록된 패밀리다. 원천 전략 명세의 모든 변형을 뜻하지 않는다. 초기 `NOT_REPRODUCED`와 보충시험 간의 포함 관계는 `strategy_scope_audit.json`에 보존했다. 현재 미재현 분류 16개에는 분봉/세션 규칙, 미정 indicator bank, 단계별 진입·청산, 원본 pair-best-partner 등이 남아 있다.
2. 등록된 98개 중 일부도 원래 정의와 근사치다. 예를 들어 거래량 단위, 실제 volume-at-price, 변동성·시장 프록시, 일부 지표 초기화와 분봉 데이터 제약이 있다. 원본 레지스트리의 `fidelity` 설명을 확인해야 한다.
3. 일봉 주식 자료만 존재해 4시간 신호 3,171개/시장(총 6,342개)은 실행하지 않았다. 일봉을 4시간으로 쪼개거나 복제하지 않았다.
4. 유니버스는 현재 캐시에 있는 미국 54종목·한국 64종목이다. 상장폐지 종목 및 과거 시점 유니버스가 충분하지 않아 생존편향·선택된 대형주 편향이 크다.
5. 합성 동일가중 시장 프록시는 실제 S&P 500, Nasdaq, KOSPI, KOSDAQ 지수가 아니다. BTC 게이트를 이 값으로 치환한 것은 비교용 근사다.
6. 한국 호가단위, 주문 규모별 시장충격, 거래정지·상하한가 체결, 대차 리콜·종목별 공매도 허용, 현금 이자, 세금 세부 사항을 완전히 모형화하지 않았다. 미국 환전·세금·배당 및 실제 수수료도 계좌별로 다를 수 있다.
7. 미래가격 교란 검사는 등록된 모든 3,171개 파라미터 단위 각각에 대해 3개 cutoff, 양 시장을 시험했다. 시장별 9,513회, 합계 19,026회에서 cutoff 이후 OHLCV 교란이 cutoff까지의 포지션·강도 출력을 바꾸지 않아 통과했다. 이는 등록 패밀리 signal 함수의 지정된 일봉 데이터·cutoff에서 수행한 실험적 누수 검사이며, 신호 이후 체결시점·외부 기업행동 자료·원천 데이터의 사후수정까지 수학적으로 증명하지 않는다.
8. 평가한 1,826,496행은 1,826,496개의 독립 전략 가설이 아니다. 같은 신호를 여러 구성·비용·사이징으로 조합한 결과행이다. 극값 선택은 다중검정·선택편향을 크게 받는다.

## 저장 산출물

- `app/rs_equity_transfer.py`: 주식 캐시를 일봉 신호 인터페이스로 전달하는 데이터 어댑터.
- `app/rs_equity_map_run.py`: 72개 구성, 주식 체결·비용·사이징 시뮬레이터, 청크 저장/재개 및 메타데이터.
- `full_runs/US_[abc]_daily_cases_*.csv.gz`, `full_runs/KR_[abc]_daily_cases_*.csv.gz`: 원시 평가표. 시장별 127개 청크.
- `full_runs/US_meta.json`, `full_runs/KR_meta.json`: 실행 범위, 실패 목록, 윈도, 청크 목록.
- `full_runs/US_summary.json`, `full_runs/KR_summary.json`: 전체 결과의 집계와 OOS 상위 목록.
- `full_runs/lookahead_perturbation.json`: 두 시장 19,026회 미래 OHLCV 교란 테스트 결과.
- `strategy_scope_audit.json`: 원본 등록 패밀리 98개의 그리드 크기·시간대·fidelity·출처, 남은 family 신호 16개 사유 및 12개 보충시험 기록. 이 수는 모든 코인 연구 스크립트의 완료 수가 아니다.
- `full_runs/round10_policy_transfer.json`, `ROUND10_POLICY_TRANSFER.md`: Round10 136개 메타정책 × 양 시장 × 두 비용의 544개 곡선과 결과 분석.
- `full_runs/round10_prefix_validation.json`: 544개 곡선 지표 재계산/미래교란 prefix 검사 및 590개 종목·signal-family prefix 비교.
- `full_runs/round11_policy_transfer.json`, `ROUND11_POLICY_TRANSFER.md`: Round11 34개 계좌 정책 × 양 시장 × 두 비용의 136개 곡선과 적응·비용 가정 분석.
- `full_runs/round11_prefix_validation.json`: Round11 136개 곡선 지표 재계산/미래교란 prefix 검사 및 354개 signal-family prefix 비교.
- `full_runs/showdown_policy_transfer.json`, `SHOWDOWN_POLICY_TRANSFER.md`: showdown의 112개 구성 × 양 시장 × 두 비용, 총 448개 daily return/equity 곡선.
- `full_runs/showdown_prefix_validation.json`: 448개 곡선 지표 재계산과 미래교란 prefix 검사.
- `full_runs/round3_policy_transfer.json`, `ROUND3_POLICY_TRANSFER.md`: Round3 53개 선언 정책실험과 기준선 3개, 양 시장·비용별 총 224개 곡선.
- `full_runs/round3_prefix_validation.json`: Round3 224개 곡선 재계산 및 590개 신호·224개 계좌 prefix 미래변형 검사.
- `full_runs/round4_robustness_transfer.json`, `ROUND4_ROBUSTNESS_TRANSFER.md`: Round4 고정 winner 5개, 8개 독립 기간, 거래·종목 집중도 및 민감도 결과. 20개 전체 곡선과 204 replay 기록.
- `full_runs/round5_policy_transfer.json`, `ROUND5_POLICY_TRANSFER.md`: Round5 Champion/N2/N3의 시장·비용별 일별 곡선, 8기간 재실행, 민감도, 집중도와 대체 확인 필터.
- `full_runs/round5_prefix_validation.json`: Round5 1,298개 신호 피처, 12개 전체 곡선, 96개 기간지표, 4개 확인곡선 미래 prefix 검증.
- `full_runs/round6_policy_transfer.json`, `ROUND6_POLICY_TRANSFER.md`: Round6 고정 전략 6개의 주식 프록시 상대성과, Champion 종목 거래비중 제한 및 기간별 결과.
- `full_runs/round6_prefix_validation.json`: Round6 전체 40개 곡선/320개 기간 결과의 독립 재실행과 미래 prefix 검증.
- `full_runs/round4_diagnostic_summary.json`: 원본 Round4 수치기준을 고정 주식 winner에 적용한 불안정 flag와 판정.
- `full_runs/round4_prefix_validation.json`: 거래 원장·곡선 재구성과 236개 신호 및 20개 곡선 미래 prefix 검증.
- `full_runs/volume_portfolio_transfer.json`, `VOLUME_PORTFOLIO_TRANSFER.md`: 거래량 R01–R16 계좌수준 전략 결과 및 방법.
- `full_runs/mach7_portfolio_transfer.json`, `MACH7_PORTFOLIO_TRANSFER.md`: Mach7 포트폴리오 72개 조합의 주식 전이 원시 자산곡선·결과·한계.
- `full_runs/round12_13_policy_transfer.json`, `ROUND12_13_POLICY_TRANSFER.md`: Round12 §§45–51 및 Round13 §§64–68 정책 88개의 비용별 원시 자산곡선과 제한.
- `full_runs/round12_extension_policy_transfer.json`, `ROUND12_EXTENSION_TRANSFER.md`: Round12 §§53–57, §§59–61 정책 59개의 비용별 원시 자산곡선과 제한.
- `full_runs/round13_policy_transfer.json`, `ROUND13_POLICY_TRANSFER.md`: Round13 §§69–76 정책 71개의 비용별 원시 자산곡선 및 분석.
- `full_runs/round13_prefix_validation.json`: Round13 71개 설정·양 시장 미래교란 prefix 검증 결과.
- `full_runs/round14_policy_transfer.json`, `ROUND14_POLICY_TRANSFER.md`: Round14 `plans()` 44개 설정과 비용별 곡선.
- `full_runs/round14_prefix_validation.json`: Round14 44개 설정·양 시장 미래교란 prefix 검증 결과.
- `full_runs/round16_liquidation_proxy_transfer.json`, `ROUND16_LIQUIDATION_PROXY_TRANSFER.md`: Round16 합성 청산근접도 연구의 397개 설정·양 시장·비용별 1,588행과 해석 한계.
- `full_runs/equity_peer_pairs.json`, `EQUITY_PEER_PAIRS_TRANSFER.md`: 코인 pair 신호를 그대로 재현하지 않고 point-in-time 주식 peer로 변환한 별도 달러중립 가설 288행과 결과곡선.
- `full_runs/equity_peer_pairs_validation.json`: 두 시장의 곡선 288개 지표 재계산과 36개 신호 설정의 미래 prefix 교란 검사.
- `full_runs/round16_summary.json`, `full_runs/round16_prefix_validation.json`: 1,588개 곡선의 지표 재계산 검증 및 Round16 397개 설정·양 시장 미래교란 결과.
- `full_runs/psar_native_transfer.json`, `PSAR_NATIVE_TRANSFER.md`: 고정 버전 pandas-ta PSAR의 신호 수준 일봉 전이와 차이·성과·한계.
- `full_runs/psar_native_validation.json`: PSAR 네 자산곡선 지표 재계산 및 양 시장 미래교란 검사.
- `full_runs/trx_dca_swing_transfer.json`, `TRX_DCA_SWING_TRANSFER.md`: 사용자 확정 EMA/DCA/RSI 규칙의 양 시장 계좌수준 다종목 포트폴리오 전이.
- `full_runs/trx_dca_swing_validation.json`: 4개 곡선 재생성·지표 재계산 및 양 시장 미래교란 검증.
- `DATA_AVAILABILITY.md`: KIS 캐시 118개 주식 OHLCV 파일의 시간대 범위 및 intraday 부재 증거.
- `REPORT.md`, `PLAN.md`, `us.json`, `kr.json`, `us.log`, `kr.log`: 기존 S1–S6 범위의 이전 재실행 자료. 이번 98패밀리 전이시험과 혼동하지 않는다.

## 판정

실행 범위 내 일봉 시험, 등록 파라미터와 Round3–6·Round10–14·Round16·showdown 및 PSAR·TRX DCA·peer-pair 보충시험의 미래교란 검사, 결과 파일 검증은 각 명시 범위에서 통과했다. 질문의 문자 그대로인 “모든 코인 전략을 미장·국장에서도 같은 시간대와 원천 조건으로 완전히 재실행”은 **미완료**다. Round7–9 원본 전체 개별 실험 및 Round15 다중검정·모멘텀 로테이션 하위 조합 감사가 남았다. 주식 4시간 OHLCV가 없어 6,342개 시간대 단위가 미평가이고, family 신호 감사표의 16개 미재현 및 등록 family 내부의 근사 구현도 남아 있다. 쇼다운의 선물 유지증거금 규칙은 합성 스트레스일 뿐 주식 브로커 마진콜·강제청산을 검증하지 않는다. PSAR는 고정된 pandas-ta 버전으로 신호를 평가했지만 원본 intrabar trailing stop·위험기반 수량은 완전히 재현되지 않았다. TRX DCA는 한 종목 규칙을 8슬롯 주식 계좌로 옮긴 전이다. Round11의 `large10`은 월별 달러거래대금 상위10으로 대체됐고, 원본 funding cost grid도 주식 비용 구조로 치환되지 않았다. Round4–6은 코인에서 선별된 winner/config를 고정해 평가했을 뿐 stock universe에서 원본 전체 grid를 새로 선별한 연구가 아니다. 따라서 현재 결과는 전략 후보를 실거래에 채택할 근거가 아니며 전 범위 완료로 표현할 수 없다.

### 전용 에이전트 추가 작업: Round7·8·9·15

2026-10-16 미장·국장 전용 에이전트 결과는 [`AGENT_ROUND7_8_9_15_SYNTHESIS.md`](AGENT_ROUND7_8_9_15_SYNTHESIS.md)에 통합했다. Round7은 미장에서 비용별 500개 무작위 대조군과 1,000회 거래수익률 bootstrap을 계산했고, 국장에서는 500개 대조군·14개 leave-out·미래변조/prefix 2회를 수행했으나 bootstrap은 엔진이 거래별 원장을 제공하지 않아 미실행이다. 두 시장 모두 Round8의 151개 설정은 인벤토리만 작성했고 평가 0개, Round9 재생 0개, Round15 시장별 가설 재검정 0개다. 특히 미장 Round7 causal prefix 검사는 미실행이다. 따라서 이 추가 작업도 남은 시나리오를 전부 완료한 것으로 보지 않는다.

### 보충 실행: 계좌 기반 거래량 라운드

2026-10-14에 원본 거래량 연구의 R01–R16 계좌 수준 규칙을 별도 주식 이식으로 실행했다. 미국과 한국 각각 16개 라운드, 2개 비용 조건을 사용해 64행을 저장했으며 원시 결과·시점 가정·제한은 [`VOLUME_PORTFOLIO_TRANSFER.md`](VOLUME_PORTFOLIO_TRANSFER.md)에 기록했다. 표에 요약한 기본 비용은 미국 KIS 0.36% 편도, 한국 기본 수수료·세금·슬리피지다. 이는 등록된 98패밀리 그리드 결과에 소급 합산하지 않았다. 특히 상위 CAGR 조합의 MDD가 22–40%였고, 사후 선택과 현재 캐시 유니버스의 생존편향이 있으므로 우위 증거로 보지 않는다. 이 보충 시험은 23개 미재현 분류 중 거래량 계좌 기반 규칙 2개를 해소한다.

### 보충 실행: Mach7 계좌 할당

원본 Mach7 포트폴리오 72개 조합도 미국·한국 일봉에 별도 이식했다. 시장별 144행(72조합 × 2비용), 총 288행과 일별 자산곡선을 저장했다. 종가 확정 신호 다음 시가 체결, OHLC stop-first, 비용을 반영해 같은 종가 신호·체결 문제를 피했다. `btc_sma200`은 주식 동일가중 프록시로 대체한 근사다. 시장별 최고 OOS CAGR은 미국 33.9%(MDD 32.7%), 한국 31.8%(MDD 38.2%)였지만 72개 중 사후 선택한 값이며, 한국 해당 조합 전체 MDD는 58.2%였다. 방법과 전 조합 결과는 [`MACH7_PORTFOLIO_TRANSFER.md`](MACH7_PORTFOLIO_TRANSFER.md)에 기록했다. 이 항목도 전체 전수시험 완료를 의미하지 않는다.

### 보충 실행: Round11 계좌 정책

Round11 `configs()`에서 사전 선언된 34개 정책을 양 시장·2개 비용 조건으로 실행해 총 136개 원시 자산곡선을 저장했다. 미래 OHLC를 3배, 거래량을 7배로 바꾼 테스트에서 신호 피처 354개 및 계좌곡선 136개의 과거 prefix가 모두 일치했고 저장 지표 재계산도 통과했다. 전체 CAGR 중앙값은 미국 0.36% 비용 조건에서 3.77%, 저비용에서 8.02%; 한국 기본에서 5.47%, 슬리피지 2배에서 4.29%였다. 그러나 중앙 MDD는 각각 31.5–41.0%로 높다. BTC 상태는 합성 주식 프록시, `large10`은 월별 달러거래대금 상위10으로 대체했다. funding rate 시나리오도 주식 비용과 등가가 아니어서 이식하지 않았다. 상세는 [`ROUND11_POLICY_TRANSFER.md`](ROUND11_POLICY_TRANSFER.md)에 기록했다.

### 보충 실행: 모멘텀 로테이션 쇼다운

원본 `crypto_strategy_showdown.py`의 필터된 112개 레짐·손실제한·레버리지 조합을 양 시장·두 비용으로 평가해 448곡선을 저장했다. 미래구간 가격 3배·거래량 7배 교란에서 모든 과거 prefix가 일치했고 지표를 원수익률에서 재계산했다. 비용별 CAGR 중앙값은 미국 -11.09%/1.52%, 한국 2.11%/-1.22%였고 MDD 중앙값은 43.9–67.2%였다. 선물 0.5% 유지증거금 청산 규칙을 그대로 주식 리스크라고 해석하지 않고 합성 계산으로 표시했다. 주식 대차·브로커 증거금·시장별 강제청산 룰이 없어 실거래 레버리지 안전성은 검증되지 않았다. 상세는 [`SHOWDOWN_POLICY_TRANSFER.md`](SHOWDOWN_POLICY_TRANSFER.md)에 기록했다.

### 보충 실행: Round12 §§45–61 및 Round13 §§64–68 계좌 정책

원본 그룹 함수의 Round12 §§45–51 47개와 Round13 §§64–68 41개 등 88개를 비용별 시험해 352행을 저장했다. Round12 §§53–57 및 §§59–61 59개는 236행, Round13 §§69–72 및 §§73–76 71개는 284행, Round14 `plans()` 44개는 176행, Round16 `plans()` 397개는 1,588행을 추가했다. 원시 곡선은 각 `full_runs/*policy_transfer.json` 파일에 저장했다. Round13·14·16 설정의 미래교란 검사는 각 `round*_prefix_validation.json`에 있다. 각 보충 보고서에 원본 범위·방법·한계를 기록했고 성과 지표는 곡선에서 재계산해 대조했다. Round12 §§45–61 선언 조합 106개, Round13 §§64–76 조합 112개, 현재 Round14 계획 44개 및 현재 Round16 계획 397개는 평가됐지만 저장소 전체의 모든 전략 변형이라는 뜻은 아니다. Round16 결과의 청산대는 주식 실제 청산가격이 아니라 합성 OHLC 프록시다. BTC 조건은 합성 주식 프록시이고 현재 캐시 유니버스의 생존편향도 계속된다.
