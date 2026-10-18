"""Indicator calculations for the regime-switching strategy (docs/trading-agent-plan.md).

Uses pandas-ta for the standard indicators instead of hand-rolling ADX/RSI/ATR/Bollinger
math from scratch. Column names are kept as valid Python identifiers because
backtesting.py exposes DataFrame columns as attributes on `Strategy.data`.
"""
from __future__ import annotations

import pandas as pd
import pandas_ta as ta

from app.regime import regime_series


def add_indicators(frame: pd.DataFrame) -> pd.DataFrame:
    out = frame.copy()

    adx_frame = ta.adx(out["High"], out["Low"], out["Close"], length=14)
    out["ADX14"] = adx_frame[[c for c in adx_frame.columns if c.startswith("ADX_")][0]]
    out["RSI3"] = ta.rsi(out["Close"], length=3)
    out["ATR14"] = ta.atr(out["High"], out["Low"], out["Close"], length=14)

    # pandas-ta 이름 규칙이 마이너 버전마다 바뀌어서(예: BBL_20_2.0 vs BBL_20_2.0_2.0)
    # 정확한 문자열 대신 접두사로 찾는다.
    bbands = ta.bbands(out["Close"], length=20, std=2)
    out["BB_LOWER"] = bbands[[c for c in bbands.columns if c.startswith("BBL_")][0]]
    out["BB_MID"] = bbands[[c for c in bbands.columns if c.startswith("BBM_")][0]]
    out["BB_UPPER"] = bbands[[c for c in bbands.columns if c.startswith("BBU_")][0]]

    out["VWAP"] = ta.vwap(out["High"], out["Low"], out["Close"], out["Volume"])
    out["VOL_MEDIAN20"] = out["Volume"].rolling(20).median()
    out["HIGHEST20"] = out["High"].rolling(20).max()
    out["LOWEST5"] = out["Low"].rolling(5).min()

    # 1시간봉 추세 필터: 1시간으로 리샘플링한 뒤 계산하고, 15분봉 인덱스로 forward-fill
    # 정렬한다 — 계획서의 "1시간봉 EMA20 > EMA50" 조건을 15분봉 실행 흐름에 결합하기 위함.
    hourly_close = out["Close"].resample("1h").last().dropna()
    ema20_1h = ta.ema(hourly_close, length=20)
    ema50_1h = ta.ema(hourly_close, length=50)
    out["EMA20_1H"] = ema20_1h.reindex(out.index, method="ffill")
    out["EMA50_1H"] = ema50_1h.reindex(out.index, method="ffill")

    # 경제팀 오버레이 필터의 백테스트용 근사치 — app/regime.py 상단 주석 참고 (실제 파이프라인의
    # 과거 데이터가 아니라 리서치 기반 재구성).
    out["REGIME"] = regime_series(out.index)

    return out
