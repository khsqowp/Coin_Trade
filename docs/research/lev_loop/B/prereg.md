# PRE-REGISTRATION (BACKTESTER-B, lev_loop round 1) - 레버리지/리스크통제 설계

작성: 코드 실행(설계 셀) 이전. 해시는 `hashes.log` 에 기록. 이후 수정은 "AMENDMENT(버그)" 라벨로 추가만 가능하며 셀 추가 금지.
렌즈: growth-optimal(Kelly) 레버리지 + 리스크통제 설계. 연구 전용(라이브 코드/상태 무접촉, 커밋/푸시 없음).

## 0. 사전 공개 (내가 이미 본 것)
- 리뷰 문서(tp_loop/review/review.md)의 V0 레버 표(2.0x~4.0x, 일종가 킬 기준)와 그 한계(킬 카오스, 3위상 동기화, 일종가 킬 vs 15초 킬 불일치)를 읽었다.
- 엔진 개발/디버깅 중 **단일 경로 전기간 스모크 실행**을 했다: V0 (T0/T1/T2), 래더 1~2종, 볼타깃 1종, 테일타깃 1종, 1.5x 스트레스(버그 발견). 숫자는 설계 선택에 쓰지 않았으나, 아래 두 가지는 이 스모크가 계기였다: (i) 롤링 HWM(30일) 도입(전체기간 HWM 래더는 노출이 낮은 상태에 갇힘), (ii) 신호 트리거를 T1 외에 T2(시간봉 종가) 추가 (T1 은 V0 를 21회 킬/최종 0.45배로 만드는 극단 보수 모델이라는 관찰).
- IS(2022-01~2024-06) 구간에서 1x gross 정규화 유닛 변동성 ≈ 25%/년(24.9~25.4%)을 측정해 볼타깃 눈금을 정했다(vt=1.25 ~ lev5 상당). OOS 데이터는 설계/눈금 선택에 쓰지 않았다.
- V0 선택 자체(lb14/킬35/쿨14)가 전체 구간을 보고 정해졌다는 알려진 편향이 있다.

## 1. 엔진 / 재현
- `app/rs_lev_b_engine.py` (rs_final_engine._sim 에서 파생, 기능 OFF 시 비트 동일). 재현 증명: `lev_loop/B/check_v0.py` (24개 경로 eq_close/eq_worst/kill 이 `Sim.run(crash_flat=True, lev4, deploy.95, kill.35, cool14)` 와 `np.array_equal`). 최종자산 위상0/1/2 = 14.5027 / 18.4064 / 15.8459, kills 10/9/9 (리뷰와 일치).
- 신호/체결/비용/펀딩/크래시필터/패널은 V0 와 동일. 비용 0.10%/편도(+킬/래더 슬리피지 0.20% 명목), 펀딩 실측.
- **트리거 기준**(모든 설계에 3종 모두 실행): T1 = 시간봉 **최악 equity**(롱=L, 숏=H 동시) 대 HWM [PRIMARY, 지정 사양]; T2 = 시간봉 종가 mark equity [현실적 중간 추정, 병행 보고]; T0 = 일 종가(V0 관례, secondary).
- **체결 모델**(T1/T2): 트리거 시각의 포지션 mark 는 직전 시간봉 종가→(T1: 불리가격/T2: 종가) 선형 경로가 임계 equity 와 교차하는 지점(first-passage 보간) + 슬리피지 0.20% 명목 + 비용. 스트레스 sc4 는 불리가격 전량 체결.
- **HWM**: 킬 = 시간봉 종가 mark 로 갱신되는 전체기간 HWM(킬/쿨다운 시 리셋, V0 와 동일). 래더 = 직전 30일(roll) HWM(래더 설계만).
- **청산(liquidation)**: 매 시간 교차마진 worst-case equity(롱 L/숏 H, 펀딩 반영) <= 유지증거금. (a) 계단식: 포지션 명목(USDT, 계좌 시작자본 E0=10,000 USDT 가정) <=5만:0.5%, <=25만:1%, <=100만:2.5%, 초과:5%. (b) 보수 일괄 3%. 청산 발생 경로는 즉시 종료(최종자산 0).
- AMENDMENT(버그, 실행 전): 1.5x 변동성 스트레스의 펀딩 환산에서 최초 종가(first) 나눗셈 누락 수정. 설계 셀 실행 전에 발견/수정.

