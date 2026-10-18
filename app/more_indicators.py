"""Indicator sets for the comparison strategies in app/strategies.py — kept separate
from app/indicators.py (which serves the original RegimeSwitchStrategy) since each
archetype here runs on its own native timeframe with a different indicator set."""
from __future__ import annotations

import pandas as pd
import pandas_ta as ta

from app.regime import regime_series


def _first_matching(frame: pd.DataFrame, prefix: str) -> pd.Series:
    # pandas-ta 컬럼 이름 규칙이 마이너 버전마다 바뀌어서 정확한 문자열 대신 접두사로 찾는다.
    return frame[[c for c in frame.columns if c.startswith(prefix)][0]]


def add_ema_cross_indicators(frame: pd.DataFrame) -> pd.DataFrame:
    out = frame.copy()
    out["EMA9"] = ta.ema(out["Close"], length=9)
    out["EMA21"] = ta.ema(out["Close"], length=21)
    out["SMA200"] = ta.sma(out["Close"], length=200)
    out["REGIME"] = regime_series(out.index)
    return out


def add_rsi2_indicators(frame: pd.DataFrame) -> pd.DataFrame:
    out = frame.copy()
    out["RSI2"] = ta.rsi(out["Close"], length=2)
    out["SMA5"] = ta.sma(out["Close"], length=5)
    out["SMA200"] = ta.sma(out["Close"], length=200)
    out["ATR14"] = ta.atr(out["High"], out["Low"], out["Close"], length=14)
    out["REGIME"] = regime_series(out.index)
    return out


def add_bb_macd_indicators(frame: pd.DataFrame) -> pd.DataFrame:
    out = frame.copy()
    bbands = ta.bbands(out["Close"], length=20, std=2)
    out["BB_LOWER"] = _first_matching(bbands, "BBL_")
    out["BB_UPPER"] = _first_matching(bbands, "BBU_")
    macd = ta.macd(out["Close"], fast=12, slow=26, signal=9)
    out["MACD"] = _first_matching(macd, "MACD_")
    out["MACD_SIGNAL"] = _first_matching(macd, "MACDs_")
    adx_frame = ta.adx(out["High"], out["Low"], out["Close"], length=14)
    out["ADX14"] = _first_matching(adx_frame, "ADX_")
    out["ATR14"] = ta.atr(out["High"], out["Low"], out["Close"], length=14)
    out["REGIME"] = regime_series(out.index)
    return out


def add_dual_thrust_indicators(frame: pd.DataFrame, length: int = 21) -> pd.DataFrame:
    out = frame.copy()
    # 고전 Dual Thrust 정의: Range = max(HH-LC, HC-LL), 전일(직전 N봉) 기준값 사용.
    hh = out["High"].rolling(length).max().shift(1)
    lc = out["Close"].rolling(length).min().shift(1)
    hc = out["Close"].rolling(length).max().shift(1)
    ll = out["Low"].rolling(length).min().shift(1)
    out["DT_RANGE"] = pd.concat([hh - lc, hc - ll], axis=1).max(axis=1)
    out["ATR14"] = ta.atr(out["High"], out["Low"], out["Close"], length=14)
    out["REGIME"] = regime_series(out.index)
    return out
