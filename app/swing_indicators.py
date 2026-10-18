"""Indicator sets for 스윙/포지션 트레이딩 전략 (app/swing_strategies.py).
일봉(1d) 기준 — 기존 15m~4h 전략군(app/strategy.py, app/strategies.py)과는 다른 시간 축을 쓴다.

거래 빈도를 늘려달라는 요청(최소 며칠~수개월 보유는 4.5년 데이터로는 표본이 너무 적었음)에
맞춰 각 지표 세트마다 "기본"(느림, 터틀 시스템1 스타일)과 "fast"(빠름, 터틀 시스템2 스타일)
두 가지 lookback 세트를 둔다 — 같은 Strategy 클래스가 두 세트를 모두 읽을 수 있도록 컬럼
이름은 동일하게 유지한다.
"""
from __future__ import annotations

import pandas as pd
import pandas_ta as ta

ENTRY_LOOKBACK = 55  # 터틀 시스템1 진입 채널 (기본, 느림)
EXIT_LOOKBACK = 20   # 터틀 시스템1 이탈 채널
ENTRY_LOOKBACK_FAST = 20  # 터틀 시스템2 진입 채널 (fast, 거래빈도 ↑)
EXIT_LOOKBACK_FAST = 10   # 터틀 시스템2 이탈 채널


def _donchian(frame: pd.DataFrame, entry_lookback: int, exit_lookback: int) -> pd.DataFrame:
    out = frame.copy()
    out["SMA200"] = ta.sma(out["Close"], length=200)
    out["ATR14"] = ta.atr(out["High"], out["Low"], out["Close"], length=14)
    out["DONCHIAN_HIGH"] = out["High"].rolling(entry_lookback).max()
    out["DONCHIAN_LOW"] = out["Low"].rolling(exit_lookback).min()
    return out


def add_donchian_indicators(frame: pd.DataFrame) -> pd.DataFrame:
    return _donchian(frame, ENTRY_LOOKBACK, EXIT_LOOKBACK)


def add_donchian_indicators_fast(frame: pd.DataFrame) -> pd.DataFrame:
    return _donchian(frame, ENTRY_LOOKBACK_FAST, EXIT_LOOKBACK_FAST)


def add_ma_pullback_indicators(frame: pd.DataFrame) -> pd.DataFrame:
    out = frame.copy()
    out["SMA50"] = ta.sma(out["Close"], length=50)
    out["SMA200"] = ta.sma(out["Close"], length=200)
    out["RSI14"] = ta.rsi(out["Close"], length=14)
    out["RSI7"] = ta.rsi(out["Close"], length=7)
    out["ATR14"] = ta.atr(out["High"], out["Low"], out["Close"], length=14)
    return out
