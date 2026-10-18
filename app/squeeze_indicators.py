"""200일선(장기추세)+20일선(단기타점) '스퀴즈 플레이' 지표 — 유튜브 이평선 매매법 요약
기반. 영상에 정확한 숫자 기준이 안 나와서 다음과 같이 해석해서 정했다:

  - 추세 필터: 종가가 SMA200 위 = 강세(롱 허용), 아래 = 매매 안 함(롱 온리 전제)
  - 스퀴즈: |SMA20-SMA200|/SMA200 이 SQUEEZE_THRESHOLD_PCT 이하로 좁혀진 상태
    ("두 선 사이 이격 공간이 좁아졌다")
  - 돌파 진입: 최근 SQUEEZE_LOOKBACK봉 안에 스퀴즈가 있었고, 종가가 SMA20을 상향돌파
    ("좁아졌다가 가격이 돌파하는 지점")
  - 청산: 종가가 SMA20 아래로 마감(영상이 강조하는 "이평선 돌파 등 명확한 기준" 기계적 적용)
  - 횡보 필터: 최근 WHIPSAW_LOOKBACK봉 안에 SMA20/SMA200 자체가 서로 WHIPSAW_MAX_CROSSES회
    넘게 교차했으면 신규진입 보류("횡보장에선 이평선이 여러번 교차하며 신호가 꼬인다")
"""
from __future__ import annotations

import pandas as pd
import pandas_ta as ta

SQUEEZE_THRESHOLD_PCT = 3.0
SQUEEZE_LOOKBACK = 10
WHIPSAW_LOOKBACK = 20
WHIPSAW_MAX_CROSSES = 3


def add_squeeze_indicators(frame: pd.DataFrame) -> pd.DataFrame:
    out = frame.copy()
    out["SMA20"] = ta.sma(out["Close"], length=20)
    out["SMA200"] = ta.sma(out["Close"], length=200)
    out["GAP_PCT"] = (out["SMA20"] - out["SMA200"]).abs() / out["SMA200"] * 100
    out["SQUEEZE"] = out["GAP_PCT"] <= SQUEEZE_THRESHOLD_PCT
    out["SQUEEZE_RECENT"] = out["SQUEEZE"].rolling(SQUEEZE_LOOKBACK, min_periods=1).max().astype(bool)

    ma20_above_ma200 = out["SMA20"] > out["SMA200"]
    ma_crossed = ma20_above_ma200 != ma20_above_ma200.shift(1)
    out["WHIPSAW_COUNT"] = ma_crossed.rolling(WHIPSAW_LOOKBACK, min_periods=1).sum()
    out["CHOPPY"] = out["WHIPSAW_COUNT"] > WHIPSAW_MAX_CROSSES

    above20 = out["Close"] > out["SMA20"]
    crossed_up_ma20 = above20 & ~above20.shift(1).fillna(False).astype(bool)
    out["ENTRY_SIGNAL"] = (
        crossed_up_ma20 & (out["Close"] > out["SMA200"]) & out["SQUEEZE_RECENT"] & ~out["CHOPPY"]
    )
    out["EXIT_SIGNAL"] = ~above20
    return out
