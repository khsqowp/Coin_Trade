"""Data loaders with parquet cache. Public data only (FinanceDataReader / yfinance), low rate.

Cache order per symbol: lib/cache/<market>/<sym>.parquet, then the legacy read-only gulp_pattern cache.
Download happens only if both are missing (never re-downloads existing data).
Holdout bars are cut off unless splits.unlock_holdout() was called.
"""
from __future__ import annotations
import re, time
from dataclasses import dataclass, field
from pathlib import Path
import numpy as np
import pandas as pd
from . import splits

LIB = Path(__file__).resolve().parent
CACHE = LIB / "cache"
LEGACY = [Path("/home/noroot/research/gulp_pattern/cache")]
END = "2026-11-12"
SLEEP = 0.4
KR_EXCL_NAME = re.compile(r"스팩|기업인수목적|ETN|ETF|KODEX|TIGER|KBSTAR|ARIRANG|HANARO|KOSEF|SOL |ACE |RISE |PLUS |우$|우B$|우\(|리츠|인프라")


def _norm(df: pd.DataFrame) -> pd.DataFrame:
    idx = pd.DatetimeIndex(pd.to_datetime(df.index))
    if idx.tz is not None:
        idx = idx.tz_localize(None)
    df = df.copy()
    df.index = idx.as_unit("ns").normalize()
    df = df[~df.index.duplicated()].sort_index()
    df.columns = [str(c).lower() for c in df.columns]
    return df


def _find(market: str, sym: str, cache: Path = CACHE, legacy=None) -> Path | None:
    for base in [cache] + list(LEGACY if legacy is None else legacy):
        p = Path(base) / market / f"{sym}.parquet"
        if p.exists():
            return p
    return None


def _download(market: str, sym: str) -> pd.DataFrame | None:
    import FinanceDataReader as fdr
    for i in range(3):
        try:
            if market == "kr":
                d = fdr.DataReader(sym, "2010-01-01", END)
                d = d[["Open", "High", "Low", "Close", "Volume"]]
                d.columns = ["open", "high", "low", "close", "volume"]
            else:
                d = fdr.DataReader(sym, "2009-01-01", END)
                f = d["Adj Close"] / d["Close"]
                d = pd.DataFrame({"open": d.Open * f, "high": d.High * f, "low": d.Low * f, "close": d.Close * f,
                                  "rawclose": d.Close, "volume": d.Volume})
            time.sleep(SLEEP)
            return d if len(d) else None
        except Exception:
            time.sleep(2 * (i + 1))
    return None


def load_ohlcv(market: str, sym: str, cache: Path = CACHE, legacy=None, download: bool = True,
               include_holdout: bool = False) -> pd.DataFrame | None:
    """Single-symbol OHLCV(+rawclose for US). Cuts holdout unless unlocked."""
    p = _find(market, sym, cache, legacy)
    if p is None:
        if not download:
            return None
        d = _download(market, sym)
        if d is None:
            return None
        out = Path(cache) / market / f"{sym}.parquet"
        out.parent.mkdir(parents=True, exist_ok=True)
        d.to_parquet(out)
        p = out
    df = _norm(pd.read_parquet(p))
    if include_holdout:
        splits.guard_dev([splits.HOLDOUT_START], f"{market}/{sym}")  # raises if locked
        return df
    return splits.dev_view(df)


def load_index(name: str, cache: Path = CACHE, legacy=None, include_holdout: bool = False) -> pd.DataFrame:
    for base in [Path(cache)] + list(LEGACY if legacy is None else legacy):
        p = base / "idx" / f"{name}.parquet"
        if p.exists():
            df = _norm(pd.read_parquet(p))
            if include_holdout:
                splits.guard_dev([splits.HOLDOUT_START], f"idx/{name}")
                return df
            return splits.dev_view(df)
    raise FileNotFoundError(name)


