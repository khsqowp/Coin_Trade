# 차트 예측 데이터·리플레이 패키지

이 패키지는 Binance USDT-M 공개 캔들 수집, 결정적 특징 생성, 예측 저장과 채점을 수행한다. 예측기 자체를 호출하지 않으며 API 키와 주문 기능을 사용하지 않는다. 모든 P2 검증은 저장된 캔들 DB와 테스트 픽스처를 사용한다.

## 기본 흐름

프로젝트 루트에서 실행한다.

```bash
python -m chart_predictor.cli collect --symbol BTCUSDT --days 30
python -m chart_predictor.cli replay --split dev --symbols 10 --tf 5m
```

Replay는 `chart_predictor/data/batches/` 아래에 특징 배치 JSON과 manifest를 쓴다. 각 배치에는 심볼, 분봉, 앵커, 과거 캔들에서 계산한 특징과 `input_sha256`만 있다. 미래 캔들이나 실현 결과는 포함하지 않는다. 에이전트는 배치마다 고정 스키마 prediction JSON을 별도 파일로 작성한다. `anchor_time`은 앵커 완료 시각(ms)이며 `created_at`은 앵커보다 앞서거나 뒤여도 허용된다.

```bash
python -m chart_predictor.cli ingest --file prediction.json --split dev
python -m chart_predictor.cli score
python -m chart_predictor.cli report
```

`ingest`는 앵커까지의 캔들 해시, 필드, 범위, 열거값, 방향별 무효화 위치를 검증한 뒤 `predictions.sqlite`에 추가한다. 예측 행은 SQLite 트리거로 UPDATE/DELETE가 거부된다. `score`는 완료된 미래 봉만 사용하고 horizon 캔들이 부족하거나 빠져 있으면 `UNSCORABLE`로 기록한다. `report`는 M1 Wilson 95% 구간, 커버리지, 신뢰도 임계값별 M4, 심볼·분봉·앵커 날짜 군집 결과, 베이스라인 비교를 출력한다. 결과에는 성공 판정을 표시하지 않는다.


포지션 손익 채점은 기본적으로 앵커 다음 첫 봉의 시가에 진입하고 그 봉부터 무효화/청산을 검사한다. `score_prediction(..., entry_delay_candles=0)`은 레거시 모드로 앵커 종가 진입을 사용한다. 청산가는 실제 진입가와 레버리지로 계산한다. 한 봉에서 손절과 청산 수준을 모두 넘으면 진입가에 더 가까운 불리한 수준을 먼저 체결한다. 봉 시가가 불리한 수준을 이미 넘어 갭이 발생하면 수준 가격 대신 시가로 체결한다. 방향·목표·경로 지표 M1-M3는 진입 지연과 무관하게 앵커 가격을 기준으로 계산한다.

## 저장과 분할

`candles.sqlite`는 수집 캔들, `predictions.sqlite`는 append-only 예측과 별도 점수, `trials.sqlite`는 모델/프롬프트/코드/분할/가설별 누적 시험과 봉인 데이터 접근 시도를 보관한다. 실험 횟수는 `cumulative_trial_count()`로 확인한다. `sealed_registry.json`은 최초 생성 때 freeze timestamp를 고정한다. 해당 시각 이후 앵커를 개발/검증용으로 읽으려 하면 접근 시도를 trials에 기록하고 예외를 낸다. 이 파일을 이동하거나 시각을 바꾸면 경계 보장이 달라지므로 보존해야 한다.

시간 분할은 시간순 앞 60% 개발, 뒤 40% 검증이며 앵커는 horizon 이상 간격을 둔다. 심볼은 SHA-256 기반으로 70% 개발 / 30% held-out으로 결정적으로 나눈다. 표본은 같은 앵커 날짜에 상관될 수 있어 날짜 군집 결과도 함께 본다. 봉인 구간 수치만으로 성공을 주장할 수 있으며, 이 패키지는 자동 성공 판정을 하지 않는다.

## 기존 P1 명령

```bash
python -m chart_predictor.cli universe --top 100
python -m chart_predictor.cli collect --symbol BTCUSDT --days 30
python -m chart_predictor.cli update --symbol BTCUSDT
python -m chart_predictor.cli features --symbol BTCUSDT --tf 5m --anchor 2026-11-14T00:50:00Z
```

특징 생성은 전달된 캔들까지만 계산하고 입력 행의 SHA-256을 출력한다. 리샘플은 UTC 경계의 완전한 버킷만 반환한다. 5m, 30m, 60m 입력에는 구성된 1분봉이 모두 있어야 한다.

## P3a 기준선과 에이전트 워크플로