## 2. 지터 프로토콜
- 시작 오프셋 0..39일 x 리밸런스 위상 0..2 = 120 경로 / (설계, 트리거, 윈도우, 시나리오).
- 윈도우: IS = 2022-01-01..2024-06-30, OOS = 2024-07-01..패널 끝(2026-10-09) (새로 시작, 자본 1), FULL = 2022-01-01.. (참고용; 선택에 미사용).
- 지표(경로 분포: 중앙값, p10, p90): 최종자산, 연환산 로그성장 = ln(W_T)/yrs, 종가 MDD, 일중 MDD(worst), 킬 횟수, 래더(디레버) 횟수, 시간평균 gross, 최대 gross, 최대 1시간 손실, 청산 경로 비율.
- 시나리오: sc0 기본(계단식 MMR), sc1 기본(3% 일괄), sc2 변동성 x1.5 (로그가격 x1.5, 3% 일괄), sc3 비용 x2(수수료/슬리피지/펀딩 x2, 3% 일괄), sc4 불리가격 체결(T1 만, 3% 일괄). 성과 지표는 sc0 기준.

## 3. 사전등록 설계 (20개, 아래가 전부; 이후 추가 금지)
| ID | lev | kill | cool | 추가 파라미터(pb) | ladder rd -> rm | 설명 |
|---|---|---|---|---|---|---|
| D00 | 4.0 | 0.35 | 14 | - | - | V0 live: lev4 x.95, kill35 cool14, no norm |
| D01 | 4.0 | 0.35 | 14 | norm=1 | - | control: V0 + gross normalisation at each rebalance |
| D02 | 5.0 | 0.35 | 14 | - | - | blunt kill, lev5 |
| D03 | 6.0 | 0.35 | 14 | - | - | blunt kill, lev6 |
| D04 | 3.0 | 0.35 | 14 | - | - | REFERENCE ONLY (lowers leverage, owner-ineligible): lev3 |
| D05 | 4.0 | 0.35 | 3 | - | - | V0 cooldown 3d |
| D06 | 4.0 | 0.35 | 7 | - | - | V0 cooldown 7d |
| D07 | 4.0 | 0.35 | 14 | norm=1, re_m=0.5, re_days=14 | - | V0 + re-entry at 0.5x size for 14d |
| D08 | 4.0 | 0.45 | 7 | norm=1, nr=2, hw=30, rec_frac=0.5 | [0.15, 0.25] -> [0.5, 0.25] | ladder A (15%->.5, 25%->.25, 30d roll HWM), hard kill45 cool7, lev4 |
| D09 | 4.0 | 0.45 | 7 | norm=1, nr=3, hw=30, rec_frac=0.5 | [0.1, 0.2, 0.3] -> [0.7, 0.4, 0.2] | ladder B (10/20/30 -> .7/.4/.2), hard kill45 cool7, lev4 |
| D10 | 5.0 | 0.45 | 7 | norm=1, nr=2, hw=30, rec_frac=0.5 | [0.15, 0.25] -> [0.5, 0.25] | ladder A at lev5 |
| D11 | 6.0 | 0.45 | 7 | norm=1, nr=2, hw=30, rec_frac=0.5 | [0.15, 0.25] -> [0.5, 0.25] | ladder A at lev6 |
| D12 | 4.0 | 0.35 | 14 | norm=1, vt=1.25, vcap=5.0 | - | vol target 1.25 (=lev5 at 25% unit vol), cap5 |
| D13 | 4.0 | 0.35 | 14 | norm=1, vt=1.5, vcap=6.0 | - | vol target 1.50, cap6 |
| D14 | 4.0 | 0.35 | 14 | norm=1, vt=1.0, vcap=4.0 | - | vol target 1.00, cap4 (pure de-risk) |
| D15 | 4.0 | 0.45 | 7 | norm=1, vt=1.25, vcap=5.0, nr=2, hw=30, rec_frac=0.5 | [0.15, 0.25] -> [0.5, 0.25] | vol target1.25 cap5 + ladder A |
| D16 | 4.0 | 0.35 | 14 | norm=1, tt=0.45, tw=100000, vcap=6.0 | - | tail target: worst-hour loss <=45% of equity, expanding window, cap6 |
| D17 | 6.0 | 0.35 | 14 | norm=1, expx=0.5 | - | lev6 start, sizing base eq^0.5 (partial compounding) |
| D18 | 4.0 | 0.5 | 14 | - | - | V0 with deeper kill 50% |
| D19 | 4.0 | 0.45 | 7 | norm=1, vt=1.5, vcap=6.0, nr=2, hw=30, rec_frac=0.5 | [0.15, 0.25] -> [0.5, 0.25] | vol target1.50 cap6 + ladder A |
공통: rebal 3d, K 8, deploy 0.95, 크래시필터 ON(V0 동일). norm = 리밸런스마다 전 포지션 균등 스케일해 gross = eq*deploy*lev_eff*m (D00 은 V0 처럼 미정규화).
vt: lev_eff = clip(vt/유닛변동성(20일), 1.0, vcap), warm-up lev 2.0 (유효 10일 미만). tt: lev_eff = clip(tt / (과거 전체 중 최대 '시간당 최악 손실/시작 gross'), 1.0, cap).
D04 는 참조 전용(레버 낮춤 = 소유자 비수용). 나머지 19개가 후보.
추가 분석 B(설계 아님, 청산 경계): D00 구조에서 lev in {2,3,4,5,6,7,8} (T0/T1/T2, 전 시나리오, IS/OOS/FULL) -> 청산 0 인 최대 lev.
추가 분석 A (Kelly): 아래 4절.

