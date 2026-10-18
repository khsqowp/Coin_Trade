"""공돌투자자 눌림목 반등매매 지표 — 직장인 트레이더의 시스템 트레이딩 전략 재현.
핵심: 상승흐름 중 일시적 투매(단기 이평선 이탈)를 공략하는 반등 매매.

진입 로직:
  - 종가가 SMA(5또는10)일선 아래로 내려갔던 상태(눌림목/투매)
  - 다시 종가가 SMA(5또는10) 위로 상향돌파(반등 신호)
  - 선택: 거래대금 필터 — 최근 거래대금이 60일 평균의 N배 이상인 종목만 (재료 연속성 근사)

청산 로직:
  - 재이탈: 종가가 다시 SMA(5또는10) 아래로 하향이탈
  - 또는 고정 손익비: 진입가 대비 -3%(손절) 또는 +6%(익절)

파라미터화된 설정으로 SMA5 vs SMA10, 거래대금 필터 유무를 비교 가능하게 함."""
from __future__ import annotations

import pandas as pd
import pandas_ta as ta


def add_pullback_rebound_indicators(
    frame: pd.DataFrame,
    ma_length: int = 5,
    volume_filter_enabled: bool = False,
    volume_lookback: int = 60,
    volume_multiplier: float = 1.5,
) -> pd.DataFrame:
    """눌림목 반등 매매 지표를 프레임에 추가한다.

    Args:
        frame: OHLCV 데이터프레임(Open, High, Low, Close, Volume)
        ma_length: 이평선 길이(5 또는 10)
        volume_filter_enabled: 거래대금 필터 적용 여부
        volume_lookback: 거래대금 평균값 계산 기간(일)
        volume_multiplier: 거래대금 필터 배수(예: 1.5 = 평균의 1.5배 이상)

    Returns:
        ENTRY_SIGNAL과 EXIT_SIGNAL을 포함한 보강 프레임.
    """
    out = frame.copy()

    # 이평선 계산
    out[f"SMA{ma_length}"] = ta.sma(out["Close"], length=ma_length)

    # 거래대금(달러환산) = Volume * Close
    out["Turnover"] = out["Volume"] * out["Close"]
    if volume_filter_enabled:
        out["Turnover_MA60"] = out["Turnover"].rolling(volume_lookback, min_periods=1).mean()
        out["Turnover_Ratio"] = out["Turnover"] / out["Turnover_MA60"]
        out["HOT_STOCK"] = out["Turnover_Ratio"] >= volume_multiplier
    else:
        out["HOT_STOCK"] = True

    # 가격과 이평선 관계
    above_ma = out["Close"] > out[f"SMA{ma_length}"]
    previously_above = above_ma.shift(1).fillna(False).astype(bool)

    # 진입 신호: 이평선 아래에 있다가 위로 상향돌파 + 거래대금 조건
    crossed_up = above_ma & ~previously_above
    out["ENTRY_SIGNAL"] = crossed_up & out["HOT_STOCK"]

    # 청산 신호: 이평선 아래로 하향이탈 (손익비는 시뮬레이션에서 처리)
    out["EXIT_SIGNAL"] = ~above_ma

    return out
