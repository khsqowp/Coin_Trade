"""올웨더 데이터 수집 및 캐시 전용 패널 로더."""
from __future__ import annotations

import argparse
import os
import time
from dataclasses import dataclass
from pathlib import Path

import numpy as np
import pandas as pd

from app import kis_ohlcv_cache as cache
from app.aw_universe import all_symbols, etfs, stocks
from app.kis_auth import issue_token

# 기본 경로는 저장소의 기존 일봉 캐시. 서버에서는 KIS_OHLCV_CACHE_DIR로 바꾼다.
cache.CACHE_DIR = Path(os.environ.get("KIS_OHLCV_CACHE_DIR", Path(__file__).resolve().parents[2] / ".kis-cache"))


@dataclass
class Panel:
    market: str
    dates: pd.DatetimeIndex
    symbols: list[str]
    roles: dict[str, str]
    names: dict[str, str]
    o: pd.DataFrame
    c: pd.DataFrame
    v: pd.DataFrame
    tradable: pd.DataFrame
    listed200: pd.DataFrame
    stock_eligible: pd.DataFrame
    missing: list[str]

    def metadata(self, symbol: str) -> dict:
        return {"role": self.roles[symbol], "name": self.names[symbol]}


def fetch_all(market: str, since: str = "2010-01-01", pause: float | None = None) -> dict:
    """시장 ETF 전체 캐시 갱신. 호출부에서만 네트워크를 사용한다."""
    market = market.upper()
    if market not in ("KR", "US"):
        raise ValueError("market은 KR 또는 US여야 합니다")
    delay = float(os.environ.get("AW_FETCH_PAUSE_SECONDS", "2")) if pause is None else float(pause)
    token = issue_token()
    items = [(market, x["code"], x["excd"]) for x in etfs(market)]
    report = {}
    for i, item in enumerate(items):
        sym = item[1]
        try:
            frames = cache.warm_cache([item], token, since, refresh=True)
            df = frames.get(sym, pd.DataFrame())
            report[sym] = {"bars": len(df), "first": str(df.index[0].date()) if len(df) else None,
                           "last": str(df.index[-1].date()) if len(df) else None, "error": None if len(df) else "빈 응답"}
        except Exception as exc:  # noqa: BLE001
            report[sym] = {"bars": 0, "first": None, "last": None, "error": str(exc)}
        print(f"{sym}: {report[sym]}", flush=True)
        if i + 1 < len(items) and delay > 0:
            time.sleep(delay)
    return report


def _cache_path(market: str, symbol: str) -> Path:
    return cache.CACHE_DIR / f"{market}_{symbol}.csv"


def _us_stock_eligibility(med: pd.DataFrame, symbols: list[str], listed200: pd.DataFrame) -> pd.DataFrame:
    """시점별 60일 거래대금 중앙값 상위 30, 상장 200일 필터."""
    rank = med[symbols].rank(axis=1, ascending=False, method="min")
    return rank.le(30) & listed200[symbols]


def load_panel(market: str) -> Panel:
    """캐시만 읽어 패널과 PIT 상장/유동성 마스크를 구성한다."""
    market = market.upper()
    defs = all_symbols(market)
    frames, missing = {}, []
    for item in defs:
        path = _cache_path(market, item["code"])
        if not path.exists():
            missing.append(item["code"])
            continue
        df = pd.read_csv(path, parse_dates=["timestamp"], index_col="timestamp")
        idx = pd.DatetimeIndex(df.index)
        if idx.tz is not None:
            idx = idx.tz_convert("UTC").tz_localize(None)
        df.index = idx.normalize()
        frames[item["code"]] = df[~df.index.duplicated(keep="last")].sort_index()
    for sym in missing:
        print(f"캐시 누락: {market}:{sym}", flush=True)
    if not frames:
        raise FileNotFoundError(f"{market} 캐시가 없습니다. 누락 심볼: {', '.join(missing)}")
    dates = pd.DatetimeIndex(sorted(set().union(*(set(f.index) for f in frames.values()))))
    symbols = [x["code"] for x in defs if x["code"] in frames]
    def matrix(col):
        return pd.DataFrame({s: frames[s][col].reindex(dates) for s in symbols}, index=dates, dtype=float)
    o, c, v = matrix("Open"), matrix("Close"), matrix("Volume")
    listed200 = c.notna().rolling(200, min_periods=200).sum().ge(200)
    traded = c * v * (1 if market == "KR" else 1.0)
    med = traded.rolling(60, min_periods=30).median()
    stk = [x["code"] for x in stocks(market) if x["code"] in symbols]
    if market == "KR":
        stock_eligible = med[stk].ge(1_000_000_000) & listed200[stk]
    else:
        stock_eligible = _us_stock_eligibility(med, stk, listed200)
    prev = c.shift(1)
    tradable = v.gt(0) & o.notna() & c.notna() & (o.div(prev).sub(1).abs().lt(.29) | prev.isna())
    roles = {x["code"]: x["role"] for x in defs if x["code"] in symbols}
    names = {x["code"]: x["name"] for x in defs if x["code"] in symbols}
    return Panel(market, dates, symbols, roles, names, o, c, v, tradable, listed200, stock_eligible, missing)


def main(argv=None):
    p = argparse.ArgumentParser(description="올웨더 ETF 캐시 수집")
    sub = p.add_subparsers(dest="command", required=True)
    f = sub.add_parser("fetch")
    f.add_argument("market", choices=("KR", "US"))
    f.add_argument("--since", default="2010-01-01")
    f.add_argument("--pause", type=float, default=None, help="종목 간 대기 초 (기본 env AW_FETCH_PAUSE_SECONDS 또는 2초)")
    a = p.parse_args(argv)
    if a.command == "fetch":
        fetch_all(a.market, a.since, a.pause)


if __name__ == "__main__":
    main()
