"""마하세븐 눌림목 3기법(이평선/RSI/볼린저밴드 눌림목) 지표 모듈.
100만원으로 100억 만든 트레이더의 손실방지+감정배제+확률 높은 자리 진입 원칙 기반.
세 기법 모두 공통 규칙: 손익비 1.5 고정(손절폭 대비 익절폭 1.5배).
"""
from __future__ import annotations

import numpy as np
import pandas as pd


def _ema(series: pd.Series, length: int) -> pd.Series:
    """Exponential Moving Average."""
    return series.ewm(span=length, adjust=False).mean()


def _rsi(series: pd.Series, length: int = 14) -> pd.Series:
    """Relative Strength Index (RSI)."""
    delta = series.diff()
    gains = delta.where(delta > 0, 0)
    losses = -delta.where(delta < 0, 0)
    avg_gain = gains.ewm(span=length, adjust=False).mean()
    avg_loss = losses.ewm(span=length, adjust=False).mean()
    rs = avg_gain / avg_loss
    return 100 - (100 / (1 + rs))


def _sma(series: pd.Series, length: int) -> pd.Series:
    """Simple Moving Average."""
    return series.rolling(length).mean()


def _bollinger_bands(series: pd.Series, length: int = 20, std_dev: float = 2.0) -> tuple[pd.Series, pd.Series, pd.Series]:
    """Bollinger Bands: (lower, mid, upper)."""
    mid = _sma(series, length)
    std = series.rolling(length).std()
    upper = mid + (std * std_dev)
    lower = mid - (std * std_dev)
    return lower, mid, upper


def _williams_bullish_fractal(low: pd.Series) -> pd.Series:
    """Williams Bullish Fractal: 가운데 봉 저가가 좌우 2봉 저가보다 모두 낮음."""
    result = pd.Series(False, index=low.index)
    for i in range(2, len(low) - 2):
        if (
            low.iloc[i] < low.iloc[i - 2]
            and low.iloc[i] < low.iloc[i - 1]
            and low.iloc[i] < low.iloc[i + 1]
            and low.iloc[i] < low.iloc[i + 2]
        ):
            result.iloc[i] = True
    return result


def add_mach7_ma_pullback(
    frame: pd.DataFrame,
    ema_fast: int = 20,
    ema_mid: int = 50,
    ema_slow: int = 100,
    pullback_window: int = 5,
    exit_ema: int = 50,
) -> pd.DataFrame:
    """이평선 눌림목 기법 (수정판).

    구버전 버그: (1) `_williams_bullish_fractal` 이 봉 i 를 i+1,i+2 로 판정 → 미래참조,
    (2) `FRACTAL_LOW` 를 `.bfill()` 로 채워 미래 프랙탈 저점을 앞당김 → 미래참조 +
    손절가가 진입가보다 높아지는 경우 발생, (3) `ENTRY = 정배열 & (Close > FRACTAL_LOW)` 는
    상승추세면 매 봉 참 → 실제 '눌림' 을 안 봄. 결과: 종목당 수백 매매, 연환산 -20~-33%.

    수정 로직 (전부 과거 정보만 사용):
      - 추세: EMA_fast > EMA_mid > EMA_slow 정배열
      - 눌림: 최근 pullback_window 봉 중 저가가 EMA_fast 이하로 눌린 적 있음
      - 방아쇠: 오늘 종가 > EMA_fast 이고 종가 > 전봉 고가 (반등 확인봉)
      - 손절: 최근 pullback_window 봉 스윙 저점 (시뮬레이터가 진입가보다 낮을 때만 진입)
      - 청산: 종가 < EMA_exit (추세 이탈). 손절/익절은 시뮬레이터에서 처리.
    """
    out = frame.copy()
    out["EMA_FAST"] = _ema(out["Close"], length=ema_fast)
    out["EMA_MID"] = _ema(out["Close"], length=ema_mid)
    out["EMA_SLOW"] = _ema(out["Close"], length=ema_slow)
    out["EMA_EXIT"] = _ema(out["Close"], length=exit_ema)

    aligned = (out["EMA_FAST"] > out["EMA_MID"]) & (out["EMA_MID"] > out["EMA_SLOW"])

    # 눌림: 최근 pullback_window 봉(오늘 포함) 안에서 저가가 EMA_FAST 이하로 내려온 적 있는지.
    dipped = (out["Low"] <= out["EMA_FAST"])
    dipped_recent = dipped.rolling(pullback_window, min_periods=1).max().astype(bool)

    # 반등 확인봉: 종가가 EMA_FAST 재돌파 + 전봉 고가 상향(반전 캔들)
    reclaim = (out["Close"] > out["EMA_FAST"]) & (out["Close"] > out["High"].shift(1))

    out["ENTRY_SIGNAL"] = aligned & dipped_recent & reclaim
    out["EXIT_SIGNAL"] = out["Close"] < out["EMA_EXIT"]
    out["STOP_PRICE"] = out["Low"].rolling(pullback_window, min_periods=1).min()

    # 하위호환: 기존 컬럼명 참조 코드가 있을 수 있어 별칭 유지
    out["EMA20"] = out["EMA_FAST"]
    out["EMA50"] = out["EMA_MID"]
    out["EMA100"] = out["EMA_SLOW"]

    return out


