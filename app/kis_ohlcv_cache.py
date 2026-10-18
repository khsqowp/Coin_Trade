"""KIS 일봉 로컬 캐시 — 종목당 한 번만 받아 CSV로 저장하고 재사용한다.

KIS 모의투자 게이트웨이는 100건/호출 + 호출간 1초 강제라 종목 100여 개를 매 백테스트마다
다시 받으면 30~75분씩 걸린다(문서 실측). 백테스트/스윕은 같은 데이터를 수십 번 읽으므로
디스크 캐시가 필수. DataFrame 계약(Open/High/Low/Close/Volume, tz-aware 오름차순 인덱스)은
app/data.py·kis_data.py와 동일하게 유지한다.

캐시 경로: env KIS_OHLCV_CACHE_DIR (기본 /app/cache). 도커에서 볼륨으로 물려 세션 간 유지.
신선도: 마지막 봉이 N 캘린더일 이내면 그대로 씀(주말·공휴일 감안 기본 4일). refresh=True 로 강제 갱신.
"""
from __future__ import annotations

import datetime as dt
import os
from pathlib import Path

import pandas as pd

from app.kis_data import fetch_ohlcv_kis
from app.kis_overseas_data import fetch_ohlcv_kis_overseas

CACHE_DIR = Path(os.environ.get("KIS_OHLCV_CACHE_DIR", "/app/cache"))
STALE_AFTER_DAYS = int(os.environ.get("KIS_OHLCV_CACHE_STALE_DAYS", "4"))
_COLS = ["Open", "High", "Low", "Close", "Volume"]


def _path(market: str, symbol: str) -> Path:
    return CACHE_DIR / f"{market}_{symbol}.csv"


def _read(path: Path) -> pd.DataFrame:
    df = pd.read_csv(path, parse_dates=["timestamp"], index_col="timestamp")
    if df.index.tz is None:
        df.index = df.index.tz_localize("UTC")
    return df[_COLS]


def _write(path: Path, df: pd.DataFrame) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    out = df[_COLS].copy()
    out.index.name = "timestamp"
    out.to_csv(path)


def _fresh(df: pd.DataFrame) -> bool:
    if df.empty:
        return False
    last = df.index[-1].date()
    return (dt.date.today() - last).days <= STALE_AFTER_DAYS


def cached_ohlcv(
    market: str,
    symbol: str,
    token: str,
    since_iso: str,
    until_iso: str | None = None,
    excd: str = "NAS",
    refresh: bool = False,
) -> pd.DataFrame:
    """market: 'KR' | 'US'. US는 excd(NAS/NYS) 필요. 캐시 히트면 API 안 침."""
    path = _path(market, symbol)
    cached = _read(path) if path.exists() else pd.DataFrame(columns=_COLS)

    need = refresh or cached.empty or not _fresh(cached)
    if need:
        # 캐시가 있으면 마지막 봉 5일 전부터만 받아 이어붙인다(전체 재조회 방지).
        fetch_since = since_iso
        if not cached.empty and not refresh:
            last = cached.index[-1].date() - dt.timedelta(days=5)
            fetch_since = max(since_iso[:10], last.isoformat())
        if market == "KR":
            fetched = fetch_ohlcv_kis(symbol, token, fetch_since, until_iso)
        elif market == "US":
            fetched = fetch_ohlcv_kis_overseas(symbol, excd, token, fetch_since, until_iso)
        else:
            raise ValueError(f"알 수 없는 시장: {market!r}")
        if not fetched.empty:
            merged = pd.concat([cached, fetched])
            merged = merged[~merged.index.duplicated(keep="last")].sort_index()
            _write(path, merged)
            cached = merged

    if cached.empty:
        return cached
    since_d = dt.date.fromisoformat(since_iso[:10])
    mask = cached.index.date >= since_d
    if until_iso:
        mask &= cached.index.date <= dt.date.fromisoformat(until_iso[:10])
    return cached[mask]


def warm_cache(items: list[tuple], token: str, since_iso: str, until_iso: str | None = None,
               refresh: bool = False) -> dict[str, pd.DataFrame]:
    """items: [('KR','005930'), ...] 또는 [('US','AAPL','NAS'), ...]. 반환: symbol -> frame."""
    out: dict[str, pd.DataFrame] = {}
    for it in items:
        market, symbol = it[0], it[1]
        excd = it[2] if len(it) > 2 else "NAS"
        try:
            df = cached_ohlcv(market, symbol, token, since_iso, until_iso, excd=excd, refresh=refresh)
        except Exception as exc:  # noqa: BLE001
            print(f"  {market}:{symbol} 실패 ({exc})", flush=True)
            continue
        if not df.empty:
            out[symbol] = df
        hit = "" if df.empty else f"{len(df)}봉 {df.index[0].date()}~{df.index[-1].date()}"
        print(f"  {market}:{symbol:8} {hit}", flush=True)
    return out
