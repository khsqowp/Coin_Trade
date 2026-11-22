"""올웨더 종가 기준 레짐 점수와 히스테리시스."""
from __future__ import annotations

import numpy as np
import pandas as pd


def score_regime(close: pd.DataFrame, market: str, index_symbol: str,
                 sector_symbols: list[str], macro_symbol: str) -> pd.DataFrame:
    """매 행은 해당 거래일 종가까지만 사용한 T/S/M/B/X 및 CRASH 신호."""
    idx = close[index_symbol]
    sma50, sma100, sma200 = idx.rolling(50, min_periods=50).mean(), idx.rolling(100, min_periods=100).mean(), idx.rolling(200, min_periods=200).mean()
    T = pd.Series(np.where(idx > sma200, 1, -1), index=idx.index, dtype=float).where(sma200.notna())
    S = pd.Series(np.where(sma50 > sma200, 1, -1), index=idx.index, dtype=float).where(sma200.notna())
    mom126 = idx.pct_change(126)
    M = pd.Series(np.where(mom126 > 0, 1, -1), index=idx.index, dtype=float).where(mom126.notna())
    sector_above = pd.DataFrame({s: close[s] > close[s].rolling(100, min_periods=100).mean() for s in sector_symbols})
    sector_ready = pd.DataFrame({s: close[s].rolling(100, min_periods=100).mean().notna() for s in sector_symbols})
    breadth = sector_above.where(sector_ready).sum(axis=1).div(sector_ready.sum(axis=1).replace(0, np.nan))
    B = pd.Series(np.select([breadth >= .6, breadth <= .4], [1, -1], default=0), index=idx.index, dtype=float).where(breadth.notna(), 0)
    macro_ret = close[macro_symbol].pct_change(63)
    if market.upper() == "KR":
        X = pd.Series(np.where(macro_ret > .03, -1, 0), index=idx.index, dtype=float).fillna(0)
    else:
        X = pd.Series(np.where(macro_ret < -.03, -1, 0), index=idx.index, dtype=float).fillna(0)
    crash_ret = idx.pct_change(14)
    out = pd.DataFrame({"T": T, "S": S, "M": M, "B": B, "X": X}, index=idx.index)
    out["score"] = out[["T", "S", "M", "B", "X"]].sum(axis=1, min_count=3)
    out["crash"] = crash_ret.le(-.10).fillna(False)
    out["crash_release"] = crash_ret.ge(0).fillna(False)
    out["raw"] = np.select([out.score >= 3, out.score <= -2], ["BULL", "BEAR"], default="RANGE")
    out.loc[out.score.isna(), "raw"] = "RANGE"
    return out


def apply_hysteresis(scores: pd.DataFrame, days: int = 5) -> pd.DataFrame:
    """보통 전환은 N연속 확인, CRASH는 즉시 BEAR, 14일 수익률 양전 시 해제."""
    if days < 1:
        raise ValueError("days는 1 이상이어야 합니다")
    result = scores.copy()
    states, current, candidate, count, crash_on = [], "RANGE", None, 0, False
    for _, row in scores.iterrows():
        was_crash = crash_on
        if bool(row.get("crash", False)):
            crash_on = True
        elif crash_on and bool(row.get("crash_release", False)):
            crash_on = False
        raw = "BEAR" if crash_on else str(row.get("raw", "RANGE"))
        released = was_crash and not crash_on
        if crash_on:
            current, candidate, count = "BEAR", None, 0
        elif released:
            current, candidate, count = raw, None, 0
        elif raw == current:
            candidate, count = None, 0
        else:
            if raw != candidate:
                candidate, count = raw, 1
            else:
                count += 1
            if count >= days:
                current, candidate, count = raw, None, 0
        states.append(current)
    result["regime"] = states
    return result


def classify(close: pd.DataFrame, market: str, index_symbol: str, sector_symbols: list[str], macro_symbol: str, days: int = 5) -> pd.DataFrame:
    return apply_hysteresis(score_regime(close, market, index_symbol, sector_symbols, macro_symbol), days)
