"""Strategy registry — pairs each Strategy class with its native timeframe and the
indicator-enrichment function it needs, so app/compare.py can iterate uniformly."""
from __future__ import annotations

from app.indicators import add_indicators
from app.more_indicators import (
    add_bb_macd_indicators,
    add_dual_thrust_indicators,
    add_ema_cross_indicators,
    add_rsi2_indicators,
)
from app.strategies import BollingerMacdStrategy, DualThrustStrategy, EmaCrossStrategy, Rsi2MeanReversionStrategy
from app.strategy import RegimeSwitchStrategy
from app.swing_indicators import add_donchian_indicators, add_donchian_indicators_fast, add_ma_pullback_indicators
from app.swing_strategies import DonchianTrendStrategy, MaPullbackFastSwingStrategy, MaPullbackSwingStrategy
from app.extra_indicators import add_range_reversion_indicators, add_supertrend_indicators
from app.extra_strategies import RangeReversionStrategy, SupertrendStrategy

# (표시용 이름, Strategy 클래스, 캔들 주기, 지표 계산 함수)
STRATEGIES = [
    ("regime_switch", RegimeSwitchStrategy, "15m", add_indicators),
    ("ema_cross", EmaCrossStrategy, "4h", add_ema_cross_indicators),
    ("rsi2_meanrev", Rsi2MeanReversionStrategy, "4h", add_rsi2_indicators),
    ("bb_macd_adx", BollingerMacdStrategy, "4h", add_bb_macd_indicators),
    ("dual_thrust", DualThrustStrategy, "1h", add_dual_thrust_indicators),
    # 스윙/포지션 트레이딩 (보유기간 며칠~수개월) — 위 5개는 전부 시간~하루 단위 보유였다.
    ("donchian_trend", DonchianTrendStrategy, "1d", add_donchian_indicators),
    ("ma_pullback_swing", MaPullbackSwingStrategy, "1d", add_ma_pullback_indicators),
    # 거래빈도를 높인 fast 변형 — 표본 부족 문제 완화용 (며칠~몇 주 보유로 목표를 낮춤)
    ("donchian_trend_fast", DonchianTrendStrategy, "1d", add_donchian_indicators_fast),
    ("ma_pullback_fast", MaPullbackFastSwingStrategy, "1d", add_ma_pullback_indicators),
    # "다른 봇들은 왜 잘 되나" 비교군 확장 — 유명 추세추종 지표 + 그리드봇 근사
    ("supertrend", SupertrendStrategy, "4h", add_supertrend_indicators),
    ("range_reversion", RangeReversionStrategy, "4h", add_range_reversion_indicators),
]

# 전략별로 추가 검증할 "더 짧은 주기" 변형 (app/full_search.py 접근법 3).
# add_indicators/add_*_indicators는 내부에서 1h로 리샘플하는 로직이 주기와 무관하게 동작하므로
# 별도 수정 없이 그대로 재사용 가능 — 데이터만 다른 주기로 받아오면 됨.
TIMEFRAME_VARIANTS: dict[str, list[str]] = {
    "regime_switch": ["5m"],
    "ema_cross": ["1h"],
    "rsi2_meanrev": ["1h"],
    "bb_macd_adx": ["1h"],
    "dual_thrust": ["30m"],
    "supertrend": ["1h"],
    "range_reversion": ["1h"],
}
