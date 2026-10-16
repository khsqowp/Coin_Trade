"""KR 일봉 로컬 캐시(.kis-cache/KR_*.csv) 로더 — API 호출 없음. 날짜x종목 패널을 만든다."""
from __future__ import annotations

import glob
import os
from dataclasses import dataclass

import numpy as np
import pandas as pd

CACHE = os.environ.get("KR_CACHE_DIR", os.path.join(os.path.dirname(__file__), "..", "..", ".kis-cache"))
MIN_VALUE_WON = 10e8  # 최근 60일 거래대금 중앙값 10억 미만이면 그 시점엔 매매 불가(point-in-time)


@dataclass
class Panel:
    dates: pd.DatetimeIndex
    syms: list
    o: np.ndarray
    h: np.ndarray
    l: np.ndarray
    c: np.ndarray
    v: np.ndarray
    elig: np.ndarray      # 거래 가능 유니버스(유동성+상장 후 충분한 봉)
    tradable: np.ndarray  # 당일 체결 가능(거래량>0, 상하한가 근처 점프 아님)
    slip: np.ndarray      # 종목별 편도 슬리피지(대형 0.05% / 소형 0.10%)


def load() -> Panel:
    frames = {}
    for f in sorted(glob.glob(os.path.join(CACHE, "KR_*.csv"))):
        sym = os.path.basename(f)[3:-4]
        d = pd.read_csv(f, parse_dates=["timestamp"], index_col="timestamp")
        d.index = d.index.tz_localize(None).normalize()
        frames[sym] = d[~d.index.duplicated()]
    dates = sorted(set().union(*[set(d.index) for d in frames.values()]))
    dates = pd.DatetimeIndex(dates)
    syms = list(frames)
    def mat(col):
        return np.column_stack([frames[s][col].reindex(dates).to_numpy(float) for s in syms])
    o, h, l, c, v = (mat(x) for x in ["Open", "High", "Low", "Close", "Volume"])
    val = pd.DataFrame(c * v, index=dates, columns=syms)
    med = val.rolling(60, min_periods=30).median().to_numpy()
    nbars = (~np.isnan(c)).cumsum(axis=0)
    elig = (med >= MIN_VALUE_WON) & (nbars >= 30) & ~np.isnan(c)
    prev = np.vstack([np.full((1, len(syms)), np.nan), c[:-1]])
    jump = np.abs(o / prev - 1)
    tradable = (v > 0) & ~np.isnan(o) & ~(jump >= 0.29)
    big = pd.Series(np.nanmedian(val.tail(750).to_numpy(), axis=0)).fillna(0).to_numpy() >= 500e8
    slip = np.where(big, 0.0005, 0.0010)
    return Panel(dates, syms, o, h, l, c, v, elig, tradable, slip)


def coverage(p: Panel) -> pd.DataFrame:
    rows = []
    for j, s in enumerate(p.syms):
        ok = np.where(~np.isnan(p.c[:, j]))[0]
        gaps = np.diff(p.dates[ok]).astype("timedelta64[D]").astype(int)
        rows.append((s, p.dates[ok[0]].date(), p.dates[ok[-1]].date(), len(ok), int(gaps.max()) if len(gaps) else 0))
    return pd.DataFrame(rows, columns=["sym", "start", "end", "n", "maxgap_days"])
