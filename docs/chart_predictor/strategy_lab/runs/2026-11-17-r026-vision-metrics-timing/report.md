# R026 — Vision metrics timestamp audit

**결론: 이 표본에서는 OI와 taker-flow 모두 `create_time` 당시에 이용 가능하다고 간주하면 안 된다. 보수적으로 `available_at = create_time + 5 minutes`를 적용한다.** 전략 성과시험은 실행하지 않았다.

## 결과

| 입력 필드 | 표본 | 관측 결과 | 잠정 시간 규칙 |
|---|---:|---|---|
| `sum_open_interest` | BTC/ETH × 3일 = 1,728개 | Vision 값 전부가 같은 거래소 REST 경로의 `timestamp = create_time + 5m` 값과 정확 일치. 같은 라벨 시각 대조의 심볼-날짜별 최대 상대오차 0.326%–0.845%. | 표시 시각보다 5분 늦게 사용 |
| `sum_taker_long_short_vol_ratio` | BTC/ETH × 2일 = 1,152개 | 원시 aggTrades로 계산한 동일 표시 구간 buy/sell base-volume 비율과 일치도가 가장 높음: 중앙 상대오차 0.020%–0.032%, p95 0.858%–1.046%. 하지만 하루당 11–16개는 상대오차 1% 초과, 최대 오차 7.7%–17.0%. ±5분 이동의 중앙 오차는 29.9%–34.4%. | 같은 행 라벨은 5분 구간의 시작으로 해석. 구간 종료 뒤(라벨+5분)만 사용 |

각 metrics 파일은 288개 유일·정시 행으로 00:00–23:55 UTC 격자를 완전히 채웠다. OI REST 응답은 날짜 경계 레코드를 포함해 symbol-day마다 289개였다. Vision ZIP 및 aggTrades ZIP 체크섬은 모두 일치했다.

## 판정과 한계

이 데이터 품질 결과는 2026-06-25 전후의 taker-flow **라벨 규약이 바뀌었다는 주장**을 이 두 코인·이틀 표본에서는 지지하지 않는다. 그러나 OI의 6월 시간 의미는 이 검증에 포함되지 않았다. OI 검증은 2026-10-31~11-02의 연속 3일뿐이며, API와 Vision 모두 Binance가 발행한 자료다. 다른 날짜·심볼·상위 트레이더 비율 필드는 미검증이다. 동일-bin taker 비율에도 상대오차가 큰 일부 행이 있으므로 그 필드의 데이터 정확도 전체가 확정된 것은 아니다.

OI 재고 충격 후 구조적 해소 가설은 성과시험 등록 대상으로 승격하지 않는다. 추가 필요 조건: 장기 metrics 수집·결측 감사, 여러 레짐과 날짜의 availability 검증, PIT 계약 유니버스·펀딩/비용·격리 OOS 경계, 명시적인 충격/해소 규칙과 기존 R021/R023/R005 대비 ablation 계획. 현재 성과 적격 전략은 코인 0개다.

## 재현

`scripts/research/verify_vision_metrics_timing.py`는 다운로드된 입력 ZIP/JSON을 로컬에서 읽고 네트워크를 호출하지 않는다. 공개 입력은 `/private/tmp/vision_metrics_probe/`와 `/private/tmp/oi_timestamp_probe/`에 보관되어 있으며 Git에는 추가하지 않았다.

```bash
python3 scripts/research/verify_vision_metrics_timing.py \
  --metrics-dir /private/tmp/oi_timestamp_probe \
  --rest-dir /private/tmp/oi_timestamp_probe \
  --aggtrades-dir /private/tmp/oi_timestamp_probe

python3 scripts/research/verify_vision_metrics_timing.py \
  --metrics-dir /private/tmp/vision_metrics_probe \
  --rest-dir /private/tmp/vision_metrics_probe \
  --aggtrades-dir /private/tmp/vision_metrics_probe
```

Complete aggregate metrics and archive SHA-256 values: [`results.json`](results.json). OI REST response JSON files are transient local inputs; refresh them only within Binance's documented latest-30-day window.