def kr_universe(cache: Path = CACHE, legacy=None) -> pd.DataFrame:
    """KOSPI+KOSDAQ listing (CURRENTLY listed only -> survivorship bias). Excludes preferred (code not ending in 0),
    SPAC, ETF/ETN/REIT-like names where flaggable."""
    for base in [Path(cache)] + list(LEGACY if legacy is None else legacy):
        p = base / "kr_universe.csv"
        if p.exists():
            u = pd.read_csv(p, dtype={"Code": str})
            u["Code"] = u.Code.str.zfill(6)
            u = u[u.Market.isin(["KOSPI", "KOSDAQ"]) & u.Code.str.endswith("0")]
            u = u[~u.Name.fillna("").str.contains(KR_EXCL_NAME)]
            return u.reset_index(drop=True)
    raise FileNotFoundError("kr_universe.csv")


def us_universe(cache: Path = CACHE, legacy=None) -> list[str]:
    for base in [Path(cache)] + list(LEGACY if legacy is None else legacy):
        p = base / "us_universe.csv"
        if p.exists():
            u = pd.read_csv(p)
            return [str(x) for x in u.iloc[:, 0].dropna()]
    raise FileNotFoundError("us_universe.csv")


@dataclass
class Panel:
    dates: pd.DatetimeIndex
    codes: list
    names: list
    group: np.ndarray
    open: np.ndarray
    high: np.ndarray
    low: np.ndarray
    close: np.ndarray
    volume: np.ndarray
    rawclose: np.ndarray | None = None
    market: str = "kr"
    _v20: np.ndarray | None = field(default=None, repr=False)

    @property
    def value(self):
        return (self.rawclose if self.rawclose is not None else self.close) * self.volume

    @property
    def value20(self):
        """20-bar mean traded value known at bar t (includes bar t)."""
        if self._v20 is None:
            self._v20 = pd.DataFrame(self.value).rolling(20, min_periods=20).mean().to_numpy()
        return self._v20

    def liquid(self, thr: float = 2e9):
        return np.nan_to_num(self.value20, nan=0.0) >= thr


def build_panel(frames: dict, calendar: pd.DatetimeIndex, names: dict | None = None, groups: dict | None = None,
                market: str = "kr") -> Panel:
    """Frames {code: df} -> aligned (T x N) panel on `calendar`. Bars with volume 0 or price<=0 become NaN."""
    codes = list(frames)
    T, N = len(calendar), len(codes)
    out = {k: np.full((T, N), np.nan) for k in ("open", "high", "low", "close", "volume")}
    raw = np.full((T, N), np.nan) if market == "us" else None
    for j, c in enumerate(codes):
        d = frames[c].reindex(calendar)
        ok = (d.volume.fillna(0) > 0) & (d[["open", "high", "low", "close"]].min(axis=1) > 0)
        for k in out:
            out[k][:, j] = np.where(ok, d[k].to_numpy(dtype=float), np.nan)
        if raw is not None and "rawclose" in d:
            raw[:, j] = np.where(ok, d["rawclose"].to_numpy(dtype=float), np.nan)
    return Panel(calendar, codes, [(names or {}).get(c, c) for c in codes],
                 np.array([(groups or {}).get(c, market.upper()) for c in codes], dtype=object),
                 out["open"], out["high"], out["low"], out["close"], out["volume"], raw, market)


def load_panel(market: str = "kr", codes: list | None = None, min_bars: int = 250, include_holdout: bool = False,
               cache: Path = CACHE, legacy=None, download: bool = False) -> Panel:
    cal_name = "KOSPI" if market == "kr" else "SPY"
    cal = load_index(cal_name, cache, legacy, include_holdout).index
    names, groups = {}, {}
    if market == "kr":
        u = kr_universe(cache, legacy)
        names = dict(zip(u.Code, u.Name)); groups = dict(zip(u.Code, u.Market))
        codes = codes or list(u.Code)
    else:
        codes = codes or us_universe(cache, legacy)
    frames = {}
    for c in codes:
        d = load_ohlcv(market, c, cache, legacy, download=download, include_holdout=include_holdout)
        if d is not None and len(d) >= min_bars:
            frames[c] = d
    return build_panel(frames, cal, names, groups, market)
