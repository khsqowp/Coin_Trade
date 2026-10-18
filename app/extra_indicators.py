"""Indicator sets for app/extra_strategies.py — Supertrend(추세추종) and 레인지/그리드 근사
전략. 다른 유명 오픈소스 봇들과 마케팅용 "그리드봇" 계열까지 비교군에 넣기 위해 추가.
"""
from __future__ import annotations

import pandas as pd
import pandas_ta as ta

SUPERTREND_LENGTH = 10
SUPERTREND_MULTIPLIER = 3
GRID_LOOKBACK = 30


def add_supertrend_indicators(frame: pd.DataFrame) -> pd.DataFrame:
    out = frame.copy()
    st = ta.supertrend(out["High"], out["Low"], out["Close"],
                        length=SUPERTREND_LENGTH, multiplier=SUPERTREND_MULTIPLIER)
    out["SUPERT"] = st[[c for c in st.columns if c.startswith("SUPERT_")][0]]
    out["SUPERTD"] = st[[c for c in st.columns if c.startswith("SUPERTd_")][0]]
    out["ATR14"] = ta.atr(out["High"], out["Low"], out["Close"], length=14)
    out["VOL_MEDIAN20"] = out["Volume"].rolling(20).median()
    adx_frame = ta.adx(out["High"], out["Low"], out["Close"], length=14)
    out["ADX14"] = adx_frame[[c for c in adx_frame.columns if c.startswith("ADX_")][0]]
    return out


def add_range_reversion_indicators(frame: pd.DataFrame) -> pd.DataFrame:
    """단순화된 그리드봇 근사 지표 — 실제 그리드봇의 다중 레벨 동시 보유 대신, 채널 하단에서
    사서 중단에서 파는 단일 포지션으로 근사한다(app/extra_strategies.py 독스트링 참고)."""
    out = frame.copy()
    out["RANGE_UPPER"] = out["High"].rolling(GRID_LOOKBACK).max()
    out["RANGE_LOWER"] = out["Low"].rolling(GRID_LOOKBACK).min()
    out["RANGE_MID"] = (out["RANGE_UPPER"] + out["RANGE_LOWER"]) / 2
    out["ATR14"] = ta.atr(out["High"], out["Low"], out["Close"], length=14)
    return out
