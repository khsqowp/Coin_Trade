"""us_daily_scan.py / us_intraday_risk.py가 공유하는 감시종목 리스트/설정.

app/us_swing_search.py의 STOCK_UNIVERSE(38종목)를 그대로 재사용한다. kr_watchlist.py와
동일한 계좌를 공유하므로(같은 모의투자 계좌, 국장/미장 나눠 씀) 예산 배분 로직도 동일 패턴.
"""
from __future__ import annotations

from app.us_swing_search import STOCK_UNIVERSE  # noqa: F401

CANO = "50203118"
ACNT_PRDT_CD = "01"

STOP_PCT = 0.02
RISK_PER_TRADE = 0.0025
MAX_POSITION_FRACTION = 0.20
MAX_CONCURRENT_POSITIONS = 5
MIN_USABLE_BARS = 250

# 계좌 예수금은 KRW 단위 하나뿐이라(별도 USD 잔고 없음), 매수 가능 USD 규모를 가늠하려면
# KRW->USD 환산이 필요하다. 실시간 환율 조회 API를 아직 안 붙여서 대략치(1,400원/달러)로
# 근사한다 — 실제 주문 체결가는 물론 거래소 실시간 호가로 나가므로 이 근사는 예산 상한 계산에만 쓰인다.
FX_KRW_PER_USD = 1400
# 국장(kr_watchlist.CAPITAL_BUDGET_KRW)과 합쳐 계좌 1천만원을 반반 나눈 미장 쪽 기준예산.
# 국장과 마찬가지로 여기에 누적 실현손익(us_state.py의 realized_pnl_usd)을 더한 값이 실제 예산이다.
CAPITAL_BUDGET_USD = 5_000_000 / FX_KRW_PER_USD