실제 LLM 예측 결과가 없는 P3a 이전 단계에서 label 정의를 한 번 조정했다. flat은 `abs(price(+H)-anchor) <= 0.25 * ATR14 * sqrt(H_candles)`로 정의하며 `H_candles = horizon_minutes / timeframe_minutes`다. 이 정의 변경은 README와 `trials.sqlite` hypothesis에 남는다. flat 비율이 목표 범위(약 15-30%) 밖이어도 이후 다시 맞추지 않고 관측 비율을 보고한다.

캔들 DB는 P3a 명령에서 SQLite 읽기 전용으로 연다. 개발 분할 기준선은 1m/5m/30m/60m별 비중첩 앵커에서 고정 seed로 표본을 뽑고 momentum, seeded random, flat, always_up, always_down 다섯 기준선을 같은 scorer와 비용 설정(진입 지연 1개 캔들, taker 0.05% 및 slippage 0.02% 각 편도)으로 평가한다. 요청한 표본 수를 채우지 못하는 셀은 제외하고 timeframe별 제외 셀을 보고한다. `coverage`는 emitted 대비 채점 가능한 예측 비율이며 `trade_coverage`는 side가 none이 아닌 거래 비율이다. 기준선 DB와 report는 결정적 run ID의 `data/runs/<run_id>/` 안에 격리한다. run ID에는 설정, 코드 버전, 심볼별 행 수/최소·최대 시각의 SHA-256 지문이 들어간다. 파일 크기와 수정 시각은 report 메타데이터로 기록하지만 지문에는 포함하지 않는다. 지문과 설정이 같은 완료 run은 재사용하며 `--force`는 기존 디렉터리를 보존하고 별도 디렉터리를 만든다. 불완전한 run 디렉터리 충돌은 오류로 중단한다. 보고서는 3-class M1과 up/down binary 정확도(모멘텀/상수 방향 기준선), 실현 label 분포, 날짜 군집을 포함한다.

```bash
python -m chart_predictor.cli baselines --split dev --per-cell 30 --seed 1
# 기존 결과를 보존하고 새 디렉터리에서 강제 재실행
python -m chart_predictor.cli baselines --split dev --per-cell 30 --seed 1 --force
python -m chart_predictor.cli make-agent-tasks --split dev --per-cell 30 --seed 1 --batch-size 20
```

## P4 신호 상한 프로브

`probe`는 dev 심볼의 비중첩 앵커에서 up/down·확장·추세지속 라벨을 만들고, 시간순 분할과 이중(초기 dev 심볼 학습, 후기 보류 심볼 시험) 분할로 L2 로지스틱 회귀 및 HistGradientBoostingClassifier를 평가한다. BTC/ETH, 시장 breadth, UTC 시간, 변동성·거래량·일/주 가격 맥락은 앵커까지의 캔들만 사용한다. 피처 캐시와 수치 보고서는 지문별 `data/probe/`에 저장하며 trials에 `signal ceiling probe v2 (market context, double holdout)` 가설을 기록한다. validation/sealed 자료는 열지 않는다.

`probe-p4c`는 기존 P4 fingerprint feature cache로 5개 expanding walk-forward test fold를 계산하고 날짜 cluster bootstrap과 Holm 조정을 출력한다. 학습 모델은 fold당 최대 8,000개 deterministic 표본을 사용하며 test는 전체 행을 사용한다. Expansion 경계는 각 학습 구간의 중앙값으로 정한다. Continuation 전략은 다음 봉 시가 진입, 2 ATR 손절, 편도 수수료 0.05%와 슬리피지 0.02%로 평가한다.

```bash
python -m chart_predictor.cli probe --split dev --seed 1
```

에이전트는 각 `task_XXXX.json`의 feature 항목에 대응하는 Prediction 객체 배열 하나를 `out_<model>_task_XXXX.json`으로 저장한다. 각 객체의 `symbol`, `timeframe`, `anchor_time`, `input_sha256`은 작업 항목과 일치해야 하며, 필드는 `schema.py` 정의를 따른다. 명확한 우위가 없으면 `side=none`, confidence 약 0.5를 사용한다.

```bash
python -m chart_predictor.cli ingest-dir --dir data/agent_tasks/<run_id> --model claude
python -m chart_predictor.cli score --db data/pred_llm.sqlite
python -m chart_predictor.cli report --db data/pred_llm.sqlite
```

`ingest-dir`는 응답 파일마다 검증하고 오류 이유를 파일별로 반환하며, 결과는 기준선 DB와 분리된 `data/pred_llm.sqlite`에 저장한다. 기준선 재실행은 `data/runs/<run_id>/pred.sqlite`를 사용하며 기존 `data/pred_baselines.sqlite`는 사용하지 않는다. 이 검증 요청에서는 dev만 선택하며 validation이나 sealed 기간을 실행하지 않는다. 이 보고서는 평가 수치를 제시하며 성공 여부를 판정하지 않는다.
