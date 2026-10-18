"""kr_daily_scan.py / kr_intraday_risk.py가 공유하는 감시종목 리스트.

app/ema_cross_watchlist.py의 STOCK_UNIVERSE(45종목, 섹터 분산)를 그대로 재사용한다.
"""
from __future__ import annotations

from app.ema_cross_watchlist import STOCK_UNIVERSE  # noqa: F401

CANO = "50203118"
ACNT_PRDT_CD = "01"

STOP_PCT = 0.02              # EmaCrossStrategy.STOP_PCT와 동일
RISK_PER_TRADE = 0.0025      # EmaCrossStrategy.RISK_PER_TRADE와 동일
MAX_POSITION_FRACTION = 0.20  # 백테스트(0.95)와 달리 실전은 종목당 최대 비중을 낮춰 분산 강제
MAX_CONCURRENT_POSITIONS = 5
MIN_USABLE_BARS = 250

# 모의투자 계좌(1천만원)를 국장/미장 테스트로 반반 나눠 쓰기로 함 — 계좌 자체는 공용이라
# 예수금만 보면 국장 쪽이 원하는 만큼 다 써버릴 수 있어서, 이 기준액에 국장 전략의 누적
# 실현손익(kr_state.py의 realized_pnl_krw)을 더한 값을 실제 예산으로 쓴다 — 벌면 예산이 늘고
# 잃으면 줄어든다. "투입한 원가(entry_cost 합)"가 이 예산을 넘지 않는 선에서만 신규 진입한다.
CAPITAL_BUDGET_KRW = 5_000_000