def add_mach7_rsi_pullback(frame: pd.DataFrame) -> pd.DataFrame:
    """RSI 눌림목 기법: 10/34 정배열 + RSI(14) 55선 상향돌파."""
    out = frame.copy()
    out["EMA10"] = _ema(out["Close"], length=10)
    out["EMA34"] = _ema(out["Close"], length=34)
    out["RSI14"] = _rsi(out["Close"], length=14)

    # 10일선 > 34일선 (상승추세 확인)
    out["TREND_UP"] = out["EMA10"] > out["EMA34"]

    # RSI 55선 상향돌파 감지 (이전 < 55, 현재 >= 55)
    rsi_above_55 = out["RSI14"] >= 55
    rsi_was_below_55 = out["RSI14"].shift(1) < 55
    out["RSI_CROSSOVER"] = rsi_above_55 & rsi_was_below_55.fillna(False)

    # 진입신호: 상승추세 + RSI 55선 상향돌파
    out["ENTRY_SIGNAL"] = out["TREND_UP"] & out["RSI_CROSSOVER"]

    # 청산신호: RSI가 55선 아래로 내려감
    out["EXIT_SIGNAL"] = out["RSI14"] < 55

    # 손절가는 진입가 근처에서 설정 (최근 5봉의 저점)
    out["STOP_PRICE"] = out["Low"].rolling(5, min_periods=1).min()

    return out


def add_mach7_bb_pullback(frame: pd.DataFrame) -> pd.DataFrame:
    """볼린저밴드 눌림목 기법: 상단 터치 + 눌림목 저점 돌파."""
    out = frame.copy()
    bb_lower, bb_mid, bb_upper = _bollinger_bands(out["Close"], length=20, std_dev=2.0)
    out["BB_LOWER"] = bb_lower
    out["BB_MID"] = bb_mid
    out["BB_UPPER"] = bb_upper

    # 상단 터치 감지 (종가 >= 상단의 99% 이상)
    out["TOUCHED_UPPER"] = out["Close"] >= out["BB_UPPER"] * 0.99

    # 최근 10봉 내 상단 터치 기록
    out["TOUCHED_UPPER_RECENT"] = out["TOUCHED_UPPER"].rolling(10, min_periods=1).max().astype(bool)

    # 눌림목 저점: 최근 5봉의 최저가 (또는 프랙탈 저점)
    out["PULLBACK_LOW"] = out["Low"].rolling(5, min_periods=1).min()

    # 진입신호: 최근에 상단 터치 있었고, 현재가가 눌림목 저점 위로 반등
    out["ENTRY_SIGNAL"] = out["TOUCHED_UPPER_RECENT"] & (out["Close"] > out["PULLBACK_LOW"])

    # 청산신호: 가격이 하단 아래로 내려감
    out["EXIT_SIGNAL"] = out["Close"] < out["BB_LOWER"]

    # 손절가 (눌림목 저점)
    out["STOP_PRICE"] = out["PULLBACK_LOW"]

    return out
