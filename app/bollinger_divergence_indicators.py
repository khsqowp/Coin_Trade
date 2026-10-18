"""1만원 룰 데이트레이딩 전략용 지표 모듈.

1분봉 차트에서:
- 볼린저밴드(20,2): 진입신호(밴드 벗어남 또는 터치)
- 이격도 다이버전스: 가격과 이동평균의 이격이 반대 방향으로 움직임 감지
- 당일청산: 진입 후 같은 날(같은 세션) 내에 완전히 청산하는 조건
- 일일 진입 횟수 제한: 선택적 최대 1회 진입
"""
from __future__ import annotations

import pandas as pd
import pandas_ta as ta


def _first_matching(frame: pd.DataFrame, prefix: str) -> pd.Series:
    """pandas-ta 컬럼명 접두사로 일치하는 첫 번째 컬럼 반환."""
    matches = [c for c in frame.columns if c.startswith(prefix)]
    if not matches:
        raise ValueError(f"No column matching prefix '{prefix}'")
    return frame[matches[0]]


def add_bollinger_divergence_indicators(
    frame: pd.DataFrame,
    bb_length: int = 20,
    bb_std: float = 2.0,
    ma_length: int = 20,
) -> pd.DataFrame:
    """1만원 룰 데이트레이딩 지표 추가.

    Parameters
    ----------
    frame : pd.DataFrame
        OHLCV 데이터 (Open, High, Low, Close, Volume, timestamp 인덱스)
    bb_length : int
        볼린저밴드 기간 (기본 20)
    bb_std : float
        볼린저밴드 표준편차 (기본 2.0)
    ma_length : int
        이격도 계산용 이동평균 기간 (기본 20, 볼린저밴드와 동일)

    Returns
    -------
    pd.DataFrame
        원본 frame에 이하 컬럼 추가:
        - BB_UPPER: 볼린저밴드 상단
        - BB_LOWER: 볼린저밴드 하단
        - BB_MIDDLE: 볼린저밴드 중앙(SMA)
        - MA: 이격도 계산용 이동평균
        - DIVERGENCE: 가격과 MA의 이격도 (Close - MA)
        - DIVERGENCE_CHANGE: 이격도 변화율 (현봉 이격도 - 직전봉 이격도)
        - BB_UPPER_TOUCH: Close > BB_UPPER (상단 터치)
        - BB_LOWER_TOUCH: Close < BB_LOWER (하단 터치)
    """
    out = frame.copy()

    # 볼린저밴드
    bbands = ta.bbands(out["Close"], length=bb_length, std=bb_std)
    out["BB_UPPER"] = _first_matching(bbands, "BBU_")
    out["BB_LOWER"] = _first_matching(bbands, "BBL_")
    out["BB_MIDDLE"] = _first_matching(bbands, "BBM_")  # 중앙값 (SMA)

    # 이격도: 가격과 이동평균의 차이
    out["MA"] = ta.sma(out["Close"], length=ma_length)
    out["DIVERGENCE"] = out["Close"] - out["MA"]
    out["DIVERGENCE_CHANGE"] = out["DIVERGENCE"].diff()

    # 볼린저밴드 터치 신호
    out["BB_UPPER_TOUCH"] = out["Close"] > out["BB_UPPER"]
    out["BB_LOWER_TOUCH"] = out["Close"] < out["BB_LOWER"]

    return out


def detect_divergence_reversal(
    divergence_series: pd.Series,
) -> pd.Series:
    """이격도 역행(다이버전스) 감지.

    이격도가 특정 방향으로 확대되다가 반대 방향으로 축소하기 시작하는 구간을 감지.
    - 상단 터치 후 이격도가 축소 → 상단 이격도 다이버전스
    - 하단 터치 후 이격도가 확대 역방향 → 하단 이격도 다이버전스

    Parameters
    ----------
    divergence_series : pd.Series
        DIVERGENCE 컬럼 (Close - MA)

    Returns
    -------
    pd.Series[bool]
        True: 역행 감지, False: 그 외
    """
    # 이격도 변화율
    div_change = divergence_series.diff()

    # 2봉 이상의 추이 확인: 이전이 증가 또는 감소 추세였는가
    prev_div_change = div_change.shift(1)

    # 부호가 바뀌는 순간 역행으로 간주
    reversing = (div_change * prev_div_change) < 0

    return reversing


def detect_entry_signals(frame: pd.DataFrame) -> pd.DataFrame:
    """진입 신호 생성 (여러 조건 결합).

    Parameters
    ----------
    frame : pd.DataFrame
        bollinger_divergence_indicators 를 통해 지표가 이미 계산된 프레임

    Returns
    -------
    pd.DataFrame
        원본 frame에 이하 컬럼 추가:
        - ENTRY_BB_BREAKOUT: 볼린저밴드 상/하단 돌파 (진입 신호 1)
        - ENTRY_DIVERGENCE_CROSS: 이격도 역행 (진입 신호 2)
        - ENTRY_SIGNAL: 위 둘 중 하나 이상 만족 시 True
    """
    out = frame.copy()

    # 신호 1: 볼린저밴드 돌파 (상단 또는 하단)
    out["ENTRY_BB_BREAKOUT"] = out["BB_UPPER_TOUCH"] | out["BB_LOWER_TOUCH"]

    # 신호 2: 이격도 역행
    out["ENTRY_DIVERGENCE_CROSS"] = detect_divergence_reversal(out["DIVERGENCE"])

    # 종합 진입 신호
    out["ENTRY_SIGNAL"] = out["ENTRY_BB_BREAKOUT"] | out["ENTRY_DIVERGENCE_CROSS"]

    return out


def detect_exit_signals(
    frame: pd.DataFrame,
    entry_price_series: pd.Series | None = None,
) -> pd.DataFrame:
    """청산 신호 생성.

    Parameters
    ----------
    frame : pd.DataFrame
        지표가 계산된 프레임
    entry_price_series : pd.Series, optional
        진입가 시리즈. 제공 시, 손절/익절 조건에 사용 가능.
        제공하지 않으면 기술적 신호만 사용.

    Returns
    -------
    pd.DataFrame
        원본 frame에 이하 컬럼 추가:
        - EXIT_MEAN_REVERSION: MA 복귀 신호 (이격도 < 0에서 > 0 또는 그 반대)
        - EXIT_SIGNAL: 청산 신호
    """
    out = frame.copy()

    # 청산 신호: 이격도가 0선을 재교차 (평균으로의 복귀)
    div = out["DIVERGENCE"]
    out["EXIT_MEAN_REVERSION"] = div.diff() != 0  # 영값이 변할 때
    out.loc[div.isna() | div.shift(1).isna(), "EXIT_MEAN_REVERSION"] = False

    # 단순 구현: 이격도 부호가 바뀔 때 청산
    out["EXIT_MEAN_REVERSION"] = (div.shift(1) * div) < 0
    out.loc[div.isna() | div.shift(1).isna(), "EXIT_MEAN_REVERSION"] = False

    out["EXIT_SIGNAL"] = out["EXIT_MEAN_REVERSION"]

    return out