시행 수: 설계 20 (비교 19) + 경계분석 7 + Kelly 곡선(통계량 1) = 28. 이웃 셀(선택 설계 +-25%)은 선택 시행이 아니라 강건성 검증.

## 4. 분석 A: 성장최적(Kelly) 노출
- 유닛 시리즈: lev=1, deploy=1.0, norm=1, 킬 없음(kill=1,cool=0), T0, 위상 0/1/2 (오프셋 0), IS / OOS / FULL. 일간 수익 r_t.
- g(f) = 365 * mean ln(1 + f r_t), f in [0.5, 12] 0.25 격자. f* = argmax. 정상 블록 부트스트랩(평균 블록 20일, 2000회, 위상 쌍으로 동일 인덱스)으로 f* 의 5/50/95 백분위, g(f) 밴드.
- 비교: 실현 성장 vs 레버 곡선(분석 B) 의 중앙 로그성장; 킬 없음 vs 킬 있음 사이의 갭 = "킬 카오스 비용".
- 해석 규칙(고정): f* 의 95% 신뢰구간 하한이 4 이상이면 ">4x 가 성장 면에서 가능", 상한이 4 미만이면 "4x 초과 정당화 불가", 그 외 구분 불가.
- 시간당 단일 갭 손실(hloss)에서 청산 안전 상한 gross 를 별도 계산: f_liq = (1 - m)/ (최대 1시간 유닛 손실), m = 3%.

## 5. 허용(ADMISSIBLE) 규칙
설계는 IS 및 OOS 모두에서, 트리거 T1 과 T2 모두, 시나리오 sc0..sc4(T1 만 sc4) 전부 **청산 경로 0/120** 일 때만 허용. T0 와 FULL 은 참고 보고. (D00 자체가 비허용일 수 있고, 그 경우도 그대로 보고.)
적격(ELIGIBLE, 소유자 제약): 명목 lev >= 4.0 AND 해당 윈도우/트리거에서 중앙 시간평균 gross >= 0.90 x D00 중앙값. (미충족 설계는 'leverage-lowering' 라벨.)

## 6. 판정/선택 규칙 (IS 만으로 선택)
1) IS 에서 허용 AND 적격인 후보들 중 T1 과 T2 의 IS 중앙 로그성장 평균이 최대인 설계 X*.
2) "better" = 쌍체 정상 블록 부트스트랩(평균 블록 20일, 2000회, seed 12345; 120경로 평균 일간 로그수익의 D00 대비 차이 x 365) 90% 구간(5~95 백분위) 하한 > 0 이 T1 과 T2 에서 동시. "worse" = 상한 < 0 (T1,T2 동시). 그 외 "not distinguishable".
3) 채택(ADOPT X*) 조건 전부: IS better; OOS 허용 및 적격; OOS better; 이웃 +-25%(모든 파라미터 각각 x0.75, x1.25) 셀의 >=75% 가 IS·OOS 에서 허용 유지 및 D00 대비 차이 부호 +; Reality-Check 헤어컷 후 IS p<0.10.
4) 하나라도 불충족 -> 채택 없음. D00 가 비허용이면 "현 설정은 비허용(수치)" 을 명시하되 채택 없음 시 "keep current (동일 위험 감수)" 로 두고 더 낮은 청산확률 설계는 '레버리지 하향' 으로만 존재함을 보고.
5) 모든 설계에 IS/OOS 별 verdict(better / not distinguishable / worse)와 강도(strongly supported / weak / unknown) 표기. 강도: strongly = IS·OOS·T1·T2 CI 모두 같은 방향, weak = 일부만, unknown = 구분 불가.

## 7. 다중검정 / 강건성
- 헤어컷: White Reality Check 식 max-통계량 부트스트랩(19개 비교, 재중심화, 동일 부트스트랩 인덱스) -> 각 설계 조정 p, 그리고 5% 임계 max 통계량 = 헤어컷.
- PBO: CSCV (S=10 -> 252 조합), 20개 설계의 일간 평균경로 로그수익 (T1, T2 각각, IS 구간).
- 집중도: D00 과 최우수 설계에 대해 상위 5 종목 / 상위 5 거래의 손익 기여 비중(이익 합 대비) 및 상위 5 거래 제거 시 근사 최종자산.
- 한계 사전 명시: 단일 역사, 45개 생존 종목, 위상 비독립(킬 동기화), 시간봉 H/L 로 분 단위 갭/체결 불확실.
