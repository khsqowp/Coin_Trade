# RB500-KR 결과 (TRAIN 전용, TRAIN_ONLY_NOT_G) — 2026-11-25

- 500설정 전부 실행(실패 0). 장부 2689→3189행, Bonferroni N=3189(1.568e-5). **합격 설정 0개.**
- 실패 항목(500 중): Sharpe≥1 실패 500, PF 347, MDD 320, 기대값 262, Wilson 244. Bonferroni 통과 6개는 Sharpe 0.93~0.96으로 미달.
- 양수 계열: XLOWVOL(32/32), XMOM(47/48), X52WH(24/24), REV(140/144). 음수 계열: TOM, VOLSURGE, DONCH, VBRK, MATREND.
- 상위: #59 XLOWVOL 519거래 PF2.65 +806bp / #3 XMOM 591거래 PF1.86 +766bp / #63 XLOWVOL 1535거래 PF2.01 +626bp p=7e-6 Sharpe0.95.
- **신뢰 불가 사유**: KR 일봉 패널이 기업행위 미조정(513종목 중 355개에 ±30% 초과 일변화). 기대값 중앙값 150bp·최고 800bp 이상은 비현실적(미조정 잔재·상폐 공백·생존편향 추정). 기존 KR R3/R5(E3-J) 결과도 같은 패널이라 재검토 필요.
- 한계: 자기상관 미보정 p, RC/SPA·무작위 귀무·비용×2·1봉지연 미실시, 종목당 1/558 가중으로 Sharpe 구조적 저하.
- 실행 문제: 경로 접두사 중단(1차), numpy bool 직렬화 중단(2차), 기업행위 미조정 발견 후 무효(3차, 상위행 진단 열람 사실 공개), 4차 정상 기록. 파일: PREREG_RB500_KR.md, search_kr_r14_batch.py, runs/rb500_kr_train_20261125T012642Z.csv.
